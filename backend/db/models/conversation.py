"""
Conversation Model for AI chat history
Stores all travel counselling conversations
"""

import uuid
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from enum import Enum as PyEnum

from sqlalchemy import String, DateTime, Text, ForeignKey, Index, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from backend.db.database import Base

if TYPE_CHECKING:
    from backend.db.models.user import User


class MessageRole(str, PyEnum):
    """Message role enum"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Conversation(Base):
    """Conversation session for AI chat"""
    
    __tablename__ = "conversations"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Session identifier for anonymous users
    session_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    
    # Conversation metadata
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    context: Mapped[str] = mapped_column(
        String(50),
        default="general",
        nullable=False
    )  # general, trip_planning, support, emergency
    
    # AI model used
    model: Mapped[str] = mapped_column(String(50), default="gpt-4o-mini")
    
    # Status
    is_active: Mapped[bool] = mapped_column(default=True)
    is_emergency: Mapped[bool] = mapped_column(default=False)
    
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
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="conversations")
    messages: Mapped[List["ConversationMessage"]] = relationship(
        "ConversationMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ConversationMessage.created_at"
    )
    
    # Indexes
    __table_args__ = (
        Index('ix_conversations_user_context', 'user_id', 'context'),
        Index('ix_conversations_session', 'session_id'),
        Index('ix_conversations_emergency', 'is_emergency'),
    )
    
    @property
    def message_count(self) -> int:
        return len(self.messages) if self.messages else 0
    
    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, context={self.context}, messages={self.message_count})>"
    
    def to_dict(self, include_messages: bool = False) -> dict:
        data = {
            "id": self.id,
            "title": self.title,
            "context": self.context,
            "model": self.model,
            "is_active": self.is_active,
            "is_emergency": self.is_emergency,
            "message_count": self.message_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if include_messages and self.messages:
            data["messages"] = [m.to_dict() for m in self.messages]
        
        return data


class ConversationMessage(Base):
    """Individual message in a conversation"""
    
    __tablename__ = "conversation_messages"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    
    conversation_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Message content
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole),
        nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Metadata
    tokens_used: Mapped[Optional[int]] = mapped_column(nullable=True)
    response_time_ms: Mapped[Optional[int]] = mapped_column(nullable=True)
    
    # Sentiment analysis
    sentiment: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    sentiment_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    
    # Emergency detection
    is_emergency: Mapped[bool] = mapped_column(default=False)
    emergency_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    emergency_severity: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    # Follow-up suggestions
    followups: Mapped[Optional[list]] = mapped_column(
        JSONB,
        default=list,
        nullable=True
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
    
    # Indexes
    __table_args__ = (
        Index('ix_messages_conversation_role', 'conversation_id', 'role'),
        Index('ix_messages_emergency', 'is_emergency'),
        Index('ix_messages_created', 'created_at'),
    )
    
    def __repr__(self) -> str:
        return f"<ConversationMessage(id={self.id}, role={self.role}, emergency={self.is_emergency})>"
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "role": self.role.value,
            "content": self.content,
            "tokens_used": self.tokens_used,
            "response_time_ms": self.response_time_ms,
            "sentiment": self.sentiment,
            "sentiment_score": self.sentiment_score,
            "is_emergency": self.is_emergency,
            "emergency_type": self.emergency_type,
            "emergency_severity": self.emergency_severity,
            "followups": self.followups or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
