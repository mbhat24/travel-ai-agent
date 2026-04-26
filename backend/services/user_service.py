"""
User Service Layer
Business logic for user management
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from backend.db.models import User
from backend.repositories.base import UserRepository
from backend.core.config import settings

logger = logging.getLogger(__name__)

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.security.bcrypt_rounds
)


class UserService:
    """User business logic service"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = UserRepository(User, db)
    
    async def register_user(
        self,
        email: str,
        username: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> User:
        """Register a new user"""
        # Check if email exists
        existing_user = await self.repository.get_by_email(email)
        if existing_user:
            raise ValueError("Email already registered")
        
        # Check if username exists
        existing_username = await self.repository.get_by_username(username)
        if existing_username:
            raise ValueError("Username already taken")
        
        # Validate password
        if len(password) < settings.security.password_min_length:
            raise ValueError(f"Password must be at least {settings.security.password_min_length} characters")
        
        # Hash password
        hashed_password = pwd_context.hash(password)
        
        # Create user
        user_data = {
            "email": email.lower().strip(),
            "username": username.lower().strip(),
            "hashed_password": hashed_password,
            "first_name": first_name,
            "last_name": last_name,
            "is_active": True,
            "is_verified": False,
            "created_at": datetime.utcnow(),
        }
        
        user = await self.repository.create(user_data)
        logger.info(f"User registered: {user.email}")
        
        return user
    
    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password"""
        user = await self.repository.get_by_email(email)
        
        if not user:
            return None
        
        # Check if account is locked
        if user.is_locked:
            logger.warning(f"Login attempt for locked account: {email}")
            return None
        
        # Verify password
        if not pwd_context.verify(password, user.hashed_password):
            # Increment failed attempts
            await self.repository.increment_login_attempts(user.id)
            logger.warning(f"Failed login attempt for: {email}")
            return None
        
        # Check if user is active
        if not user.is_active:
            logger.warning(f"Login attempt for inactive account: {email}")
            return None
        
        return user
    
    async def update_user(
        self,
        user_id: str,
        update_data: Dict[str, Any]
    ) -> Optional[User]:
        """Update user profile"""
        # Remove sensitive fields that shouldn't be updated directly
        protected_fields = ["id", "hashed_password", "is_superuser", "created_at"]
        for field in protected_fields:
            update_data.pop(field, None)
        
        user = await self.repository.update(user_id, update_data)
        if user:
            logger.info(f"User updated: {user.email}")
        
        return user
    
    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str
    ) -> bool:
        """Change user password"""
        user = await self.repository.get_by_id(user_id)
        if not user:
            return False
        
        # Verify current password
        if not pwd_context.verify(current_password, user.hashed_password):
            return False
        
        # Validate new password
        if len(new_password) < settings.security.password_min_length:
            raise ValueError(f"Password must be at least {settings.security.password_min_length} characters")
        
        # Hash and update
        hashed_password = pwd_context.hash(new_password)
        await self.repository.update(user_id, {"hashed_password": hashed_password})
        
        logger.info(f"Password changed for user: {user.email}")
        return True
    
    async def lock_account(self, user_id: str, minutes: int = 30) -> Optional[User]:
        """Lock user account temporarily"""
        locked_until = datetime.utcnow() + timedelta(minutes=minutes)
        return await self.repository.update(user_id, {
            "locked_until": locked_until,
            "login_attempts": 0
        })
    
    async def unlock_account(self, user_id: str) -> Optional[User]:
        """Unlock user account"""
        return await self.repository.update(user_id, {
            "locked_until": None,
            "login_attempts": 0
        })
    
    async def deactivate_user(self, user_id: str) -> Optional[User]:
        """Deactivate user account"""
        user = await self.repository.update(user_id, {
            "is_active": False,
            "deleted_at": datetime.utcnow()
        })
        
        if user:
            logger.info(f"User deactivated: {user.email}")
        
        return user
    
    async def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get complete user profile with statistics"""
        user = await self.repository.get_user_with_trips(user_id)
        if not user:
            return None
        
        # Calculate statistics
        total_trips = len(user.trips) if user.trips else 0
        active_trips = sum(1 for t in user.trips if t.is_active_now) if user.trips else 0
        upcoming_trips = sum(1 for t in user.trips if not t.is_past and not t.is_active_now) if user.trips else 0
        
        profile = user.to_dict()
        profile["statistics"] = {
            "total_trips": total_trips,
            "active_trips": active_trips,
            "upcoming_trips": upcoming_trips,
        }
        
        return profile
    
    def create_access_token(self, user_id: str, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.security.access_token_expire_minutes)
        
        to_encode = {
            "sub": user_id,
            "exp": expire,
            "type": "access",
            "iat": datetime.utcnow(),
        }
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.security.jwt_secret,
            algorithm=settings.security.jwt_algorithm
        )
        
        return encoded_jwt
    
    def create_refresh_token(self, user_id: str) -> str:
        """Create JWT refresh token"""
        expire = datetime.utcnow() + timedelta(days=settings.security.refresh_token_expire_days)
        
        to_encode = {
            "sub": user_id,
            "exp": expire,
            "type": "refresh",
            "iat": datetime.utcnow(),
        }
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.security.jwt_secret,
            algorithm=settings.security.jwt_algorithm
        )
        
        return encoded_jwt
    
    def verify_token(self, token: str, token_type: str = "access") -> Optional[str]:
        """Verify JWT token and return user_id"""
        try:
            payload = jwt.decode(
                token,
                settings.security.jwt_secret,
                algorithms=[settings.security.jwt_algorithm]
            )
            
            if payload.get("type") != token_type:
                return None
            
            user_id = payload.get("sub")
            if not user_id:
                return None
            
            return user_id
            
        except JWTError:
            return None
