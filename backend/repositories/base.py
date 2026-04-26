"""
Base Repository Pattern
Professional-grade generic repository with CRUD operations
"""

from typing import TypeVar, Generic, Optional, List, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import joinedload
import logging

from backend.db.database import Base

logger = logging.getLogger(__name__)

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Generic repository with standard CRUD operations
    All repositories should inherit from this
    """
    
    def __init__(self, model: type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db
    
    async def get_by_id(self, id: str, load_relations: Optional[List[str]] = None) -> Optional[ModelType]:
        """Get entity by ID with optional relation loading"""
        query = select(self.model).where(self.model.id == id)
        
        if load_relations:
            for relation in load_relations:
                query = query.options(joinedload(getattr(self.model, relation)))
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_field(self, field: str, value: Any, load_relations: Optional[List[str]] = None) -> Optional[ModelType]:
        """Get entity by any field"""
        query = select(self.model).where(getattr(self.model, field) == value)
        
        if load_relations:
            for relation in load_relations:
                query = query.options(joinedload(getattr(self.model, relation)))
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_many(
        self,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        load_relations: Optional[List[str]] = None
    ) -> List[ModelType]:
        """Get multiple entities with filtering and pagination"""
        query = select(self.model)
        
        # Apply filters
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    query = query.where(getattr(self.model, field) == value)
        
        # Load relations
        if load_relations:
            for relation in load_relations:
                query = query.options(joinedload(getattr(self.model, relation)))
        
        # Order by
        if order_by:
            if order_by.startswith("-"):
                query = query.order_by(getattr(self.model, order_by[1:]).desc())
            else:
                query = query.order_by(getattr(self.model, order_by))
        
        # Pagination
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count entities with optional filtering"""
        query = select(func.count()).select_from(self.model)
        
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    query = query.where(getattr(self.model, field) == value)
        
        result = await self.db.execute(query)
        return result.scalar()
    
    async def create(self, obj_in: Dict[str, Any]) -> ModelType:
        """Create new entity"""
        db_obj = self.model(**obj_in)
        self.db.add(db_obj)
        await self.db.flush()
        await self.db.refresh(db_obj)
        logger.debug(f"Created {self.model.__name__}: {db_obj.id}")
        return db_obj
    
    async def update(self, id: str, obj_in: Dict[str, Any]) -> Optional[ModelType]:
        """Update entity by ID"""
        query = (
            update(self.model)
            .where(self.model.id == id)
            .values(**obj_in)
            .returning(self.model)
        )
        
        result = await self.db.execute(query)
        db_obj = result.scalar_one_or_none()
        
        if db_obj:
            await self.db.refresh(db_obj)
            logger.debug(f"Updated {self.model.__name__}: {id}")
        
        return db_obj
    
    async def delete(self, id: str) -> bool:
        """Delete entity by ID"""
        query = delete(self.model).where(self.model.id == id)
        result = await self.db.execute(query)
        
        if result.rowcount > 0:
            logger.debug(f"Deleted {self.model.__name__}: {id}")
            return True
        return False
    
    async def exists(self, id: str) -> bool:
        """Check if entity exists"""
        query = select(self.model.id).where(self.model.id == id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None
    
    async def soft_delete(self, id: str) -> Optional[ModelType]:
        """Soft delete by setting deleted_at timestamp"""
        from datetime import datetime
        return await self.update(id, {"deleted_at": datetime.utcnow(), "is_active": False})


class UserRepository(BaseRepository):
    """User repository with user-specific operations"""
    
    from backend.db.models import User
    
    async def get_by_email(self, email: str, load_relations: Optional[List[str]] = None) -> Optional[User]:
        """Get user by email"""
        return await self.get_by_field("email", email, load_relations)
    
    async def get_by_username(self, username: str, load_relations: Optional[List[str]] = None) -> Optional[User]:
        """Get user by username"""
        return await self.get_by_field("username", username, load_relations)
    
    async def get_active_users(self, limit: int = 100, offset: int = 0) -> List[User]:
        """Get active users with pagination"""
        return await self.get_many(
            filters={"is_active": True},
            order_by="-created_at",
            limit=limit,
            offset=offset
        )
    
    async def get_user_with_trips(self, user_id: str) -> Optional[User]:
        """Get user with all trips loaded"""
        return await self.get_by_id(user_id, load_relations=["trips"])
    
    async def update_last_login(self, user_id: str, ip_address: str) -> Optional[User]:
        """Update user's last login info"""
        from datetime import datetime
        return await self.update(user_id, {
            "last_login": datetime.utcnow(),
            "last_ip": ip_address,
            "login_attempts": 0,
            "locked_until": None
        })
    
    async def increment_login_attempts(self, user_id: str) -> Optional[User]:
        """Increment login attempts"""
        user = await self.get_by_id(user_id)
        if user:
            attempts = (user.login_attempts or 0) + 1
            return await self.update(user_id, {"login_attempts": attempts})
        return None


class TripRepository(BaseRepository):
    """Trip repository with trip-specific operations"""
    
    from backend.db.models import Trip
    
    async def get_user_trips(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Trip]:
        """Get trips for a specific user"""
        filters = {"user_id": user_id}
        if status:
            filters["status"] = status
        
        return await self.get_many(
            filters=filters,
            order_by="-start_date",
            limit=limit,
            offset=offset
        )
    
    async def get_active_trips(self, user_id: str) -> List[Trip]:
        """Get currently active trips for user"""
        from datetime import date
        from backend.db.models import TripStatus
        
        return await self.get_many(
            filters={
                "user_id": user_id,
                "status": TripStatus.ACTIVE,
            },
            order_by="start_date"
        )
    
    async def get_upcoming_trips(self, user_id: str, days: int = 30) -> List[Trip]:
        """Get upcoming trips within specified days"""
        from datetime import date, timedelta
        from sqlalchemy import and_
        
        start_date = date.today()
        end_date = start_date + timedelta(days=days)
        
        query = select(self.model).where(
            and_(
                self.model.user_id == user_id,
                self.model.start_date >= start_date,
                self.model.start_date <= end_date,
                self.model.status.in_(["planned", "booked"])
            )
        ).order_by(self.model.start_date)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_trip_with_bookings(self, trip_id: str) -> Optional[Trip]:
        """Get trip with all bookings loaded"""
        return await self.get_by_id(trip_id, load_relations=["bookings", "user"])


class BookingRepository(BaseRepository):
    """Booking repository with booking-specific operations"""
    
    from backend.db.models import Booking
    
    async def get_trip_bookings(
        self,
        trip_id: str,
        booking_type: Optional[str] = None
    ) -> List[Booking]:
        """Get bookings for a trip"""
        filters = {"trip_id": trip_id}
        if booking_type:
            filters["type"] = booking_type
        
        return await self.get_many(
            filters=filters,
            order_by="start_datetime"
        )
    
    async def get_confirmed_bookings(self, trip_id: str) -> List[Booking]:
        """Get confirmed bookings for a trip"""
        from backend.db.models import BookingStatus
        
        return await self.get_many(
            filters={
                "trip_id": trip_id,
                "status": BookingStatus.CONFIRMED
            },
            order_by="start_datetime"
        )


class ConversationRepository(BaseRepository):
    """Conversation repository with message operations"""
    
    from backend.db.models import Conversation, ConversationMessage
    
    async def get_user_conversations(
        self,
        user_id: str,
        context: Optional[str] = None,
        limit: int = 50
    ) -> List[Conversation]:
        """Get conversations for a user"""
        filters = {"user_id": user_id, "is_active": True}
        if context:
            filters["context"] = context
        
        return await self.get_many(
            filters=filters,
            order_by="-updated_at",
            limit=limit,
            load_relations=["messages"]
        )
    
    async def get_conversation_with_messages(self, conversation_id: str) -> Optional[Conversation]:
        """Get conversation with all messages"""
        return await self.get_by_id(conversation_id, load_relations=["messages", "user"])
    
    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> ConversationMessage:
        """Add a message to a conversation"""
        message_data = {
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            **(metadata or {})
        }
        
        message = ConversationMessage(**message_data)
        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)
        
        # Update conversation timestamp
        from datetime import datetime
        await self.update(conversation_id, {"updated_at": datetime.utcnow()})
        
        return message


class SessionRepository(BaseRepository):
    """Session repository for authentication sessions"""
    
    from backend.db.models import Session
    
    async def get_active_sessions(self, user_id: str) -> List[Session]:
        """Get active (non-expired) sessions for user"""
        from datetime import datetime
        
        query = select(self.model).where(
            self.model.user_id == user_id,
            self.model.is_active == True,
            self.model.expires_at > datetime.utcnow()
        )
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def revoke_session(self, session_id: str, reason: str = "user_logout") -> Optional[Session]:
        """Revoke a session"""
        from datetime import datetime
        
        return await self.update(session_id, {
            "is_active": False,
            "is_revoked": True,
            "revoked_at": datetime.utcnow(),
            "revoked_reason": reason
        })
    
    async def revoke_all_user_sessions(self, user_id: str, reason: str = "security") -> int:
        """Revoke all sessions for a user"""
        sessions = await self.get_active_sessions(user_id)
        revoked_count = 0
        
        for session in sessions:
            if await self.revoke_session(session.id, reason):
                revoked_count += 1
        
        return revoked_count
