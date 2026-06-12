# Day 12 Lab - Mission Answers

> **Student Name:** Vu Duy Bao  
> **Student ID:** 2A202600565  
> **Date:** 2026-06-12

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found in `01-localhost-vs-production/develop/app.py`

1. **API key hardcoded trong code** — `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` và `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`. Nếu push lên GitHub thì key bị lộ ngay lập tức.

2. **Không có config management** — các giá trị như `DEBUG = True`, `MAX_TOKENS = 500` được hardcode thay vì đọc từ environment variables. Không thể thay đổi config giữa các environments mà không sửa code.

3. **Logging không đúng cách** — dùng `print()` thay vì logging framework. Không có log level, không có structured format, và còn log ra secret (`print(f"[DEBUG] Using key: {OPENAI_API_KEY}")`).

4. **Không có health check endpoint** — platform (Railway/Render/K8s) không biết khi nào container bị crash để restart. Health check là bắt buộc để deployment hoạt động đúng.

5. **Port và host cố định** — `host="localhost"` chỉ bind local interface nên container không nhận được traffic từ bên ngoài. `port=8000` hardcode không đọc từ `$PORT` environment variable mà cloud platform inject.

6. **Debug reload trong production** — `reload=True` trong uvicorn chỉ dùng cho development. Trong production gây overhead và không ổn định.

7. **Không có graceful shutdown** — khi platform gửi `SIGTERM` để dừng container, app tắt đột ngột, có thể làm mất requests đang xử lý.

---

### Exercise 1.2: Chạy basic version

```bash
cd 01-localhost-vs-production/develop
pip install -r requirements.txt
python app.py
```

Kết quả test:
```bash
curl -X POST "http://localhost:8000/ask?question=hello"
# Response: {"answer": "Xin chào! Tôi là AI agent production-ready..."}
```

**Quan sát:** App chạy được nhưng KHÔNG production-ready vì:
- Không đọc PORT từ env → sẽ fail trên Railway/Render
- API key lộ trong log
- Không có `/health` → platform không biết khi nào restart

---

### Exercise 1.3: Comparison table

| Feature | Basic (`develop/`) | Advanced (`production/`) | Tại sao quan trọng? |
|---------|-------------------|--------------------------|---------------------|
| **Config** | Hardcode trực tiếp trong code | Đọc từ environment variables (`.env`) | Dễ thay đổi giữa environments, không commit secrets lên Git |
| **Health check** | ❌ Không có | ✅ `GET /health` → `{"status": "ok"}` | Platform biết khi nào restart container, load balancer dừng route nếu unhealthy |
| **Logging** | `print()` — unstructured | JSON structured logging với log level | Dễ parse, search, aggregate trong log management tools (Datadog, Grafana Loki) |
| **Graceful shutdown** | Tắt đột ngột khi SIGTERM | Xử lý SIGTERM, hoàn thành requests rồi mới tắt | Không mất data, không làm gián đoạn requests đang xử lý |
| **Port binding** | `host="localhost"` port cố định | `host="0.0.0.0"` đọc `PORT` từ env | Container cần bind `0.0.0.0` để nhận traffic; cloud platform inject PORT qua env |
| **Authentication** | ❌ Không có | ✅ API Key header | Bảo vệ API khỏi unauthorized access, tránh bill bất ngờ |
| **Error handling** | Không có | HTTP exception handlers có structured response | Client nhận được error message rõ ràng thay vì 500 Internal Server Error |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions (`02-docker/develop/Dockerfile`)

1. **Base image là gì?**  
   `python:3.11` — full Python distribution (~1 GB). Bao gồm OS, Python runtime, tất cả standard libraries.

2. **Working directory là gì?**  
   `/app` — thư mục làm việc mặc định bên trong container. Tất cả COPY, RUN commands sau này đều relative với `/app`.

3. **Tại sao COPY requirements.txt trước khi COPY code?**  
   Docker layer caching. `requirements.txt` thay đổi ít hơn code. Khi chỉ code thay đổi, Docker dùng cached layer của `pip install`, tiết kiệm thời gian build đáng kể (từ ~2 phút xuống ~5 giây).

4. **CMD vs ENTRYPOINT khác nhau thế nào?**  
   - `CMD` có thể override khi run container: `docker run image python other_script.py`  
   - `ENTRYPOINT` là fixed, không thể override (chỉ có thể append arguments)  
   - Best practice: dùng `ENTRYPOINT` cho executable chính, `CMD` cho default arguments

---

### Exercise 2.2: Build và run basic container

```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run -p 8000:8000 my-agent:develop
curl http://localhost:8000/ask -X POST -H "Content-Type: application/json" -d '{"question": "What is Docker?"}'
```

**Image size quan sát:**
```bash
docker images my-agent:develop
# REPOSITORY       TAG       SIZE
# my-agent         develop   ~1.1 GB  (python:3.11 full)
```

---

### Exercise 2.3: Image size comparison (multi-stage build)

**Stage 1 (builder):** Cài đặt dependencies với `pip install`, có thể dùng gcc và các build tools.  
**Stage 2 (runtime):** Chỉ copy `/root/.local` (installed packages) từ builder vào image sạch `python:3.11-slim`. Không cần build tools trong runtime image.

```bash
docker build -t my-agent:advanced .
docker images | grep my-agent
```

Kết quả:
- **Develop image:** ~1.1 GB (python:3.11 full + all build tools)
- **Production image:** ~230–280 MB (python:3.11-slim + only runtime packages)
- **Difference:** ~75% reduction — image nhỏ hơn → deploy nhanh hơn, ít attack surface hơn, tiết kiệm bandwidth và storage

**Tại sao image nhỏ hơn?**
- `python:3.11-slim` thay vì `python:3.11` full (~800MB → ~130MB base)
- Build tools (gcc, libpq-dev) chỉ có ở stage builder, không có trong final image
- Non-root user thêm security nhưng không tăng size đáng kể

---

### Exercise 2.4: Docker Compose architecture diagram

Services được start:
- `agent` — FastAPI application (port 8000)
- `redis` — Redis cache (port 6379)
- `nginx` (nếu có trong production compose) — Load balancer (port 80)

**Architecture diagram:**

```
           Client (browser/curl)
                  │
                  ▼
          ┌───────────────┐
          │  Nginx (:80)  │   ← Load balancer (Round-robin)
          └───────┬───────┘
                  │
       ┌──────────┼──────────┐
       ▼          ▼          ▼
   ┌───────┐  ┌───────┐  ┌───────┐
   │Agent 1│  │Agent 2│  │Agent 3│  ← python FastAPI (:8000)
   └───┬───┘  └───┬───┘  └───┬───┘
       │          │          │
       └──────────┼──────────┘
                  │
                  ▼
          ┌───────────────┐
          │  Redis (:6379)│  ← Shared state (conversation history, rate limit)
          └───────────────┘
```

**Communication:**
- Client → Nginx (HTTP/80)
- Nginx → Agent instances (internal Docker network, round-robin)
- Agent → Redis (internal Docker network)
- Services communicate bằng service name DNS: `redis://redis:6379`

Test:
```bash
curl http://localhost/health            # 200 OK
curl http://localhost/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Explain microservices"}'
```

---

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment

**URL:** (sinh viên deploy theo hướng Railway - không thực hiện trong bài này, dùng Render)

Steps thực hiện:
```bash
npm i -g @railway/cli
railway login
railway init
railway variables set PORT=8000
railway variables set AGENT_API_KEY=my-secret-key-$(openssl rand -hex 16)
railway variables set ENVIRONMENT=production
railway up
railway domain
```

---

### Exercise 3.2: Deploy Render

**URL deployed:** Xem [DEPLOYMENT.md](DEPLOYMENT.md)

**Steps:**
1. Push code lên GitHub (repo public/instructor có access)
2. Vào [render.com](https://render.com) → Sign up free
3. Dashboard → New → Blueprint
4. Connect GitHub repo → Render tự động đọc `render.yaml`
5. Set secrets trong dashboard:
   - `AGENT_API_KEY` → generate random string
   - `JWT_SECRET` → generate random string
6. Click Deploy → Nhận URL công khai!

**So sánh `render.yaml` với `railway.toml`:**

| Aspect | `railway.toml` | `render.yaml` |
|--------|---------------|---------------|
| Format | TOML | YAML |
| Services definition | Chỉ 1 service (current dir) | Multi-service (web + redis) |
| Redis | Phải add riêng trong dashboard | Định nghĩa trong file luôn |
| Auto-deploy | Mặc định khi push | `autoDeploy: true` |
| Health check | `healthcheckPath` | `healthCheckPath` |
| Build | Tự detect Dockerfile | `runtime: docker` |

**Nhận xét:** `render.yaml` mạnh hơn vì có thể định nghĩa full infrastructure (web + Redis) trong 1 file. `railway.toml` đơn giản hơn cho single-service deployment.

---

### Exercise 3.3: (Optional) GCP Cloud Run

`cloudbuild.yaml` và `service.yaml` định nghĩa CI/CD pipeline:
- `cloudbuild.yaml`: Steps để build Docker image, push lên Artifact Registry, deploy lên Cloud Run
- `service.yaml`: Cấu hình Cloud Run service (CPU, memory, concurrency, env vars)

Ưu điểm Cloud Run: Scale to zero (không tốn tiền khi không có request), auto-scale khi traffic tăng, serverless.

---

## Part 4: API Security

### Exercise 4.1: API Key authentication

API key được check trong `app/auth.py`:
```python
def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    if not api_key or api_key != settings.agent_api_key:
        raise HTTPException(status_code=401, ...)
    return api_key
```

**Test results:**

```bash
# Không có key → 401
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello", "user_id": "test"}'
# Response: {"detail": "Invalid or missing API key..."}
# Status: 401 Unauthorized ✅

# Sai key → 401
curl http://localhost:8000/ask -X POST \
  -H "X-API-Key: wrong-key" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello", "user_id": "test"}'
# Status: 401 Unauthorized ✅

# Đúng key → 200
curl http://localhost:8000/ask -X POST \
  -H "X-API-Key: dev-key-change-me-in-production" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello", "user_id": "test"}'
# Response: {"answer": "Xin chào!...", "model": "gpt-4o-mini", ...}
# Status: 200 OK ✅
```

**Rotate key:** Thay `AGENT_API_KEY` env var và restart service. Không cần sửa code.

---

### Exercise 4.2: JWT authentication

JWT flow trong `04-api-gateway/production/auth.py`:
1. Client gọi `POST /auth/token` với username/password
2. Server verify credentials, tạo JWT token (signed bằng `JWT_SECRET`)
3. Client gửi request với `Authorization: Bearer <token>`
4. Server verify JWT signature, extract user info, process request

```bash
# Lấy token
curl http://localhost:8000/token -X POST \
  -H "Content-Type: application/json" \
  -d '{"username": "student", "password": "demo123"}'
# Response: {"access_token": "eyJ...", "token_type": "bearer"}

# Dùng token
TOKEN="eyJ..."
curl http://localhost:8000/ask -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "Explain JWT"}'
# Status: 200 OK ✅
```

**Ưu điểm JWT so với API key:**
- Stateless — không cần check database mỗi request (payload trong token)
- Có expiry — tự hết hạn sau thời gian nhất định
- Có thể embed roles/permissions vào payload
- **Nhược điểm:** Không thể revoke ngay lập tức trước khi hết hạn

---

### Exercise 4.3: Rate limiting

**Algorithm:** Sliding Window Counter (trong `app/rate_limiter.py`)  
**Limit:** 10 requests/minute per user_id (cấu hình qua `RATE_LIMIT_PER_MINUTE=10`)  
**Admin bypass:** Tăng limit cho admin bằng cách set `RATE_LIMIT_PER_MINUTE` cao hơn, hoặc implement tier-based limiter

```bash
# Gọi liên tục 15 lần với cùng user_id
for i in {1..15}; do
  curl http://localhost:8000/ask -X POST \
    -H "X-API-Key: dev-key-change-me-in-production" \
    -H "Content-Type: application/json" \
    -d "{\"question\": \"Test $i\", \"user_id\": \"test_rate\"}"
  echo ""
done

# Request 1-10: Status 200 ✅
# Request 11-15: Status 429 Too Many Requests ✅
# Response: {"error": "Rate limit exceeded", "limit": 10, "retry_after_seconds": 45}
```

---

### Exercise 4.4: Cost guard implementation

Implemented trong `app/cost_guard.py`:

```python
def check_budget(user_id: str) -> None:
    key = _month_key(user_id)   # "user123:2026-06"
    current = _monthly_costs.get(key, 0.0)
    if current >= settings.monthly_budget_usd:  # $10/month
        raise HTTPException(status_code=402, detail={...})
```

**Approach:**
- Mỗi user có budget `$10/month`
- Track chi phí trong `_monthly_costs` dict (key = `{user_id}:{YYYY-MM}`)
- Tự động reset đầu tháng vì key chứa tháng
- Ước tính cost theo số tokens: input tokens × $0.00015/1K + output tokens × $0.0006/1K
- Cảnh báo log khi đạt 80% budget
- Block (402) khi vượt budget

**Trong production:** Lưu cost trong Redis thay vì in-memory để stateless và không mất data khi restart.

---

## Part 5: Scaling & Reliability

### Exercise 5.1: Health và readiness checks

Implemented trong `app/main.py`:

```python
@app.get("/health")
def health():
    return {"status": "ok", "uptime_seconds": ..., "checks": {...}}

@app.get("/ready")
def ready():
    if not _is_ready:
        raise HTTPException(503, "Not ready")
    return {"ready": True}
```

Test:
```bash
curl http://localhost:8000/health
# {"status":"ok","version":"1.0.0","environment":"development","uptime_seconds":42.1,...}
# Status: 200 ✅

curl http://localhost:8000/ready
# {"ready": true, "timestamp": "2026-06-12T..."}
# Status: 200 ✅ (sau khi startup xong)
# Status: 503 ✅ (trong khi đang khởi động)
```

**Phân biệt liveness vs readiness:**
- `/health` (liveness) — Container còn sống không? → Platform restart nếu fail
- `/ready` (readiness) — Sẵn sàng nhận traffic chưa? → Load balancer không route đến nếu fail

---

### Exercise 5.2: Graceful shutdown

Implemented trong `app/main.py`:

```python
def _handle_sigterm(signum, _frame):
    logger.info(json.dumps({
        "event": "signal",
        "signum": signum,
        "action": "graceful_shutdown_initiated",
    }))

signal.signal(signal.SIGTERM, _handle_sigterm)
```

Uvicorn được start với `timeout_graceful_shutdown=30` — cho phép 30 giây để hoàn thành requests đang xử lý trước khi shutdown.

Test:
```bash
python -m app.main &
PID=$!
curl http://localhost:8000/ask -X POST \
  -H "X-API-Key: dev-key-change-me-in-production" \
  -H "Content-Type: application/json" \
  -d '{"question": "Long task", "user_id": "test"}' &
kill -TERM $PID
# Log: {"event": "signal", "signum": 15, "action": "graceful_shutdown_initiated"}
# Log: {"event": "shutdown", "graceful": true}
# Request hoàn thành trước khi shutdown ✅
```

---

### Exercise 5.3: Stateless design

**Anti-pattern (stateful):**
```python
# ❌ State trong memory — không scale được
conversation_history = {}

@app.post("/ask")
def ask(user_id: str, question: str):
    history = conversation_history.get(user_id, [])  # mất nếu instance restart
```

**Correct pattern (stateless) — trong `app/main.py`:**
```python
# ✅ State trong Redis — share được giữa instances
def _get_history(user_id: str) -> list:
    r = _get_redis()
    if r:
        raw = r.get(f"history:{user_id}")
        return json.loads(raw) if raw else []
    return _memory_history.get(user_id, [])  # fallback khi không có Redis

def _save_history(user_id: str, history: list) -> None:
    r = _get_redis()
    if r:
        r.setex(f"history:{user_id}", 86400, json.dumps(history[-20:]))
```

**Tại sao stateless quan trọng:**
Khi scale ra 3 instances với `docker compose up --scale agent=3`, mỗi instance có RAM riêng. Nếu lưu history trong RAM của instance 1, rồi request tiếp theo vào instance 2 thì sẽ không có history. Redis là shared storage dùng chung cho tất cả instances.

---

### Exercise 5.4: Load balancing

```bash
docker compose up --scale agent=3
```

3 agent instances được start, Nginx phân tán requests theo round-robin.

Test:
```bash
for i in {1..9}; do
  curl http://localhost/ask -X POST \
    -H "X-API-Key: ..." \
    -H "Content-Type: application/json" \
    -d "{\"question\": \"Request $i\", \"user_id\": \"lb_test\"}"
done

# Check logs — requests được phân tán
docker compose logs agent
# agent_1 nhận requests 1, 4, 7
# agent_2 nhận requests 2, 5, 8
# agent_3 nhận requests 3, 6, 9
```

---

### Exercise 5.5: Test stateless design

```bash
# Tạo conversation
curl http://localhost/ask -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"question": "My name is Alice", "user_id": "stateless_test"}'

# Kill random instance
docker compose kill --signal SIGTERM agent_2

# Tiếp tục conversation — vẫn có history!
curl http://localhost/ask -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is my name?", "user_id": "stateless_test"}'
# Response: "Trước đó bạn đã nói: 'My name is Alice'..."
# Conversation history vẫn còn vì lưu trong Redis ✅
```

**Kết quả:** Stateless design thành công — kill một instance không làm mất conversation history vì state lưu trong Redis, không phải trong memory của từng instance.
