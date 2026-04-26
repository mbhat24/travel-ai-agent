"""
User Model with SQLAlchemy 2.0
Professional user model with relationships and proper typing
"""

import uuid
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Boolean, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from backend.db.database import Base

if TYPE_CHECKING:
    from backend.db.models.trip import Trip
    from backend.db.models.session import Session
    from backend.db.models.conversation import Conversation


class User(Base):
    """User model with all related data"""
    
    __tablename__ = "users"
    
    # Primary key with UUID
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    
    # Authentication
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    # Profile information
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Preferences stored as JSONB
    preferences: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict,
        nullable=True
    )
    
    # Account status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    
    # Security
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv6 compatible
    login_attempts: Mapped[int] = mapped_column(
        default=0,
        nullable=False
    )
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    trips: Mapped[List["Trip"]] = relationship(
        "Trip",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    sessions: Mapped[List["Session"]] = relationship(
        "Session",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    # Indexes for common queries
    __table_args__ = (
        Index('ix_users_email_active', 'email', 'is_active'),
        Index('ix_users_created', 'created_at'),
        Index('ix_users_preferences_gin', 'preferences', postgresql_using='gin'),
    )
    
    @property
    def full_name(self) -> str:
        """Get user's full name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    @property
    def is_locked(self) -> bool:
        """Check if account is locked"""
        if self.locked_until and self.locked_until > datetime.utcnow():
            return True
        return False
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, username={self.username})>"
    
    def to_dict(self, include_relations: bool = False) -> dict:
        """Convert to dictionary for serialization"""
        data = {
            "id": self.id,
            "email": self.email,
            "username": self.username,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "phone": self.phone,
            "avatar_url": self.avatar_url,
            "preferences": self.preferences or {},
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "is_superuser": self.is_superuser,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if include_relations:
            data["trip_count"] = len(self.trips) if self.trips else 0
            data["session_count"] = len(self.sessions) if self.sessions else 0
        
        return data
