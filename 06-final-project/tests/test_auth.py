"""Unit tests — API key authentication."""


def test_ask_no_key_returns_401(client):
    r = client.post("/ask", json={"question": "hi", "user_id": "u1"})
    assert r.status_code == 401


def test_ask_wrong_key_returns_401(client):
    r = client.post(
        "/ask",
        json={"question": "hi", "user_id": "u1"},
        headers={"X-API-Key": "wrong-key"},
    )
    assert r.status_code == 401


def test_ask_valid_key_returns_200(client, auth_headers):
    r = client.post(
        "/ask",
        json={"question": "What is Docker?", "user_id": "test-user"},
        headers=auth_headers,
    )
    assert r.status_code == 200


def test_ask_response_schema(client, auth_headers):
    r = client.post(
        "/ask",
        json={"question": "Hello", "user_id": "schema-test"},
        headers=auth_headers,
    )
    body = r.json()
    assert "question" in body
    assert "answer" in body
    assert "user_id" in body
    assert "instance" in body
    assert body["user_id"] == "schema-test"
