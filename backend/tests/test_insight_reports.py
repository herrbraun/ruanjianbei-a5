from __future__ import annotations

import json
from datetime import date, datetime, time, timezone
from io import BytesIO
from unittest.mock import patch

import httpx
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base
from app.models.guide import InsightReportSchedule, ScenicInsightReport
from app.models.knowledge import ScenicArea
from app.services.insight_report import (
    build_report_docx,
    create_due_reports,
    generate_insight_report,
)
from app.schemas.insights import InsightReportCreate
from pydantic import ValidationError
import pytest


@pytest.fixture()
def report_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine)
    db = testing_session()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_report_generator_uses_only_aggregate_snapshot() -> None:
    snapshot = {"service_visitors": 20, "question_count": 35, "average_rating": 4.6, "top_topics": [{"name": "历史文化", "count": 10}]}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        prompt = body["messages"][1]["content"]
        assert "20" in prompt and "历史文化" in prompt
        assert "username" not in prompt and "游客原始问题" not in prompt
        content = {"summary": "整体体验良好", "attention_points": ["历史文化关注度高", "满意度稳定", "服务规模增长"], "risk_findings": ["暂无显著风险"], "recommendations": ["增加文化讲解", "持续关注评价", "优化热门问答"]}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}]})

    with patch.object(settings, "dashscope_api_key", "test-key"), patch.object(settings, "insight_report_model", "qwen-report-test"):
        result = generate_insight_report(snapshot, client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert result.summary == "整体体验良好"
    assert len(result.recommendations) == 3


def test_report_generator_repairs_invalid_structured_result_once() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json={"choices": [{"message": {"content": '{"summary":"内容不足"}'}}]})
        content = {"summary": "整体平稳", "attention_points": ["关注一", "关注二", "关注三"], "risk_findings": ["暂无显著风险"], "recommendations": ["建议一", "建议二", "建议三"]}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}]})

    with patch.object(settings, "dashscope_api_key", "test-key"):
        result = generate_insight_report({"question_count": 2}, client=httpx.Client(transport=httpx.MockTransport(handler)))

    assert calls == 2
    assert result.summary == "整体平稳"


def test_report_period_type_matches_date_range() -> None:
    InsightReportCreate(scenic_area_id=1, period_type="daily", period_start="2026-07-17", period_end="2026-07-17")
    InsightReportCreate(scenic_area_id=1, period_type="weekly", period_start="2026-07-11", period_end="2026-07-17")

    with pytest.raises(ValidationError):
        InsightReportCreate(scenic_area_id=1, period_type="daily", period_start="2026-07-16", period_end="2026-07-17")
    with pytest.raises(ValidationError):
        InsightReportCreate(scenic_area_id=1, period_type="weekly", period_start="2026-07-10", period_end="2026-07-17")


def test_insight_report_endpoints_require_admin(client: TestClient) -> None:
    visitor = client.post("/api/auth/visitor-register", json={"username": "reportvisitor", "password": "password123"})
    headers = {"Authorization": f"Bearer {visitor.json()['access_token']}"}
    assert client.get("/api/admin/insight-reports?scenic_area_id=1", headers=headers).status_code == 403

    admin = client.post("/api/auth/admin-login", json={"username": "admin", "password": "123456"})
    admin_headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}
    invalid_period = client.get("/api/admin/insights/messages?start_date=2026-07-01", headers=admin_headers)
    assert invalid_period.status_code == 422


def test_report_is_idempotent_and_schedule_is_configurable(client: TestClient) -> None:
    admin = client.post("/api/auth/admin-login", json={"username": "admin", "password": "123456"})
    headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}
    scenic = client.post(
        "/api/admin/scenic-areas",
        headers=headers,
        json={"code": "report-area", "name": "报告测试景区", "is_enabled": True},
    )
    assert scenic.status_code == 201
    scenic_area_id = scenic.json()["id"]

    schedule = client.get(
        f"/api/admin/insight-report-schedules/{scenic_area_id}",
        headers=headers,
    )
    assert schedule.status_code == 200
    assert schedule.json()["daily_enabled"] is True
    updated = client.put(
        f"/api/admin/insight-report-schedules/{scenic_area_id}",
        headers=headers,
        json={
            "daily_enabled": True,
            "daily_run_time": "01:15:00",
            "weekly_enabled": False,
            "weekly_weekday": 4,
            "weekly_run_time": "02:30:00",
            "timezone": "Asia/Shanghai",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["daily_run_time"] == "01:15:00"
    assert updated.json()["weekly_enabled"] is False

    payload = {
        "scenic_area_id": scenic_area_id,
        "period_type": "daily",
        "period_start": "2026-07-16",
        "period_end": "2026-07-16",
    }
    with patch("app.routers.insights.process_report"):
        first = client.post("/api/admin/insight-reports", headers=headers, json=payload)
        duplicate = client.post("/api/admin/insight-reports", headers=headers, json=payload)
    assert first.status_code == 202
    assert duplicate.status_code == 202
    assert duplicate.json()["id"] == first.json()["id"]
    assert duplicate.json()["generation_status"] == "pending"

    not_ready = client.get(
        f"/api/admin/insight-reports/{first.json()['id']}/export",
        headers=headers,
    )
    assert not_ready.status_code == 409


def test_completed_report_can_be_exported_as_valid_docx() -> None:
    report = ScenicInsightReport(
        scenic_area_id=1,
        period_type="daily",
        period_start=date(2026, 7, 16),
        period_end=date(2026, 7, 16),
        metrics_snapshot={
            "service_visitors": 0,
            "question_count": 0,
            "answer_success_rate": 0,
            "average_answer_duration_ms": None,
            "average_rating": None,
            "negative_rate": 0,
            "top_topics": [],
            "popular_questions": [],
        },
        summary="本周期暂无有效游客互动数据，暂不能形成趋势判断。",
        attention_points=["服务人次为零", "暂无有效问答", "暂无满意度评价"],
        risk_findings=["数据量不足，无法识别稳定风险"],
        recommendations=["确认导览入口正常开放", "持续收集游客互动", "下一周期继续观察数据"],
        generation_status="completed",
        generation_model="deterministic-empty-period",
        trigger_source="scheduled",
        generation_attempts=1,
        generated_at=datetime(2026, 7, 17, tzinfo=timezone.utc),
    )
    content = build_report_docx(report, "报告测试景区")
    document = Document(BytesIO(content))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "报告测试景区游客感受度日报" in text
    assert "本周期暂无有效游客互动数据" in text


def test_report_schedule_rejects_invalid_timezone(client: TestClient) -> None:
    admin = client.post("/api/auth/admin-login", json={"username": "admin", "password": "123456"})
    headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}
    scenic = client.post(
        "/api/admin/scenic-areas",
        headers=headers,
        json={"code": "timezone-area", "name": "时区测试景区", "is_enabled": True},
    )
    scenic_area_id = scenic.json()["id"]
    response = client.put(
        f"/api/admin/insight-report-schedules/{scenic_area_id}",
        headers=headers,
        json={
            "daily_enabled": True,
            "daily_run_time": "00:10:00",
            "weekly_enabled": True,
            "weekly_weekday": 0,
            "weekly_run_time": "00:20:00",
            "timezone": "Mars/Olympus",
        },
    )
    assert response.status_code == 422


def test_scheduler_catches_up_each_missing_daily_period(report_db: Session) -> None:
    scenic = ScenicArea(code="catchup-area", name="补偿测试景区", is_enabled=True)
    report_db.add(scenic)
    report_db.flush()
    report_db.add(
        InsightReportSchedule(
            scenic_area_id=scenic.id,
            daily_enabled=True,
            daily_run_time=time(0, 10),
            weekly_enabled=False,
            weekly_weekday=0,
            weekly_run_time=time(0, 20),
            timezone="Asia/Shanghai",
        )
    )
    report_db.add(
        ScenicInsightReport(
            scenic_area_id=scenic.id,
            period_type="daily",
            period_start=date(2026, 7, 15),
            period_end=date(2026, 7, 15),
            metrics_snapshot={},
            generation_status="completed",
            trigger_source="scheduled",
            deduplication_key="catchup-anchor",
        )
    )
    report_db.commit()

    created = create_due_reports(
        report_db,
        datetime(2026, 7, 20, 1, 0, tzinfo=timezone.utc),
    )
    assert len(created) == 4
    periods = list(
        report_db.scalars(
            select(ScenicInsightReport.period_end)
            .where(ScenicInsightReport.scenic_area_id == scenic.id)
            .order_by(ScenicInsightReport.period_end)
        )
    )
    assert periods == [
        date(2026, 7, 15),
        date(2026, 7, 16),
        date(2026, 7, 17),
        date(2026, 7, 18),
        date(2026, 7, 19),
    ]
    assert create_due_reports(
        report_db,
        datetime(2026, 7, 20, 1, 0, tzinfo=timezone.utc),
    ) == []


def test_scheduler_skips_disabled_scenic_area(report_db: Session) -> None:
    scenic = ScenicArea(code="disabled-area", name="停用景区", is_enabled=False)
    report_db.add(scenic)
    report_db.flush()
    report_db.add(
        InsightReportSchedule(
            scenic_area_id=scenic.id,
            daily_enabled=True,
            daily_run_time=time(0, 10),
            weekly_enabled=True,
            weekly_weekday=0,
            weekly_run_time=time(0, 20),
            timezone="Asia/Shanghai",
        )
    )
    report_db.commit()

    assert create_due_reports(
        report_db,
        datetime(2026, 7, 20, 1, 0, tzinfo=timezone.utc),
    ) == []
    assert report_db.scalar(
        select(ScenicInsightReport.id).where(
            ScenicInsightReport.scenic_area_id == scenic.id
        )
    ) is None
