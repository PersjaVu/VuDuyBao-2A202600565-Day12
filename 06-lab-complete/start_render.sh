#!/bin/bash
# Start all agents inside a single Render container.
# IMPORTANT: serve_render.py must start FIRST so $PORT is bound before Render
# scans for the primary port. Agents start in background afterwards.

echo "=== Legal Multi-Agent System — Startup ==="

# ── 1. Proxy server binds $PORT FIRST (Render detects this as the primary port)
echo "[1/6] Starting Proxy Server on port ${PORT:-8080}..."
python serve_render.py &
PROXY_PID=$!

# Brief pause so the proxy has time to bind the socket before Render scans
sleep 1

# ── 2–6. Internal agents (background, register with retry so order doesn't matter)
echo "[2/6] Starting Registry (port 19000)..."
python -m registry &

echo "[3/6] Starting Law Agent (port 19101)..."
python -m law_agent &

echo "[4/6] Starting Tax Agent (port 19102)..."
python -m tax_agent &

echo "[5/6] Starting Compliance Agent (port 19103)..."
python -m compliance_agent &

echo "[6/6] Starting Customer Agent (port 19100)..."
python -m customer_agent &

echo "=== All services started. Container stays alive with proxy PID $PROXY_PID ==="
# Keep container alive as long as the proxy is running
wait $PROXY_PID
