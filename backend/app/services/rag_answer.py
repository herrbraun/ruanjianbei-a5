from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

import httpx

from app.config import settings


class AnswerGenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class GeneratedAnswer:
    content: str
    model: str
    duration_ms: int


def _context_text(hits: list[dict[str, Any]]) -> str:
    if not hits:
        return "（本次检索没有命中任何资料）"

    sections: list[str] = []
    for index, hit in enumerate(hits, start=1):
        source = hit.get("source_locator") or hit.get("knowledge_base_name") or "未知来源"
        spot = hit.get("spot_name") or hit.get("section") or "资料片段"
        content = str(hit.get("content") or "")[:1200]
        sections.append(f"[资料{index}] 来源：{source}；主题：{spot}\n{content}")
    return "\n\n".join(sections)


def _response_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AnswerGenerationError("大模型返回缺少 choices")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        parts = [item.get("text", "") for item in content if isinstance(item, dict)]
        combined = "".join(parts).strip()
        if combined:
            return combined
    raise AnswerGenerationError("大模型返回的回答内容为空")


def generate_rag_answer(
    query: str,
    hits: list[dict[str, Any]],
    scenic_area_name: str,
    profile_name: str,
    client: httpx.Client | None = None,
) -> GeneratedAnswer:
    if not settings.dashscope_api_key or settings.dashscope_api_key == "your_dashscope_api_key":
        raise AnswerGenerationError("未配置 DASHSCOPE_API_KEY，无法生成 AI 示例回答")

    started = perf_counter()
    own_client = client is None
    active_client = client or httpx.Client(timeout=90.0)
    try:
        response = active_client.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.dashscope_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.llm_chat_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你是景区导览知识库的回答预览器。只能依据提供的检索资料作答，"
                            "不得编造时间、地点、价格或文化事实。回答使用简洁自然的中文；"
                            "关键事实后用[资料1]这样的编号标注依据。资料不足时明确说明。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"景区：{scenic_area_name}\n"
                            f"RAG Profile：{profile_name}\n"
                            f"游客问题：{query}\n\n"
                            f"检索资料：\n{_context_text(hits)}"
                        ),
                    },
                ],
                "temperature": 0.2,
                "max_tokens": 800,
                "stream": False,
            },
        )
        if response.is_error:
            raise AnswerGenerationError(f"大模型调用失败（HTTP {response.status_code}）：{response.text[:300]}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise AnswerGenerationError("大模型返回了无法解析的响应") from exc
        return GeneratedAnswer(
            content=_response_content(payload),
            model=settings.llm_chat_model,
            duration_ms=round((perf_counter() - started) * 1000),
        )
    except httpx.HTTPError as exc:
        raise AnswerGenerationError("大模型服务连接失败") from exc
    finally:
        if own_client:
            active_client.close()
