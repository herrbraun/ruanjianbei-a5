"""add visitor insights, guide feedback, and reports

Revision ID: 202607160002
Revises: 202607160001
Create Date: 2026-07-16
"""

from alembic import op
import sqlalchemy as sa

revision = "202607160002"
down_revision = "202607160001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guide_message_insights",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scenic_area_id", sa.Integer(), sa.ForeignKey("scenic_areas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("guide_session_id", sa.Integer(), sa.ForeignKey("guide_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("visitor_message_id", sa.Integer(), sa.ForeignKey("guide_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assistant_message_id", sa.Integer(), sa.ForeignKey("guide_messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("normalized_question", sa.String(120)), sa.Column("primary_topic", sa.String(50)), sa.Column("topic_tags", sa.JSON()),
        sa.Column("intent", sa.String(50)), sa.Column("sentiment", sa.String(20)), sa.Column("sentiment_score", sa.Float()),
        sa.Column("issue_type", sa.String(50)), sa.Column("needs_attention", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("resolution_status", sa.String(20), server_default="unresolved", nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)), sa.Column("resolved_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("analysis_status", sa.String(20), server_default="pending", nullable=False), sa.Column("analysis_model", sa.String(100)),
        sa.Column("analysis_attempts", sa.Integer(), server_default="0", nullable=False), sa.Column("error_message", sa.Text()),
        sa.Column("analyzed_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("visitor_message_id", name="uq_guide_message_insights_visitor_message"),
        sa.CheckConstraint("analysis_status IN ('pending','processing','completed','failed')", name="ck_guide_message_insights_analysis_status"),
        sa.CheckConstraint("sentiment IS NULL OR sentiment IN ('positive','neutral','negative')", name="ck_guide_message_insights_sentiment"),
        sa.CheckConstraint("sentiment_score IS NULL OR (sentiment_score >= -1 AND sentiment_score <= 1)", name="ck_guide_message_insights_sentiment_score"),
        sa.CheckConstraint("resolution_status IN ('unresolved','resolved')", name="ck_guide_message_insights_resolution_status"),
    )
    op.create_index("ix_guide_insights_scenic_created", "guide_message_insights", ["scenic_area_id", "created_at"])
    op.create_index("ix_guide_insights_scenic_sentiment_created", "guide_message_insights", ["scenic_area_id", "sentiment", "created_at"])
    op.create_index("ix_guide_insights_status_updated", "guide_message_insights", ["analysis_status", "updated_at"])
    op.create_index("ix_guide_insights_attention_resolution_created", "guide_message_insights", ["needs_attention", "resolution_status", "created_at"])

    op.create_table(
        "guide_feedbacks",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("guide_session_id", sa.Integer(), sa.ForeignKey("guide_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("scenic_area_id", sa.Integer(), sa.ForeignKey("scenic_areas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False), sa.Column("tags", sa.JSON(), nullable=False), sa.Column("comment", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("guide_session_id", name="uq_guide_feedbacks_session"), sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_guide_feedbacks_rating"),
    )
    op.create_index("ix_guide_feedbacks_scenic_created", "guide_feedbacks", ["scenic_area_id", "created_at"])

    op.create_table(
        "scenic_insight_reports",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("scenic_area_id", sa.Integer(), sa.ForeignKey("scenic_areas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_type", sa.String(20), nullable=False), sa.Column("period_start", sa.Date(), nullable=False), sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("metrics_snapshot", sa.JSON(), nullable=False), sa.Column("summary", sa.Text()), sa.Column("attention_points", sa.JSON()), sa.Column("risk_findings", sa.JSON()), sa.Column("recommendations", sa.JSON()),
        sa.Column("generation_status", sa.String(20), server_default="pending", nullable=False), sa.Column("generation_model", sa.String(100)), sa.Column("error_message", sa.Text()),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("generated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("period_type IN ('daily','weekly')", name="ck_scenic_insight_reports_period_type"),
        sa.CheckConstraint("generation_status IN ('pending','processing','completed','failed')", name="ck_scenic_insight_reports_generation_status"),
    )
    op.create_index("ix_scenic_insight_reports_scenic_period", "scenic_insight_reports", ["scenic_area_id", "period_start", "period_end"])


def downgrade() -> None:
    op.drop_table("scenic_insight_reports")
    op.drop_table("guide_feedbacks")
    op.drop_table("guide_message_insights")
