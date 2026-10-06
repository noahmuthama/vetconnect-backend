"""add veterinarian verification audit fields

Revision ID: 0002_vet_verification
Revises: 0001_initial_schema
Create Date: 2026-09-08
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_vet_verification"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("verification_reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("verification_reviewed_by", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("verification_notes", sa.String(length=1000), nullable=True))
    with op.batch_alter_table("users") as batch_op:
        batch_op.create_foreign_key(
            "fk_users_verification_reviewed_by_users",
            "users",
            ["verification_reviewed_by"],
            ["id"],
            referent_schema=None,
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("fk_users_verification_reviewed_by_users", type_="foreignkey")
        batch_op.drop_column("verification_notes")
        batch_op.drop_column("verification_reviewed_by")
        batch_op.drop_column("verification_reviewed_at")
