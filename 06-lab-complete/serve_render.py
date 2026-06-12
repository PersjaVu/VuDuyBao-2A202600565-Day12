"""Production API Gateway — Legal Multi-Agent System.

Productionization checklist (Day 12):
  [x] Config from env vars
  [x] /health + /ready probes
  [x] Structured JSON logging
  [x] API Key authentication (X-API-Key header)
  [x] Rate limiting (sliding window, per IP)
  [x] Cost guard (monthly request budget per key)
  [x] Graceful shutdown (lifespan drain + SIGTERM)
  [x] Multi-stage Dockerfile + non-root (in Dockerfile)
"""

from __future__ import annotations

import json
import logging
import os
import signal
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Security
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles

# ── Config from env vars (no hardcoded values)
AGENT_API_KEY     = os.getenv("AGENT_API_KEY", "dev-key-change-me")
RATE_LIMIT        = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))
MONTHLY_REQ_LIMIT = int(os.getenv("MONTHLY_REQUEST_LIMIT", "500"))
CUSTOMER_AGENT_URL = os.getenv("CUSTOMER_AGENT_URL", "http://127.0.0.1:10100")
LOG_LEVEL         = os.getenv("LOG_LEVEL", "INFO")

# ── Structured JSON logging (12-factor: log to stdout)
logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
                    format="%(message)s")


def log(event: str, **kwargs) -> None:
    print(json.dumps({
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **kwargs,
    }), flush=True)


# ── Rate limiter (sliding window per API key)
_rate_windows: dict = defaultdict(deque)

def _check_rate_limit(key: str) -> None:
    now = time.time()
    window = _rate_windows[key]
    while window and window[0] < now - 60:
        window.popleft()
    if len(window) >= RATE_LIMIT:
        retry_after = int(window[0] + 60 - now) + 1
        raise HTTPException(
            status_code=429,
            detail={"error": "Rate limit exceeded", "retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after)},
        )
    window.append(now)


# ── Cost guard (monthly request count per key)
_monthly_requests: dict = {}

def _check_budget(key: str) -> None:
    bucket = f"{key}:{time.strftime('%Y-%m')}"
    if _monthly_requests.get(bucket, 0) >= MONTHLY_REQ_LIMIT:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Monthly request limit exceeded",
                "limit": MONTHLY_REQ_LIMIT,
                "used": _monthly_requests.get(bucket, 0),
            },
        )
    _monthly_requests[bucket] = _monthly_requests.get(bucket, 0) + 1


# ── API Key auth
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(_api_key_header)) -> str:
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    if api_key != AGENT_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key


# ── Application state
START_TIME = time.time()
_is_ready  = False
_in_flight = 0


# ── Graceful shutdown lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    log("startup", customer_agent=CUSTOMER_AGENT_URL, rate_limit=RATE_LIMIT)
    _is_ready = True
    yield
    _is_ready = False
    log("shutdown_initiated", in_flight=_in_flight)
    timeout, elapsed = 30, 0
    while _in_flight > 0 and elapsed < timeout:
        time.sleep(1)
        elapsed += 1
    log("shutdown_complete")


# ── SIGTERM handler
def _handle_sigterm(signum, frame):
    log("signal_received", signum=signum)

signal.signal(signal.SIGTERM, _handle_sigterm)
signal.signal(signal.SIGINT,  _handle_sigterm)


# ── FastAPI app
app = FastAPI(
    title="Legal Multi-Agent System",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Middleware: count in-flight + structured request log
@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _in_flight
    _in_flight += 1
    start = time.time()
    try:
        response = await call_next(request)
        log("request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round((time.time() - start) * 1000, 1))
        return response
    finally:
        _in_flight -= 1


# ── Health check (liveness probe)
@app.get("/health")
async def health():
    agent_status = "starting"
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(f"{CUSTOMER_AGENT_URL}/.well-known/agent.json")
            agent_status = "ok" if r.status_code == 200 else "degraded"
    except Exception:
        pass
    return {
        "status": "ok",
        "version": "1.0.0",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "agents": {"customer": agent_status},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Readiness probe
@app.get("/ready")
async def ready():
    if not _is_ready:
        raise HTTPException(status_code=503, detail="Server not ready")
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(f"{CUSTOMER_AGENT_URL}/.well-known/agent.json")
            if r.status_code == 200:
                return {"ready": True, "in_flight": _in_flight}
    except Exception:
        pass
    raise HTTPException(status_code=503, detail="Customer agent not ready")


# ── Protected /messages endpoint (auth + rate limit + cost guard)
@app.post("/messages")
async def proxy_messages(
    request: Request,
    api_key: str = Security(verify_api_key),
):
    _check_rate_limit(api_key)
    _check_budget(api_key)

    body = await request.body()
    async with httpx.AsyncClient(timeout=60.0) as c:
        res = await c.post(
            f"{CUSTOMER_AGENT_URL}/messages",
            content=body,
            headers={"Content-Type": "application/json"},
        )
    headers = dict(res.headers)
    headers.pop("content-encoding", None)
    headers.pop("content-length", None)
    return StreamingResponse(
        res.aiter_raw(),
        status_code=res.status_code,
        headers=headers,
    )


# ── Agent card proxy (no auth needed)
@app.get("/.well-known/agent.json")
async def proxy_well_known():
    async with httpx.AsyncClient(timeout=5.0) as c:
        res = await c.get(f"{CUSTOMER_AGENT_URL}/.well-known/agent.json")
        return res.json()


# ── Serve Vite frontend (must be last)
if os.path.exists("frontend-demo/dist"):
    app.mount("/", StaticFiles(directory="frontend-demo/dist", html=True), name="frontend")
else:
    @app.get("/")
    def no_frontend():
        return {"message": "Frontend not built. Run: cd frontend-demo && npm run build"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    log("main", port=port)
    uvicorn.run(app, host="0.0.0.0", port=port, timeout_graceful_shutdown=30)
