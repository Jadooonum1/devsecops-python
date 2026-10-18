"""catalogue (books, copies) and members

Revision ID: 0001
Revises:
Create Date: 2026-10-18
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "books",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("isbn", sa.String(17), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("author", sa.String(120), nullable=False),
        sa.Column("genre", sa.String(60)),
        sa.Column("published_year", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("published_year IS NULL OR published_year BETWEEN 1400 AND 2100", name="ck_books_year"),
    )
    op.create_table(
        "copies",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("book_id", sa.Integer, sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("barcode", sa.String(32), nullable=False, unique=True),
        sa.Column("shelf", sa.String(20)),
        sa.Column("status", sa.String(20), nullable=False, server_default="available"),
        sa.CheckConstraint("status IN ('available', 'on_loan', 'maintenance', 'lost')", name="ck_copies_status"),
    )
    op.create_index("ix_copies_book_id", "copies", ["book_id"])
    op.create_table(
        "members",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(200), nullable=False, unique=True),
        sa.Column("max_loans", sa.Integer, nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("max_loans BETWEEN 1 AND 10", name="ck_members_max_loans"),
    )


def downgrade() -> None:
    op.drop_table("members")
    op.drop_index("ix_copies_book_id", table_name="copies")
    op.drop_table("copies")
    op.drop_table("books")
