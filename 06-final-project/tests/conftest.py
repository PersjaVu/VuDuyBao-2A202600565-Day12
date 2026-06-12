import os
import pytest
from fastapi.testclient import TestClient

# Set test env vars BEFORE importing app
os.environ.setdefault("AGENT_API_KEY", "test-key-12345")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("REDIS_URL", "")  # force in-memory fallback


@pytest.fixture(scope="module")
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers():
    return {"X-API-Key": "test-key-12345"}
