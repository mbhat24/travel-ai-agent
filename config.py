"""
Configuration Management Module
Extreme Professional Grade Configuration with Pydantic Settings
Provides type-safe, validated configuration with environment variable support
"""

import os
import secrets
import hashlib
from functools import lru_cache
from typing import List, Optional
from pydantic import Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings


class SecuritySettings(BaseSettings):
    """Security-related configuration"""
    model_config = ConfigDict(env_prefix="TRAVEL_", extra="ignore")
    
    # JWT Configuration
    jwt_secret: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="JWT signing secret - auto-generated if not provided"
    )
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30)
    refresh_token_expire_days: int = Field(default=7)
    
    # Consent/CSRF Secret
    consent_secret: str = Field(
        default_factory=lambda: hashlib.sha256(os.urandom(32)).hexdigest(),
        description="HMAC secret for consent tokens"
    )
    
    # Password Security
    bcrypt_rounds: int = Field(default=12, ge=4, le=31)
    
    @field_validator('jwt_secret')
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT secret must be at least 32 characters for security")
        if v == "your-super-secret-jwt-key-change-in-production":
            # Auto-generate secure secret
            return secrets.token_urlsafe(32)
        return v


class DatabaseSettings(BaseSettings):
    """Database configuration"""
    model_config = ConfigDict(env_prefix="TRAVEL_DB_", extra="ignore")
    
    url: Optional[str] = Field(default=None)
    pool_size: int = Field(default=5, ge=1, le=100)
    max_overflow: int = Field(default=10, ge=0, le=100)
    pool_timeout: int = Field(default=30, ge=1)
    echo: bool = Field(default=False)
    
    @property
    def is_configured(self) -> bool:
        return self.url is not None


class LLMSettings(BaseSettings):
    """LLM/AI configuration"""
    model_config = ConfigDict(env_prefix="TRAVEL_LLM_", extra="ignore")
    
    backend: str = Field(default="openai")
    model: str = Field(default="gpt-4o-mini")
    base_url: str = Field(default="https://api.openai.com/v1")
    api_key: Optional[str] = Field(default=None)
    timeout: int = Field(default=30, ge=1, le=300)
    max_retries: int = Field(default=3, ge=0, le=10)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    
    @property
    def is_configured(self) -> bool:
        return self.api_key is not None and len(self.api_key) > 0


class RedisSettings(BaseSettings):
    """Redis configuration for caching and sessions"""
    model_config = ConfigDict(env_prefix="TRAVEL_REDIS_", extra="ignore")
    
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    db: int = Field(default=0)
    password: Optional[str] = Field(default=None)
    ssl: bool = Field(default=False)
    
    @property
    def url(self) -> str:
        auth = f":{self.password}@" if self.password else ""
        scheme = "rediss" if self.ssl else "redis"
        return f"{scheme}://{auth}{self.host}:{self.port}/{self.db}"
    
    @property
    def is_configured(self) -> bool:
        # Try to connect to verify
        try:
            import redis
            client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                socket_connect_timeout=2
            )
            client.ping()
            return True
        except:
            return False


class RateLimitSettings(BaseSettings):
    """Rate limiting configuration"""
    model_config = ConfigDict(env_prefix="TRAVEL_RATE_", extra="ignore")
    
    requests_per_minute: int = Field(default=60, ge=1)
    window_seconds: int = Field(default=60, ge=1)
    burst_size: int = Field(default=10, ge=1)
    
    # Different limits for different endpoints
    auth_limit: int = Field(default=5, ge=1)  # Stricter for auth
    api_limit: int = Field(default=100, ge=1)  # Standard API


class APICredentials(BaseSettings):
    """External API credentials"""
    model_config = ConfigDict(env_prefix="", extra="ignore")
    
    openweather_api_key: Optional[str] = Field(default=None, alias="OPENWEATHER_API_KEY")
    amadeus_api_key: Optional[str] = Field(default=None, alias="AMADEUS_API_KEY")
    amadeus_secret: Optional[str] = Field(default=None, alias="AMADEUS_SECRET")
    exchange_rate_api_key: Optional[str] = Field(default=None, alias="EXCHANGE_RATE_API_KEY")


class CORSSettings(BaseSettings):
    """CORS configuration"""
    model_config = ConfigDict(env_prefix="TRAVEL_", extra="ignore")
    
    allowed_origins: List[str] = Field(default_factory=lambda: ["*"])
    allowed_methods: List[str] = Field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    allowed_headers: List[str] = Field(default_factory=lambda: ["*"])
    allow_credentials: bool = Field(default=True)
    max_age: int = Field(default=600)
    
    @field_validator('allowed_origins', mode='before')
    @classmethod
    def parse_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


class LoggingSettings(BaseSettings):
    """Logging configuration"""
    model_config = ConfigDict(env_prefix="TRAVEL_LOG_", extra="ignore")
    
    level: str = Field(default="INFO")
    format: str = Field(default="json")  # json or text
    structured: bool = Field(default=True)
    include_timestamp: bool = Field(default=True)
    include_request_id: bool = Field(default=True)
    
    @field_validator('level')
    @classmethod
    def validate_level(cls, v: str) -> str:
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v_upper


class ApplicationSettings(BaseSettings):
    """Main application settings"""
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Environment
    env: str = Field(default="development", alias="TELOSCOPY_ENV")
    debug: bool = Field(default=False)
    version: str = Field(default="3.1.0")
    
    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1, le=65535)
    workers: int = Field(default=1, ge=1)
    
    # Security
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    
    # Database
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    
    # LLM
    llm: LLMSettings = Field(default_factory=LLMSettings)
    
    # Redis
    redis: RedisSettings = Field(default_factory=RedisSettings)
    
    # Rate Limiting
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    
    # API Credentials
    api_credentials: APICredentials = Field(default_factory=APICredentials)
    
    # CORS
    cors: CORSSettings = Field(default_factory=CORSSettings)
    
    # Logging
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    
    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        return self.env.lower() == "development"


@lru_cache()
def get_settings() -> ApplicationSettings:
    """Get cached application settings"""
    return ApplicationSettings()


# Global settings instance
settings = get_settings()
