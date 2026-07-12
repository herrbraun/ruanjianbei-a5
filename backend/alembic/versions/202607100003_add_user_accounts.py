"""add visitor account profile fields

Revision ID: 202607100003
Revises: 202607100002
Create Date: 2026-07-10 22:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "202607100003"
down_revision = "202607100002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_url", sa.String(length=500), nullable=True))
    op.create_index(
        "uq_users_username_lower",
        "users",
        [sa.text("lower(username)")],
        unique=True,
        postgresql_where=sa.text("username IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_users_username_lower", table_name="users")
    op.drop_column("users", "avatar_url")
