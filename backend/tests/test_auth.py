from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.database import get_db
from app.models.user import User


def test_visitor_registration_returns_a_valid_session(client: TestClient) -> None:
    login_response = client.post(
        "/api/auth/visitor-register",
        json={"username": "visitor001", "password": "password123"},
    )

    assert login_response.status_code == 201
    payload = login_response.json()
    assert payload["token_type"] == "bearer"
    assert isinstance(payload["user"]["id"], int)
    assert payload["user"]["id"] >= 1
    assert payload["user"]["role"] == "visitor"
    assert payload["user"]["username"] == "visitor001"
    assert payload["user"]["nickname"] == "visitor001"
    assert payload["user"]["interest"] is None
    assert payload["user"]["interests"] == []
    assert payload["user"]["needs_interest_setup"] is True
    assert payload["user"]["is_guest"] is False

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


def test_admin_can_change_password_and_use_the_new_password(client: TestClient) -> None:
    login = client.post(
        "/api/auth/admin-login",
        json={"username": "admin", "password": "123456"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    changed = client.post(
        "/api/auth/admin/change-password",
        headers=headers,
        json={"current_password": "123456", "new_password": "new-admin-pass-2026"},
    )

    assert changed.status_code == 204
    assert client.post(
        "/api/auth/admin-login",
        json={"username": "admin", "password": "123456"},
    ).status_code == 401
    assert client.post(
        "/api/auth/admin-login",
        json={"username": "admin", "password": "new-admin-pass-2026"},
    ).status_code == 200


def test_admin_password_change_rejects_invalid_passwords(client: TestClient) -> None:
    login = client.post(
        "/api/auth/admin-login",
        json={"username": "admin", "password": "123456"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    wrong_current = client.post(
        "/api/auth/admin/change-password",
        headers=headers,
        json={"current_password": "wrong-password", "new_password": "new-admin-pass-2026"},
    )
    assert wrong_current.status_code == 400
    assert wrong_current.json()["detail"] == "当前密码不正确"

    too_short = client.post(
        "/api/auth/admin/change-password",
        headers=headers,
        json={"current_password": "123456", "new_password": "short-pass"},
    )
    assert too_short.status_code == 422

    oversized_current = client.post(
        "/api/auth/admin/change-password",
        headers=headers,
        json={"current_password": "密" * 30, "new_password": "new-admin-pass-2026"},
    )
    assert oversized_current.status_code == 422

    assert client.post(
        "/api/auth/admin/change-password",
        headers=headers,
        json={"current_password": "123456", "new_password": "new-admin-pass-2026"},
    ).status_code == 204
    reused = client.post(
        "/api/auth/admin/change-password",
        headers=headers,
        json={"current_password": "new-admin-pass-2026", "new_password": "new-admin-pass-2026"},
    )
    assert reused.status_code == 400
    assert reused.json()["detail"] == "新密码不能与当前密码相同"


def test_visitor_cannot_change_admin_password(client: TestClient) -> None:
    visitor = client.post(
        "/api/auth/visitor-register",
        json={"username": "visitor002", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {visitor.json()['access_token']}"}

    response = client.post(
        "/api/auth/admin/change-password",
        headers=headers,
        json={"current_password": "password123", "new_password": "visitor-pass-2026"},
    )

    assert response.status_code == 403


def test_guest_session_creates_and_recovers_the_same_anonymous_visitor(client: TestClient) -> None:
    created = client.post(
        "/api/auth/guest-session",
        json={},
        headers={"X-Forwarded-For": "198.51.100.21"},
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["user"]["role"] == "visitor"
    assert payload["user"]["is_guest"] is True
    assert payload["user"]["username"] is None
    assert payload["user"]["nickname"].startswith("匿名游客 ")
    assert len(payload["guest_key"]) >= 32

    recovered = client.post(
        "/api/auth/guest-session",
        json={"guest_key": payload["guest_key"]},
        headers={"X-Forwarded-For": "198.51.100.21"},
    )
    assert recovered.status_code == 200
    assert recovered.json()["user"]["id"] == payload["user"]["id"]
    assert recovered.json()["guest_key"] is None

    guest_headers = {"Authorization": f"Bearer {recovered.json()['access_token']}"}
    assert client.get("/api/admin/avatars/humans", headers=guest_headers).status_code == 403


def test_invalid_guest_key_rotates_to_a_new_identity(client: TestClient) -> None:
    first = client.post(
        "/api/auth/guest-session",
        json={},
        headers={"X-Forwarded-For": "198.51.100.22"},
    ).json()
    second = client.post(
        "/api/auth/guest-session",
        json={"guest_key": "x" * 43},
        headers={"X-Forwarded-For": "198.51.100.22"},
    )
    assert second.status_code == 200
    assert second.json()["user"]["id"] != first["user"]["id"]
    assert second.json()["guest_key"] != first["guest_key"]


def test_expired_guest_key_rotates_and_guest_creation_is_rate_limited(client: TestClient) -> None:
    ip_address = "198.51.100.23"
    first = client.post(
        "/api/auth/guest-session",
        json={},
        headers={"X-Forwarded-For": ip_address},
    ).json()
    override = client.app.dependency_overrides[get_db]
    generator = override()
    db = next(generator)
    try:
        user = db.get(User, first["user"]["id"])
        assert user is not None
        user.guest_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    finally:
        generator.close()

    rotated = client.post(
        "/api/auth/guest-session",
        json={"guest_key": first["guest_key"]},
        headers={"X-Forwarded-For": ip_address},
    )
    assert rotated.status_code == 200
    assert rotated.json()["user"]["id"] != first["user"]["id"]

    for _ in range(8):
        assert client.post(
            "/api/auth/guest-session",
            json={},
            headers={"X-Forwarded-For": ip_address},
        ).status_code == 200
    limited = client.post(
        "/api/auth/guest-session",
        json={},
        headers={"X-Forwarded-For": ip_address},
    )
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "3600"


def test_me_rejects_missing_invalid_and_malformed_tokens(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer invalid-token"}).status_code == 401

    malformed_token = create_access_token({"user_id": "not-an-integer", "role": "visitor"})
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {malformed_token}"})
    assert response.status_code == 401
