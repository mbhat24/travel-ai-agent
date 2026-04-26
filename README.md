# 🌍 Travel AI Agent Platform

**Production-ready AI-powered travel platform with intelligent trip planning, booking assistance, and 24/7 customer support.**

> 📚 **For complete documentation, see [README_FINAL.md](README_FINAL.md)**
> 📊 **For project summary, see [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)**

---

## ✨ Quick Start

### Prerequisites
- Python 3.11+
- pip

### Installation & Run

```bash
# Install dependencies
pip install -r requirements.txt

# Start the application
python start.py
# OR
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### Access the App

- 🌐 **Web App**: http://localhost:8000/app
- 📖 **API Docs**: http://localhost:8000/docs
- ✅ **Health**: http://localhost:8000/health

---

## 🚀 What's Included

### 🤖 AI Features
- **Travel Planning**: AI-generated itineraries with LLM + fallback templates
- **Travel Counsellor**: 24/7 conversational support with sentiment analysis
- **Emergency Detection**: Automatic detection with resource provision

### 🗄️ Data & Persistence
- **SQLite Database**: Full persistence for users, trips, conversations
- **Trip Management**: CRUD operations, status tracking, history
- **User Profiles**: Personalized experience with statistics

### 🌐 External Integrations
- **Weather API**: Real-time weather & forecasts
- **Travel Advisories**: Country-specific safety info
- **Currency Converter**: Real-time exchange rates
- **Amadeus**: Flight & hotel search (when configured)

### 🔐 Security
- JWT Authentication with refresh tokens
- Rate limiting & CSRF protection
- Security headers & consent management
- bcrypt password hashing

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [README_FINAL.md](README_FINAL.md) | Complete documentation & API reference |
| [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) | Summary of all enhancements |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture details |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Deployment guides |

---

## 🐳 Docker Deployment

```bash
docker build -t travel-ai-agent .
docker run -p 8000:8000 -e TRAVEL_LLM_API_KEY=your_key travel-ai-agent
```

## ☸️ Kubernetes Deployment

```bash
kubectl apply -f k8s-simple/
```

---

## 📊 Stats

- **30+ API Endpoints**
- **5 Database Tables**
- **4 External API Integrations**
- **Production-Ready Security**

---

## 📝 License

MIT License - See LICENSE file

Built with ❤️ by Mahesh Bhat
