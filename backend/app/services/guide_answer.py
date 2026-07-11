from __future__ import annotations

from dataclasses import dataclass
import re
from time import perf_counter
from typing import Any

import httpx

from app.config import settings


class GuideAnswerError(RuntimeError):
    pass


@dataclass(frozen=True)
class GuideGeneratedAnswer:
    content: str
    model: str
    duration_ms: int


_SOURCE_MARKER_PATTERN = re.compile(r"\s*\[(?:资料|來源|来源)\s*[0-9一二三四五六七八九十]+\]")


def strip_source_markers(content: str) -> str:
    """Keep references in structured UI data, never in visitor-facing prose or speech."""
    return _SOURCE_MARKER_PATTERN.sub("", content).strip()


def _source_context(hits: list[dict[str, Any]]) -> str:
    if not hits:
        return "（本次未检索到可用资料）"

    sections: list[str] = []
    for index, hit in enumerate(hits, start=1):
        source = hit.get("source_locator") or hit.get("knowledge_base_name") or "未知资料"
        title = hit.get("spot_name") or hit.get("section") or "资料片段"
        content = str(hit.get("content") or "")[:1000]
        sections.append(f"[资料{index}] 来源：{source}；主题：{title}\n{content}")
    return "\n\n".join(sections)


def _history_context(history: list[tuple[str, str]]) -> str:
    if not history:
        return "（这是本次会话的第一个问题）"
    return "\n".join(f"{'游客' if role == 'user' else '导览员'}：{content[:360]}" for role, content in history[-6:])


def _extract_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise GuideAnswerError("大模型返回缺少 choices")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str) and content.strip():
        return content.strip()
    raise GuideAnswerError("大模型没有返回有效回答")


def generate_guide_answer(
    *,
    query: str,
    hits: list[dict[str, Any]],
    scenic_area_name: str,
    profile_name: str,
    history: list[tuple[str, str]],
    client: httpx.Client | None = None,
) -> GuideGeneratedAnswer:
    if not settings.dashscope_api_key or settings.dashscope_api_key == "your_dashscope_api_key":
        raise GuideAnswerError("未配置 DASHSCOPE_API_KEY，无法生成导览回答")

    started = perf_counter()
    own_client = client is None
    active_client = client or httpx.Client(timeout=90.0)
    try:
        response = active_client.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.dashscope_api_key}", "Content-Type": "application/json"},
            json={
                "model": settings.llm_chat_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你是亲切、准确的中文景区数字导览员。只能依据提供的检索资料作答，不得编造。"
                            "若资料不足，请直接说明暂未在景区资料中找到答案。回答适合语音播报，控制在 450 个汉字以内；"
                            "不要在回答中出现资料编号、方括号引用、文件名、表号或任何来源标记；相关资料由产品界面单独展示。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"景区：{scenic_area_name}\n"
                            f"当前知识版本：{profile_name}\n"
                            f"最近会话：\n{_history_context(history)}\n\n"
                            f"本次问题：{query}\n\n"
                            f"检索资料：\n{_source_context(hits)}"
                        ),
                    },
                ],
                "temperature": 0.2,
                "max_tokens": 650,
                "stream": False,
            },
        )
        if response.is_error:
            raise GuideAnswerError(f"大模型调用失败（HTTP {response.status_code}）：{response.text[:300]}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise GuideAnswerError("大模型返回了无法解析的响应") from exc
        return GuideGeneratedAnswer(
            content=strip_source_markers(_extract_content(payload)),
            model=settings.llm_chat_model,
            duration_ms=round((perf_counter() - started) * 1000),
        )
    except httpx.HTTPError as exc:
        raise GuideAnswerError("大模型服务连接失败") from exc
    finally:
        if own_client:
            active_client.close()
