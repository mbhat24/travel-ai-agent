"""
Professional Configuration Module with Pydantic Settings
Extreme-grade configuration management with validation and environment support
"""

import os
import secrets
from functools import lru_cache
from typing import List, Optional, Union
from pydantic import Field, field_validator, ConfigDict, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """PostgreSQL database configuration with connection pooling"""
    model_config = ConfigDict(env_prefix="DB_", extra="ignore")
    
    url: Optional[PostgresDsn] = Field(
        default="postgresql+asyncpg://travel_user:travel_pass@localhost:5432/travel_db",
        description="Database connection URL with async driver"
    )
    pool_size: int = Field(default=20, ge=1, le=100, description="Connection pool size")
    max_overflow: int = Field(default=10, ge=0, le=50, description="Max overflow connections")
    pool_timeout: int = Field(default=30, ge=1, description="Pool timeout in seconds")
    pool_recycle: int = Field(default=3600, ge=300, description="Connection recycle time")
    echo: bool = Field(default=False, description="Echo SQL queries (dev only)")
    
    @property
    def async_url(self) -> str:
        """Get async PostgreSQL URL"""
        return str(self.url).replace("postgresql://", "postgresql+asyncpg://")
    
    @property
    def sync_url(self) -> str:
        """Get sync PostgreSQL URL"""
        return str(self.url).replace("postgresql+asyncpg://", "postgresql://")


class RedisSettings(BaseSettings):
    """Redis configuration for caching and sessions"""
    model_config = ConfigDict(env_prefix="REDIS_", extra="ignore")
    
    url: Optional[RedisDsn] = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    password: Optional[str] = Field(default=None)
    ssl: bool = Field(default=False)
    socket_timeout: int = Field(default=5)
    socket_connect_timeout: int = Field(default=5)
    
    @property
    def broker_url(self) -> str:
        """URL for Celery broker"""
        return str(self.url)


class SecuritySettings(BaseSettings):
    """Security configuration with proper secret management"""
    model_config = ConfigDict(env_prefix="SECURITY_", extra="ignore")
    
    secret_key: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="Application secret key - auto-generated if not set"
    )
    jwt_secret: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="JWT signing secret"
    )
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30, ge=5)
    refresh_token_expire_days: int = Field(default=7, ge=1)
    password_min_length: int = Field(default=8, ge=6)
    bcrypt_rounds: int = Field(default=12, ge=4, le=31)
    
    @field_validator('secret_key', 'jwt_secret')
    @classmethod
    def validate_secret_length(cls, v: str) -> str:
        if len(v) < 32:
            # Auto-generate secure secret if too short
            return secrets.token_urlsafe(32)
        return v


class LLMSettings(BaseSettings):
    """LLM/AI configuration"""
    model_config = ConfigDict(env_prefix="LLM_", extra="ignore")
    
    provider: str = Field(default="openai", pattern="^(openai|anthropic|azure|local)$")
    model: str = Field(default="gpt-4o-mini")
    api_key: Optional[str] = Field(default=None)
    base_url: Optional[str] = Field(default=None)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2000, ge=100, le=8000)
    timeout: int = Field(default=30, ge=5, le=120)
    retry_attempts: int = Field(default=3, ge=1, le=5)
    
    @property
    def is_configured(self) -> bool:
        return self.api_key is not None and len(self.api_key) > 0


class CORSSettings(BaseSettings):
    """CORS configuration"""
    model_config = ConfigDict(env_prefix="CORS_", extra="ignore")
    
    origins: List[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost:8000"])
    allow_credentials: bool = Field(default=True)
    allow_methods: List[str] = Field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"])
    allow_headers: List[str] = Field(default_factory=lambda: ["*"])
    max_age: int = Field(default=600)
    
    @field_validator('origins', mode='before')
    @classmethod
    def parse_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


class RateLimitSettings(BaseSettings):
    """Rate limiting configuration"""
    model_config = ConfigDict(env_prefix="RATE_LIMIT_", extra="ignore")
    
    enabled: bool = Field(default=True)
    requests_per_minute: int = Field(default=60, ge=1)
    burst_size: int = Field(default=10, ge=1)
    window_seconds: int = Field(default=60, ge=1)
    # Different limits for different endpoints
    auth_limit: int = Field(default=5, ge=1)
    api_limit: int = Field(default=100, ge=1)
    webhook_limit: int = Field(default=1000, ge=1)


class LoggingSettings(BaseSettings):
    """Logging configuration"""
    model_config = ConfigDict(env_prefix="LOG_", extra="ignore")
    
    level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    format: str = Field(default="json", pattern="^(json|text|pretty)$")
    include_timestamp: bool = Field(default=True)
    include_correlation_id: bool = Field(default=True)
    include_request_path: bool = Field(default=True)
    file_path: Optional[str] = Field(default=None)
    max_bytes: int = Field(default=10_000_000)  # 10MB
    backup_count: int = Field(default=5)


class MonitoringSettings(BaseSettings):
    """Monitoring and observability configuration"""
    model_config = ConfigDict(env_prefix="MONITORING_", extra="ignore")
    
    enabled: bool = Field(default=True)
    prometheus_enabled: bool = Field(default=True)
    prometheus_port: int = Field(default=9090)
    health_check_interval: int = Field(default=30)
    metrics_retention_days: int = Field(default=30)
    tracing_enabled: bool = Field(default=False)
    jaeger_url: Optional[str] = Field(default=None)


class TravelAPISettings(BaseSettings):
    """External travel API configurations"""
    model_config = ConfigDict(env_prefix="API_", extra="ignore")
    
    amadeus_key: Optional[str] = Field(default=None)
    amadeus_secret: Optional[str] = Field(default=None)
    openweather_key: Optional[str] = Field(default=None)
    exchange_rate_key: Optional[str] = Field(default=None)
    booking_key: Optional[str] = Field(default=None)


class Settings(BaseSettings):
    """Main application settings combining all sub-configurations"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )
    
    # Application
    app_name: str = Field(default="Travel AI Agent Platform")
    app_version: str = Field(default="4.0.0")
    debug: bool = Field(default=False)
    environment: str = Field(default="development", pattern="^(development|staging|production|test)$")
    
    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1, le=65535)
    workers: int = Field(default=1, ge=1, le=16)
    reload: bool = Field(default=False)
    
    # Sub-configurations
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    cors: CORSSettings = Field(default_factory=CORSSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    travel_apis: TravelAPISettings = Field(default_factory=TravelAPISettings)
    
    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"
    
    @property
    def is_test(self) -> bool:
        return self.environment.lower() == "test"
    
    def __hash__(self):
        return hash(self.app_version)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Global settings instance
settings = get_settings()
