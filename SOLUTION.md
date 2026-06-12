# Solution — Code Lab Day 12

> **Student:** Vu Duy Bao — 2A202600565

---

## Part 1: Localhost vs Production

### Exercise 1.1 — 7 anti-patterns trong `01-localhost-vs-production/develop/app.py`

1. **API key hardcode** — `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` viết thẳng trong code. Push lên GitHub là lộ key ngay.
2. **Không có config management** — `DEBUG = True`, `MAX_TOKENS = 500` hardcode. Không thể thay đổi giữa dev/staging/prod mà không sửa code.
3. **Logging sai cách** — dùng `print()` thay vì logging framework, còn in ra secret: `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")`.
4. **Không có `/health` endpoint** — platform (Railway/Render/K8s) không biết khi nào app crash để restart.
5. **Port và host cố định** — `host="localhost"` chỉ bind loopback → container không nhận traffic từ ngoài. `port=8000` hardcode không đọc `$PORT` mà cloud inject.
6. **`reload=True` trong production** — uvicorn dev reload mode gây overhead và không ổn định.
7. **Không có graceful shutdown** — SIGTERM → app tắt đột ngột, mất requests đang xử lý.

### Exercise 1.2 — Tại sao không production-ready

App chạy được nhưng:
- `host="localhost"` → container không nhận traffic từ ngoài
- Không đọc `$PORT` → fail ngay trên Render/Railway
- API key lộ trong log
- Không có `/health` → platform không biết khi nào restart

### Exercise 1.3 — So sánh basic vs production

| Feature | Basic (`develop/`) | Production (`production/`) | Tại sao quan trọng? |
|---------|-------------------|---------------------------|---------------------|
| Config | Hardcode trong code | Đọc từ env vars (`.env`) | Không bao giờ commit secrets lên Git |
| Health check | Không có | `GET /health` → `{"status":"ok"}` | Platform biết khi nào restart |
| Logging | `print()` — lộ secret | JSON structured, có log level | Dễ parse, không lộ sensitive data |
| Shutdown | Đột ngột | Graceful — hoàn thành rồi mới tắt | Không mất requests đang xử lý |

---

## Part 2: Docker Containerization

### Exercise 2.1 — Dockerfile cơ bản (`02-docker/develop/Dockerfile`)

1. **Base image:** `python:3.11` — Full Python ~1 GB, gồm compiler, debug tools, docs.
2. **Working directory:** `/app` — tất cả `COPY`, `RUN`, `CMD` chạy relative với `/app`.
3. **COPY requirements.txt trước** vì Docker layer caching: nếu `requirements.txt` không đổi thì layer `pip install` được cache → lần build sau nhanh hơn nhiều.
4. **CMD vs ENTRYPOINT:**
   - `CMD` có thể override: `docker run image python other.py`
   - `ENTRYPOINT` là fixed, không override được (chỉ append args)
   - Best practice: `ENTRYPOINT ["python"]` + `CMD ["app.py"]`

### Exercise 2.2 — Image size

```
REPOSITORY   TAG       SIZE
my-agent     develop   1.08 GB   ← python:3.11 full
```

### Exercise 2.3 — Multi-stage build (`02-docker/production/Dockerfile`)

- **Stage 1 (builder):** `python:3.11-slim AS builder` — cài gcc, libpq-dev, chạy `pip install --user`. Mục đích: compile packages cần native code.
- **Stage 2 (runtime):** `python:3.11-slim AS runtime` — image sạch, không có build tools. Chỉ copy packages đã compile và app code. Non-root user `appuser`.
- **Tại sao nhỏ hơn:** `python:3.11-slim` (~130MB) thay vì `python:3.11` (~900MB). Không có gcc, docs, tests trong final image.

```
REPOSITORY   TAG       SIZE
my-agent     develop   1.08 GB
my-agent     advanced  245 MB    ← giảm ~77%
```

### Exercise 2.4 — Docker Compose (`02-docker/production/docker-compose.yml`)

**4 services:**
- `nginx` — Load balancer (port 80/443 ra host)
- `agent` — FastAPI app, không expose port ra host (chỉ qua Docker network), non-root user `appuser`
- `redis` — Cache session + rate limit state (port 6379 nội bộ)
- `qdrant` — Vector database cho RAG (port 6333 nội bộ)

**Architecture:**
```
Client (:80)
    │
    ▼
  nginx
    │ :8000 (internal)
    ├──────────────┐
    ▼              ▼
  Agent 1      Agent 2     (appuser, non-root)
    │              │
    └──────┬───────┘
           │
    ┌──────┴──────┐
    ▼             ▼
  redis:6379   qdrant:6333
```

---

## Part 3: Cloud Deployment

### Exercise 3.1 — Railway

```bash
npm i -g @railway/cli
railway login
railway init
railway variables set AGENT_API_KEY=my-secret-key
railway up
railway domain
```

**Deployed URL:** https://ai-agent-day12-production.up.railway.app

```bash
curl https://ai-agent-day12-production.up.railway.app/health
```

### Exercise 3.2 — Deploy Render

**Deployed URL:** https://ai-agent-7so8.onrender.com

```bash
curl https://ai-agent-7so8.onrender.com/health
```

### Exercise 3.2 — So sánh `railway.toml` vs `render.yaml`

| Khía cạnh | `railway.toml` | `render.yaml` |
|-----------|---------------|---------------|
| Format | TOML | YAML |
| Services | 1 service | Multi-service trong 1 file |
| Redis | Add riêng trong dashboard | Khai báo `type: redis` trong file |
| Build | `NIXPACKS` — tự detect | `runtime: python` + `buildCommand` |
| Secrets | `railway variables set KEY=VALUE` | `generateValue: true` hoặc dashboard |
| Mạnh hơn cho | Single service nhanh | Infrastructure as Code đầy đủ |

### Exercise 3.3 — GCP Cloud Run (optional)

`cloudbuild.yaml` CI/CD pipeline: **Build** image → **Push** lên Artifact Registry → **Deploy** lên Cloud Run.

`service.yaml`: định nghĩa CPU/memory limits, concurrency, env vars, auto-scaling min/max instances.

**Ưu điểm Cloud Run:** Scale to zero, pay per request, serverless, tích hợp GCP ecosystem.

---

## Part 4: API Security

### Exercise 4.1 — API Key authentication (`04-api-gateway/develop/app.py`)

- **Check ở đâu:** Hàm `verify_api_key()` định nghĩa trực tiếp trong `app.py`, inject vào `/ask` qua `Depends(verify_api_key)`. FastAPI gọi dependency trước khi chạy handler.
- **Nếu sai key:**
  - Không có header `X-API-Key` → `401` — *"Missing API key"*
  - Có header nhưng sai giá trị → `401` — *"Invalid API key"*
- **Rotate key:** Thay `AGENT_API_KEY` trong env var / Render dashboard → restart service. Không sửa code.

### Exercise 4.2 — JWT authentication (`04-api-gateway/production/`)

- Endpoint lấy token: `POST /auth/token`
- Credentials: `student/demo123` (role: student) hoặc `teacher/teach456` (role: admin)
- Flow: credentials → `authenticate_user()` → `create_token()` (PyJWT, HS256, exp 60 phút) → Bearer token
- `verify_token()`: FastAPI dependency dùng `HTTPBearer`, decode JWT, trả payload

```bash
curl http://localhost:8000/auth/token -X POST \
  -H "Content-Type: application/json" \
  -d '{"username": "student", "password": "demo123"}'
# → {"access_token": "eyJ...", "token_type": "bearer"}
```

### Exercise 4.3 — Rate limiting (`04-api-gateway/production/rate_limiter.py`)

- **Algorithm:** Sliding Window Counter — lưu timestamps trong `defaultdict(deque)`, loại bỏ timestamps cũ hơn 60s.
- **Limits:** `rate_limiter_user = RateLimiter(max_requests=10)` / `rate_limiter_admin = RateLimiter(max_requests=100)`
- **Bypass cho admin:** Endpoint `/ask` dùng `rate_limiter_user` hoặc `rate_limiter_admin` tùy `role` trong JWT — đã implement sẵn.

```
Request 1–10:  HTTP 200
Request 11+:   HTTP 429 — {"error":"Rate limit exceeded","retry_after_seconds":45}
               Header: Retry-After: 45
```

### Exercise 4.4 — Cost guard

```python
# Logic từ 04-api-gateway/production/cost_guard.py (class CostGuard)
key = f"{user_id}:{time.strftime('%Y-%m')}"   # reset đầu tháng tự động
current = _monthly_costs.get(key, 0.0)
if current >= MONTHLY_BUDGET_USD:             # $10/user/month
    raise HTTPException(status_code=402, detail={"error": "Monthly budget exceeded"})
_monthly_costs[key] = current + cost          # record sau khi call LLM
```

- Key format `user_id:YYYY-MM` → tự động reset đầu tháng
- Raises HTTP 402 (Payment Required) khi vượt budget

---

## Part 5: Scaling & Reliability

### Exercise 5.1 — Health checks (`05-scaling-reliability/develop/app.py`)

```python
@app.get("/health")   # Liveness probe — container còn sống không?
def health():
    return {"status": "ok", "uptime_seconds": round(time.time() - START_TIME, 1), ...}

@app.get("/ready")    # Readiness probe — có nên route traffic vào không?
def ready():
    if not _is_ready:
        raise HTTPException(status_code=503, detail="Agent not ready")
    return {"ready": True, "in_flight_requests": _in_flight_requests}
```

- `/health` → 200 nếu process chạy được (platform dùng để restart)
- `/ready` → 503 khi đang startup hoặc shutdown (LB dùng để dừng route)

### Exercise 5.2 — Graceful shutdown (`05-scaling-reliability/develop/app.py`)

**3 cơ chế kết hợp:**

1. **Middleware đếm in-flight requests:**
```python
@app.middleware("http")
async def track_requests(request, call_next):
    global _in_flight_requests
    _in_flight_requests += 1
    try:
        return await call_next(request)
    finally:
        _in_flight_requests -= 1
```

2. **Lifespan drain loop (tối đa 30s):**
```python
_is_ready = False   # LB dừng route ngay
while _in_flight_requests > 0 and elapsed < 30:
    time.sleep(1); elapsed += 1
```

3. **Signal handler + uvicorn timeout:**
```python
signal.signal(signal.SIGTERM, handle_sigterm)
uvicorn.run(app, timeout_graceful_shutdown=30)
```

**Flow SIGTERM:** signal → uvicorn trigger lifespan shutdown → `_is_ready=False` → chờ drain → exit sạch.

### Exercise 5.3 — Stateless design (`05-scaling-reliability/production/app.py`)

**Anti-pattern (stateful):**
```python
conversation_history = {}   # mỗi instance có memory riêng → scale ra là mất session
```

**Correct (stateless):**
```python
# State trong Redis — key: "session:{session_id}"
def save_session(session_id, data, ttl=3600):
    r.setex(f"session:{session_id}", ttl, json.dumps(data))

def load_session(session_id):
    raw = r.get(f"session:{session_id}")
    return json.loads(raw) if raw else {}
```

Endpoint là `/chat` (không phải `/ask`). Response có `served_by: INSTANCE_ID` để trace instance.

### Exercise 5.4 — Load balancing (`05-scaling-reliability/production/`)

- Nginx lắng nghe **port 8080** (`ports: "8080:80"`)
- Scale qua `deploy.replicas: 3` trong `docker-compose.yml`
- Endpoint: `POST /chat` (không có API key auth trong lab này)

```bash
docker compose up
curl http://localhost:8080/health
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# Response: {"answer":"...","served_by":"instance-a1b2c3","storage":"redis"}
```

### Exercise 5.5 — Test stateless

```bash
python test_stateless.py   # target: http://localhost:8080
```

Kết quả: 5 requests route sang 3 instances khác nhau, nhưng history đủ 10 messages vì tất cả đọc/ghi cùng Redis key `session:{id}`. Không cần sticky session.

```
Instances used: {instance-a1b2c3, instance-d4e5f6, instance-g7h8i9}
✅ Session history preserved across all instances via Redis!
```

### Checkpoint 5

- [x] Implement health và readiness checks
- [x] Implement graceful shutdown
- [x] Refactor code thành stateless
- [x] Hiểu load balancing với Nginx
- [x] Test stateless design

---

## Part 6: Final Project — Production AI Agent

### Checkpoint 6

**Functional:**

- [x] Agent trả lời câu hỏi qua REST API
- [x] Support conversation history
- [ ] Streaming responses (optional)

**Non-functional:**

- [x] Dockerized với multi-stage build
- [x] Config từ environment variables
- [x] API key authentication
- [x] Rate limiting (10 req/min per user)
- [x] Cost guard ($10/month per user)
- [x] Health check endpoint
- [x] Readiness check endpoint
- [x] Graceful shutdown
- [x] Stateless design (state trong Redis)
- [x] Structured JSON logging
- [x] Deploy lên Render (xem DEPLOYMENT.md)
- [x] Public URL hoạt động

### 🏗 Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  Nginx (LB)     │
└──────┬──────────┘
       │
       ├─────────┬─────────┐
       ▼         ▼         ▼
   ┌──────┐  ┌──────┐  ┌──────┐
   │Agent1│  │Agent2│  │Agent3│
   └───┬──┘  └───┬──┘  └───┬──┘
       │         │         │
       └─────────┴─────────┘
                 │
                 ▼
           ┌──────────┐
           │  Redis   │
           └──────────┘
```

**Deployed URL:** https://vuduybao-2a202600565-day12.onrender.com
