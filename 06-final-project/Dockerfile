# ============================================================
# Multi-stage Dockerfile — Production AI Agent
# Stage 1 (builder): install deps with build tools
# Stage 2 (runtime): clean image, non-root user, no build tools
# ============================================================

# Stage 1: Builder
FROM python:3.11-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim AS runtime

RUN groupadd -r agent && useradd -r -g agent -d /app agent
WORKDIR /app

# Install deps from builder into system path — always discoverable
COPY --from=builder /install /usr/local
COPY app/ ./app/
COPY utils/ ./utils/

RUN chown -R agent:agent /app
USER agent

ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--timeout-graceful-shutdown", "30"]
