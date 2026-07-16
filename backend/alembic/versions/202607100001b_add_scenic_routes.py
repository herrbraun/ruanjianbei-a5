"""add scenic spots and routes

Revision ID: 202607100001
Revises: 202607080001
Create Date: 2026-07-10 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "202607100001b"
down_revision = "202607080001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scenic_spots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location", sa.String(length=120), nullable=True),
        sa.Column("opening_hours", sa.String(length=120), nullable=True),
        sa.Column("recommended_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("cover_image_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('enabled', 'disabled')", name="ck_scenic_spots_status"),
    )
    op.create_index("ix_scenic_spots_id", "scenic_spots", ["id"])
    op.create_index("ix_scenic_spots_name", "scenic_spots", ["name"])

    op.create_table(
        "spot_tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("spot_id", sa.Integer(), sa.ForeignKey("scenic_spots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("spot_id", "name", name="uq_spot_tags_spot_name"),
    )
    op.create_index("ix_spot_tags_id", "spot_tags", ["id"])
    op.create_index("ix_spot_tags_spot_id", "spot_tags", ["spot_id"])
    op.create_index("ix_spot_tags_name", "spot_tags", ["name"])

    op.create_table(
        "route_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("interest", sa.String(length=100), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("total_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_route_plans_id", "route_plans", ["id"])
    op.create_index("ix_route_plans_user_id", "route_plans", ["user_id"])

    op.create_table(
        "route_spots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("route_plan_id", sa.Integer(), sa.ForeignKey("route_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("spot_id", sa.Integer(), sa.ForeignKey("scenic_spots.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("stay_minutes", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
    )
    op.create_index("ix_route_spots_id", "route_spots", ["id"])
    op.create_index("ix_route_spots_route_plan_id", "route_spots", ["route_plan_id"])
    op.create_index("ix_route_spots_spot_id", "route_spots", ["spot_id"])

    op.create_table(
        "route_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("route_plan_id", sa.Integer(), sa.ForeignKey("route_plans.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_route_feedback_rating"),
    )
    op.create_index("ix_route_feedback_id", "route_feedback", ["id"])
    op.create_index("ix_route_feedback_user_id", "route_feedback", ["user_id"])

def downgrade() -> None:
    op.drop_index("ix_route_feedback_user_id", table_name="route_feedback")
    op.drop_index("ix_route_feedback_id", table_name="route_feedback")
    op.drop_table("route_feedback")
    op.drop_index("ix_route_spots_spot_id", table_name="route_spots")
    op.drop_index("ix_route_spots_route_plan_id", table_name="route_spots")
    op.drop_index("ix_route_spots_id", table_name="route_spots")
    op.drop_table("route_spots")
    op.drop_index("ix_route_plans_user_id", table_name="route_plans")
    op.drop_index("ix_route_plans_id", table_name="route_plans")
    op.drop_table("route_plans")
    op.drop_index("ix_spot_tags_name", table_name="spot_tags")
    op.drop_index("ix_spot_tags_spot_id", table_name="spot_tags")
    op.drop_index("ix_spot_tags_id", table_name="spot_tags")
    op.drop_table("spot_tags")
    op.drop_index("ix_scenic_spots_name", table_name="scenic_spots")
    op.drop_index("ix_scenic_spots_id", table_name="scenic_spots")
    op.drop_table("scenic_spots")
