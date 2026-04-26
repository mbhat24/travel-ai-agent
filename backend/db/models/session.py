"""
Session Model for authentication sessions
Tracks user login sessions across devices
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, INET

from backend.db.database import Base


class Session(Base):
    """User session for authentication tracking"""
    
    __tablename__ = "sessions"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Token
    refresh_token_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    # Device info
    device_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    device_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    device_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # mobile, desktop, tablet
    os: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    browser: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Location
    ip_address: Mapped[Optional[str]] = mapped_column(INET, nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(default=True)
    is_revoked: Mapped[bool] = mapped_column(default=False)
    revoked_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    # Indexes
    __table_args__ = (
        Index('ix_sessions_user_active', 'user_id', 'is_active'),
        Index('ix_sessions_expires', 'expires_at'),
    )
    
    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        return self.is_active and not self.is_revoked and not self.is_expired
    
    def __repr__(self) -> str:
        return f"<Session(id={self.id}, user_id={self.user_id}, valid={self.is_valid})>"
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "device_name": self.device_name,
            "device_type": self.device_type,
            "os": self.os,
            "browser": self.browser,
            "location": {
                "country": self.country,
                "city": self.city
            },
            "is_valid": self.is_valid,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
