from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import httpx
from pydantic import ValidationError

from app.config import settings
from app.database import SessionLocal
from app.models.guide import ScenicInsightReport
from app.schemas.insights import ReportNarrative


class InsightReportError(RuntimeError):
    pass


def generate_insight_report(snapshot: dict, *, client: httpx.Client | None = None) -> ReportNarrative:
    if not settings.dashscope_api_key or settings.dashscope_api_key == "your_dashscope_api_key":
        raise InsightReportError("未配置 DASHSCOPE_API_KEY，无法生成感受度报告")
    own = client is None
    active = client or httpx.Client(timeout=60.0)
    try:
        response = active.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.dashscope_api_key}", "Content-Type": "application/json"},
            json={
                "model": settings.insight_report_model,
                "messages": [
                    {"role": "system", "content": "你是景区运营分析师。只能依据聚合指标输出纯JSON，不得改写数字。字段为summary、attention_points(恰好3条)、risk_findings、recommendations(3至5条)。"},
                    {"role": "user", "content": json.dumps(snapshot, ensure_ascii=False)},
                ],
                "temperature": 0.2,
                "stream": False,
            },
        )
        if response.is_error:
            raise InsightReportError(f"报告模型调用失败（HTTP {response.status_code}）")
        try:
            raw = response.json()["choices"][0]["message"]["content"]
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.IGNORECASE)
            return ReportNarrative.model_validate(json.loads(cleaned))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as exc:
            raise InsightReportError("报告模型返回格式无效") from exc
    except httpx.HTTPError as exc:
        raise InsightReportError("报告模型连接失败") from exc
    finally:
        if own:
            active.close()


def process_report(report_id: int) -> None:
    with SessionLocal() as db:
        report = db.get(ScenicInsightReport, report_id)
        if report is None or report.generation_status not in {"pending", "failed"}:
            return
        report.generation_status = "processing"
        report.error_message = None
        db.commit()
        try:
            narrative = generate_insight_report(report.metrics_snapshot)
            report.summary = narrative.summary
            report.attention_points = narrative.attention_points
            report.risk_findings = narrative.risk_findings
            report.recommendations = narrative.recommendations
            report.generation_model = settings.insight_report_model
            report.generation_status = "completed"
            report.generated_at = datetime.now(timezone.utc)
        except Exception as exc:
            report.generation_status = "failed"
            report.error_message = str(exc)[:2000]
        db.commit()
