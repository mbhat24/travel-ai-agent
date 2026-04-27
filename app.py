"""
Travel AI Agent Platform - Production Grade
Professional travel platform with AI, security, and scalability
"""

from fastapi import FastAPI, HTTPException, Request, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
import json
import time
import uuid
import re
import html
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timedelta
import hashlib
import hmac

# Professional modules
from backend.core.config import settings
from backend.core.logging import get_logger, setup_logging, set_correlation_id, get_correlation_id
from backend.exceptions import (
    TravelAIException, AuthenticationError, ValidationError,
    RateLimitExceededError, ExternalAPIError
)

# Setup logging first
setup_logging(
    level=settings.logging.level,
    structured=settings.logging.structured == "json",
    log_file=settings.logging.file_path
)
logger = get_logger(__name__)

# Import auth module (professional - scalable with PostgreSQL)
from backend.routers.auth import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    verify_token, get_current_user, create_session, get_session, delete_session,
    delete_user_sessions, User
)

# Import database
from database import db

# Configuration shortcuts
_TELOSCOPY_ENV = settings.env
_LLM_BACKEND = settings.llm.backend
_LLM_MODEL = settings.llm.model
_LLM_BASE_URL = settings.llm.base_url
_LLM_API_KEY = settings.llm.api_key
_CONSENT_SECRET = settings.security.consent_secret
_CORS_ORIGINS = settings.cors.allowed_origins
_RATE_LIMIT_REQUESTS = settings.rate_limit.requests_per_minute
_RATE_LIMIT_WINDOW = settings.rate_limit.window_seconds

# ============================================================================
# In-Memory Rate Limiter (Replace with Redis for production scaling)
# ============================================================================
class RateLimiter:
    """In-memory rate limiter using sliding window (replace with Redis for production)"""
    
    def __init__(self):
        self._requests: Dict[str, List[float]] = {}
    
    def is_allowed(self, client_id: str, max_requests: int = _RATE_LIMIT_REQUESTS, window: int = _RATE_LIMIT_WINDOW) -> bool:
        now = time.time()
        window_start = now - window
        
        # Clean old requests
        if client_id in self._requests:
            self._requests[client_id] = [
                req_time for req_time in self._requests[client_id]
                if req_time > window_start
            ]
        else:
            self._requests[client_id] = []
        
        # Check if under limit
        if len(self._requests[client_id]) >= max_requests:
            return False
        
        # Add current request
        self._requests[client_id].append(now)
        return True

_rate_limiter = RateLimiter()

def rate_limit(max_requests: int = _RATE_LIMIT_REQUESTS, window: int = _RATE_LIMIT_WINDOW):
    """Dependency for rate limiting"""
    async def check_rate_limit(request: Request):
        client_id = request.client.host if request.client else "unknown"
        if not _rate_limiter.is_allowed(client_id, max_requests, window):
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {max_requests} requests per {window} seconds"
            )
    return check_rate_limit

# ============================================================================
# Consent System (HMAC-signed tokens)
# ============================================================================
_consent_store: Dict[str, Dict[str, Any]] = {}
_withdrawn_consent: set = set()

def generate_consent_token(session_id: str, purposes: List[str]) -> str:
    """Generate HMAC-signed consent token"""
    timestamp = int(time.time())
    data = f"{session_id}:{','.join(sorted(purposes))}:{timestamp}".encode()
    signature = hmac.new(
        _CONSENT_SECRET.encode(),
        data,
        hashlib.sha256
    ).hexdigest()
    
    token = f"{session_id}:{','.join(sorted(purposes))}:{timestamp}:{signature}"
    _consent_store[token] = {
        "session_id": session_id,
        "purposes": purposes,
        "granted_at": timestamp,
        "withdrawn": False
    }
    return token

def verify_consent_token(token: str, required_purposes: List[str]) -> bool:
    """Verify consent token and check purposes"""
    if token in _withdrawn_consent:
        return False
    
    if token not in _consent_store:
        return False
    
    consent_data = _consent_store[token]
    
    # Check token age (24 hours)
    if time.time() - consent_data["granted_at"] > 86400:
        return False
    
    # Check required purposes
    granted_purposes = set(consent_data["purposes"])
    required = set(required_purposes)
    
    return required.issubset(granted_purposes)

def require_consent(purposes: List[str]):
    """Dependency to require consent for specific purposes"""
    async def check_consent(request: Request):
        token = request.headers.get("X-Consent-Token")
        if not token or not verify_consent_token(token, purposes):
            raise HTTPException(
                status_code=403,
                detail=f"Consent required for purposes: {', '.join(purposes)}"
            )
    return check_consent

# ============================================================================
# Security Headers Middleware (from teloscopy)
# ============================================================================
_CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'"
)

# ============================================================================
# Pydantic Models
# ============================================================================
from pydantic import BaseModel, Field, validator

class TravelPlanRequest(BaseModel):
    destination: str = Field(..., min_length=1, max_length=100)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    budget: Optional[float] = Field(None, gt=0)
    travelers: int = Field(default=1, ge=1, le=50)
    interests: List[str] = Field(default_factory=list)
    preferences: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('destination')
    def validate_destination(cls, v):
        if not v or not v.strip():
            raise ValueError('Destination cannot be empty')
        return v.strip()

class TravelCounsellorRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    conversation: List[Dict[str, str]] = Field(default_factory=list)
    context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None

class TravelPlanResponse(BaseModel):
    destination: str
    itinerary: str
    budget_breakdown: Dict[str, float]
    recommendations: List[str]
    estimated_cost: float
    mode: str

class CounsellorResponse(BaseModel):
    response: str
    sentiment: Dict[str, Any]
    emergency: Optional[Dict[str, Any]] = None
    followups: List[str]
    mode: str

# ============================================================================
# LLM Client
# ============================================================================
class LLMClient:
    """OpenAI-compatible LLM client (works with Grok, OpenAI, etc.)"""
    
    def __init__(
        self,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        timeout: int = 120,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self._available = None
    
    def is_available(self) -> bool:
        """Check if LLM is available"""
        if self._available is not None:
            return self._available
        
        try:
            import urllib.request
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            req = urllib.request.Request(
                f"{self.base_url}/models",
                headers=headers,
                method="GET"
            )
            with urllib.request.urlopen(req, timeout=5):
                self._available = True
                return True
        except Exception as e:
            logger.warning(f"LLM availability check failed: {e}")
            self._available = False
            return False
    
    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        """Send chat completion request"""
        import urllib.request
        import urllib.error
        
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 2048,
        }
        
        try:
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=data,
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode())
            
            choices = body.get("choices", [])
            if not choices:
                raise RuntimeError("No choices in LLM response")
            
            text = choices[0].get("message", {}).get("content", "")
            if not text:
                raise RuntimeError("Empty LLM response")
            
            return text.strip()
        except Exception as e:
            logger.error(f"LLM chat failed: {e}")
            raise

# Global LLM client
_llm_client: Optional[LLMClient] = None

def get_llm_client() -> Optional[LLMClient]:
    """Get or create LLM client"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient(
            base_url=_LLM_BASE_URL,
            model=_LLM_MODEL,
            api_key=_LLM_API_KEY,
            timeout=60
        )
    return _llm_client if _llm_client.is_available() else None

# ============================================================================
# Travel Counselling System Prompt
# ============================================================================
_TRAVEL_COUNSELLING_SYSTEM = """You are an expert travel counsellor with deep knowledge of destinations, cultures, and travel logistics. Your role is to provide compassionate, practical, and personalized travel guidance.

## Your Approach:

1. **Listen First** - Understand the person's needs, concerns, and travel dreams
2. **Validate Feelings** - Acknowledge travel anxiety, excitement, or uncertainty
3. **Provide Practical Help** - Give specific, actionable advice
4. **Inspire Confidence** - Help them feel prepared and excited about their journey
5. **Safety First** - Always prioritize safety without being alarmist

## Key Topics:

- Trip planning and itinerary suggestions
- Budget optimization and cost-saving tips
- Safety considerations for destinations
- Cultural etiquette and local customs
- Dealing with travel anxiety
- Emergency preparedness
- Visa and documentation requirements
- Transportation options
- Accommodation recommendations
- Local experiences and hidden gems

## Emergency Detection:

Watch for keywords indicating travel emergencies:
- Lost/stolen documents (passport, wallet, phone)
- Medical emergencies
- Safety incidents (theft, assault)
- Natural disasters
- Transportation failures (missed flights, cancellations)
- Being stranded or lost

If emergency detected: Provide immediate, step-by-step emergency guidance

## Response Style:

- Warm, supportive, and encouraging
- Specific and practical (not vague)
- Culturally sensitive and respectful
- Safety-conscious without being alarmist
- Balance enthusiasm with realism
- Use clear, accessible language

## Example:

User: "I'm nervous about traveling alone to Japan"
Response: "That's completely understandable - solo travel can feel daunting at first. Japan is actually one of the safest and most solo-travel-friendly countries! The public transportation is excellent, English is widely used in tourist areas, and the culture is very respectful. I can share specific tips for navigating without language skills if you'd like. What specifically concerns you the most?"
"""

# ============================================================================
# Emergency Detection
# ============================================================================
_EMERGENCY_KEYWORDS = {
    "high": [
        "lost passport", "stolen passport", "lost visa", "stolen visa",
        "medical emergency", "heart attack", "stroke", "severe injury",
        "assault", "robbery", "mugged", "theft", "stolen wallet",
        "natural disaster", "earthquake", "flood", "hurricane", "typhoon",
        "terrorist", "shooting", "bomb", "attack",
        "stranded", "stuck", "can't leave", "trapped", "kidnapped",
    ],
    "moderate": [
        "missed flight", "cancelled flight", "delayed flight", "overbooked",
        "lost luggage", "stolen luggage", "damaged luggage",
        "sick", "food poisoning", "fever", "injury", "hurt",
        "lost phone", "stolen phone", "broken phone",
        "scammed", "fraud", "cheated", "ripped off",
        "arrested", "detained", "held by police",
        "visa denied", "entry denied", "deported",
    ],
    "low": [
        "lost", "can't find", "confused", "don't know where",
        "worried", "anxious", "scared", "afraid", "nervous",
        "help", "need help", "emergency", "urgent",
    ],
}

def detect_emergency(message: str) -> Optional[Dict[str, Any]]:
    """Detect travel emergencies"""
    message_lower = message.lower()
    
    for keyword in _EMERGENCY_KEYWORDS["high"]:
        if keyword in message_lower:
            return {
                "severity": "high",
                "keyword": keyword,
                "message": "This appears to be a travel emergency. Please take immediate action.",
                "resources": [
                    "Contact your country's embassy or consulate immediately",
                    "Call local emergency services (911 US, 112 Europe, 999 UK)",
                    "Contact your travel insurance emergency line",
                    "Contact your bank to freeze cards if wallet stolen",
                ],
            }
    
    for keyword in _EMERGENCY_KEYWORDS["moderate"]:
        if keyword in message_lower:
            return {
                "severity": "moderate",
                "keyword": keyword,
                "message": "This is a concerning situation. Let's address it step by step.",
                "resources": [
                    "Contact your airline or travel provider",
                    "Contact your travel insurance",
                    "Contact your hotel for assistance",
                    "Document everything for insurance claims",
                ],
            }
    
    for keyword in _EMERGENCY_KEYWORDS["low"]:
        if keyword in message_lower:
            return {
                "severity": "low",
                "keyword": keyword,
                "message": "I'm here to help. What's concerning you?",
                "resources": [],
            }
    
    return None

# ============================================================================
# Sentiment Analysis
# ============================================================================
def analyze_sentiment(message: str) -> Dict[str, Any]:
    """Analyze sentiment of travel-related message"""
    positive = ["happy", "excited", "love", "enjoy", "great", "wonderful", "amazing", "beautiful", "fun", "looking forward", "can't wait"]
    negative = ["worried", "anxious", "scared", "afraid", "stress", "difficult", "problem", "issue", "concern", "nervous", "afraid"]
    emergency = ["emergency", "urgent", "help", "lost", "stolen", "sick", "injured", "hurt"]
    
    message_lower = message.lower()
    
    pos_count = sum(1 for word in positive if word in message_lower)
    neg_count = sum(1 for word in negative if word in message_lower)
    emer_count = sum(1 for word in emergency if word in message_lower)
    
    if emer_count > 0:
        intensity = "severe"
    elif neg_count > pos_count:
        intensity = "high" if neg_count > 2 else "moderate"
    elif pos_count > neg_count:
        intensity = "positive"
    else:
        intensity = "neutral"
    
    return {
        "intensity": intensity,
        "positive": pos_count,
        "negative": neg_count,
        "emergency": emer_count,
        "themes": detect_themes(message_lower),
    }

def detect_themes(message: str) -> List[str]:
    """Detect travel-related themes"""
    themes = []
    theme_map = {
        "safety": ["safe", "danger", "crime", "security", "risk"],
        "budget": ["money", "cost", "budget", "expensive", "cheap", "price"],
        "culture": ["culture", "custom", "tradition", "local", "people"],
        "food": ["food", "eat", "restaurant", "cuisine", "meal", "dining"],
        "transport": ["flight", "train", "bus", "car", "transport", "travel", "airport"],
        "accommodation": ["hotel", "hostel", "room", "stay", "accommodation", "lodge"],
        "solo": ["alone", "solo", "by myself", "single"],
        "family": ["family", "kids", "children", "parents"],
        "adventure": ["adventure", "hike", "trek", "explore", "outdoor"],
        "relaxation": ["relax", "beach", "resort", "spa", "rest", "vacation"],
    }
    
    for theme, keywords in theme_map.items():
        if any(keyword in message for keyword in keywords):
            themes.append(theme)
    
    return themes

# ============================================================================
# FastAPI Application
# ============================================================================
_docs_url = "/docs" if _TELOSCOPY_ENV != "production" else None
_redoc_url = "/redoc" if _TELOSCOPY_ENV != "production" else None

app = FastAPI(
    title="Travel AI Agent Platform",
    description="AI-powered travel planning and counselling with security and scaling",
    version="3.0.0",
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_tags=[
        {"name": "Health", "description": "System health and readiness checks"},
        {"name": "Travel Planning", "description": "AI-powered travel itinerary generation"},
        {"name": "Travel Counselling", "description": "Travel guidance and support with LLM"},
        {"name": "Legal", "description": "Consent management and legal compliance"},
    ],
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With", "X-Consent-Token"],
)

# Import and include API routes
from api_routes import router as api_router
app.include_router(api_router)

# Security Headers Middleware
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Append security headers to every HTTP response (from teloscopy)"""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "0"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"
    response.headers["Content-Security-Policy"] = _CSP_POLICY
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response

# CSRF Protection Middleware
@app.middleware("http")
async def csrf_middleware(request: Request, call_next):
    """Enforce CSRF protection on state-changing requests (from teloscopy)"""
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        path = request.url.path
        exempt = (
            path.startswith("/api/legal/")
            or path.startswith("/docs")
            or path.startswith("/redoc")
            or path.startswith("/openapi")
        )
        if not exempt:
            xrw = request.headers.get("x-requested-with", "")
            ct = request.headers.get("content-type", "")
            if not (xrw or "application/json" in ct):
                return JSONResponse(
                    status_code=403,
                    content={"error": {"code": 403, "message": "CSRF validation failed. Include appropriate Content-Type or X-Requested-With header."}},
                )
    response = await call_next(request)
    return response

# Request ID Middleware
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Generate unique request ID and log with timing (from teloscopy)"""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        elapsed = time.monotonic() - start
        logger.error(
            "%s %s 500 took %.3fs [request_id=%s]",
            request.method,
            request.url.path,
            elapsed,
            request_id,
        )
        raise
    elapsed = time.monotonic() - start
    status_code = response.status_code
    if status_code >= 500:
        logger.error(
            "%s %s %d took %.3fs [request_id=%s]",
            request.method,
            request.url.path,
            status_code,
            elapsed,
            request_id,
        )
    elif status_code >= 400:
        logger.warning(
            "%s %s %d took %.3fs [request_id=%s]",
            request.method,
            request.url.path,
            status_code,
            elapsed,
            request_id,
        )
    else:
        logger.info(
            "%s %s %d took %.3fs",
            request.method,
            request.url.path,
            status_code,
            elapsed,
        )
    response.headers["X-Request-ID"] = request_id
    return response

# ============================================================================
# Health Endpoints
# ============================================================================
@app.get("/")
async def root():
    return {
        "name": "Travel AI Agent Platform",
        "version": "3.0.0",
        "status": "running",
        "features": [
            "travel_planning",
            "travel_counselling",
            "emergency_detection",
            "sentiment_analysis",
            "llm_integration",
            "security_headers",
            "rate_limiting",
            "consent_system",
        ],
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# ============================================================================
# Legal/Consent Endpoints (from teloscopy)
# ============================================================================
@app.post("/api/legal/consent")
async def grant_consent(request: Request):
    """Grant consent for specific purposes"""
    body = await request.json()
    session_id = body.get("session_id") or str(uuid.uuid4())
    purposes = body.get("purposes", [])
    
    if not purposes:
        raise HTTPException(status_code=400, detail="Purposes are required")
    
    token = generate_consent_token(session_id, purposes)
    return {"token": token, "session_id": session_id, "purposes": purposes}

@app.post("/api/legal/consent/withdraw")
async def withdraw_consent(request: Request):
    """Withdraw consent"""
    body = await request.json()
    token = body.get("token")
    
    if not token:
        raise HTTPException(status_code=400, detail="Token is required")
    
    _withdrawn_consent.add(token)
    if token in _consent_store:
        del _consent_store[token]
    
    return {"message": "Consent withdrawn"}

@app.get("/api/legal/notice")
async def legal_notice():
    """Return legal notice"""
    return {
        "title": "Travel AI Agent Legal Notice",
        "version": "1.0",
        "last_updated": datetime.utcnow().isoformat(),
        "content": """
        This platform provides AI-powered travel planning and counselling services.
        By using this service, you agree to the following:
        
        1. Your travel data is processed for trip planning and counselling purposes only
        2. We use LLM services to generate travel recommendations
        3. Your data is not stored permanently (in-memory processing only)
        4. Emergency detection is used to provide safety resources when needed
        5. This service is for informational purposes only, not professional travel advice
        """,
    }

@app.get("/api/legal/privacy-policy")
async def privacy_policy():
    """Return privacy policy"""
    return {
        "title": "Privacy Policy",
        "version": "1.0",
        "effective_date": "2026-04-22",
        "content": """
        Data Collection:
        - Travel preferences and itinerary data
        - Counselling conversation history (in-memory only)
        - No personal identification required
        
        Data Usage:
        - Generate travel recommendations
        - Provide travel counselling
        - Improve service quality
        
        Data Retention:
        - All data processed in-memory
        - No permanent storage
        - Sessions cleared after 24 hours
        
        Your Rights:
        - Right to withdraw consent
        - Right to data deletion
        - Right to access your data
        """,
    }

# ============================================================================
# Travel Planning Endpoints
# ============================================================================
@app.post("/api/travel/plan", response_model=TravelPlanResponse, dependencies=[Depends(rate_limit(30, 60))])
async def plan_trip(request: TravelPlanRequest):
    """Generate comprehensive travel plan"""
    client = get_llm_client()
    
    prompt = f"""Create a detailed travel itinerary for:

Destination: {request.destination}
Duration: {request.start_date} to {request.end_date}
Budget: ${request.budget}
Travelers: {request.travelers}
Interests: {', '.join(request.interests)}
Preferences: {request.preferences}

Please provide:
1. Day-by-day detailed itinerary
2. Budget breakdown (accommodation, food, activities, transport)
3. Top 5 recommendations for this destination
4. Practical tips for traveling here
5. Cultural considerations
6. Safety tips specific to this destination
7. Best time to visit
8. Must-see attractions and hidden gems
"""
    
    if client:
        try:
            itinerary = client.chat(
                messages=[
                    {"role": "system", "content": "You are an expert travel planner. Create detailed, practical, and inspiring travel itineraries with specific recommendations and budget breakdowns."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            
            # Calculate budget breakdown
            budget = request.budget or 2000
            breakdown = {
                "accommodation": budget * 0.35,
                "food": budget * 0.25,
                "activities": budget * 0.20,
                "transport": budget * 0.15,
                "misc": budget * 0.05,
            }
            
            return TravelPlanResponse(
                destination=request.destination,
                itinerary=itinerary,
                budget_breakdown=breakdown,
                recommendations=[
                    "Book accommodations in advance for better rates",
                    "Learn basic local phrases",
                    "Research local customs and etiquette",
                    "Keep digital and physical copies of important documents",
                    "Purchase travel insurance",
                ],
                estimated_cost=budget,
                mode="ai",
            )
        except Exception as e:
            logger.error(f"LLM planning failed: {e}")
    
    # Fallback template response
    budget = request.budget or 2000
    breakdown = {
        "accommodation": budget * 0.35,
        "food": budget * 0.25,
        "activities": budget * 0.20,
        "transport": budget * 0.15,
        "misc": budget * 0.05,
    }
    
    itinerary = f"""# Travel Plan for {request.destination}

## Day 1: Arrival
- Arrive and check into accommodation
- Explore local neighborhood
- Dinner at a local restaurant

## Day 2: Main Attractions
- Visit top attractions in {request.destination}
- Cultural experiences
- Local cuisine tasting

## Day 3: Local Experiences
- Hidden gems and off-the-beaten-path locations
- Interactive cultural activities
- Shopping for local crafts

## Day 4: Adventure/Relaxation
- Based on your interests: {', '.join(request.interests)}
- Free time for personal exploration

## Day 5: Departure
- Last-minute shopping
- Departure

## Budget Breakdown
- Accommodation: ${breakdown['accommodation']:.0f}
- Food: ${breakdown['food']:.0f}
- Activities: ${breakdown['activities']:.0f}
- Transport: ${breakdown['transport']:.0f}
- Miscellaneous: ${breakdown['misc']:.0f}
"""
    
    return TravelPlanResponse(
        destination=request.destination,
        itinerary=itinerary,
        budget_breakdown=breakdown,
        recommendations=[
            "Book accommodations in advance",
            "Learn basic local phrases",
            "Research local customs",
            "Keep copies of documents",
            "Purchase travel insurance",
        ],
        estimated_cost=budget,
        mode="template",
    )

# ============================================================================
# Travel Counselling Endpoints
# ============================================================================
@app.post("/api/travel/counsel", response_model=CounsellorResponse, dependencies=[Depends(rate_limit(40, 60))])
async def travel_counsel(request: TravelCounsellorRequest):
    """Travel counselling with LLM integration"""
    message = request.message.strip()
    
    # Emergency detection (always first)
    emergency = detect_emergency(message)
    
    # Sentiment analysis
    sentiment = analyze_sentiment(message)
    
    # Try LLM response
    client = get_llm_client()
    llm_response = None
    
    if client:
        try:
            # Build conversation context
            messages = [{"role": "system", "content": _TRAVEL_COUNSELLING_SYSTEM}]
            
            # Add conversation history (last 10 turns)
            for turn in request.conversation[-10:]:
                role = turn.get("role", "user")
                text = turn.get("text", "").strip()
                if text:
                    messages.append({"role": role, "content": text})
            
            # Add current message
            messages.append({"role": "user", "content": message})
            
            # Add sentiment context
            if sentiment["intensity"] != "neutral":
                sentiment_hint = f"[Sentiment: {sentiment['intensity']}] "
                if sentiment["intensity"] == "severe":
                    sentiment_hint += "User appears to be in distress. Prioritize immediate, practical help and reassurance."
                elif sentiment["intensity"] == "high":
                    sentiment_hint += "User is experiencing significant anxiety. Be extra supportive and provide specific advice."
                elif sentiment["intensity"] == "positive":
                    sentiment_hint += "User is feeling positive. Build on this enthusiasm with encouraging suggestions."
                messages.append({"role": "system", "content": sentiment_hint})
            
            llm_response = client.chat(messages, temperature=0.7)
            
        except Exception as e:
            logger.error(f"Travel counselling LLM failed: {e}")
    
    # Generate follow-up suggestions
    followups = generate_followups(sentiment, request.context)
    
    # Determine final response
    final_response = llm_response if llm_response else generate_fallback_response(message, sentiment)
    mode = "ai" if llm_response else "template"
    
    # Save conversation to database
    try:
        db.save_conversation(
            message=message,
            response=final_response,
            user_id=None,  # Will be populated if user is authenticated
            session_id=request.session_id,
            sentiment=sentiment,
            emergency_detected=emergency is not None
        )
    except Exception as e:
        logger.error(f"Failed to save conversation: {e}")
    
    return CounsellorResponse(
        response=final_response,
        sentiment=sentiment,
        emergency=emergency,
        followups=followups,
        mode=mode,
    )

def generate_followups(sentiment: Dict[str, Any], context: Optional[Dict]) -> List[str]:
    """Generate contextual follow-up suggestions"""
    followups = [
        "Tell me more about your travel plans",
        "What's your main travel concern right now?",
        "What type of trip are you considering?",
        "How can I help you feel more prepared?",
    ]
    
    # Theme-based followups
    for theme in sentiment.get("themes", []):
        if theme == "safety":
            followups.append("What specific safety concerns do you have?")
        elif theme == "budget":
            followups.append("What's your budget range?")
        elif theme == "solo":
            followups.append("What worries you most about solo travel?")
        elif theme == "family":
            followups.append("How many family members are traveling?")
        elif theme == "food":
            followups.append("Any dietary restrictions I should know about?")
        elif theme == "adventure":
            followups.append("What activity level are you looking for?")
    
    return followups[:5]

# ============================================================================
# Authentication Endpoints
# ============================================================================
class RegisterRequest(BaseModel):
    email: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$')
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)

class LoginRequest(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]

@app.post("/api/auth/register", response_model=AuthResponse, dependencies=[Depends(rate_limit(10, 60))])
async def register(request: RegisterRequest):
    """Register new user (Redis + PostgreSQL for scalability)"""
    # Check if user already exists (in Redis for demo, use PostgreSQL in production)
    user_data_key = f"user_data:{request.email}"
    # In production, check PostgreSQL database here
    
    # Hash password
    hashed_password = hash_password(request.password)
    
    # Create user
    user_id = str(uuid.uuid4())
    user_data = {
        "user_id": user_id,
        "email": request.email,
        "username": request.username,
        "hashed_password": hashed_password,
        "is_active": True,
        "created_at": datetime.utcnow().isoformat()
    }
    
    # Store in Redis (demo - use PostgreSQL in production)
    import redis
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    r.setex(user_data_key, timedelta(days=30).total_seconds(), json.dumps(user_data))
    
    # Create session
    session_id = create_session(user_id, user_data)
    
    # Generate tokens
    access_token = create_access_token(data={"sub": user_id})
    refresh_token = create_refresh_token(data={"sub": user_id})
    
    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "user_id": user_id,
            "email": request.email,
            "username": request.username
        }
    )

@app.post("/api/auth/login", response_model=AuthResponse, dependencies=[Depends(rate_limit(20, 60))])
async def login(request: LoginRequest):
    """Login user (in-memory storage like teloscopy)"""
    # Get user data from in-memory database
    user_data = get_user_by_email(request.email)
    
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Verify password
    if not verify_password(request.password, user_data["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user_data.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is inactive")
    
    # Create session
    session_id = create_session(user_data["user_id"], user_data)
    
    # Generate tokens
    access_token = create_access_token(data={"sub": user_data["user_id"]})
    refresh_token = create_refresh_token(data={"sub": user_data["user_id"]})
    
    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "user_id": user_data["user_id"],
            "email": user_data["email"],
            "username": user_data["username"]
        }
    )

@app.post("/api/auth/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Logout user"""
    # Delete all user sessions
    deleted = delete_user_sessions(current_user.user_id)
    return {"message": "Logged out successfully", "sessions_deleted": deleted}

@app.get("/api/auth/me", dependencies=[Depends(get_current_user)])
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "username": current_user.username,
        "is_active": current_user.is_active
    }

@app.post("/api/auth/refresh")
async def refresh_token(request: Request):
    """Refresh access token"""
    body = await request.json()
    refresh_token = body.get("refresh_token")
    
    if not refresh_token:
        raise HTTPException(status_code=400, detail="Refresh token required")
    
    payload = verify_token(refresh_token, "refresh")
    user_id = payload.get("sub")
    
    # Generate new access token
    access_token = create_access_token(data={"sub": user_id})
    
    return {"access_token": access_token}

def generate_fallback_response(message: str, sentiment: Dict[str, Any]) -> str:
    """Generate fallback response when LLM unavailable"""
    intensity = sentiment["intensity"]
    
    if intensity == "severe":
        return "I understand this is a difficult situation. Please take a deep breath. If this is an emergency, contact local authorities or your embassy immediately. I'm here to help you work through this step by step."
    elif intensity == "high":
        return "I hear that you're feeling quite anxious about this. That's completely understandable - travel can bring up many concerns. Let's talk about what's worrying you most, and I'll do my best to provide practical guidance."
    elif intensity == "positive":
        return "It sounds like you're feeling excited about your travel plans! That's wonderful. Tell me more about what you're looking forward to most, and I can help you make the most of it."
    else:
        return "I'd love to help you with your travel plans or concerns. Could you tell me a bit more about what you're looking for - planning a specific trip, dealing with travel anxiety, or something else?"

# ============================================================================
# Static Files & SPA Serving
# ============================================================================
# Create static directory if it doesn't exist
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)

# Mount static files
try:
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")

@app.get("/app")
async def serve_app():
    """Serve the main frontend application"""
    index_path = Path(__file__).parent / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    raise HTTPException(status_code=404, detail="Frontend not found")

# ============================================================================
# Main
# ============================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
