"""add recoverable anonymous visitors

Revision ID: 202607170002
Revises: 202607170001
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa


revision = "202607170002"
down_revision = "202607170001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_guest", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("users", sa.Column("guest_key_hash", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("guest_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_guest_key_hash", "users", ["guest_key_hash"], unique=True)
    op.create_index("ix_users_guest_expires_at", "users", ["guest_expires_at"])


def downgrade() -> None:
    op.drop_index("ix_users_guest_expires_at", table_name="users")
    op.drop_index("ix_users_guest_key_hash", table_name="users")
    op.drop_column("users", "last_seen_at")
    op.drop_column("users", "guest_expires_at")
    op.drop_column("users", "guest_key_hash")
    op.drop_column("users", "is_guest")
