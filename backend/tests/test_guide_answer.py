from __future__ import annotations

import json
from unittest.mock import patch

import httpx

from app.config import settings
from app.services.guide_answer import generate_guide_answer


def test_generate_guide_answer_keeps_sources_and_recent_history() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "qwen-plus-test"
        assert "[资料1]" in body["messages"][1]["content"]
        assert "previous question" in body["messages"][1]["content"]
        return httpx.Response(200, json={"choices": [{"message": {"content": "Grounded guide answer [资料1]"}}]})

    with (
        patch.object(settings, "dashscope_api_key", "test-key"),
        patch.object(settings, "llm_base_url", "https://dashscope.test/compatible-mode/v1"),
        patch.object(settings, "llm_chat_model", "qwen-plus-test"),
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
    ):
        result = generate_guide_answer(
            query="current question",
            hits=[{"knowledge_base_name": "guide knowledge", "spot_name": "spot", "content": "grounded fact"}],
            scenic_area_name="Lingshan",
            profile_name="Lingshan active profile",
            history=[("user", "previous question"), ("assistant", "previous answer")],
            client=client,
        )

    assert result.content == "Grounded guide answer"
    assert result.model == "qwen-plus-test"
    assert result.duration_ms >= 0
