#!/bin/bash
# Start all agents inside a single Render container, then start the proxy.
set -e

echo "=== Legal Multi-Agent System — Startup ==="

# ── 1. Registry (port 10000)
echo "[1/6] Starting Registry..."
python -m registry &
sleep 2

# ── 2. Law Agent (port 10101)
echo "[2/6] Starting Law Agent..."
python -m law_agent &

# ── 3. Tax Agent (port 10102)
echo "[3/6] Starting Tax Agent..."
python -m tax_agent &

# ── 4. Compliance Agent (port 10103)
echo "[4/6] Starting Compliance Agent..."
python -m compliance_agent &

# ── 5. Customer Agent (port 10100) — last because it registers with registry
echo "[5/6] Starting Customer Agent..."
python -m customer_agent &

# Wait for all agents to be up before starting the proxy
echo "Waiting for agents to initialise..."
sleep 6

# ── 6. Proxy / Frontend server (public $PORT, foreground)
echo "[6/6] Starting Proxy Server on port ${PORT:-8080}..."
exec python serve_render.py
