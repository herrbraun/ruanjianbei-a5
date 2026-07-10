from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.security import create_access_token


def test_visitor_login_returns_a_valid_session(client: TestClient) -> None:
    login_response = client.post(
        "/api/auth/visitor-login",
        json={"nickname": "游客001", "interest": "历史文化"},
    )

    assert login_response.status_code == 200
    payload = login_response.json()
    assert payload["token_type"] == "bearer"
    assert isinstance(payload["user"]["id"], int)
    assert payload["user"] == {
        "id": payload["user"]["id"],
        "role": "visitor",
        "username": None,
        "nickname": "游客001",
        "interest": "历史文化",
    }

    me_response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json() == payload["user"]


def test_admin_login_accepts_only_the_correct_password(client: TestClient) -> None:
    invalid_response = client.post(
        "/api/auth/admin-login",
        json={"username": "admin", "password": "wrong-password"},
    )
    assert invalid_response.status_code == 401

    login_response = client.post(
        "/api/auth/admin-login",
        json={"username": "admin", "password": "123456"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["user"]["role"] == "admin"


def test_me_rejects_missing_invalid_and_malformed_tokens(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer invalid-token"}).status_code == 401

    malformed_token = create_access_token({"user_id": "not-an-integer", "role": "visitor"})
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {malformed_token}"})
    assert response.status_code == 401
