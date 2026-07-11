"""add digital human avatar management

Revision ID: 202607110003
Revises: 202607110002
Create Date: 2026-07-11 19:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "202607110003"
down_revision = "202607110002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "digital_humans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=80), nullable=False, unique=True),
        sa.Column("gender", sa.String(length=20), nullable=False, server_default=sa.text("'unspecified'")),
        sa.Column("role_title", sa.String(length=120), nullable=False),
        sa.Column("introduction", sa.Text(), nullable=True),
        sa.Column("tts_voice", sa.String(length=100), nullable=False),
        sa.Column("tts_instructions", sa.Text(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("gender IN ('female', 'male', 'unspecified')", name="ck_digital_humans_gender"),
    )
    op.create_table(
        "avatar_variants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("digital_human_id", sa.Integer(), sa.ForeignKey("digital_humans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("outfit_name", sa.String(length=120), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False, server_default=sa.text("'v1'")),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False, unique=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("thumbnail_url", sa.String(length=500), nullable=True),
        sa.Column("validation_status", sa.String(length=20), nullable=False, server_default=sa.text("'ready'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("validation_status IN ('ready', 'failed')", name="ck_avatar_variants_validation_status"),
        sa.UniqueConstraint("digital_human_id", "outfit_name", "version", name="uq_avatar_variants_human_outfit_version"),
    )
    op.create_index("ix_avatar_variants_digital_human_id", "avatar_variants", ["digital_human_id"])
    op.create_table(
        "scenic_avatar_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scenic_area_id", sa.Integer(), sa.ForeignKey("scenic_areas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("avatar_variant_id", sa.Integer(), sa.ForeignKey("avatar_variants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("scenic_area_id", "avatar_variant_id", name="uq_scenic_avatar_configs_area_variant"),
    )
    op.create_index("ix_scenic_avatar_configs_scenic_area_id", "scenic_avatar_configs", ["scenic_area_id"])
    op.create_index("ix_scenic_avatar_configs_avatar_variant_id", "scenic_avatar_configs", ["avatar_variant_id"])
    op.create_index(
        "ix_scenic_avatar_configs_area_enabled_sort",
        "scenic_avatar_configs",
        ["scenic_area_id", "is_enabled", "sort_order"],
    )
    op.create_index(
        "uq_scenic_avatar_configs_one_default",
        "scenic_avatar_configs",
        ["scenic_area_id"],
        unique=True,
        postgresql_where=sa.text("is_default AND is_enabled"),
        sqlite_where=sa.text("is_default AND is_enabled"),
    )


def downgrade() -> None:
    op.drop_index("uq_scenic_avatar_configs_one_default", table_name="scenic_avatar_configs")
    op.drop_index("ix_scenic_avatar_configs_area_enabled_sort", table_name="scenic_avatar_configs")
    op.drop_index("ix_scenic_avatar_configs_avatar_variant_id", table_name="scenic_avatar_configs")
    op.drop_index("ix_scenic_avatar_configs_scenic_area_id", table_name="scenic_avatar_configs")
    op.drop_table("scenic_avatar_configs")
    op.drop_index("ix_avatar_variants_digital_human_id", table_name="avatar_variants")
    op.drop_table("avatar_variants")
    op.drop_table("digital_humans")
