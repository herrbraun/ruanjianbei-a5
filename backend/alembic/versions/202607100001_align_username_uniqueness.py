"""align username uniqueness metadata

Revision ID: 202607100001
Revises: 202607080001
Create Date: 2026-07-10 00:00:00
"""

from alembic import op


revision = "202607100001"
down_revision = "202607080001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The users.username UNIQUE constraint already provides a unique index.
    # Drop the redundant non-unique index created by the initial migration.
    op.drop_index("ix_users_username", table_name="users")


def downgrade() -> None:
    op.create_index("ix_users_username", "users", ["username"])
