"""loans with lending rules enforced in the database, plus the audit trail

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-18
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "loans",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("copy_id", sa.Integer, sa.ForeignKey("copies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("member_id", sa.Integer, sa.ForeignKey("members.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("borrowed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("returned_at", sa.DateTime(timezone=True)),
        sa.Column("renewals", sa.Integer, nullable=False, server_default="0"),
        sa.Column("fine", sa.Integer, nullable=False, server_default="0"),
        sa.Column("fine_paid", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.CheckConstraint("status IN ('active', 'returned', 'lost')", name="ck_loans_status"),
        sa.CheckConstraint("due_at > borrowed_at", name="ck_loans_due_after_borrow"),
        sa.CheckConstraint("fine >= 0", name="ck_loans_fine_nonneg"),
        sa.CheckConstraint("renewals >= 0", name="ck_loans_renewals_nonneg"),
        sa.CheckConstraint(
            "(status = 'active' AND returned_at IS NULL) OR (status <> 'active' AND returned_at IS NOT NULL)",
            name="ck_loans_closed_has_returned_at",
        ),
    )
    op.create_index("ix_loans_copy_id", "loans", ["copy_id"])
    op.create_index("ix_loans_member_id", "loans", ["member_id"])
    # At most one open loan per physical copy, enforced by the database.
    op.create_index(
        "uq_loans_one_active_per_copy", "loans", ["copy_id"], unique=True,
        postgresql_where=sa.text("status = 'active'"), sqlite_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("entity", sa.String(20), nullable=False),
        sa.Column("entity_id", sa.Integer, nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("detail", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("uq_loans_one_active_per_copy", table_name="loans")
    op.drop_index("ix_loans_member_id", table_name="loans")
    op.drop_index("ix_loans_copy_id", table_name="loans")
    op.drop_table("loans")
