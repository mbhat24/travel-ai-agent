"""
FastAPI Middleware
Exception handling, logging, and request tracking
"""

import time
import traceback
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging

from backend.exceptions import TravelAIException
from backend.core.logging import get_logger, set_correlation_id, get_correlation_id, clear_correlation_id

logger = get_logger(__name__)


class ExceptionHandlerMiddleware(BaseHTTPMiddleware):
    """Global exception handling middleware"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
            
        except TravelAIException as exc:
            # Our custom exceptions are already formatted
            logger.warning(
                f"Application error: {exc.error_code}",
                extra={'extras': {'error_code': exc.error_code, 'path': request.url.path}}
            )
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.detail,
                headers=exc.headers
            )
            
        except Exception as exc:
            # Unexpected errors
            correlation_id = get_correlation_id()
            logger.error(
                f"Unhandled exception: {str(exc)}",
                extra={
                    'extras': {
                        'correlation_id': correlation_id,
                        'path': request.url.path,
                        'method': request.method,
                        'traceback': traceback.format_exc()
                    }
                }
            )
            
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_001",
                        "message": "An unexpected error occurred",
                        "correlation_id": correlation_id,
                        "type": "InternalServerError"
                    }
                }
            )


class LoggingMiddleware(BaseHTTPMiddleware):
    """Request logging middleware with correlation IDs"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Set correlation ID
        correlation_id = request.headers.get('X-Correlation-ID')
        set_correlation_id(correlation_id)
        
        # Add correlation ID to response headers
        request.state.correlation_id = get_correlation_id()
        
        start_time = time.time()
        
        # Log request
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                'extras': {
                    'method': request.method,
                    'path': request.url.path,
                    'query_params': str(request.query_params),
                    'client_ip': request.client.host if request.client else None,
                    'user_agent': request.headers.get('user-agent')
                }
            }
        )
        
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log response
            logger.info(
                f"Request completed: {request.method} {request.url.path}",
                extra={
                    'extras': {
                        'method': request.method,
                        'path': request.url.path,
                        'status_code': response.status_code,
                        'duration_ms': duration_ms
                    }
                }
            )
            
            # Add correlation ID to response
            response.headers['X-Correlation-ID'] = request.state.correlation_id
            
            return response
            
        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000
            
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                extra={
                    'extras': {
                        'method': request.method,
                        'path': request.url.path,
                        'duration_ms': duration_ms,
                        'error': str(exc)
                    }
                }
            )
            raise
            
        finally:
            clear_correlation_id()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        
        # Content Security Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self' https:;"
        )
        response.headers['Content-Security-Policy'] = csp
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware"""
    
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        
        # Clean old entries
        self.requests = {
            ip: timestamps for ip, timestamps in self.requests.items()
            if any(now - t < self.window_seconds for t in timestamps)
        }
        
        # Check rate limit
        if client_ip in self.requests:
            recent_requests = [
                t for t in self.requests[client_ip]
                if now - t < self.window_seconds
            ]
            
            if len(recent_requests) >= self.max_requests:
                retry_after = int(self.window_seconds - (now - recent_requests[0]))
                
                logger.warning(
                    f"Rate limit exceeded for {client_ip}",
                    extra={'extras': {'client_ip': client_ip, 'request_count': len(recent_requests)}}
                )
                
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_001",
                            "message": f"Rate limit exceeded: {self.max_requests} requests per {self.window_seconds} seconds",
                            "retry_after": retry_after
                        }
                    },
                    headers={"Retry-After": str(retry_after)}
                )
            
            self.requests[client_ip] = recent_requests + [now]
        else:
            self.requests[client_ip] = [now]
        
        response = await call_next(request)
        
        # Add rate limit headers
        remaining = self.max_requests - len(self.requests.get(client_ip, []))
        response.headers['X-RateLimit-Limit'] = str(self.max_requests)
        response.headers['X-RateLimit-Remaining'] = str(remaining)
        response.headers['X-RateLimit-Window'] = str(self.window_seconds)
        
        return response
