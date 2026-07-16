from __future__ import annotations

import json
import re

import httpx
from pydantic import ValidationError

from app.config import settings
from app.schemas.insights import INTENTS, ISSUE_TYPES, TOPICS, InteractionInsightResult


class InteractionInsightError(RuntimeError):
    pass


def _content(payload: dict) -> str:
    try:
        value = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise InteractionInsightError("洞察模型返回缺少有效内容") from exc
    if not isinstance(value, str) or not value.strip():
        raise InteractionInsightError("洞察模型返回内容为空")
    return value.strip()


def _parse(value: str) -> InteractionInsightResult:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", value.strip(), flags=re.IGNORECASE)
    try:
        return InteractionInsightResult.model_validate(json.loads(cleaned))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise InteractionInsightError(f"洞察结果格式无效：{exc}") from exc


def analyze_interaction(
    question: str,
    answer: str,
    answer_status: str,
    *,
    client: httpx.Client | None = None,
) -> InteractionInsightResult:
    if not settings.dashscope_api_key or settings.dashscope_api_key == "your_dashscope_api_key":
        raise InteractionInsightError("未配置 DASHSCOPE_API_KEY，无法分析游客感受")
    own_client = client is None
    active = client or httpx.Client(timeout=60.0)
    system = (
        "你是景区游客交互分析器，只输出一个 JSON 对象。"
        f"主题只能从{list(TOPICS)}选择；意图只能从{list(INTENTS)}选择；问题类型只能从{list(ISSUE_TYPES)}选择。"
        "sentiment 只能为 positive、neutral、negative，sentiment_score 范围为 -1 到 1。"
        "normalized_question 不超过30个中文字符，不含游客身份；primary_topic 必须包含在 topic_tags 中。"
    )
    user = f"游客问题：{question}\n数字人回答状态：{answer_status}\n数字人回答：{answer}"
    try:
        for attempt in range(2):
            response = active.post(
                f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.dashscope_api_key}", "Content-Type": "application/json"},
                json={"model": settings.insight_analysis_model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "temperature": 0.1, "stream": False},
            )
            if response.is_error:
                raise InteractionInsightError(f"洞察模型调用失败（HTTP {response.status_code}）")
            raw = _content(response.json())
            try:
                return _parse(raw)
            except InteractionInsightError:
                if attempt:
                    raise
                user = f"请把下面内容修复为符合既定字段和枚举的纯 JSON：\n{raw}"
        raise InteractionInsightError("洞察模型没有返回有效结果")
    except httpx.HTTPError as exc:
        raise InteractionInsightError("洞察模型连接失败") from exc
    finally:
        if own_client:
            active.close()
