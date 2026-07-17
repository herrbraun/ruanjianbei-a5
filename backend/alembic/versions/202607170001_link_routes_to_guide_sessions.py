"""link personalized routes to guide sessions

Revision ID: 202607170001
Revises: 202607160002
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa


revision = "202607170001"
down_revision = "202607160002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("guide_sessions", sa.Column("route_plan_id", sa.Integer(), nullable=True))
    op.add_column("guide_sessions", sa.Column("current_spot_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_guide_sessions_route_plan_id",
        "guide_sessions",
        "route_plans",
        ["route_plan_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_guide_sessions_current_spot_id",
        "guide_sessions",
        "scenic_spots",
        ["current_spot_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_guide_sessions_route_plan_id", "guide_sessions", ["route_plan_id"])
    op.create_index("ix_guide_sessions_current_spot_id", "guide_sessions", ["current_spot_id"])


def downgrade() -> None:
    op.drop_index("ix_guide_sessions_current_spot_id", table_name="guide_sessions")
    op.drop_index("ix_guide_sessions_route_plan_id", table_name="guide_sessions")
    op.drop_constraint("fk_guide_sessions_current_spot_id", "guide_sessions", type_="foreignkey")
    op.drop_constraint("fk_guide_sessions_route_plan_id", "guide_sessions", type_="foreignkey")
    op.drop_column("guide_sessions", "current_spot_id")
    op.drop_column("guide_sessions", "route_plan_id")
