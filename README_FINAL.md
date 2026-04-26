# 🌍 Travel AI Agent Platform
## Your Intelligent Travel Companion

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An AI-powered travel agency platform with intelligent agents for trip planning, booking assistance, and 24/7 customer support. Built with modern architecture for scalability and exceptional user experience.

## ✨ Features

### 🤖 AI-Powered Core
- **Travel Planning Agent**: Generates personalized itineraries with AI
- **Travel Counsellor**: 24/7 conversational support with sentiment analysis
- **Emergency Detection**: Automatically identifies travel emergencies and provides resources
- **Smart Follow-ups**: Context-aware conversation suggestions

### 🗄️ Data Persistence
- **SQLite Database**: Persistent storage for users, trips, and conversations
- **Trip Management**: Create, track, and manage travel plans
- **Conversation History**: Full chat history with sentiment tracking
- **User Profiles**: Personalized user experience with trip statistics

### 🌐 Travel APIs Integration
- **Weather API**: Real-time weather and forecasts for destinations
- **Travel Advisories**: Country-specific safety information
- **Currency Converter**: Real-time exchange rates
- **Amadeus Integration**: Flight and hotel search (when configured)

### 🔐 Security & Compliance
- **JWT Authentication**: Secure token-based auth with refresh tokens
- **Rate Limiting**: Request throttling to prevent abuse
- **CSRF Protection**: Cross-site request forgery prevention
- **Consent System**: GDPR-compliant consent management
- **Security Headers**: CSP, HSTS, XSS protection

### 🚀 Production Ready
- **Horizontal Scaling**: Kubernetes-ready with HPA support
- **Docker Support**: Containerized deployment
- **Render Deployment**: One-click deployment configuration
- **Health Checks**: Comprehensive monitoring endpoints

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │   Web App    │  │  Mobile API  │  │  Chat Widget │           │
│  │  (index.html)│  │   (Future)   │  │   (Future)   │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Application                         │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐   │
│  │   Auth     │ │   Travel   │ │   Travel   │ │    API     │   │
│  │  Module    │ │  Planning  │ │ Counsellor │ │    Routes  │   │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘   │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐                │
│  │   Trip     │ │    User    │ │  External  │                │
│  │ Management │ │   Profile  │ │    APIs    │                │
│  └────────────┘ └────────────┘ └────────────┘                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                         Data Layer                               │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐                │
│  │  SQLite    │ │  In-Memory │ │  External  │                │
│  │  (Persist) │ │  (Session) │ │    APIs    │                │
│  └────────────┘ └────────────┘ └────────────┘                │
└─────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/Mahesh2023/travel-ai-agent.git
cd travel-ai-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### Access the Application

- **Web App**: http://localhost:8000/app
- **API Docs**: http://localhost:8000/docs (Swagger UI)
- **API Spec**: http://localhost:8000/redoc (ReDoc)
- **Health Check**: http://localhost:8000/health

## 📚 API Documentation

### Authentication Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login user |
| POST | `/api/auth/logout` | Logout user |
| GET | `/api/auth/me` | Get current user |
| POST | `/api/auth/refresh` | Refresh access token |
| POST | `/api/auth/register-db` | Register with database |
| POST | `/api/auth/login-db` | Login with database |

### Trip Management Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/trips` | Create a new trip |
| GET | `/api/trips` | List all trips |
| GET | `/api/trips/{trip_id}` | Get trip details |
| PUT | `/api/trips/{trip_id}` | Update trip |
| DELETE | `/api/trips/{trip_id}` | Delete trip |
| POST | `/api/trips/{trip_id}/activate` | Activate trip |
| POST | `/api/trips/{trip_id}/complete` | Complete trip |

### Travel Planning Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/travel/plan` | Generate travel plan |
| POST | `/api/travel/counsel` | Travel counselling chat |
| POST | `/api/travel/enrich` | Enrich with real-time data |

### Travel API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/weather` | Get weather for destination |
| POST | `/api/weather/forecast` | Get weather forecast |
| GET | `/api/advisory/{country_code}` | Get travel advisory |
| POST | `/api/currency/convert` | Convert currency |

### User Profile Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/profile` | Get user profile |
| PUT | `/api/profile` | Update profile |
| GET | `/api/profile/history` | Get conversation history |

### Legal/Compliance Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/legal/consent` | Grant consent |
| POST | `/api/legal/consent/withdraw` | Withdraw consent |
| GET | `/api/legal/notice` | Legal notice |
| GET | `/api/legal/privacy-policy` | Privacy policy |

## 🔧 Configuration

### Environment Variables

```env
# Required
TRAVEL_LLM_API_KEY=your_openai_or_grok_api_key
TRAVEL_CONSENT_SECRET=your_consent_signing_secret

# Optional - Travel APIs
OPENWEATHER_API_KEY=your_openweather_key
AMADEUS_API_KEY=your_amadeus_key
AMADEUS_SECRET=your_amadeus_secret

# Optional - Application
TELOSCOPY_ENV=development
RATE_LIMIT_REQUESTS=60
RATE_LIMIT_WINDOW=60
TRAVEL_CORS_ORIGINS=*
```

## 🐳 Docker Deployment

```bash
# Build image
docker build -t travel-ai-agent:latest .

# Run container
docker run -p 8000:8000 \
  -e TRAVEL_LLM_API_KEY=your_key \
  -e TRAVEL_CONSENT_SECRET=your_secret \
  travel-ai-agent:latest
```

## ☸️ Kubernetes Deployment

```bash
# Apply configurations
kubectl apply -f k8s-simple/namespace.yaml
kubectl apply -f k8s-simple/secrets.yaml
kubectl apply -f k8s-simple/configmap.yaml
kubectl apply -f k8s-simple/travel-agent.yaml
kubectl apply -f k8s-simple/hpa.yaml

# Check status
kubectl get pods -n travel-agent-simple
kubectl get hpa -n travel-agent-simple
```

## 🌐 Render Deployment

The project includes `render.yaml` for one-click deployment on Render:

1. Push to GitHub
2. Create new Web Service on Render
3. Connect your repository
4. Render will auto-deploy using the configuration

## 📁 Project Structure

```
travel-ai-agent/
├── app.py                 # Main FastAPI application
├── api_routes.py          # Enhanced API routes
├── database.py            # SQLite database module
├── auth_simple.py         # Authentication module
├── travel_apis.py         # External API integrations
├── voice.py              # Voice assistant module
├── index.html            # Frontend application
├── requirements.txt      # Python dependencies
├── Dockerfile           # Docker configuration
├── render.yaml          # Render deployment config
├── k8s-simple/          # Kubernetes manifests
│   ├── namespace.yaml
│   ├── secrets.yaml
│   ├── configmap.yaml
│   ├── travel-agent.yaml
│   └── hpa.yaml
└── docs/                # Documentation
    ├── ARCHITECTURE.md
    ├── COMPLETE_IMPLEMENTATION.md
    └── DEPLOYMENT.md
```

## 🧪 Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test
pytest tests/test_api.py
```

## 🎯 Key Features Explained

### 1. AI Travel Planning
The system uses LLM (Large Language Model) integration to generate personalized travel itineraries. When an LLM is unavailable, it falls back to intelligent templates.

### 2. Emergency Detection
The system automatically detects travel emergencies (lost passport, medical issues, etc.) and provides immediate resources and guidance.

### 3. Sentiment Analysis
Analyzes user messages to detect emotional state (positive, negative, emergency) and adapts responses accordingly.

### 4. Database Persistence
All user data, trips, and conversations are stored in SQLite for persistence. The database schema includes:
- Users
- Sessions
- Trips
- Conversations
- Bookings (future)

### 5. Security
Following industry best practices:
- JWT authentication with refresh tokens
- bcrypt password hashing
- Rate limiting per IP
- CSRF protection
- Security headers
- Consent management

## 📈 Performance & Scaling

### Capacity Planning

**For 1,000 Users:**
- 1-2 instances
- 512MB RAM per instance
- SQLite database

**For 100,000 Users:**
- 10-20 instances
- PostgreSQL database (see k8s-simple/postgres.yaml)
- Redis for caching/sessions
- CDN for static assets

### Horizontal Pod Autoscaler

The Kubernetes HPA configuration automatically scales based on CPU/memory usage:
- Minimum: 3 replicas
- Maximum: 100 replicas
- Target CPU: 70%

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- FastAPI for the excellent web framework
- OpenAI/Grok for LLM capabilities
- Amadeus for travel API integration
- Booking.com, Expedia, and Airbnb for architectural inspiration

## 📞 Support

For support, email support@travel-ai-agent.com or join our Slack channel.

---

Built with ❤️ by Mahesh Bhat
