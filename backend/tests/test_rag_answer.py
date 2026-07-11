from __future__ import annotations

import json
from unittest.mock import patch

import httpx

from app.config import settings
from app.services.rag_answer import generate_rag_answer


def test_generate_rag_answer_calls_real_compatible_chat_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-key"
        assert body["model"] == "qwen-plus-test"
        assert "[资料1]" in body["messages"][1]["content"]
        assert "九龙灌浴几点表演" in body["messages"][1]["content"]
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "九龙灌浴的演出时间请以当天公告为准。[资料1]"}}]},
        )

    with (
        patch.object(settings, "dashscope_api_key", "test-key"),
        patch.object(settings, "llm_base_url", "https://dashscope.test/compatible-mode/v1"),
        patch.object(settings, "llm_chat_model", "qwen-plus-test"),
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
    ):
        result = generate_rag_answer(
            query="九龙灌浴几点表演？",
            hits=[
                {
                    "knowledge_base_name": "灵山结构化景点资料库",
                    "source_locator": "景点表第 6 行",
                    "spot_name": "九龙灌浴",
                    "content": "九龙灌浴是灵山胜境的动态景观。",
                }
            ],
            scenic_area_name="灵山胜境",
            profile_name="灵山正式版 RAG",
            client=client,
        )

    assert result.content.endswith("[资料1]")
    assert result.model == "qwen-plus-test"
    assert result.duration_ms >= 0
