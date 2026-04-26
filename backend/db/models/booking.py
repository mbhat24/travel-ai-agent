"""
Booking Model with SQLAlchemy 2.0
Hotel, flight, and activity booking model
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from enum import Enum as PyEnum

from sqlalchemy import String, DateTime, Text, Numeric, ForeignKey, Index, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from backend.db.database import Base

if TYPE_CHECKING:
    from backend.db.models.trip import Trip


class BookingType(str, PyEnum):
    """Booking type enum"""
    FLIGHT = "flight"
    HOTEL = "hotel"
    CAR_RENTAL = "car_rental"
    ACTIVITY = "activity"
    RESTAURANT = "restaurant"
    INSURANCE = "insurance"
    TRANSFER = "transfer"
    CRUISE = "cruise"


class BookingStatus(str, PyEnum):
    """Booking status enum"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    REFUNDED = "refunded"


class Booking(Base):
    """Booking model for all travel reservations"""
    
    __tablename__ = "bookings"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    
    # Foreign keys
    trip_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("trips.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Booking details
    type: Mapped[BookingType] = mapped_column(
        Enum(BookingType),
        nullable=False,
        index=True
    )
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus),
        default=BookingStatus.PENDING,
        nullable=False,
        index=True
    )
    
    # Provider information
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # amadeus, booking_com, expedia, etc.
    provider_booking_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    provider_confirmation_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Item details
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    
    # Dates
    start_datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Pricing
    base_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    taxes_fees: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    
    # Payment
    payment_status: Mapped[str] = mapped_column(String(20), default="pending")
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Cancellation
    cancellation_policy: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_cancellable: Mapped[bool] = mapped_column(default=True)
    cancellation_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    refund_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    
    # Raw data from provider
    raw_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict,
        nullable=True
    )
    
    # Passengers/guests
    guests: Mapped[Optional[list]] = mapped_column(
        JSONB,
        default=list,
        nullable=True
    )
    guest_count: Mapped[int] = mapped_column(default=1)
    
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
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    trip: Mapped["Trip"] = relationship("Trip", back_populates="bookings")
    
    # Indexes
    __table_args__ = (
        Index('ix_bookings_trip_type', 'trip_id', 'type'),
        Index('ix_bookings_status_provider', 'status', 'provider'),
        Index('ix_bookings_provider_id', 'provider', 'provider_booking_id'),
        Index('ix_bookings_dates', 'start_datetime', 'end_datetime'),
    )
    
    @property
    def is_confirmed(self) -> bool:
        return self.status == BookingStatus.CONFIRMED
    
    @property
    def is_past(self) -> bool:
        return self.end_datetime and self.end_datetime < datetime.utcnow()
    
    def __repr__(self) -> str:
        return f"<Booking(id={self.id}, type={self.type}, status={self.status})>"
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "trip_id": self.trip_id,
            "type": self.type.value,
            "status": self.status.value,
            "provider": self.provider,
            "provider_booking_id": self.provider_booking_id,
            "confirmation_code": self.provider_confirmation_code,
            "title": self.title,
            "description": self.description,
            "location": self.location,
            "start_datetime": self.start_datetime.isoformat() if self.start_datetime else None,
            "end_datetime": self.end_datetime.isoformat() if self.end_datetime else None,
            "price": {
                "base": float(self.base_price),
                "taxes_fees": float(self.taxes_fees),
                "total": float(self.total_price),
                "currency": self.currency
            },
            "guests_count": self.guest_count,
            "payment_status": self.payment_status,
            "is_cancellable": self.is_cancellable,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
