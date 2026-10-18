from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

COPY_STATUSES = ("available", "on_loan", "maintenance", "lost")
LOAN_STATUSES = ("active", "returned", "lost")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Book(Base):
    __tablename__ = "books"
    __table_args__ = (
        CheckConstraint("published_year IS NULL OR published_year BETWEEN 1400 AND 2100", name="ck_books_year"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    isbn: Mapped[str] = mapped_column(String(17), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    author: Mapped[str] = mapped_column(String(120), nullable=False)
    genre: Mapped[str | None] = mapped_column(String(60))
    published_year: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    copies: Mapped[list["Copy"]] = relationship(back_populates="book", cascade="all, delete-orphan")


class Copy(Base):
    __tablename__ = "copies"
    __table_args__ = (
        CheckConstraint(f"status IN {COPY_STATUSES}", name="ck_copies_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    barcode: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    shelf: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="available", nullable=False)

    book: Mapped[Book] = relationship(back_populates="copies")


class Member(Base):
    __tablename__ = "members"
    __table_args__ = (
        CheckConstraint("max_loans BETWEEN 1 AND 10", name="ck_members_max_loans"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    max_loans: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Loan(Base):
    __tablename__ = "loans"
    __table_args__ = (
        CheckConstraint(f"status IN {LOAN_STATUSES}", name="ck_loans_status"),
        CheckConstraint("due_at > borrowed_at", name="ck_loans_due_after_borrow"),
        CheckConstraint("fine >= 0", name="ck_loans_fine_nonneg"),
        CheckConstraint("renewals >= 0", name="ck_loans_renewals_nonneg"),
        CheckConstraint(
            "(status = 'active' AND returned_at IS NULL) OR (status <> 'active' AND returned_at IS NOT NULL)",
            name="ck_loans_closed_has_returned_at",
        ),
        # The database itself refuses a second open loan for the same copy.
        Index("uq_loans_one_active_per_copy", "copy_id", unique=True,
              postgresql_where=text("status = 'active'"), sqlite_where=text("status = 'active'")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    copy_id: Mapped[int] = mapped_column(ForeignKey("copies.id", ondelete="RESTRICT"), nullable=False, index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="RESTRICT"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    borrowed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    renewals: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fine: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fine_paid: Mapped[bool] = mapped_column(default=False, nullable=False)

    copy: Mapped[Copy] = relationship()
    member: Mapped[Member] = relationship()


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
