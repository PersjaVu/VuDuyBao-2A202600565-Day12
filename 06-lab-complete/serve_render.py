"""Proxy Server để deploy Render.
Phục vụ Frontend (dist) và proxy /messages tới Customer Agent.
"""
import os
import time
import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
import httpx

app = FastAPI(title="Legal Multi-Agent System", version="1.0.0")

START_TIME = time.time()


@app.get("/health")
async def health():
    """Liveness probe — Render dùng để check service còn sống không."""
    # Check customer agent reachable
    agent_status = "unknown"
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get("http://127.0.0.1:10100/.well-known/agent.json")
            agent_status = "ok" if r.status_code == 200 else "degraded"
    except Exception:
        agent_status = "starting"

    return {
        "status": "ok",
        "version": "1.0.0",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "agents": {"customer": agent_status},
    }


@app.get("/ready")
async def ready():
    """Readiness probe — trả 503 khi agents chưa sẵn sàng."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get("http://127.0.0.1:10100/.well-known/agent.json")
            if r.status_code == 200:
                return {"ready": True}
    except Exception:
        pass
    from fastapi import HTTPException
    raise HTTPException(status_code=503, detail="Agents not ready yet")

# HTTPX Client kết nối tới Customer Agent ở local
client = httpx.AsyncClient(base_url="http://127.0.0.1:10100")

@app.post("/messages")
async def proxy_messages(request: Request):
    body = await request.body()
    res = await client.post(
        "/messages", 
        content=body, 
        headers={"Content-Type": "application/json"}
    )
    # Lọc bỏ các header liên quan đến encoding để tránh lỗi trên một số trình duyệt
    headers = dict(res.headers)
    headers.pop("content-encoding", None)
    headers.pop("content-length", None)
    
    return StreamingResponse(
        res.aiter_raw(), 
        status_code=res.status_code, 
        headers=headers
    )

@app.get("/.well-known/agent.json")
async def proxy_well_known():
    res = await client.get("/.well-known/agent.json")
    return res.json()

# Phục vụ file tĩnh của Vite (phải build trước)
if os.path.exists("frontend-demo/dist"):
    app.mount("/", StaticFiles(directory="frontend-demo/dist", html=True), name="frontend")
else:
    @app.get("/")
    def no_frontend():
        return {"message": "Frontend chưa được build (thiếu thư mục frontend-demo/dist)."}

if __name__ == "__main__":
    # Render sẽ tự động gán biến môi trường PORT
    port = int(os.environ.get("PORT", 8080))
    print(f"Bắt đầu khởi chạy Proxy Server (Public Web) trên cổng {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
