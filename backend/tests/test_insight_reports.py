from __future__ import annotations

import json
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from app.config import settings
from app.services.insight_report import generate_insight_report
from app.schemas.insights import InsightReportCreate
from pydantic import ValidationError
import pytest


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
