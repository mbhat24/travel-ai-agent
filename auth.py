"""
Authentication Module for Travel AI Agent
JWT + Redis Session Management for scalable production use
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from jose import JWTError, jwt as jwt_lib
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import json
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

# Password hashing
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=BCRYPT_ROUNDS
)

# Security scheme
security = HTTPBearer()

# Redis client (lazy initialization)
_redis_client = None


def get_redis_client():
    """Get or create Redis client with lazy initialization"""
    global _redis_client
    if _redis_client is None:
        try:
            import redis
            _redis_client = redis.Redis(
                host=settings.redis.host,
                port=settings.redis.port,
                db=settings.redis.db,
                password=settings.redis.password,
                decode_responses=True,
                socket_connect_timeout=5
            )
            # Test connection
            _redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.warning(f"Redis not available, using fallback: {e}")
            _redis_client = None
    return _redis_client

class User:
    """User model"""
    def __init__(self, user_id: str, email: str, username: str, is_active: bool = True):
        self.user_id = user_id
        self.email = email
        self.username = username
        self.is_active = is_active

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt_lib.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt_lib.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def verify_token(token: str, token_type: str = "access") -> Dict[str, Any]:
    """Verify JWT token"""
    try:
        payload = jwt_lib.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != token_type:
            raise InvalidTokenError("Invalid token type")
        return payload
    except JWTError as e:
        logger.warning(f"JWT verification failed: {str(e)}")
        raise InvalidTokenError("Could not validate credentials")

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Get current user from JWT token"""
    token = credentials.credentials
    payload = verify_token(token, "access")
    user_id = payload.get("sub")
    
    if user_id is None:
        raise InvalidTokenError("Invalid authentication credentials")
    
    # Check if user is active (from Redis or fallback)
    redis = get_redis_client()
    if redis:
        user_data = redis.get(f"user:{user_id}")
        if user_data:
            user_dict = json.loads(user_data)
            return User(
                user_id=user_id,
                email=user_dict.get("email"),
                username=user_dict.get("username"),
                is_active=user_dict.get("is_active", True)
            )
    
    # Fallback: user not found
    raise UserNotFoundError(user_id=user_id)

def create_session(user_id: str, user_data: Dict[str, Any]) -> str:
    """Create session in Redis or memory fallback"""
    session_id = str(uuid.uuid4())
    session_key = f"session:{session_id}"
    
    session_data = json.dumps({
        "user_id": user_id,
        "created_at": datetime.utcnow().isoformat(),
        **user_data
    })
    
    # Try Redis first
    redis = get_redis_client()
    if redis:
        # Store session data
        redis.setex(
            session_key,
            timedelta(hours=24).total_seconds(),
            session_data
        )
        # Store user data
        redis.setex(
            f"user:{user_id}",
            timedelta(days=30).total_seconds(),
            json.dumps(user_data)
        )
        logger.debug(f"Session created in Redis: {session_id}")
    else:
        # Fallback: use in-memory storage from auth_simple
        from auth_simple import _sessions_db as _fallback_sessions
        _fallback_sessions[session_id] = json.loads(session_data)
        logger.debug(f"Session created in memory: {session_id}")
    
    return session_id

def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get session from Redis or memory fallback"""
    redis = get_redis_client()
    if redis:
        session_data = redis.get(f"session:{session_id}")
        if session_data:
            return json.loads(session_data)
    
    # Fallback: try in-memory
    from auth_simple import _sessions_db as _fallback_sessions
    return _fallback_sessions.get(session_id)

def delete_session(session_id: str) -> bool:
    """Delete session from Redis or memory fallback"""
    redis = get_redis_client()
    if redis:
        return redis.delete(f"session:{session_id}") > 0
    
    # Fallback: try in-memory
    from auth_simple import _sessions_db as _fallback_sessions
    if session_id in _fallback_sessions:
        del _fallback_sessions[session_id]
        return True
    return False

def delete_user_sessions(user_id: str) -> int:
    """Delete all sessions for a user"""
    deleted = 0
    
    # Try Redis first
    redis = get_redis_client()
    if redis:
        pattern = "session:*"
        for key in redis.scan_iter(match=pattern):
            session_data = redis.get(key)
            if session_data:
                session_dict = json.loads(session_data)
                if session_dict.get("user_id") == user_id:
                    redis.delete(key)
                    deleted += 1
    
    # Also clean fallback memory
    from auth_simple import _sessions_db as _fallback_sessions
    to_delete = [
        sid for sid, data in _fallback_sessions.items()
        if data.get("user_id") == user_id
    ]
    for sid in to_delete:
        del _fallback_sessions[sid]
        deleted += 1
    
    logger.info(f"Deleted {deleted} sessions for user {user_id}")
    return deleted
