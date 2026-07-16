"""complete developer B data model

Revision ID: 202607100002
Revises: 202607100001
Create Date: 2026-07-10 18:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "202607100002"
down_revision = "202607100001b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("scenic_spots", "location", type_=sa.String(length=500), existing_type=sa.String(length=120))
    op.alter_column("scenic_spots", "opening_hours", type_=sa.String(length=1000), existing_type=sa.String(length=120))
    op.alter_column("scenic_spots", "cover_image_url", type_=sa.String(length=1000), existing_type=sa.String(length=500))
    op.add_column("scenic_spots", sa.Column("external_id", sa.String(length=30), nullable=True))
    op.add_column(
        "scenic_spots",
        sa.Column("scenic_area", sa.String(length=120), server_default="灵山胜境", nullable=False),
    )
    op.add_column(
        "scenic_spots",
        sa.Column("spot_type", sa.String(length=20), server_default="attraction", nullable=False),
    )
    op.add_column("scenic_spots", sa.Column("landscape_parameters", sa.Text(), nullable=True))
    op.add_column("scenic_spots", sa.Column("cultural_context", sa.Text(), nullable=True))
    op.add_column("scenic_spots", sa.Column("highlights", sa.Text(), nullable=True))
    op.add_column("scenic_spots", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("scenic_spots", sa.Column("source_name", sa.String(length=255), nullable=True))
    op.create_unique_constraint("uq_scenic_spots_external_id", "scenic_spots", ["external_id"])
    op.create_index("ix_scenic_spots_external_id", "scenic_spots", ["external_id"])
    op.create_index("ix_scenic_spots_scenic_area", "scenic_spots", ["scenic_area"])
    op.create_index("ix_scenic_spots_spot_type", "scenic_spots", ["spot_type"])
    op.create_check_constraint(
        "ck_scenic_spots_type",
        "scenic_spots",
        "spot_type IN ('attraction', 'area', 'service')",
    )

    op.create_table(
        "spot_media_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("spot_id", sa.Integer(), sa.ForeignKey("scenic_spots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("media_type", sa.String(length=20), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="enabled", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("media_type IN ('image', 'video', 'audio')", name="ck_spot_media_type"),
        sa.CheckConstraint("status IN ('enabled', 'disabled')", name="ck_spot_media_status"),
        sa.UniqueConstraint("spot_id", "url", name="uq_spot_media_spot_url"),
    )
    op.create_index("ix_spot_media_assets_id", "spot_media_assets", ["id"])
    op.create_index("ix_spot_media_assets_spot_id", "spot_media_assets", ["spot_id"])

    op.create_table(
        "route_recommendation_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tag_match_weight", sa.Integer(), server_default="100", nullable=False),
        sa.Column("priority_weight", sa.Numeric(6, 2), server_default="1", nullable=False),
        sa.Column("max_spots", sa.Integer(), server_default="12", nullable=False),
        sa.Column("include_service_points", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("tag_match_weight BETWEEN 0 AND 1000", name="ck_route_settings_tag_weight"),
        sa.CheckConstraint("priority_weight BETWEEN 0 AND 100", name="ck_route_settings_priority_weight"),
        sa.CheckConstraint("max_spots BETWEEN 1 AND 30", name="ck_route_settings_max_spots"),
    )

    op.add_column("route_plans", sa.Column("start_spot_id", sa.Integer(), nullable=True))
    op.add_column(
        "route_plans",
        sa.Column("preference", sa.String(length=20), server_default="balanced", nullable=False),
    )
    op.create_foreign_key(
        "fk_route_plans_start_spot_id",
        "route_plans",
        "scenic_spots",
        ["start_spot_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_route_plans_start_spot_id", "route_plans", ["start_spot_id"])
    op.create_check_constraint(
        "ck_route_plans_preference",
        "route_plans",
        "preference IN ('balanced', 'priority', 'more_spots')",
    )
    op.create_unique_constraint("uq_route_spots_plan_sequence", "route_spots", ["route_plan_id", "sequence"])

    op.create_table(
        "visitor_behavior_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_record_key", sa.String(length=64), nullable=False),
        sa.Column("tourist_id", sa.String(length=30), nullable=False),
        sa.Column("user_nickname", sa.String(length=100), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("gender", sa.String(length=10), nullable=False),
        sa.Column("attraction_name", sa.String(length=120), nullable=False),
        sa.Column("attraction_content", sa.Text(), nullable=False),
        sa.Column("attraction_type", sa.String(length=50), nullable=False),
        sa.Column("visit_date", sa.Date(), nullable=False),
        sa.Column("stay_duration_hours", sa.Numeric(6, 2), nullable=False),
        sa.Column("ticket_cost", sa.Numeric(10, 2), nullable=False),
        sa.Column("food_cost", sa.Numeric(10, 2), nullable=False),
        sa.Column("shopping_cost", sa.Numeric(10, 2), nullable=False),
        sa.Column("transport_cost", sa.Numeric(10, 2), nullable=False),
        sa.Column("entertainment_cost", sa.Numeric(10, 2), nullable=False),
        sa.Column("total_cost", sa.Numeric(10, 2), nullable=False),
        sa.Column("group_size", sa.Integer(), nullable=False),
        sa.Column("satisfaction", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("satisfaction BETWEEN 1 AND 5", name="ck_behavior_satisfaction"),
        sa.UniqueConstraint("source_record_key", name="uq_behavior_source_record_key"),
    )
    op.create_index("ix_visitor_behavior_records_id", "visitor_behavior_records", ["id"])
    op.create_index("ix_visitor_behavior_records_source_record_key", "visitor_behavior_records", ["source_record_key"])
    op.create_index("ix_visitor_behavior_records_tourist_id", "visitor_behavior_records", ["tourist_id"])
    op.create_index("ix_visitor_behavior_records_attraction_name", "visitor_behavior_records", ["attraction_name"])
    op.create_index("ix_visitor_behavior_records_attraction_type", "visitor_behavior_records", ["attraction_type"])
    op.create_index("ix_visitor_behavior_records_visit_date", "visitor_behavior_records", ["visit_date"])


def downgrade() -> None:
    op.drop_index("ix_visitor_behavior_records_visit_date", table_name="visitor_behavior_records")
    op.drop_index("ix_visitor_behavior_records_attraction_type", table_name="visitor_behavior_records")
    op.drop_index("ix_visitor_behavior_records_attraction_name", table_name="visitor_behavior_records")
    op.drop_index("ix_visitor_behavior_records_tourist_id", table_name="visitor_behavior_records")
    op.drop_index("ix_visitor_behavior_records_source_record_key", table_name="visitor_behavior_records")
    op.drop_index("ix_visitor_behavior_records_id", table_name="visitor_behavior_records")
    op.drop_table("visitor_behavior_records")
    op.drop_constraint("uq_route_spots_plan_sequence", "route_spots", type_="unique")
    op.drop_constraint("ck_route_plans_preference", "route_plans", type_="check")
    op.drop_index("ix_route_plans_start_spot_id", table_name="route_plans")
    op.drop_constraint("fk_route_plans_start_spot_id", "route_plans", type_="foreignkey")
    op.drop_column("route_plans", "preference")
    op.drop_column("route_plans", "start_spot_id")
    op.drop_table("route_recommendation_settings")
    op.drop_index("ix_spot_media_assets_spot_id", table_name="spot_media_assets")
    op.drop_index("ix_spot_media_assets_id", table_name="spot_media_assets")
    op.drop_table("spot_media_assets")
    op.drop_constraint("ck_scenic_spots_type", "scenic_spots", type_="check")
    op.drop_index("ix_scenic_spots_spot_type", table_name="scenic_spots")
    op.drop_index("ix_scenic_spots_scenic_area", table_name="scenic_spots")
    op.drop_index("ix_scenic_spots_external_id", table_name="scenic_spots")
    op.drop_constraint("uq_scenic_spots_external_id", "scenic_spots", type_="unique")
    op.drop_column("scenic_spots", "source_name")
    op.drop_column("scenic_spots", "notes")
    op.drop_column("scenic_spots", "highlights")
    op.drop_column("scenic_spots", "cultural_context")
    op.drop_column("scenic_spots", "landscape_parameters")
    op.drop_column("scenic_spots", "spot_type")
    op.drop_column("scenic_spots", "scenic_area")
    op.drop_column("scenic_spots", "external_id")
    op.alter_column("scenic_spots", "cover_image_url", type_=sa.String(length=500), existing_type=sa.String(length=1000))
    op.alter_column("scenic_spots", "opening_hours", type_=sa.String(length=120), existing_type=sa.String(length=1000))
    op.alter_column("scenic_spots", "location", type_=sa.String(length=120), existing_type=sa.String(length=500))
