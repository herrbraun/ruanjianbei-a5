"""add insight report scheduling and durable generation

Revision ID: 202607170003
Revises: 202607170002
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa


revision = "202607170003"
down_revision = "202607170002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scenic_insight_reports",
        sa.Column("trigger_source", sa.String(length=20), server_default=sa.text("'manual'"), nullable=False),
    )
    op.add_column("scenic_insight_reports", sa.Column("deduplication_key", sa.String(length=160), nullable=True))
    op.add_column(
        "scenic_insight_reports",
        sa.Column("generation_attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "scenic_insight_reports",
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_scenic_insight_reports_trigger_source",
        "scenic_insight_reports",
        "trigger_source IN ('manual','scheduled')",
    )
    op.create_unique_constraint(
        "uq_scenic_insight_reports_deduplication_key",
        "scenic_insight_reports",
        ["deduplication_key"],
    )
    op.create_table(
        "insight_report_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "scenic_area_id",
            sa.Integer(),
            sa.ForeignKey("scenic_areas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("daily_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("daily_run_time", sa.Time(), server_default=sa.text("'00:10:00'"), nullable=False),
        sa.Column("weekly_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("weekly_weekday", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("weekly_run_time", sa.Time(), server_default=sa.text("'00:20:00'"), nullable=False),
        sa.Column("timezone", sa.String(length=64), server_default=sa.text("'Asia/Shanghai'"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("weekly_weekday BETWEEN 0 AND 6", name="ck_insight_report_schedules_weekday"),
        sa.UniqueConstraint("scenic_area_id", name="uq_insight_report_schedules_scenic_area"),
    )
    op.execute(
        """
        INSERT INTO insight_report_schedules (scenic_area_id)
        SELECT id FROM scenic_areas WHERE is_enabled = true
        ON CONFLICT (scenic_area_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("insight_report_schedules")
    op.drop_constraint(
        "uq_scenic_insight_reports_deduplication_key",
        "scenic_insight_reports",
        type_="unique",
    )
    op.drop_constraint(
        "ck_scenic_insight_reports_trigger_source",
        "scenic_insight_reports",
        type_="check",
    )
    op.drop_column("scenic_insight_reports", "processing_started_at")
    op.drop_column("scenic_insight_reports", "generation_attempts")
    op.drop_column("scenic_insight_reports", "deduplication_key")
    op.drop_column("scenic_insight_reports", "trigger_source")
