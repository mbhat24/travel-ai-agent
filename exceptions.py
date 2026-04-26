"""
Custom Exception Classes
Extreme Professional Grade Error Handling with HTTP status codes and structured error responses
"""

from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status


class TravelAIException(HTTPException):
    """Base exception for Travel AI Agent"""
    
    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        
        error_response = {
            'error': {
                'code': error_code,
                'message': message,
                'details': self.details,
                'type': self.__class__.__name__
            }
        }
        
        super().__init__(status_code=status_code, detail=error_response, headers=headers)


# Authentication & Authorization Exceptions
class AuthenticationError(TravelAIException):
    """Invalid or missing authentication"""
    
    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="AUTH_001",
            message=message,
            details=details,
            headers={"WWW-Authenticate": "Bearer"}
        )


class AuthorizationError(TravelAIException):
    """Insufficient permissions"""
    
    def __init__(
        self,
        message: str = "Access denied",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="AUTH_002",
            message=message,
            details=details
        )


class TokenExpiredError(TravelAIException):
    """JWT token has expired"""
    
    def __init__(
        self,
        message: str = "Token has expired",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="AUTH_003",
            message=message,
            details=details,
            headers={"WWW-Authenticate": "Bearer"}
        )


class InvalidTokenError(TravelAIException):
    """Invalid JWT token"""
    
    def __init__(
        self,
        message: str = "Invalid token",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="AUTH_004",
            message=message,
            details=details,
            headers={"WWW-Authenticate": "Bearer"}
        )


# User Management Exceptions
class UserNotFoundError(TravelAIException):
    """User not found in database"""
    
    def __init__(
        self,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"User {user_id} not found" if user_id else "User not found"
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="USER_001",
            message=message,
            details=details
        )


class UserAlreadyExistsError(TravelAIException):
    """User already exists"""
    
    def __init__(
        self,
        email: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"User with email {email} already exists" if email else "User already exists"
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_code="USER_002",
            message=message,
            details=details
        )


class InvalidCredentialsError(TravelAIException):
    """Invalid login credentials"""
    
    def __init__(
        self,
        message: str = "Invalid email or password",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="USER_003",
            message=message,
            details=details
        )


# Trip Management Exceptions
class TripNotFoundError(TravelAIException):
    """Trip not found"""
    
    def __init__(
        self,
        trip_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Trip {trip_id} not found" if trip_id else "Trip not found"
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="TRIP_001",
            message=message,
            details=details
        )


class InvalidTripDataError(TravelAIException):
    """Invalid trip data"""
    
    def __init__(
        self,
        message: str = "Invalid trip data",
        errors: Optional[List[str]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        full_details = details or {}
        if errors:
            full_details['validation_errors'] = errors
        
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="TRIP_002",
            message=message,
            details=full_details
        )


class TripOwnershipError(TravelAIException):
    """User doesn't own the trip"""
    
    def __init__(
        self,
        trip_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        message = "You don't have permission to access this trip"
        if trip_id:
            message += f" ({trip_id})"
        
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="TRIP_003",
            message=message,
            details=details
        )


# External API Exceptions
class ExternalAPIError(TravelAIException):
    """External API call failed"""
    
    def __init__(
        self,
        service: str,
        message: Optional[str] = None,
        status_code: int = 503,
        details: Optional[Dict[str, Any]] = None
    ):
        message = message or f"{service} API is unavailable"
        super().__init__(
            status_code=status_code,
            error_code=f"API_{service.upper()}_001",
            message=message,
            details=details
        )


class WeatherAPIError(ExternalAPIError):
    """Weather API error"""
    
    def __init__(
        self,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            service="WEATHER",
            message=message or "Weather service unavailable",
            status_code=503,
            details=details
        )


class FlightAPIError(ExternalAPIError):
    """Flight search API error"""
    
    def __init__(
        self,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            service="FLIGHT",
            message=message or "Flight search service unavailable",
            status_code=503,
            details=details
        )


# Rate Limiting Exceptions
class RateLimitExceededError(TravelAIException):
    """Rate limit exceeded"""
    
    def __init__(
        self,
        limit: int,
        window: int,
        retry_after: int,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Rate limit exceeded: {limit} requests per {window} seconds"
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code="RATE_001",
            message=message,
            details=details,
            headers={"Retry-After": str(retry_after)}
        )


# Validation Exceptions
class ValidationError(TravelAIException):
    """Input validation error"""
    
    def __init__(
        self,
        message: str = "Validation failed",
        errors: Optional[List[Dict[str, Any]]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        full_details = details or {}
        if errors:
            full_details['validation_errors'] = errors
        
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="VAL_001",
            message=message,
            details=full_details
        )


# LLM/AI Exceptions
class LLMError(TravelAIException):
    """LLM service error"""
    
    def __init__(
        self,
        message: str = "AI service unavailable",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="LLM_001",
            message=message,
            details=details
        )


class LLMTimeoutError(TravelAIException):
    """LLM request timed out"""
    
    def __init__(
        self,
        message: str = "AI service request timed out",
        timeout: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        full_details = details or {}
        if timeout:
            full_details['timeout_seconds'] = timeout
        
        super().__init__(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            error_code="LLM_002",
            message=message,
            details=full_details
        )


# Database Exceptions
class DatabaseError(TravelAIException):
    """Database operation error"""
    
    def __init__(
        self,
        message: str = "Database error",
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        full_details = details or {}
        if operation:
            full_details['operation'] = operation
        
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="DB_001",
            message=message,
            details=full_details
        )


# Consent/Legal Exceptions
class ConsentRequiredError(TravelAIException):
    """User consent required"""
    
    def __init__(
        self,
        message: str = "User consent required",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="LEGAL_001",
            message=message,
            details=details
        )


class ConsentWithdrawnError(TravelAIException):
    """User has withdrawn consent"""
    
    def __init__(
        self,
        message: str = "Consent has been withdrawn",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="LEGAL_002",
            message=message,
            details=details
        )


# Emergency Detection
class EmergencyDetectedError(TravelAIException):
    """Travel emergency detected - special handling"""
    
    def __init__(
        self,
        emergency_type: str,
        severity: str,
        resources: Optional[List[str]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        full_details = details or {}
        full_details['emergency_type'] = emergency_type
        full_details['severity'] = severity
        full_details['resources'] = resources or []
        
        super().__init__(
            status_code=200,  # Special case - not an error but needs attention
            error_code="EMERGENCY_001",
            message=f"Travel emergency detected: {emergency_type}",
            details=full_details
        )


# Generic error response builder
def build_error_response(
    error_code: str,
    message: str,
    status_code: int = 500,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """Build standardized error response"""
    response = {
        'error': {
            'code': error_code,
            'message': message,
            'type': 'TravelAIException',
            'status': status_code,
            'timestamp': __import__('datetime').datetime.utcnow().isoformat()
        }
    }
    
    if details:
        response['error']['details'] = details
    
    if request_id:
        response['error']['request_id'] = request_id
    
    return response
