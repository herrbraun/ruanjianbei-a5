from __future__ import annotations

from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.config import settings


def visitor_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/visitor-register",
        json={"username": "guidevisitor", "password": "password123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_asr_rejects_oversized_upload_before_transcoding(
    client: TestClient,
    monkeypatch,
) -> None:
    recognize = Mock()
    monkeypatch.setattr(settings, "guide_max_audio_bytes", 8)
    monkeypatch.setattr("app.routers.guide.recognize_speech", recognize)

    response = client.post(
        "/api/guide/asr",
        headers=visitor_headers(client),
        files={"file": ("recording.webm", b"123456789", "audio/webm")},
    )

    assert response.status_code == 413
    recognize.assert_not_called()
