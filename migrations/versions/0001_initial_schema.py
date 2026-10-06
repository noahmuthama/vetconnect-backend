"""initial VetConnect schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-08
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    user_role = sa.Enum("CLIENT", "VET", name="userrole", native_enum=False)
    request_status = sa.Enum("PENDING", "ACCEPTED", "IN_PROGRESS", "COMPLETED", "CANCELLED", name="requeststatus", native_enum=False)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("vet_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_id", "users", ["id"])

    op.create_table(
        "pets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("species", sa.String(length=80), nullable=False),
        sa.Column("breed", sa.String(length=120), nullable=True),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_pets_id", "pets", ["id"])
    op.create_index("ix_pets_owner_id", "pets", ["owner_id"])

    op.create_table(
        "service_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("vet_id", sa.Integer(), nullable=True),
        sa.Column("pet_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.Column("status", request_status, nullable=False, server_default="PENDING"),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["vet_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["pet_id"], ["pets.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_service_requests_id", "service_requests", ["id"])
    op.create_index("ix_service_requests_client_id", "service_requests", ["client_id"])
    op.create_index("ix_service_requests_vet_id", "service_requests", ["vet_id"])
    op.create_index("ix_service_requests_pet_id", "service_requests", ["pet_id"])
    op.create_index("ix_service_requests_status", "service_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_service_requests_status", table_name="service_requests")
    op.drop_index("ix_service_requests_pet_id", table_name="service_requests")
    op.drop_index("ix_service_requests_vet_id", table_name="service_requests")
    op.drop_index("ix_service_requests_client_id", table_name="service_requests")
    op.drop_index("ix_service_requests_id", table_name="service_requests")
    op.drop_table("service_requests")
    op.drop_index("ix_pets_owner_id", table_name="pets")
    op.drop_index("ix_pets_id", table_name="pets")
    op.drop_table("pets")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
