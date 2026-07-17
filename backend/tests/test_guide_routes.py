from __future__ import annotations

from unittest.mock import Mock
from types import SimpleNamespace
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_db
from app.models.guide import GuideMessageInsight, GuideSession
from app.models.knowledge import RagProfile, ScenicArea
from app.models.spot import RoutePlan, RouteSpot, ScenicSpot
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


def test_route_context_is_validated_persisted_and_used_for_personalized_answer(
    client: TestClient,
    monkeypatch,
) -> None:
    headers = visitor_headers(client)
    other_response = client.post(
        "/api/auth/visitor-register",
        json={"username": "otherguidevisitor", "password": "password123"},
    )
    other_headers = {"Authorization": f"Bearer {other_response.json()['access_token']}"}
    override = client.app.dependency_overrides[get_db]
    generator = override()
    db = next(generator)
    try:
        user_id = client.get("/api/auth/me", headers=headers).json()["id"]
        other_user_id = client.get("/api/auth/me", headers=other_headers).json()["id"]
        scenic = ScenicArea(code="route-guide", name="路线讲解景区", is_enabled=True)
        db.add(scenic); db.flush()
        db.add(RagProfile(scenic_area_id=scenic.id, name="路线讲解知识版", status="active"))
        first = ScenicSpot(scenic_area=scenic.name, name="古寺", summary="历史建筑", description="古寺介绍", recommended_duration_minutes=30)
        second = ScenicSpot(scenic_area=scenic.name, name="竹林", summary="自然景观", description="竹林介绍", recommended_duration_minutes=20)
        db.add_all([first, second]); db.flush()
        plan = RoutePlan(
            user_id=user_id, scenic_area=scenic.name, interest="历史文化,自然风光", preference="balanced",
            duration_minutes=60, total_duration_minutes=50, reason="个性化路线",
        )
        db.add(plan); db.flush()
        db.add_all([
            RouteSpot(route_plan_id=plan.id, spot_id=first.id, sequence=1, stay_minutes=30, reason="历史文化重点"),
            RouteSpot(route_plan_id=plan.id, spot_id=second.id, sequence=2, stay_minutes=20, reason="自然风光重点"),
        ])
        other_plan = RoutePlan(
            user_id=other_user_id, scenic_area=scenic.name, interest="历史文化", preference="balanced",
            duration_minutes=30, total_duration_minutes=30, reason="其他游客路线",
        )
        cross_scenic_plan = RoutePlan(
            user_id=user_id, scenic_area="其他景区", interest="自然风光", preference="balanced",
            duration_minutes=20, total_duration_minutes=20, reason="跨景区路线",
        )
        other_scenic_spot = ScenicSpot(
            scenic_area="其他景区", name="异地景点", summary="其他景区景点", description="异地介绍",
            recommended_duration_minutes=20,
        )
        db.add_all([other_plan, cross_scenic_plan, other_scenic_spot]); db.flush()
        db.add_all([
            RouteSpot(route_plan_id=other_plan.id, spot_id=first.id, sequence=1, stay_minutes=30, reason="其他游客站点"),
            RouteSpot(route_plan_id=cross_scenic_plan.id, spot_id=other_scenic_spot.id, sequence=1, stay_minutes=20, reason="异地站点"),
        ])
        db.commit()
        route_id, first_id, second_id = plan.id, first.id, second.id
        other_route_id = other_plan.id
        cross_scenic_route_id, other_scenic_spot_id = cross_scenic_plan.id, other_scenic_spot.id
    finally:
        generator.close()

    created = client.post(
        "/api/guide/sessions",
        headers=headers,
        json={"scenic_area_code": "route-guide", "route_plan_id": route_id, "current_spot_id": first_id},
    )
    assert created.status_code == 201
    session_id = created.json()["id"]
    assert created.json()["route_plan_id"] == route_id
    assert created.json()["current_spot_id"] == first_id

    context = client.get(f"/api/guide/sessions/{session_id}/context", headers=headers)
    assert context.status_code == 200
    assert context.json()["interest"] == "历史文化,自然风光"
    assert [item["name"] for item in context.json()["spots"]] == ["古寺", "竹林"]

    updated = client.patch(
        f"/api/guide/sessions/{session_id}/context",
        headers=headers,
        json={"route_plan_id": route_id, "current_spot_id": second_id},
    )
    assert updated.status_code == 200
    assert updated.json()["current_sequence"] == 2

    unauthorized = client.patch(
        f"/api/guide/sessions/{session_id}/context",
        headers=headers,
        json={"route_plan_id": other_route_id, "current_spot_id": first_id},
    )
    assert unauthorized.status_code == 404

    cross_scenic = client.patch(
        f"/api/guide/sessions/{session_id}/context",
        headers=headers,
        json={"route_plan_id": cross_scenic_route_id, "current_spot_id": other_scenic_spot_id},
    )
    assert cross_scenic.status_code == 422

    invalid_spot = client.patch(
        f"/api/guide/sessions/{session_id}/context",
        headers=headers,
        json={"route_plan_id": route_id, "current_spot_id": other_scenic_spot_id},
    )
    assert invalid_spot.status_code == 422

    captured: dict[str, object] = {}
    def generate(**kwargs):
        captured.update(kwargs)
        return GuideGeneratedAnswer(content="为你讲解竹林", model="test", duration_ms=5)

    monkeypatch.setattr("app.routers.guide.search_profile", lambda *args, **kwargs: (captured.update({"retrieval_query": args[3]}) or {"hits": []}))
    monkeypatch.setattr("app.routers.guide.generate_guide_answer", generate)
    monkeypatch.setattr("app.routers.guide.process_insight", Mock())
    response = client.post(
        f"/api/guide/sessions/{session_id}/messages",
        headers=headers,
        json={"content": "请介绍这一站", "input_mode": "text"},
    )
    assert response.status_code == 200
    assert str(captured["retrieval_query"]).startswith("竹林 ")
    assert captured["visitor_interests"] == "历史文化,自然风光"
    assert "当前第 2/2 站：竹林" in str(captured["route_context"])
