"""Unit tests — health & readiness endpoints (no auth required)."""


def test_health_returns_200(client):
    r = client.get("/health")
    assert r.status_code == 200


def test_health_schema(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "uptime_seconds" in body
    assert "instance" in body
    assert "checks" in body


def test_ready_returns_200_when_up(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["ready"] is True
