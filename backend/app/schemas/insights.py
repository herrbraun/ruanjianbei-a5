from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TOPICS = ("历史文化", "景点特色", "演出活动", "开放时间", "游览路线", "交通停车", "门票价格", "餐饮购物", "公共设施", "无障碍与特殊需求", "服务体验", "其他")
INTENTS = ("知识咨询", "路线推荐", "服务咨询", "投诉反馈", "闲聊互动", "其他")
ISSUE_TYPES = ("排队时间", "路线指引", "价格问题", "环境卫生", "工作人员服务", "数字人回答不准确", "响应速度", "语音或数字人体验", "设施问题", "无明确问题")


class InteractionInsightResult(BaseModel):
    normalized_question: str = Field(min_length=1, max_length=30)
    primary_topic: str
    topic_tags: list[str] = Field(min_length=1)
    intent: str
    sentiment: Literal["positive", "neutral", "negative"]
    sentiment_score: float = Field(ge=-1, le=1)
    issue_type: str
    needs_attention: bool

    @model_validator(mode="after")
    def validate_fixed_labels(self) -> "InteractionInsightResult":
        if self.primary_topic not in TOPICS or any(tag not in TOPICS for tag in self.topic_tags):
            raise ValueError("主题必须来自固定分类")
        if self.primary_topic not in self.topic_tags:
            raise ValueError("主要主题必须包含在主题标签中")
        if self.intent not in INTENTS:
            raise ValueError("意图必须来自固定分类")
        if self.issue_type not in ISSUE_TYPES:
            raise ValueError("问题类型必须来自固定分类")
        self.topic_tags = list(dict.fromkeys(self.topic_tags))
        return self


class InsightReportCreate(BaseModel):
    scenic_area_id: int = Field(gt=0)
    period_type: Literal["daily", "weekly"]
    period_start: date
    period_end: date


class InsightReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    scenic_area_id: int
    period_type: str
    period_start: date
    period_end: date
    metrics_snapshot: dict
    summary: str | None
    attention_points: list[str] | None
    risk_findings: list[str] | None
    recommendations: list[str] | None
    generation_status: str
    generation_model: str | None
    error_message: str | None
    generated_at: datetime | None
    created_at: datetime


class ReportNarrative(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)
    attention_points: list[str] = Field(min_length=3, max_length=3)
    risk_findings: list[str] = Field(min_length=1, max_length=10)
    recommendations: list[str] = Field(min_length=3, max_length=5)


class InsightResolve(BaseModel):
    resolved: bool = True
