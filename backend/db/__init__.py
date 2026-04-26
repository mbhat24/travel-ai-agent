"""
Database package
Async database with SQLAlchemy 2.0
"""

from backend.db.database import (
    Base,
    db_manager,
    get_db_session,
    get_db_connection,
    transaction,
    init_database,
    close_database,
)

from backend.db.models.user import User
from backend.db.models.trip import Trip, TripStatus
from backend.db.models.booking import Booking, BookingType, BookingStatus
from backend.db.models.session import Session
from backend.db.models.conversation import Conversation, ConversationMessage, MessageRole

__all__ = [
    "Base",
    "db_manager",
    "get_db_session",
    "get_db_connection",
    "transaction",
    "init_database",
    "close_database",
    "User",
    "Trip",
    "TripStatus",
    "Booking",
    "BookingType",
    "BookingStatus",
    "Session",
    "Conversation",
    "ConversationMessage",
    "MessageRole",
]
