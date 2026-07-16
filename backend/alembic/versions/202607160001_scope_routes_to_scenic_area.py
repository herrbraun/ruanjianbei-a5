"""scope route recommendations to one scenic area

Revision ID: 202607160001
Revises: 202607120001
Create Date: 2026-07-16
"""

from alembic import op
import sqlalchemy as sa


revision = "202607160001"
down_revision = "202607120001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("route_plans", sa.Column("scenic_area", sa.String(length=120), nullable=True))
    op.execute(
        """
        UPDATE route_plans AS plan
        SET scenic_area = COALESCE(
            (SELECT spot.scenic_area FROM scenic_spots AS spot WHERE spot.id = plan.start_spot_id),
            (
                SELECT spot.scenic_area
                FROM route_spots AS route_spot
                JOIN scenic_spots AS spot ON spot.id = route_spot.spot_id
                WHERE route_spot.route_plan_id = plan.id
                ORDER BY route_spot.sequence
                LIMIT 1
            ),
            '未指定景区'
        )
        """
    )
    op.alter_column("route_plans", "scenic_area", nullable=False)
    op.create_index("ix_route_plans_scenic_area", "route_plans", ["scenic_area"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_route_plans_scenic_area", table_name="route_plans")
    op.drop_column("route_plans", "scenic_area")
