"""
Trip Model with SQLAlchemy 2.0
Comprehensive trip planning model with itinerary and budget
"""

import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
from enum import Enum as PyEnum

from sqlalchemy import String, DateTime, Date, Text, Numeric, ForeignKey, Index, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from backend.db.database import Base

if TYPE_CHECKING:
    from backend.db.models.user import User
    from backend.db.models.booking import Booking


class TripStatus(str, PyEnum):
    """Trip status enum"""
    DRAFT = "draft"
    PLANNED = "planned"
    BOOKED = "booked"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Trip(Base):
    """Trip model with full itinerary and budget tracking"""
    
    __tablename__ = "trips"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    
    # Foreign key to user
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Basic information
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    destination: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    destination_country: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)  # ISO country code
    
    # Dates
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    duration_days: Mapped[int] = mapped_column(nullable=False)
    
    # Status
    status: Mapped[TripStatus] = mapped_column(
        Enum(TripStatus),
        default=TripStatus.DRAFT,
        nullable=False,
        index=True
    )
    
    # Budget
    budget_total: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True
    )
    budget_currency: Mapped[str] = mapped_column(String(3), default="USD")
    budget_breakdown: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict,
        nullable=True
    )
    actual_spent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00")
    )
    
    # Travelers
    travelers_count: Mapped[int] = mapped_column(default=1, nullable=False)
    travelers_details: Mapped[Optional[list]] = mapped_column(
        JSONB,
        default=list,
        nullable=True
    )
    
    # Itinerary (stored as JSONB for flexibility)
    itinerary: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict,
        nullable=True
    )
    
    # AI-generated content
    ai_recommendations: Mapped[Optional[list]] = mapped_column(
        JSONB,
        default=list,
        nullable=True
    )
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # External IDs
    amadeus_search_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    booking_com_search_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Preferences
    interests: Mapped[Optional[list]] = mapped_column(
        JSONB,
        default=list,
        nullable=True
    )
    travel_style: Mapped[Optional[str]] = mapped_column(
        String(20),
        default="balanced"
    )  # budget, balanced, luxury
    accommodation_type: Mapped[Optional[str]] = mapped_column(
        String(20),
        default="hotel"
    )  # hotel, hostel, apartment, resort
    
    # Emergency info
    emergency_contacts: Mapped[Optional[list]] = mapped_column(
        JSONB,
        default=list,
        nullable=True
    )
    insurance_info: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict,
        nullable=True
    )
    
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
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="trips")
    bookings: Mapped[List["Booking"]] = relationship(
        "Booking",
        back_populates="trip",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    # Indexes
    __table_args__ = (
        Index('ix_trips_user_status', 'user_id', 'status'),
        Index('ix_trips_dates', 'start_date', 'end_date'),
        Index('ix_trips_destination_dates', 'destination', 'start_date'),
        Index('ix_trips_itinerary_gin', 'itinerary', postgresql_using='gin'),
        Index('ix_trips_budget_currency', 'budget_currency'),
    )
    
    @property
    def is_past(self) -> bool:
        """Check if trip is in the past"""
        return self.end_date < date.today()
    
    @property
    def is_active_now(self) -> bool:
        """Check if trip is currently active"""
        return self.start_date <= date.today() <= self.end_date
    
    @property
    def budget_remaining(self) -> Optional[Decimal]:
        """Calculate remaining budget"""
        if self.budget_total:
            return self.budget_total - (self.actual_spent or Decimal("0.00"))
        return None
    
    @property
    def progress_percentage(self) -> int:
        """Calculate trip progress percentage"""
        if self.is_past:
            return 100
        if date.today() < self.start_date:
            return 0
        
        total_days = (self.end_date - self.start_date).days
        if total_days == 0:
            return 100
        
        elapsed = (date.today() - self.start_date).days
        return min(100, int((elapsed / total_days) * 100))
    
    def __repr__(self) -> str:
        return f"<Trip(id={self.id}, destination={self.destination}, status={self.status})>"
    
    def to_dict(self, include_bookings: bool = False) -> dict:
        """Convert to dictionary"""
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "destination": self.destination,
            "destination_country": self.destination_country,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "duration_days": self.duration_days,
            "status": self.status.value,
            "budget": {
                "total": float(self.budget_total) if self.budget_total else None,
                "currency": self.budget_currency,
                "spent": float(self.actual_spent) if self.actual_spent else 0.0,
                "remaining": float(self.budget_remaining) if self.budget_remaining else None,
                "breakdown": self.budget_breakdown or {}
            },
            "travelers_count": self.travelers_count,
            "interests": self.interests or [],
            "travel_style": self.travel_style,
            "accommodation_type": self.accommodation_type,
            "progress_percentage": self.progress_percentage,
            "is_active_now": self.is_active_now,
            "is_past": self.is_past,
            "ai_summary": self.ai_summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if include_bookings and self.bookings:
            data["bookings"] = [b.to_dict() for b in self.bookings]
        else:
            data["booking_count"] = len(self.bookings) if self.bookings else 0
        
        return data
