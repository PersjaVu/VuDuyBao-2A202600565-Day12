# ============================================================
# Stage 1: Build Frontend (Vite)
# ============================================================
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend-demo
COPY frontend-demo/package*.json ./
RUN npm install
COPY frontend-demo/ ./
RUN npm run build

# ============================================================
# Stage 2: Python runtime
# ============================================================
FROM python:3.11-slim AS runtime

RUN groupadd -r agent && useradd -r -g agent -d /app agent
WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Install Python dependencies from pyproject.toml
COPY pyproject.toml uv.lock ./
RUN uv pip install --system .

# Copy source code
COPY common/ ./common/
COPY registry/ ./registry/
COPY customer_agent/ ./customer_agent/
COPY law_agent/ ./law_agent/
COPY tax_agent/ ./tax_agent/
COPY compliance_agent/ ./compliance_agent/
COPY Lab_Assignment/ ./Lab_Assignment/
COPY serve_render.py start_render.sh ./

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/frontend-demo/dist ./frontend-demo/dist

RUN chmod +x start_render.sh && chown -R agent:agent /app
USER agent

ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8080}/health')"

CMD ["./start_render.sh"]
