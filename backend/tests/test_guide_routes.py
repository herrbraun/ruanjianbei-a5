from __future__ import annotations

from unittest.mock import Mock
from types import SimpleNamespace
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_db
from app.models.guide import GuideMessageInsight, GuideSession
from app.models.knowledge import RagProfile, ScenicArea
from app.services.guide_answer import GuideGeneratedAnswer
from app.schemas.guide import GuideMessageOut


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


def test_chat_creates_pending_insight_and_schedules_analysis(client: TestClient, monkeypatch) -> None:
    headers = visitor_headers(client)
    override = client.app.dependency_overrides[get_db]
    generator = override()
    db = next(generator)
    try:
        user_id = client.get("/api/auth/me", headers=headers).json()["id"]
        scenic = ScenicArea(code="insight-chat", name="洞察测试景区", is_enabled=True)
        db.add(scenic); db.flush()
        profile = RagProfile(scenic_area_id=scenic.id, name="洞察测试版", status="active")
        db.add(profile); db.flush()
        session = GuideSession(user_id=user_id, scenic_area_id=scenic.id, initial_rag_profile_id=profile.id)
        db.add(session); db.commit(); session_id = session.id
    finally:
        generator.close()
    process = Mock()
    monkeypatch.setattr("app.routers.guide.search_profile", lambda *args, **kwargs: {"hits": []})
    monkeypatch.setattr("app.routers.guide.generate_guide_answer", lambda **kwargs: GuideGeneratedAnswer(content="测试回答", model="test", duration_ms=5))
    monkeypatch.setattr("app.routers.guide.process_insight", process)

    response = client.post(f"/api/guide/sessions/{session_id}/messages", headers=headers, json={"content": "这里有什么故事？", "input_mode": "text"})
    assert response.status_code == 200
    process.assert_called_once()

    generator = override(); db = next(generator)
    try:
        row = db.query(GuideMessageInsight).one()
        assert row.analysis_status == "pending"
        assert row.visitor_message_id == response.json()["visitor_message"]["id"]
    finally:
        generator.close()


def test_visitor_message_schema_hides_internal_model_error() -> None:
    message = SimpleNamespace(
        id=1, session_id=1, role="assistant", input_mode=None, content="回答暂时不可用",
        rag_profile_id=None, sources=None, answer_model=None, answer_duration_ms=None,
        status="failed", error_message="provider secret diagnostic", created_at=datetime.now(timezone.utc),
    )

    payload = GuideMessageOut.model_validate(message).model_dump()

    assert "error_message" not in payload
