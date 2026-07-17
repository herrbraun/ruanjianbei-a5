"""add configurable tts providers

Revision ID: 202607170004
Revises: 202607170003
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa


revision = "202607170004"
down_revision = "202607170003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "digital_humans",
        sa.Column("tts_provider", sa.String(length=30), server_default=sa.text("'volcengine'"), nullable=False),
    )
    op.create_check_constraint(
        "ck_digital_humans_tts_provider",
        "digital_humans",
        "tts_provider IN ('volcengine', 'dashscope')",
    )
    op.create_table(
        "tts_provider_settings",
        sa.Column("provider", sa.String(length=30), primary_key=True),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_fallback", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("default_voice", sa.String(length=100), nullable=False),
        sa.Column("first_chunk_timeout_ms", sa.Integer(), server_default=sa.text("4500"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("provider IN ('volcengine', 'dashscope')", name="ck_tts_provider_settings_provider"),
        sa.CheckConstraint(
            "first_chunk_timeout_ms BETWEEN 500 AND 10000",
            name="ck_tts_provider_settings_first_chunk_timeout",
        ),
    )
    op.create_index(
        "uq_tts_provider_settings_one_default",
        "tts_provider_settings",
        ["is_default"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )
    op.create_index(
        "uq_tts_provider_settings_one_fallback",
        "tts_provider_settings",
        ["is_fallback"],
        unique=True,
        postgresql_where=sa.text("is_fallback"),
    )
    op.execute(
        """
        INSERT INTO tts_provider_settings
            (provider, display_name, is_enabled, is_default, is_fallback, model, default_voice, first_chunk_timeout_ms)
        VALUES
            ('volcengine', '火山引擎实时语音', true, true, false, 'seed-tts-2.0', 'zh_female_vv_uranus_bigtts', 4500),
            ('dashscope', '阿里云百炼千问语音', true, false, true, 'qwen3-tts-instruct-flash', 'Cherry', 4500)
        """
    )
    op.execute(
        """
        UPDATE digital_humans
        SET tts_provider = 'volcengine',
            tts_voice = CASE
                WHEN gender = 'male' THEN 'zh_male_dayi_uranus_bigtts'
                ELSE 'zh_female_vv_uranus_bigtts'
            END
        """
    )


def downgrade() -> None:
    op.drop_index("uq_tts_provider_settings_one_fallback", table_name="tts_provider_settings")
    op.drop_index("uq_tts_provider_settings_one_default", table_name="tts_provider_settings")
    op.drop_table("tts_provider_settings")
    op.drop_constraint("ck_digital_humans_tts_provider", "digital_humans", type_="check")
    op.drop_column("digital_humans", "tts_provider")
