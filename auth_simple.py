"""
Authentication Module - Simplified (In-Memory)
Professional Grade Authentication with Secure Configuration
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from jose import JWTError, jwt as jwt_lib
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uuid

from config import settings
from logger import get_logger
from exceptions import (
    AuthenticationError,
    TokenExpiredError,
    InvalidTokenError,
    UserNotFoundError
)

logger = get_logger(__name__)

# Configuration from secure settings
JWT_SECRET = settings.security.jwt_secret
JWT_ALGORITHM = settings.security.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.security.access_token_expire_minutes
REFRESH_TOKEN_EXPIRE_DAYS = settings.security.refresh_token_expire_days
BCRYPT_ROUNDS = settings.security.bcrypt_rounds

# Password hashing with configured rounds
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=BCRYPT_ROUNDS
)

# Security scheme
security = HTTPBearer()

# In-memory storage
_users_db: Dict[str, Dict[str, Any]] = {}
_sessions_db: Dict[str, Dict[str, Any]] = {}


class User:
    """User model with full metadata"""
    def __init__(
        self,
        user_id: str,
        email: str,
        username: str,
        is_active: bool = True,
        created_at: Optional[str] = None
    ):
        self.user_id = user_id
        self.email = email
        self.username = username
        self.is_active = is_active
        self.created_at = created_at or datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "email": self.email,
            "username": self.username,
            "is_active": self.is_active,
            "created_at": self.created_at
        }


def hash_password(password: str) -> str:
    """Hash password using bcrypt with configured rounds"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create JWT access token with secure configuration"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "type": "access",
        "iat": datetime.utcnow(),
        "jti": str(uuid.uuid4())  # JWT ID for revocation
    })
    
    encoded_jwt = jwt_lib.encode(
        to_encode,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM
    )
    
    logger.debug("Access token created", extra={
        'extras': {
            'user_id': data.get('sub'),
            'expires': expire.isoformat()
        }
    })
    
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create JWT refresh token with longer expiry"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "iat": datetime.utcnow(),
        "jti": str(uuid.uuid4())
    })
    
    encoded_jwt = jwt_lib.encode(
        to_encode,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM
    )
    
    logger.debug("Refresh token created", extra={
        'extras': {
            'user_id': data.get('sub'),
            'expires': expire.isoformat()
        }
    })
    
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Dict[str, Any]:
    """Verify JWT token with comprehensive error handling"""
    try:
        payload = jwt_lib.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM]
        )
        
        # Check token type
        if payload.get("type") != token_type:
            logger.warning(
                f"Invalid token type: expected {token_type}, got {payload.get('type')}",
                extra={'extras': {'token_type_expected': token_type}}
            )
            raise InvalidTokenError(f"Invalid token type. Expected: {token_type}")
        
        # Check expiration manually for better error messages
        exp = payload.get("exp")
        if exp and datetime.utcnow().timestamp() > exp:
            logger.warning("Token has expired", extra={
                'extras': {'expired_at': datetime.fromtimestamp(exp).isoformat()}
            })
            raise TokenExpiredError()
        
        return payload
        
    except JWTError as e:
        logger.warning(f"JWT verification failed: {str(e)}")
        raise InvalidTokenError("Could not validate credentials")


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """Get current authenticated user from JWT token"""
    token = credentials.credentials
    
    try:
        payload = verify_token(token, "access")
        user_id = payload.get("sub")
        
        if user_id is None:
            logger.warning("Token missing 'sub' claim")
            raise InvalidTokenError("Invalid authentication credentials")
        
        # Find user in database
        user_data = None
        for email, data in _users_db.items():
            if data.get("user_id") == user_id:
                user_data = data
                break
        
        if not user_data:
            logger.warning(f"User not found: {user_id}")
            raise UserNotFoundError(user_id=user_id)
        
        # Check if user is active
        if not user_data.get("is_active", True):
            logger.warning(f"Inactive user attempted access: {user_id}")
            raise AuthenticationError("User account is disabled")
        
        logger.debug(f"User authenticated: {user_id}")
        
        return User(
            user_id=user_id,
            email=user_data.get("email"),
            username=user_data.get("username"),
            is_active=user_data.get("is_active", True),
            created_at=user_data.get("created_at")
        )
        
    except (JWTError, InvalidTokenError, TokenExpiredError):
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_current_user: {str(e)}", exc_info=True)
        raise AuthenticationError("Authentication failed")

def create_session(user_id: str, user_data: Dict[str, Any]) -> str:
    """Create session in memory"""
    session_id = str(uuid.uuid4())
    
    _sessions_db[session_id] = {
        "user_id": user_id,
        "created_at": datetime.utcnow().isoformat(),
        **user_data
    }
    
    return session_id

def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get session from memory"""
    return _sessions_db.get(session_id)

def delete_session(session_id: str) -> bool:
    """Delete session from memory"""
    if session_id in _sessions_db:
        del _sessions_db[session_id]
        return True
    return False

def delete_user_sessions(user_id: str) -> int:
    """Delete all sessions for a user"""
    deleted = 0
    to_delete = []
    
    for session_id, session_data in _sessions_db.items():
        if session_data.get("user_id") == user_id:
            to_delete.append(session_id)
    
    for session_id in to_delete:
        del _sessions_db[session_id]
        deleted += 1
    
    return deleted

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get user by email from in-memory database"""
    return _users_db.get(email)

def save_user(email: str, user_data: Dict[str, Any]) -> None:
    """Save user to in-memory database"""
    _users_db[email] = user_data
