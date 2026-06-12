import os
import time
import json
import signal
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .config import settings
from .auth import verify_api_key
from .rate_limiter import check_rate_limit
from .cost_guard import check_budget, record_cost
from utils.mock_llm import ask as llm_ask

# ── Structured JSON logging (12-factor: log to stdout)
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(message)s",
)
logger = logging.getLogger(__name__)


def log(event: str, **kwargs):
    print(json.dumps({"event": event, "timestamp": datetime.now(timezone.utc).isoformat(), **kwargs}), flush=True)


# ── Redis (stateless session storage)
try:
    import redis as _redis_lib
    _redis = _redis_lib.from_url(settings.redis_url or "redis://localhost:6379/0", decode_responses=True)
    _redis.ping()
    USE_REDIS = True
    log("redis_connected", url=settings.redis_url)
except Exception:
    USE_REDIS = False
    _memory_store: dict = {}
    log("redis_unavailable", note="using in-memory fallback — not scalable")

INSTANCE_ID = os.getenv("INSTANCE_ID", f"instance-{uuid.uuid4().hex[:6]}")

# ── Application state
START_TIME = time.time()
_is_ready = False
_in_flight = 0


# ── Session helpers (stateless: state in Redis, not RAM)
def _get_history(user_id: str) -> list:
    key = f"history:{user_id}"
    if USE_REDIS:
        raw = _redis.get(key)
        return json.loads(raw) if raw else []
    return _memory_store.get(key, [])


def _save_history(user_id: str, history: list) -> None:
    # Keep last 20 messages (10 turns)
    trimmed = history[-20:]
    key = f"history:{user_id}"
    if USE_REDIS:
        _redis.setex(key, 3600, json.dumps(trimmed))
    else:
        _memory_store[key] = trimmed


# ── Lifespan: startup / graceful shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    log("startup", instance=INSTANCE_ID, environment=settings.environment)
    _is_ready = True

    yield

    # Graceful shutdown: stop accepting traffic, drain in-flight
    _is_ready = False
    log("shutdown_initiated", instance=INSTANCE_ID)
    timeout, elapsed = 30, 0
    while _in_flight > 0 and elapsed < timeout:
        log("draining", in_flight=_in_flight, elapsed=elapsed)
        time.sleep(1)
        elapsed += 1
    log("shutdown_complete", instance=INSTANCE_ID)


# ── SIGTERM handler (uvicorn + lifespan handle the rest)
def _handle_sigterm(signum, frame):
    log("signal_received", signum=signum)


signal.signal(signal.SIGTERM, _handle_sigterm)
signal.signal(signal.SIGINT, _handle_sigterm)


# ── FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)


# ── Middleware: count in-flight requests + structured request log
@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _in_flight
    _in_flight += 1
    start = time.time()
    try:
        response = await call_next(request)
        log(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round((time.time() - start) * 1000, 1),
            instance=INSTANCE_ID,
        )
        return response
    finally:
        _in_flight -= 1


# ── Models
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str = Field(default="anonymous", max_length=100)


# ── Endpoints

@app.get("/health")
def health():
    """Liveness probe — is the container alive?"""
    redis_status = "unavailable"
    if USE_REDIS:
        try:
            _redis.ping()
            redis_status = "connected"
        except Exception:
            redis_status = "error"

    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "instance": INSTANCE_ID,
        "checks": {
            "redis": redis_status,
            "llm": "mock",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready")
def ready():
    """Readiness probe — should load balancer route traffic here?"""
    if not _is_ready:
        raise HTTPException(status_code=503, detail="Agent not ready")
    return {
        "ready": True,
        "in_flight": _in_flight,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/hello")
def hello():
    return {"message": "Hello, World!"}


@app.post("/ask", responses={401: {"description": "Missing or invalid API key"}, 429: {"description": "Rate limit exceeded"}, 402: {"description": "Monthly budget exceeded"}})
async def ask(body: AskRequest, _key: str = Depends(verify_api_key)):
    """Protected endpoint — requires X-API-Key header."""
    # 1. Rate limit per user_id — raises 429 if exceeded
    check_rate_limit(body.user_id)
    # 2. Budget check — raises 402 if exceeded
    check_budget(body.user_id)
    # 3. Get conversation history from Redis (stateless design)
    history = _get_history(body.user_id)
    # 4. Call LLM
    answer = llm_ask(body.question, history=history)
    # 5. Save updated history to Redis
    history.extend([
        {"role": "user", "content": body.question},
        {"role": "assistant", "content": answer},
    ])
    _save_history(body.user_id, history)
    # 6. Record token cost
    record_cost(
        body.user_id,
        input_tokens=len(body.question.split()) * 2,
        output_tokens=len(answer.split()) * 2,
    )

    return {
        "question": body.question,
        "answer": answer,
        "user_id": body.user_id,
        "model": settings.llm_model,
        "instance": INSTANCE_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        timeout_graceful_shutdown=30,
    )
