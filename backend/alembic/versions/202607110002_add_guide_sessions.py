"""add visitor guide sessions and messages

Revision ID: 202607110002
Revises: 202607110001
Create Date: 2026-07-11 12:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "202607110002"
down_revision = "202607110001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guide_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scenic_area_id", sa.Integer(), sa.ForeignKey("scenic_areas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("initial_rag_profile_id", sa.Integer(), sa.ForeignKey("rag_profiles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_guide_sessions_user_id", "guide_sessions", ["user_id"])
    op.create_index("ix_guide_sessions_scenic_area_id", "guide_sessions", ["scenic_area_id"])
    op.create_index("ix_guide_sessions_initial_rag_profile_id", "guide_sessions", ["initial_rag_profile_id"])
    op.create_index("ix_guide_sessions_user_updated", "guide_sessions", ["user_id", "updated_at"])

    op.create_table(
        "guide_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("guide_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("input_mode", sa.String(length=20), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("rag_profile_id", sa.Integer(), sa.ForeignKey("rag_profiles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sources", sa.JSON(), nullable=True),
        sa.Column("answer_model", sa.String(length=100), nullable=True),
        sa.Column("answer_duration_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'success'")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_guide_messages_role"),
        sa.CheckConstraint("input_mode IS NULL OR input_mode IN ('text', 'voice')", name="ck_guide_messages_input_mode"),
        sa.CheckConstraint("status IN ('success', 'failed')", name="ck_guide_messages_status"),
    )
    op.create_index("ix_guide_messages_session_id", "guide_messages", ["session_id"])
    op.create_index("ix_guide_messages_rag_profile_id", "guide_messages", ["rag_profile_id"])
    op.create_index("ix_guide_messages_session_created", "guide_messages", ["session_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_guide_messages_session_created", table_name="guide_messages")
    op.drop_index("ix_guide_messages_rag_profile_id", table_name="guide_messages")
    op.drop_index("ix_guide_messages_session_id", table_name="guide_messages")
    op.drop_table("guide_messages")
    op.drop_index("ix_guide_sessions_user_updated", table_name="guide_sessions")
    op.drop_index("ix_guide_sessions_initial_rag_profile_id", table_name="guide_sessions")
    op.drop_index("ix_guide_sessions_scenic_area_id", table_name="guide_sessions")
    op.drop_index("ix_guide_sessions_user_id", table_name="guide_sessions")
    op.drop_table("guide_sessions")
