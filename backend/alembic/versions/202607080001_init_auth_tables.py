"""init auth tables

Revision ID: 202607080001
Revises:
Create Date: 2026-07-08 22:30:00
"""
from alembic import op
import sqlalchemy as sa

revision = "202607080001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=100), nullable=True, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("nickname", sa.String(length=100), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('visitor', 'admin')", name="ck_users_role"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "visitor_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("interest", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_visitor_profiles_id", "visitor_profiles", ["id"])
    op.create_index("ix_visitor_profiles_user_id", "visitor_profiles", ["user_id"])

    op.create_table(
        "admin_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_admin_profiles_id", "admin_profiles", ["id"])
    op.create_index("ix_admin_profiles_user_id", "admin_profiles", ["user_id"])

    op.create_table(
        "login_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=True),
        sa.Column("login_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ip_address", sa.String(length=100), nullable=True),
    )
    op.create_index("ix_login_logs_id", "login_logs", ["id"])
    op.create_index("ix_login_logs_user_id", "login_logs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_login_logs_user_id", table_name="login_logs")
    op.drop_index("ix_login_logs_id", table_name="login_logs")
    op.drop_table("login_logs")
    op.drop_index("ix_admin_profiles_user_id", table_name="admin_profiles")
    op.drop_index("ix_admin_profiles_id", table_name="admin_profiles")
    op.drop_table("admin_profiles")
    op.drop_index("ix_visitor_profiles_user_id", table_name="visitor_profiles")
    op.drop_index("ix_visitor_profiles_id", table_name="visitor_profiles")
    op.drop_table("visitor_profiles")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
