# Production AI Agent — Day 12 Final Project

> **Student:** Vu Duy Bao — 2A202600565  
> **Course:** AICB-P1 · VinUniversity 2026  

Production-ready AI agent combining all concepts from Day 12: Docker, cloud deployment, authentication, rate limiting, cost guard, graceful shutdown, stateless design.

---

## Architecture

```
Client
  │
  ▼ :80
Nginx (load balancer)
  │
  ├──────────┬──────────┐
  ▼          ▼          ▼
Agent 1   Agent 2   Agent 3   ← FastAPI + uvicorn (stateless)
  │          │          │
  └──────────┴──────────┘
             │
             ▼ :6379
           Redis             ← conversation history, rate limit state
```

---

## Quick Start (Local — no Docker)

```bash
cd 06-final-project

# 1. Copy env template
cp .env.example .env

# 2. Edit .env — set your API key
#    AGENT_API_KEY=my-secret-key

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run (Redis optional — falls back to in-memory)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 5. Test
curl http://localhost:8000/health
curl -X POST http://localhost:8000/ask \
  -H "X-API-Key: my-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello!", "user_id": "test"}'
```

---

## Docker Compose (Full Stack)

```bash
cd 06-final-project

# 1. Setup env
cp .env.example .env
# Edit .env: set AGENT_API_KEY

# 2. Start full stack (nginx + 3 agents + redis)
docker compose up --scale agent=3

# 3. Test via Nginx on port 80
curl http://localhost/health
curl http://localhost/ready
curl -X POST http://localhost/ask \
  -H "X-API-Key: <your-key>" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Docker?", "user_id": "user1"}'

# 4. Stop
docker compose down
```

---

## API Reference

### `GET /health` — Liveness probe
```json
{
  "status": "ok",
  "version": "1.0.0",
  "environment": "development",
  "uptime_seconds": 12.3,
  "instance": "instance-a1b2c3",
  "checks": {"redis": "connected", "llm": "mock"}
}
```

### `GET /ready` — Readiness probe
```json
{"ready": true, "in_flight": 0}
```
Returns `503` when starting up or shutting down.

### `POST /ask` — Chat endpoint (requires auth)

**Headers:** `X-API-Key: <your-key>` | `Content-Type: application/json`

**Body:**
```json
{"question": "What is Redis?", "user_id": "alice"}
```

**Response:**
```json
{
  "question": "What is Redis?",
  "answer": "Redis la in-memory data store...",
  "user_id": "alice",
  "model": "gpt-4o-mini",
  "instance": "instance-a1b2c3"
}
```

**Error codes:**
| Code | Reason |
|------|--------|
| `401` | Missing or invalid `X-API-Key` |
| `422` | Invalid request body |
| `429` | Rate limit exceeded (10 req/min per user) |
| `402` | Monthly budget exceeded ($10/user) |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_API_KEY` | `dev-key-change-me` | API key clients must send |
| `ENVIRONMENT` | `development` | dev / staging / production |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `RATE_LIMIT_PER_MINUTE` | `10` | Max requests per user per minute |
| `MONTHLY_BUDGET_USD` | `10.0` | Max spend per user per month |
| `LOG_LEVEL` | `INFO` | DEBUG / INFO / WARNING |
| `PORT` | `8000` | App port (injected by cloud platform) |

---

## Project Structure

```
06-final-project/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app — lifespan, middleware, endpoints
│   ├── config.py        # 12-factor settings (all from env vars)
│   ├── auth.py          # X-API-Key authentication
│   ├── rate_limiter.py  # Sliding window rate limiter
│   └── cost_guard.py    # Monthly budget guard
├── utils/
│   └── mock_llm.py      # Mock LLM (no API key needed)
├── Dockerfile           # Multi-stage: builder + runtime (non-root)
├── docker-compose.yml   # nginx + agent + redis
├── nginx.conf           # Upstream agent_pool, proxy_pass
├── render.yaml          # Render Blueprint (web + redis)
├── requirements.txt
├── .env.example         # Environment template
└── .dockerignore
```

---

## Deploy to Render

1. Push this folder to a GitHub repository
2. Go to [render.com](https://render.com) → **New** → **Blueprint**
3. Connect your GitHub repo → Render reads `render.yaml`
4. Review: `ai-agent-final` (web) + `ai-agent-final-redis` (Redis)
5. `AGENT_API_KEY` is auto-generated (`generateValue: true`)
6. Click **Apply** → wait ~2 min → get public URL

**Verify:**
```bash
curl https://<your-app>.onrender.com/health
```

---

## Production Features Implemented

| Feature | Implementation |
|---------|---------------|
| Config from env | `app/config.py` — `Settings` dataclass |
| API key auth | `app/auth.py` — `APIKeyHeader`, raises 401 |
| Rate limiting | `app/rate_limiter.py` — sliding window, raises 429 |
| Cost guard | `app/cost_guard.py` — monthly budget, raises 402 |
| Health check | `GET /health` — liveness probe |
| Readiness check | `GET /ready` — 503 during startup/shutdown |
| Graceful shutdown | Lifespan drain loop (30s timeout) + SIGTERM handler |
| Stateless design | Redis `history:{user_id}` key, in-memory fallback |
| JSON logging | `log()` helper — structured stdout |
| Multi-stage Docker | builder (gcc) → runtime (non-root `agent`) |
| Load balancing | Nginx upstream `agent_pool` → `--scale agent=3` |
