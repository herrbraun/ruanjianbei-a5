"""add latest visitor tts latency

Revision ID: 202607190001
Revises: 202607170004
Create Date: 2026-07-19
"""

from alembic import op
import sqlalchemy as sa


revision = "202607190001"
down_revision = "202607170004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tts_provider_settings", sa.Column("last_visitor_first_chunk_ms", sa.Integer(), nullable=True))
    op.add_column(
        "tts_provider_settings",
        sa.Column("last_visitor_first_chunk_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tts_provider_settings", "last_visitor_first_chunk_at")
    op.drop_column("tts_provider_settings", "last_visitor_first_chunk_ms")
