"""
Async Database Module with SQLAlchemy 2.0
Professional-grade async database with connection pooling and session management
"""

import contextlib
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
    AsyncConnection
)
from sqlalchemy.orm import declarative_base
from sqlalchemy import event, text
import logging

from backend.core.config import settings

logger = logging.getLogger(__name__)

# Base class for all models
Base = declarative_base()


class DatabaseManager:
    """Async database manager with connection pooling"""
    
    def __init__(self):
        self._engine: Optional[AsyncEngine] = None
        self._session_maker: Optional[async_sessionmaker] = None
    
    async def init(self, db_url: Optional[str] = None) -> None:
        """Initialize database engine with connection pooling"""
        db_url = db_url or settings.database.async_url
        
        self._engine = create_async_engine(
            db_url,
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow,
            pool_timeout=settings.database.pool_timeout,
            pool_recycle=settings.database.pool_recycle,
            echo=settings.database.echo,
            future=True,  # SQLAlchemy 2.0 style
        )
        
        self._session_maker = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        
        # Set up connection event listeners
        @event.listens_for(self._engine.sync_engine, "connect")
        def on_connect(dbapi_conn, connection_record):
            logger.debug("Database connection established")
        
        @event.listens_for(self._engine.sync_engine, "checkout")
        def on_checkout(dbapi_conn, connection_record, connection_proxy):
            logger.debug("Database connection checked out from pool")
        
        logger.info(f"Database initialized with pool_size={settings.database.pool_size}")
    
    async def close(self) -> None:
        """Close database engine and all connections"""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_maker = None
            logger.info("Database connections closed")
    
    async def create_tables(self) -> None:
        """Create all tables based on models"""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created")
    
    async def drop_tables(self) -> None:
        """Drop all tables - use with caution!"""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            logger.warning("Database tables dropped")
    
    async def health_check(self) -> bool:
        """Check database connectivity"""
        try:
            async with self._engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    @property
    def engine(self) -> AsyncEngine:
        """Get the async engine"""
        if not self._engine:
            raise RuntimeError("Database not initialized. Call init() first.")
        return self._engine
    
    @property
    def session_maker(self) -> async_sessionmaker:
        """Get the session maker"""
        if not self._session_maker:
            raise RuntimeError("Database not initialized. Call init() first.")
        return self._session_maker


# Global database manager instance
db_manager = DatabaseManager()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for getting database sessions"""
    if not db_manager._session_maker:
        raise RuntimeError("Database not initialized")
    
    session = db_manager.session_maker()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_db_connection() -> AsyncGenerator[AsyncConnection, None]:
    """Get a raw database connection for executing SQL directly"""
    async with db_manager.engine.connect() as conn:
        yield conn


@contextlib.asynccontextmanager
async def transaction():
    """Context manager for database transactions"""
    async with db_manager.session_maker() as session:
        async with session.begin():
            yield session


async def init_database():
    """Initialize database on application startup"""
    await db_manager.init()
    
    # Create tables if in development mode
    if settings.is_development:
        await db_manager.create_tables()
        logger.info("Database tables auto-created in development mode")


async def close_database():
    """Close database on application shutdown"""
    await db_manager.close()


# Import models to register them with Base
from backend.db.models.user import User
from backend.db.models.trip import Trip
from backend.db.models.booking import Booking
from backend.db.models.session import Session
from backend.db.models.conversation import Conversation

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
    "Booking",
    "Session",
    "Conversation",
]
