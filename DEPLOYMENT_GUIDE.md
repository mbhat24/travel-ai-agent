# Travel AI Agent - Deployment Guide

## Two Deployment Options

### Option 1: Simple Deployment (Like Teloscopy)
**Best for:** Development, testing, small scale (100-1000 users)

**Branch:** `main`
**Deployment:** Render single service
**Database:** In-memory only
**Complexity:** Low

**Limitations:**
- **Max Users:** ~1,000 concurrent users
- **Memory:** Limited to instance RAM (512MB-1GB on Render free tier)
- **Data Persistence:** Data lost on every restart/deployment
- **Scaling:** Single instance only (no horizontal scaling)
- **Rate Limiting:** Per-instance only
- **Session Management:** Lost on restart

**What breaks at scale:**
- Memory overflow with 1M users' sessions
- Single instance can't handle 1M concurrent requests
- All user data lost on restart
- Rate limiting fails across instances
- Sessions don't persist across restarts

**Deployment:**
```bash
# Deploy to Render (simple)
# render.yaml is configured for single service
# Set TRAVEL_LLM_API_KEY environment variable
# Click deploy on Render dashboard
```

---

### Option 2: Scalable Deployment (Millions of Users)
**Best for:** Production, large scale (1M+ users)

**Branch:** `scalable`
**Deployment:** Kubernetes with HPA
**Database:** Redis + PostgreSQL
**Complexity:** High

**Features:**
- **Max Users:** 1M+ concurrent users
- **Memory:** Distributed across instances
- **Data Persistence:** PostgreSQL for permanent storage
- **Scaling:** Horizontal Pod Autoscaler (3-100 replicas)
- **Rate Limiting:** Redis-backed distributed rate limiting
- **Session Management:** Redis-backed sessions

**Deployment:**
```bash
# Build and push Docker image
docker build -t ghcr.io/mahesh2023/travel-agent:latest .
docker push ghcr.io/mahesh2023/travel-agent:latest

# Deploy to Kubernetes
kubectl apply -f k8s-simple/namespace.yaml
kubectl apply -f k8s-simple/secrets.yaml  # Update with real values
kubectl apply -f k8s-simple/configmap.yaml
kubectl apply -f k8s-simple/redis.yaml
kubectl apply -f k8s-simple/postgres.yaml
kubectl apply -f k8s-simple/travel-agent.yaml
kubectl apply -f k8s-simple/hpa.yaml
```

---

## When to Switch

**Switch to scalable branch when:**
- You have >1,000 concurrent users
- You need data persistence
- You need horizontal scaling
- You need distributed rate limiting
- You need session persistence across restarts

**Stay on simple branch when:**
- Development/testing
- Small user base (<1,000)
- Prototyping
- Don't need data persistence
- Want easy deployment

---

## Architecture Comparison

| Feature | Simple (main) | Scalable (scalable) |
|---------|---------------|---------------------|
| Deployment | Render single service | Kubernetes |
| Database | In-memory | Redis + PostgreSQL |
| Max Users | ~1,000 | 1M+ |
| Persistence | No | Yes |
| Scaling | Single instance | HPA (3-100 replicas) |
| Complexity | Low | High |
| Cost | Low (Render free tier) | High (Kubernetes cluster) |
| Data Loss | Yes (on restart) | No |
| Horizontal Scaling | No | Yes |
| Rate Limiting | Per-instance | Distributed |

---

## Quick Decision Guide

**Use Simple (main branch) if:**
- ✅ You're just starting
- ✅ You have <1,000 users
- ✅ You want easy deployment
- ✅ You don't need data persistence
- ✅ You're testing/prototyping

**Use Scalable (scalable branch) if:**
- ✅ You have >1,000 users
- ✅ You need data persistence
- ✅ You need to scale horizontally
- ✅ You need production-grade reliability
- ✅ You have budget for Kubernetes cluster

---

## Migration Path

**To migrate from simple to scalable:**

1. **Backup data** (if any - simple version has no persistence)
2. **Switch branch:** `git checkout scalable`
3. **Set up infrastructure:**
   - Kubernetes cluster (GKE, EKS, AKS, or managed)
   - Redis (ElastiCache, Memorystore, or self-hosted)
   - PostgreSQL (RDS, Cloud SQL, or self-hosted)
4. **Deploy:** Follow scalable deployment guide
5. **Configure environment variables** in secrets.yaml
6. **Deploy to Kubernetes**
7. **Test** before switching DNS

---

## Current Status

- **main branch:** Simple deployment (like teloscopy) - READY for small scale
- **scalable branch:** Scalable deployment (millions of users) - NEEDS to be created

**Next step:** Create `scalable` branch with Redis/PostgreSQL/Kubernetes setup.
