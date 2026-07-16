from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.crud.insights import get_guide_dashboard
from app.database import Base, get_db
from app.models.guide import GuideFeedback, GuideMessage, GuideMessageInsight, GuideSession
from app.models.knowledge import ScenicArea
from app.models.user import User


def test_dashboard_aggregates_one_scenic_area_and_reports_coverage() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime(2026, 7, 16, 4, 0, tzinfo=timezone.utc)
    with Session(engine) as db:
        users = [User(username=f"dash-{i}", role="visitor", nickname=f"游客{i}") for i in range(3)]
        first = ScenicArea(code="dash-first", name="第一景区", is_enabled=True)
        second = ScenicArea(code="dash-second", name="第二景区", is_enabled=True)
        db.add_all([*users, first, second]); db.flush()
        sessions = [
            GuideSession(user_id=users[0].id, scenic_area_id=first.id, created_at=now),
            GuideSession(user_id=users[1].id, scenic_area_id=first.id, created_at=now),
            GuideSession(user_id=users[2].id, scenic_area_id=second.id, created_at=now),
        ]
        db.add_all(sessions); db.flush()
        statuses = [(sessions[0], "success", "negative"), (sessions[0], "failed", "neutral"), (sessions[1], "success", None), (sessions[2], "success", "positive")]
        for index, (guide_session, answer_status, sentiment) in enumerate(statuses):
            question = GuideMessage(session_id=guide_session.id, role="user", content=f"问题{index}", status="success", created_at=now)
            answer = GuideMessage(session_id=guide_session.id, role="assistant", content=f"回答{index}", status=answer_status, answer_duration_ms=100 + index, created_at=now)
            db.add_all([question, answer]); db.flush()
            insight = GuideMessageInsight(
                scenic_area_id=guide_session.scenic_area_id,
                guide_session_id=guide_session.id,
                visitor_message_id=question.id,
                assistant_message_id=answer.id,
                analysis_status="completed" if sentiment else "failed",
                normalized_question="演出时间" if index < 2 else "路线推荐",
                primary_topic="演出活动" if index < 2 else "游览路线",
                topic_tags=["演出活动" if index < 2 else "游览路线"],
                intent="服务咨询",
                sentiment=sentiment,
                sentiment_score=-0.7 if sentiment == "negative" else 0,
                issue_type="排队时间" if sentiment == "negative" else "无明确问题",
                needs_attention=sentiment == "negative",
                created_at=now,
            )
            db.add(insight)
        db.add_all([
            GuideFeedback(guide_session_id=sessions[0].id, user_id=users[0].id, scenic_area_id=first.id, rating=5, tags=[], created_at=now),
            GuideFeedback(guide_session_id=sessions[1].id, user_id=users[1].id, scenic_area_id=first.id, rating=4, tags=[], created_at=now),
        ])
        db.commit()

        dashboard = get_guide_dashboard(db, first.id, date(2026, 7, 16), date(2026, 7, 16))

    metrics = dashboard["metrics"]
    assert metrics["service_visitors"] == 2
    assert metrics["session_count"] == 2
    assert metrics["question_count"] == 3
    assert metrics["answer_success_rate"] == 0.6667
    assert metrics["analysis_coverage_rate"] == 0.6667
    assert metrics["average_rating"] == 4.5
    assert metrics["negative_rate"] == 0.5
    assert dashboard["popular_questions"][0] == {"name": "演出时间", "count": 2}
    assert len(dashboard["attention_preview"]) == 1


def test_dashboard_endpoint_requires_admin_and_valid_period(client: TestClient) -> None:
    admin_login = client.post("/api/auth/admin-login", json={"username": "admin", "password": "123456"})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    scenic = client.post("/api/admin/scenic-areas", headers=admin_headers, json={"code": "dashboard-api", "name": "大屏景区", "description": "测试"})
    assert scenic.status_code == 201

    response = client.get(f"/api/admin/analytics/guide?scenic_area_id={scenic.json()['id']}&start_date=2026-07-01&end_date=2026-07-07", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["metrics"]["session_count"] == 0

    visitor = client.post("/api/auth/visitor-register", json={"username": "dashboardvisitor", "password": "password123"})
    visitor_headers = {"Authorization": f"Bearer {visitor.json()['access_token']}"}
    assert client.get(f"/api/admin/analytics/guide?scenic_area_id={scenic.json()['id']}&start_date=2026-07-01&end_date=2026-07-07", headers=visitor_headers).status_code == 403


def test_insight_message_endpoint_enforces_scenic_and_date_filters(client: TestClient) -> None:
    login = client.post("/api/auth/admin-login", json={"username": "admin", "password": "123456"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    override = client.app.dependency_overrides[get_db]
    generator = override()
    db = next(generator)
    now = datetime.now(timezone.utc)
    try:
        visitor = User(username="risk-filter-user", role="visitor", nickname="筛选游客")
        first = ScenicArea(code="risk-first", name="风险景区一", is_enabled=True)
        second = ScenicArea(code="risk-second", name="风险景区二", is_enabled=True)
        db.add_all([visitor, first, second]); db.flush()
        for index, scenic in enumerate((first, second)):
            session = GuideSession(user_id=visitor.id, scenic_area_id=scenic.id, created_at=now)
            db.add(session); db.flush()
            question = GuideMessage(session_id=session.id, role="user", content=f"问题{index}", status="success", created_at=now)
            db.add(question); db.flush()
            db.add(GuideMessageInsight(
                scenic_area_id=scenic.id, guide_session_id=session.id, visitor_message_id=question.id,
                analysis_status="completed", normalized_question=f"摘要{index}", primary_topic="服务体验",
                topic_tags=["服务体验"], intent="投诉反馈", sentiment="negative", sentiment_score=-0.8,
                issue_type="响应速度", needs_attention=True, created_at=now,
            ))
        db.commit()
        first_id = first.id
    finally:
        generator.close()

    day = now.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
    response = client.get(
        f"/api/admin/insights/messages?scenic_area_id={first_id}&start_date={day}&end_date={day}&sentiment=negative",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["normalized_question"] == "摘要0"

    invalid = client.get(
        f"/api/admin/insights/messages?scenic_area_id={first_id}&start_date={day}&end_date={day}&sentiment=unknown",
        headers=headers,
    )
    assert invalid.status_code == 422
