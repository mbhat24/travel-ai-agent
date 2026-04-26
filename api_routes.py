"""
Enhanced API Routes for Travel AI Agent
Includes trip management, user profiles, and conversation history
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from database import db
from auth_simple import (
    get_current_user, User, hash_password, verify_password,
    create_access_token, create_refresh_token, verify_token
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["api"])
security = HTTPBearer()

# ============================================================================
# Pydantic Models
# ============================================================================

class TripCreateRequest(BaseModel):
    destination: str = Field(..., min_length=1, max_length=200)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    budget: Optional[float] = Field(None, gt=0)
    travelers: int = Field(default=1, ge=1, le=50)
    interests: List[str] = Field(default_factory=list)
    itinerary: Optional[str] = None
    budget_breakdown: Optional[Dict[str, float]] = Field(default_factory=dict)
    recommendations: List[str] = Field(default_factory=list)

class TripUpdateRequest(BaseModel):
    destination: Optional[str] = Field(None, min_length=1, max_length=200)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    budget: Optional[float] = Field(None, gt=0)
    travelers: Optional[int] = Field(None, ge=1, le=50)
    interests: Optional[List[str]] = None
    itinerary: Optional[str] = None
    budget_breakdown: Optional[Dict[str, float]] = None
    recommendations: Optional[List[str]] = None
    status: Optional[str] = Field(None, pattern=r'^(planned|active|completed|cancelled)$')

class TripResponse(BaseModel):
    id: str
    user_id: str
    destination: str
    start_date: Optional[str]
    end_date: Optional[str]
    budget: Optional[float]
    travelers: int
    interests: List[str]
    itinerary: Optional[str]
    budget_breakdown: Dict[str, float]
    recommendations: List[str]
    status: str
    created_at: str
    updated_at: str

class UserProfileUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    profile_data: Optional[Dict[str, Any]] = None

class UserProfileResponse(BaseModel):
    user_id: str
    email: str
    username: str
    is_active: bool
    created_at: str
    profile_data: Dict[str, Any]
    trip_count: int

class ConversationHistoryResponse(BaseModel):
    id: str
    message: str
    response: Optional[str]
    sentiment: Optional[Dict[str, Any]]
    emergency_detected: bool
    created_at: str

class StatsResponse(BaseModel):
    total_users: int
    total_trips: int
    total_conversations: int
    active_sessions: int

# ============================================================================
# Trip Management Endpoints
# ============================================================================

@router.post("/trips", response_model=TripResponse)
async def create_trip(
    request: TripCreateRequest,
    current_user: User = Depends(get_current_user)
):
    """Create a new trip"""
    trip = db.create_trip(
        user_id=current_user.user_id,
        destination=request.destination,
        start_date=request.start_date,
        end_date=request.end_date,
        budget=request.budget,
        travelers=request.travelers,
        interests=request.interests,
        itinerary=request.itinerary,
        budget_breakdown=request.budget_breakdown,
        recommendations=request.recommendations
    )
    
    if not trip:
        raise HTTPException(status_code=500, detail="Failed to create trip")
    
    return TripResponse(**trip)

@router.get("/trips", response_model=List[TripResponse])
async def list_trips(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """List all trips for the current user"""
    trips = db.get_user_trips(current_user.user_id, status=status)
    return [TripResponse(**trip) for trip in trips]

@router.get("/trips/{trip_id}", response_model=TripResponse)
async def get_trip(
    trip_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get a specific trip by ID"""
    trip = db.get_trip_by_id(trip_id)
    
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    if trip['user_id'] != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this trip")
    
    return TripResponse(**trip)

@router.put("/trips/{trip_id}", response_model=TripResponse)
async def update_trip(
    trip_id: str,
    request: TripUpdateRequest,
    current_user: User = Depends(get_current_user)
):
    """Update a trip"""
    existing = db.get_trip_by_id(trip_id)
    
    if not existing:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    if existing['user_id'] != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this trip")
    
    # Build update dict with only provided fields
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    success = db.update_trip(trip_id, **updates)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update trip")
    
    updated = db.get_trip_by_id(trip_id)
    return TripResponse(**updated)

@router.delete("/trips/{trip_id}")
async def delete_trip(
    trip_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a trip"""
    existing = db.get_trip_by_id(trip_id)
    
    if not existing:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    if existing['user_id'] != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this trip")
    
    success = db.delete_trip(trip_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete trip")
    
    return {"message": "Trip deleted successfully", "trip_id": trip_id}

@router.post("/trips/{trip_id}/activate")
async def activate_trip(
    trip_id: str,
    current_user: User = Depends(get_current_user)
):
    """Activate a trip (mark as currently traveling)"""
    existing = db.get_trip_by_id(trip_id)
    
    if not existing:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    if existing['user_id'] != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    success = db.update_trip(trip_id, status='active')
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to activate trip")
    
    return {"message": "Trip activated", "trip_id": trip_id}

@router.post("/trips/{trip_id}/complete")
async def complete_trip(
    trip_id: str,
    current_user: User = Depends(get_current_user)
):
    """Complete a trip"""
    existing = db.get_trip_by_id(trip_id)
    
    if not existing:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    if existing['user_id'] != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    success = db.update_trip(trip_id, status='completed')
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to complete trip")
    
    return {"message": "Trip marked as completed", "trip_id": trip_id}

# ============================================================================
# User Profile Endpoints
# ============================================================================

@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile with stats"""
    user = db.get_user_by_id(current_user.user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    trips = db.get_user_trips(current_user.user_id)
    
    return UserProfileResponse(
        user_id=user['id'],
        email=user['email'],
        username=user['username'],
        is_active=user['is_active'],
        created_at=user['created_at'],
        profile_data=user.get('profile_data', {}),
        trip_count=len(trips)
    )

@router.put("/profile")
async def update_profile(
    request: UserProfileUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update user profile"""
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    success = db.update_user(current_user.user_id, **updates)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update profile")
    
    return {"message": "Profile updated successfully"}

@router.get("/profile/history", response_model=List[ConversationHistoryResponse])
async def get_conversation_history(
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """Get conversation history for the user"""
    conversations = db.get_conversation_history(user_id=current_user.user_id, limit=limit)
    return [ConversationHistoryResponse(**conv) for conv in conversations]

# ============================================================================
# Stats Endpoint
# ============================================================================

@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Get platform statistics"""
    stats = db.get_stats()
    return StatsResponse(
        total_users=stats.get('users', 0),
        total_trips=stats.get('trips', 0),
        total_conversations=stats.get('conversations', 0),
        active_sessions=stats.get('sessions', 0)
    )

# ============================================================================
# Travel API Integration Endpoints
# ============================================================================

from travel_apis import weather_api, advisory_api, currency_api, enrich_travel_plan

class WeatherRequest(BaseModel):
    city: str
    country: Optional[str] = None

class CurrencyConvertRequest(BaseModel):
    amount: float
    from_currency: str = Field(..., min_length=3, max_length=3)
    to_currency: str = Field(..., min_length=3, max_length=3)

@router.post("/weather")
async def get_weather(request: WeatherRequest):
    """Get current weather for a destination"""
    if not weather_api.is_available():
        raise HTTPException(status_code=503, detail="Weather API not configured")
    
    weather = weather_api.get_current_weather(request.city, request.country)
    if not weather:
        raise HTTPException(status_code=404, detail="Weather data not available")
    
    return weather

@router.post("/weather/forecast")
async def get_weather_forecast(request: WeatherRequest, days: int = 5):
    """Get weather forecast for a destination"""
    if not weather_api.is_available():
        raise HTTPException(status_code=503, detail="Weather API not configured")
    
    forecast = weather_api.get_forecast(request.city, request.country, days)
    if not forecast:
        raise HTTPException(status_code=404, detail="Forecast data not available")
    
    return {"city": request.city, "forecast": forecast}

@router.get("/advisory/{country_code}")
async def get_travel_advisory(country_code: str):
    """Get travel advisory for a country"""
    advisory = advisory_api.get_advisory(country_code)
    return advisory

@router.post("/currency/convert")
async def convert_currency(request: CurrencyConvertRequest):
    """Convert currency"""
    result = currency_api.convert_currency(
        request.amount, 
        request.from_currency, 
        request.to_currency
    )
    
    if result is None:
        raise HTTPException(status_code=400, detail="Currency conversion failed")
    
    return {
        "original": {"amount": request.amount, "currency": request.from_currency},
        "converted": {"amount": round(result, 2), "currency": request.to_currency}
    }

@router.post("/travel/enrich")
async def enrich_destination(
    destination: str,
    country_code: Optional[str] = None,
    start_date: Optional[str] = None,
    budget: Optional[float] = None,
    home_currency: str = "USD"
):
    """Enrich travel plan with real-time data (weather, advisory, etc.)"""
    enrichment = enrich_travel_plan(
        destination=destination,
        country_code=country_code,
        start_date=start_date,
        budget=budget,
        home_currency=home_currency
    )
    
    return {
        "destination": destination,
        "enrichment": enrichment
    }

# ============================================================================
# Enhanced Auth Endpoints (using database)
# ============================================================================

from pydantic import BaseModel, Field

class RegisterRequestDB(BaseModel):
    email: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$')
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)

class LoginRequestDB(BaseModel):
    email: str
    password: str

@router.post("/auth/register-db")
async def register_db(request: RegisterRequestDB):
    """Register new user with database persistence"""
    # Check if user exists
    existing = db.get_user_by_email(request.email)
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    
    # Hash password
    hashed_password = hash_password(request.password)
    
    # Create user
    user = db.create_user(
        email=request.email,
        username=request.username,
        hashed_password=hashed_password
    )
    
    if not user:
        raise HTTPException(status_code=500, detail="Failed to create user")
    
    # Create tokens
    access_token = create_access_token(data={"sub": user['id']})
    refresh_token = create_refresh_token(data={"sub": user['id']})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "user_id": user['id'],
            "email": user['email'],
            "username": user['username']
        }
    }

@router.post("/auth/login-db")
async def login_db(request: LoginRequestDB):
    """Login user with database"""
    user = db.get_user_by_email(request.email)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_password(request.password, user['hashed_password']):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.get('is_active', True):
        raise HTTPException(status_code=403, detail="Account is inactive")
    
    # Create tokens
    access_token = create_access_token(data={"sub": user['id']})
    refresh_token = create_refresh_token(data={"sub": user['id']})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "user_id": user['id'],
            "email": user['email'],
            "username": user['username']
        }
    }
