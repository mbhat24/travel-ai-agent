"""
Authentication Router - Professional Grade
User registration, authentication, and session management
"""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr, Field, field_validator
import logging

from backend.db import get_db_session
from backend.db.models import User
from backend.services.user_service import UserService
from backend.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    UserAlreadyExistsError,
    PasswordTooWeakError,
    AccountLockedError,
    UserNotFoundError
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# Request/Response Schemas
class UserRegisterRequest(BaseModel):
    """User registration request"""
    email: EmailStr = Field(..., description="User email address")
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8, max_length=100)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLoginRequest(BaseModel):
    """User login request"""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """User profile response"""
    id: str
    email: str
    username: str
    first_name: Optional[str]
    last_name: Optional[str]
    full_name: str
    is_active: bool
    is_verified: bool
    created_at: str
    last_login: Optional[str]


class UserProfileResponse(BaseModel):
    """Complete user profile with statistics"""
    user: UserResponse
    statistics: dict


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
    data: Optional[dict] = None


# Dependencies
async def get_user_service(db: AsyncSession = Depends(get_db_session)) -> UserService:
    """Dependency to get user service"""
    return UserService(db)


async def get_current_user_dependency(
    token: str = Depends(oauth2_scheme),
    user_service: UserService = Depends(get_user_service)
) -> User:
    """Get current authenticated user"""
    user_id = user_service.verify_token(token)
    if not user_id:
        raise AuthenticationError("Invalid or expired token")
    
    user = await user_service.repository.get_by_id(user_id)
    if not user:
        raise UserNotFoundError(user_id=user_id)
    
    if not user.is_active:
        raise AuthenticationError("Account is deactivated")
    
    if user.is_locked:
        raise AccountLockedError(locked_until=user.locked_until.isoformat() if user.locked_until else None)
    
    return user


# Routes
@router.post(
    "/register",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create a new user account with email, username, and password"
)
async def register(
    request: UserRegisterRequest,
    user_service: UserService = Depends(get_user_service)
):
    """Register new user"""
    try:
        user = await user_service.register_user(
            email=request.email,
            username=request.username,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name
        )
        
        logger.info(f"User registered successfully: {user.email}")
        
        return MessageResponse(
            message="User registered successfully",
            data={
                "user_id": user.id,
                "email": user.email,
                "username": user.username
            }
        )
        
    except ValueError as e:
        if "already" in str(e).lower():
            raise UserAlreadyExistsError(email=request.email)
        elif "password" in str(e).lower():
            raise PasswordTooWeakError()
        raise


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User login",
    description="Authenticate user and return access token"
)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    user_service: UserService = Depends(get_user_service)
):
    """Login user with email and password"""
    # Get client IP
    client_ip = request.client.host if request.client else None
    
    # Authenticate
    user = await user_service.authenticate_user(
        email=form_data.username,  # OAuth2 uses username field for email
        password=form_data.password
    )
    
    if not user:
        raise InvalidCredentialsError()
    
    # Check if account is locked
    if user.is_locked:
        raise AccountLockedError(
            locked_until=user.locked_until.isoformat() if user.locked_until else None
        )
    
    # Update last login
    await user_service.repository.update_last_login(user.id, client_ip or "unknown")
    
    # Generate tokens
    access_token = user_service.create_access_token(user.id)
    refresh_token = user_service.create_refresh_token(user.id)
    
    logger.info(f"User logged in: {user.email} from {client_ip}")
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=1800  # 30 minutes
    )


@router.post(
    "/login/json",
    response_model=TokenResponse,
    summary="User login (JSON)",
    description="Authenticate user with JSON payload"
)
async def login_json(
    request: Request,
    login_request: UserLoginRequest,
    user_service: UserService = Depends(get_user_service)
):
    """Login user with JSON request body"""
    client_ip = request.client.host if request.client else None
    
    user = await user_service.authenticate_user(
        email=login_request.email,
        password=login_request.password
    )
    
    if not user:
        raise InvalidCredentialsError()
    
    if user.is_locked:
        raise AccountLockedError(
            locked_until=user.locked_until.isoformat() if user.locked_until else None
        )
    
    await user_service.repository.update_last_login(user.id, client_ip or "unknown")
    
    access_token = user_service.create_access_token(user.id)
    refresh_token = user_service.create_refresh_token(user.id)
    
    logger.info(f"User logged in (JSON): {user.email} from {client_ip}")
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=1800
    )


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current user profile",
    description="Get complete profile of authenticated user"
)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user_dependency)
):
    """Get current user profile with statistics"""
    # Get user service to fetch profile with stats
    from backend.db import get_db_session
    from sqlalchemy.ext.asyncio import AsyncSession
    
    # We need a fresh service instance for the profile query
    # In production, you'd cache this
    
    return UserProfileResponse(
        user=UserResponse(
            id=current_user.id,
            email=current_user.email,
            username=current_user.username,
            first_name=current_user.first_name,
            last_name=current_user.last_name,
            full_name=current_user.full_name,
            is_active=current_user.is_active,
            is_verified=current_user.is_verified,
            created_at=current_user.created_at.isoformat() if current_user.created_at else None,
            last_login=current_user.last_login.isoformat() if current_user.last_login else None
        ),
        statistics={
            "total_trips": 0,  # Would be populated from actual query
            "active_trips": 0,
            "upcoming_trips": 0
        }
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Get new access token using refresh token"
)
async def refresh_token(
    token: str = Depends(oauth2_scheme),
    user_service: UserService = Depends(get_user_service)
):
    """Refresh access token"""
    user_id = user_service.verify_token(token, token_type="refresh")
    if not user_id:
        raise AuthenticationError("Invalid or expired refresh token")
    
    user = await user_service.repository.get_by_id(user_id)
    if not user or not user.is_active:
        raise AuthenticationError("User not found or inactive")
    
    # Generate new tokens
    new_access_token = user_service.create_access_token(user_id)
    new_refresh_token = user_service.create_refresh_token(user_id)
    
    logger.info(f"Token refreshed for user: {user.email}")
    
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=1800
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout user",
    description="Invalidate current session"
)
async def logout(
    current_user: User = Depends(get_current_user_dependency)
):
    """Logout user - in production this would invalidate the session"""
    logger.info(f"User logged out: {current_user.email}")
    
    return MessageResponse(
        message="Successfully logged out"
    )
