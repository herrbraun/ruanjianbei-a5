from __future__ import annotations

import json
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from app.config import settings
from app.services.insight_report import generate_insight_report


def test_report_generator_uses_only_aggregate_snapshot() -> None:
    snapshot = {"service_visitors": 20, "question_count": 35, "average_rating": 4.6, "top_topics": [{"name": "历史文化", "count": 10}]}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        prompt = body["messages"][1]["content"]
        assert "20" in prompt and "历史文化" in prompt
        assert "username" not in prompt and "游客原始问题" not in prompt
        content = {"summary": "整体体验良好", "attention_points": ["历史文化关注度高", "满意度稳定", "服务规模增长"], "risk_findings": ["暂无显著风险"], "recommendations": ["增加文化讲解", "持续关注评价", "优化热门问答"]}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}]})

    with patch.object(settings, "dashscope_api_key", "test-key"), patch.object(settings, "insight_report_model", "qwen-report-test"):
        result = generate_insight_report(snapshot, client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert result.summary == "整体体验良好"
    assert len(result.recommendations) == 3


def test_insight_report_endpoints_require_admin(client: TestClient) -> None:
    visitor = client.post("/api/auth/visitor-register", json={"username": "reportvisitor", "password": "password123"})
    headers = {"Authorization": f"Bearer {visitor.json()['access_token']}"}
    assert client.get("/api/admin/insight-reports", headers=headers).status_code == 403
