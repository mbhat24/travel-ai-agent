"""
Travel AI Agent Platform - Professional FastAPI Application
Enterprise-grade backend with async SQLAlchemy, structured logging, and comprehensive error handling
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.core.config import settings
from backend.core.logging import setup_logging, get_logger
from backend.db import init_database, close_database, db_manager
from backend.middleware import (
    ExceptionHandlerMiddleware,
    LoggingMiddleware,
    SecurityHeadersMiddleware,
    RateLimitMiddleware
)
from backend.routers import auth, trips, bookings, agents, rag

# Setup logging
setup_logging(
    level=settings.logging.level,
    structured=settings.logging.structured == "json",
    log_file=settings.logging.file_path
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - handles startup and shutdown"""
    # Startup
    logger.info("=" * 60)
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info("=" * 60)
    
    try:
        # Initialize database
        await init_database()
        logger.info("Database initialized successfully")
        
        # Check database health
        if await db_manager.health_check():
            logger.info("Database health check passed")
        else:
            logger.error("Database health check failed")
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}", exc_info=True)
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    
    try:
        await close_database()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)
    
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="AI-powered travel agency platform with professional architecture",
    version=settings.app_version,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    openapi_url="/openapi.json" if settings.is_development else None,
    lifespan=lifespan
)

# Add middleware (order matters!)
# 1. Exception handling should be first to catch all errors
app.add_middleware(ExceptionHandlerMiddleware)

# 2. Rate limiting
if settings.rate_limit.enabled:
    app.add_middleware(
        RateLimitMiddleware,
        max_requests=settings.rate_limit.requests_per_minute,
        window_seconds=settings.rate_limit.window_seconds
    )

# 3. Logging
app.add_middleware(LoggingMiddleware)

# 4. Security headers
app.add_middleware(SecurityHeadersMiddleware)

# 5. CORS (must be after security headers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.origins,
    allow_credentials=settings.cors.allow_credentials,
    allow_methods=settings.cors.allowed_methods,
    allow_headers=settings.cors.allowed_headers,
    max_age=settings.cors.max_age
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(trips.router, prefix="/api/trips", tags=["Trips"])
app.include_router(bookings.router, prefix="/api/bookings", tags=["Bookings"])
app.include_router(agents.router, prefix="/api/agents", tags=["AI Agents"])
app.include_router(rag.router, prefix="/api/rag", tags=["RAG"])


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint with API information"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "status": "running",
        "documentation": "/docs" if settings.is_development else None
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Comprehensive health check endpoint"""
    health_status = {
        "status": "healthy",
        "timestamp": __import__('datetime').datetime.utcnow().isoformat(),
        "version": settings.app_version,
        "environment": settings.environment,
        "checks": {}
    }
    
    # Database health check
    try:
        db_healthy = await db_manager.health_check()
        health_status["checks"]["database"] = "healthy" if db_healthy else "unhealthy"
        if not db_healthy:
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["checks"]["database"] = f"error: {str(e)}"
        health_status["status"] = "degraded"
    
    return health_status


@app.get("/ready", tags=["Health"])
async def readiness_check():
    """Readiness probe for Kubernetes"""
    try:
        db_healthy = await db_manager.health_check()
        if db_healthy:
            return {"status": "ready"}
        else:
            return JSONResponse(
                status_code=503,
                content={"status": "not ready", "reason": "database unhealthy"}
            )
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "reason": str(e)}
        )


@app.get("/live", tags=["Health"])
async def liveness_check():
    """Liveness probe for Kubernetes"""
    return {"status": "alive"}


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        workers=settings.workers if not settings.reload else 1,
        log_level=settings.logging.level.lower()
    )
