from __future__ import annotations

import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import UniqueConstraint

from app.database import get_db
from app.models.guide import GuideFeedback, GuideMessageInsight
from app.models.guide import GuideMessage, GuideSession
from app.models.knowledge import ScenicArea
from app.schemas.guide import GuideFeedbackUpsert


def test_feedback_schema_accepts_only_fixed_tags() -> None:
    payload = GuideFeedbackUpsert(
        rating=5,
        tags=["answer_accurate", "voice_natural"],
        comment="讲解清楚",
    )

    assert payload.tags == ["answer_accurate", "voice_natural"]

    with pytest.raises(ValidationError):
        GuideFeedbackUpsert(rating=4, tags=["custom-tag"])


def test_insight_and_feedback_have_one_to_one_unique_constraints() -> None:
    insight_unique_columns = {
        tuple(constraint.columns.keys())
        for constraint in GuideMessageInsight.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    feedback_unique_columns = {
        tuple(constraint.columns.keys())
        for constraint in GuideFeedback.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("visitor_message_id",) in insight_unique_columns
    assert ("guide_session_id",) in feedback_unique_columns


def _visitor(client: TestClient, username: str) -> tuple[dict[str, str], int]:
    response = client.post("/api/auth/visitor-register", json={"username": username, "password": "password123"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}, response.json()["user"]["id"]


def _session(client: TestClient, user_id: int, *, with_answer: bool) -> int:
    override = client.app.dependency_overrides[get_db]
    generator = override()
    db = next(generator)
    try:
        scenic = ScenicArea(code=f"feedback-{uuid4().hex[:8]}", name=f"评价景区{user_id}", is_enabled=True)
        db.add(scenic)
        db.flush()
        session = GuideSession(user_id=user_id, scenic_area_id=scenic.id, title=scenic.name)
        db.add(session)
        db.flush()
        if with_answer:
            db.add(GuideMessage(session_id=session.id, role="assistant", content="欢迎游览", status="success"))
        db.commit()
        return session.id
    finally:
        generator.close()


def test_feedback_requires_an_answer_and_can_be_updated(client: TestClient) -> None:
    headers, user_id = _visitor(client, "feedbackvisitor")
    empty_session_id = _session(client, user_id, with_answer=False)
    assert client.post(f"/api/guide/sessions/{empty_session_id}/feedback", headers=headers, json={"rating": 5, "tags": []}).status_code == 422

    session_id = _session(client, user_id, with_answer=True)
    created = client.post(f"/api/guide/sessions/{session_id}/feedback", headers=headers, json={"rating": 5, "tags": ["answer_accurate"]})
    assert created.status_code == 200
    assert created.json()["rating"] == 5

    updated = client.post(f"/api/guide/sessions/{session_id}/feedback", headers=headers, json={"rating": 3, "tags": ["slow_response"], "comment": "稍慢"})
    assert updated.status_code == 200
    assert updated.json()["rating"] == 3
    assert client.get(f"/api/guide/sessions/{session_id}/feedback", headers=headers).json()["comment"] == "稍慢"


def test_feedback_is_private_to_session_owner(client: TestClient) -> None:
    first_headers, first_user_id = _visitor(client, "feedbackowner")
    other_headers, _ = _visitor(client, "feedbackother")
    session_id = _session(client, first_user_id, with_answer=True)
    assert client.post(f"/api/guide/sessions/{session_id}/feedback", headers=first_headers, json={"rating": 4, "tags": []}).status_code == 200
    assert client.get(f"/api/guide/sessions/{session_id}/feedback", headers=other_headers).status_code == 404
