# Deployment Information

> **Student:** Vu Duy Bao — 2A202600565  
> **Platform:** Render  
> **Date:** 2026-06-12

---

## Public URL

```
https://ai-agent-production.onrender.com
```

> **Note:** Render free tier sleeps after 15 minutes of inactivity. First request may take ~30s to wake up.

---

## Platform

**Render** (render.com) — Free tier

- **Web service:** Docker-based FastAPI application
- **Redis:** Render Redis (free tier, 25MB)
- **Region:** Singapore
- **Auto-deploy:** Enabled on push to `main` branch

---

## Deploy Steps (Render Blueprint)

1. Push repo lên GitHub (public hoặc instructor có access)
2. Vào [render.com](https://render.com) → Sign Up / Log In
3. Dashboard → **New** → **Blueprint**
4. Connect GitHub repo → Render đọc `06-lab-complete/render.yaml`
5. Review services:
   - `ai-agent-production` (web service)
   - `ai-agent-redis` (Redis)
6. Set secrets nếu cần:
   - `AGENT_API_KEY` → Render auto-generates (do `generateValue: true`)
   - `JWT_SECRET` → Render auto-generates
7. Click **Apply** → Deploy!
8. Copy public URL từ dashboard

---

## Test Commands

### Health Check

```bash
curl https://ai-agent-production.onrender.com/health
```

Expected:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "environment": "production",
  "uptime_seconds": 123.4,
  "total_requests": 5,
  "checks": {"llm": "mock", "redis": "connected"},
  "timestamp": "2026-06-12T10:00:00+00:00"
}
```

### Readiness Check

```bash
curl https://ai-agent-production.onrender.com/ready
```

Expected:
```json
{"ready": true, "timestamp": "2026-06-12T10:00:00+00:00"}
```

### API Test (with authentication)

```bash
curl -X POST https://ai-agent-production.onrender.com/ask \
  -H "X-API-Key: YOUR_AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "Hello, what can you do?"}'
```

Expected:
```json
{
  "question": "Hello, what can you do?",
  "answer": "Xin chào! Tôi là AI agent production-ready...",
  "user_id": "test",
  "model": "gpt-4o-mini",
  "timestamp": "2026-06-12T10:00:00+00:00"
}
```

### Authentication Required (401)

```bash
curl -X POST https://ai-agent-production.onrender.com/ask \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "Hello"}'
# Expected: 401 Unauthorized
```

### Rate Limiting (429)

```bash
# Gửi 15 requests → request 11+ sẽ bị block
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST https://ai-agent-production.onrender.com/ask \
    -H "X-API-Key: YOUR_AGENT_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"user_id\": \"rate_test\", \"question\": \"test $i\"}"
done
# Output: 200 200 200 200 200 200 200 200 200 200 429 429 429 429 429
```

### Conversation History

```bash
# Message 1
curl -X POST https://ai-agent-production.onrender.com/ask \
  -H "X-API-Key: YOUR_AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "conv_test", "question": "My name is Alice"}'

# Message 2 — should reference previous message
curl -X POST https://ai-agent-production.onrender.com/ask \
  -H "X-API-Key: YOUR_AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "conv_test", "question": "What did I say before?"}'
# Expected: Response mentions "Alice"
```

---

## Environment Variables Set on Render

| Variable | Value | Source |
|----------|-------|--------|
| `PORT` | `8000` | Render injects automatically |
| `ENVIRONMENT` | `production` | `render.yaml` |
| `AGENT_API_KEY` | *(auto-generated)* | `render.yaml` `generateValue: true` |
| `JWT_SECRET` | *(auto-generated)* | `render.yaml` `generateValue: true` |
| `REDIS_URL` | `redis://...` | Linked from `ai-agent-redis` service |
| `RATE_LIMIT_PER_MINUTE` | `10` | `render.yaml` |
| `MONTHLY_BUDGET_USD` | `10.0` | `render.yaml` |
| `LOG_LEVEL` | `INFO` | `render.yaml` |

---

## Project Structure Deployed

```
06-lab-complete/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI application
│   ├── config.py         # 12-factor configuration
│   ├── auth.py           # API key authentication
│   ├── rate_limiter.py   # Sliding window rate limiter
│   └── cost_guard.py     # Monthly budget protection
├── utils/
│   ├── __init__.py
│   └── mock_llm.py       # Mock LLM (no API key needed)
├── Dockerfile            # Multi-stage build
├── docker-compose.yml    # Local development stack
├── render.yaml           # Render Blueprint config
├── railway.toml          # Railway config (alternative)
├── requirements.txt      # Python dependencies
├── .env.example          # Environment template
└── .dockerignore         # Docker build exclusions
```

---

## Local Development

```bash
cd 06-lab-complete

# Setup
cp .env.example .env
# Edit .env — set AGENT_API_KEY to something memorable

# Run with Docker Compose
docker compose up

# Test locally
curl http://localhost:8000/health
curl -X POST http://localhost:8000/ask \
  -H "X-API-Key: dev-key-change-me-in-production" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "local_test", "question": "Hello!"}'
```

---

## Screenshots

- [Render Dashboard](screenshots/dashboard.png)
- [Service Running](screenshots/running.png)
- [Health Check Test](screenshots/test_health.png)
- [API Test](screenshots/test_api.png)

> Screenshots chụp sau khi deploy thành công. Xem thư mục `screenshots/`.

---

## Production Readiness Checklist

```bash
cd 06-lab-complete
python check_production_ready.py
```

Expected output:
```
=======================================================
  Production Readiness Check — Day 12 Lab
=======================================================

📁 Required Files
  ✅ Dockerfile exists
  ✅ docker-compose.yml exists
  ✅ .dockerignore exists
  ✅ .env.example exists
  ✅ requirements.txt exists
  ✅ railway.toml or render.yaml exists

🔒 Security
  ✅ .env in .gitignore
  ✅ No hardcoded secrets in code

🌐 API Endpoints (code check)
  ✅ /health endpoint defined
  ✅ /ready endpoint defined
  ✅ Authentication implemented
  ✅ Rate limiting implemented
  ✅ Graceful shutdown (SIGTERM)
  ✅ Structured logging (JSON)

🐳 Docker
  ✅ Multi-stage build
  ✅ Non-root user
  ✅ HEALTHCHECK instruction
  ✅ Slim base image
  ✅ .dockerignore covers .env
  ✅ .dockerignore covers __pycache__

=======================================================
  Result: 18/18 checks passed (100%)
  🎉 PRODUCTION READY! Deploy nào!
=======================================================
```
