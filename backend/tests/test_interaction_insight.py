from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base
from app.models.guide import GuideMessage, GuideMessageInsight, GuideSession
from app.models.knowledge import ScenicArea
from app.models.user import User
from app.crud.insights import ensure_pending_insight, recover_stale_insights
from app.services.interaction_insight import analyze_interaction


def test_analyze_interaction_parses_fixed_structured_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "qwen-plus-insight-test"
        assert body["response_format"] == {"type": "json_object"}
        assert "needs_attention" in body["messages"][0]["content"]
        assert "九龙灌浴几点开始" in body["messages"][1]["content"]
        return httpx.Response(200, json={"choices": [{"message": {"content": "```json\n{\"normalized_question\":\"九龙灌浴演出时间\",\"primary_topic\":\"演出活动\",\"topic_tags\":[\"演出活动\",\"开放时间\"],\"intent\":\"服务咨询\",\"sentiment\":\"neutral\",\"sentiment_score\":0,\"issue_type\":\"无明确问题\",\"needs_attention\":false}\n```"}}]})

    with patch.object(settings, "dashscope_api_key", "test-key"), patch.object(settings, "insight_analysis_model", "qwen-plus-insight-test"):
        result = analyze_interaction(
            "九龙灌浴几点开始？",
            "每天上午十点开始。",
            "success",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )

    assert result.normalized_question == "九龙灌浴演出时间"
    assert result.topic_tags == ["演出活动", "开放时间"]
    assert result.sentiment == "neutral"


def test_pending_insight_is_idempotent_and_stale_processing_recovers() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(username="insight-user", role="visitor", nickname="游客")
        scenic = ScenicArea(code="insight-area", name="洞察景区", is_enabled=True)
        db.add_all([user, scenic]); db.flush()
        session = GuideSession(user_id=user.id, scenic_area_id=scenic.id)
        db.add(session); db.flush()
        visitor = GuideMessage(session_id=session.id, role="user", content="排队太久了", status="success")
        assistant = GuideMessage(session_id=session.id, role="assistant", content="很抱歉", status="success")
        db.add_all([visitor, assistant]); db.commit()

        first = ensure_pending_insight(db, session, visitor, assistant)
        second = ensure_pending_insight(db, session, visitor, assistant)
        assert first.id == second.id

        first.analysis_status = "processing"
        first.updated_at = datetime.now(timezone.utc) - timedelta(minutes=20)
        db.commit()
        assert recover_stale_insights(db, datetime.now(timezone.utc) - timedelta(minutes=10)) == 1
        assert db.scalar(select(GuideMessageInsight).where(GuideMessageInsight.id == first.id)).analysis_status == "pending"
