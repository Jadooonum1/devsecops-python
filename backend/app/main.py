import math
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from prometheus_fastapi_instrumentator import Instrumentator, metrics
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import schemas
from app.config import settings
from app.db import engine, get_db
from app.metrics import register_business_metrics
from app.models import AuditEvent, Book, Copy, Loan, Member

app = FastAPI(
    title="ShelfLend API",
    version=settings.app_version,
    description="Library lending: books, physical copies, members and loans.",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

Instrumentator(excluded_handlers=["/metrics", "/health", "/ready"]).add(
    metrics.default(latency_lowr_buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5))
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
register_business_metrics()


# --------------------------------------------------------------------------- helpers

def now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; Postgres returns aware ones."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def days_late(due: datetime, at: datetime) -> int:
    late = (at - as_utc(due)).total_seconds()
    return max(0, math.ceil(late / 86400))


def audit(db: Session, entity: str, entity_id: int, action: str, detail: str) -> None:
    db.add(AuditEvent(entity=entity, entity_id=entity_id, action=action, detail=detail))


def get_or_404(db: Session, model, obj_id: int, *, lock: bool = False):
    stmt = select(model).where(model.id == obj_id)
    if lock:
        stmt = stmt.with_for_update()
    obj = db.scalars(stmt).first()
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{model.__name__.lower()} {obj_id} not found")
    return obj


def conflict(msg: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, msg)


def book_out(db: Session, book: Book) -> schemas.BookOut:
    counts = dict(
        db.execute(
            select(Copy.status, func.count()).where(Copy.book_id == book.id).group_by(Copy.status)
        ).all()
    )
    out = schemas.BookOut.model_validate(book)
    out.total_copies = sum(counts.values())
    out.available_copies = counts.get("available", 0)
    return out


def unpaid_fines(db: Session, member_id: int) -> int:
    return db.scalar(
        select(func.coalesce(func.sum(Loan.fine), 0)).where(Loan.member_id == member_id, Loan.fine_paid.is_(False))
    ) or 0


def member_out(db: Session, m: Member) -> schemas.MemberOut:
    out = schemas.MemberOut.model_validate(m)
    out.active_loans = db.scalar(
        select(func.count()).select_from(Loan).where(Loan.member_id == m.id, Loan.status == "active")
    )
    out.unpaid_fines = unpaid_fines(db, m.id)
    return out


def loan_out(loan: Loan) -> schemas.LoanOut:
    out = schemas.LoanOut.model_validate(loan)
    out.borrowed_at = as_utc(loan.borrowed_at)
    out.due_at = as_utc(loan.due_at)
    out.returned_at = as_utc(loan.returned_at)
    if loan.status == "active":
        out.days_overdue = days_late(loan.due_at, now())
        out.overdue = out.days_overdue > 0
    out.book_title = loan.copy.book.title
    out.barcode = loan.copy.barcode
    out.member_name = loan.member.name
    return out


# --------------------------------------------------------------------------- probes

@app.get("/health", tags=["ops"])
def health():
    """Liveness: the process is up. Never touches the database."""
    return {"status": "ok"}


@app.get("/ready", tags=["ops"])
def ready(response: Response):
    """Readiness: the database answers and the schema has been migrated."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM loans LIMIT 1"))
    except Exception as exc:  # noqa: BLE001 - any DB failure means not ready
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "reason": type(exc).__name__}
    return {"status": "ready"}


@app.get("/api/info", tags=["ops"])
def info():
    """Build info plus the lending rules, so the UI never hardcodes them."""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "pod": settings.pod_name,
        "rules": {
            "loan_days": settings.loan_days,
            "max_renewals": settings.max_renewals,
            "fine_per_day": settings.fine_per_day,
            "fine_block_limit": settings.fine_block_limit,
            "default_max_loans": settings.default_max_loans,
        },
    }


# --------------------------------------------------------------------------- books

@app.get("/api/books", response_model=list[schemas.BookOut], tags=["books"])
def list_books(q: str | None = Query(default=None, max_length=100), db: Session = Depends(get_db)):
    stmt = select(Book).order_by(Book.title)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Book.title).like(like), func.lower(Book.author).like(like), Book.isbn.like(like)))
    return [book_out(db, b) for b in db.scalars(stmt)]


@app.post("/api/books", response_model=schemas.BookOut, status_code=201, tags=["books"])
def create_book(body: schemas.BookIn, db: Session = Depends(get_db)):
    book = Book(**body.model_dump())
    db.add(book)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise conflict(f"a book with isbn {body.isbn} already exists")
    audit(db, "book", book.id, "created", f"{book.title} by {book.author}")
    db.commit()
    db.refresh(book)
    return book_out(db, book)


@app.get("/api/books/{book_id}", response_model=schemas.BookOut, tags=["books"])
def get_book(book_id: int, db: Session = Depends(get_db)):
    return book_out(db, get_or_404(db, Book, book_id))


@app.put("/api/books/{book_id}", response_model=schemas.BookOut, tags=["books"])
def update_book(book_id: int, body: schemas.BookIn, db: Session = Depends(get_db)):
    book = get_or_404(db, Book, book_id)
    for k, v in body.model_dump().items():
        setattr(book, k, v)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise conflict(f"a book with isbn {body.isbn} already exists")
    audit(db, "book", book.id, "updated", book.title)
    db.commit()
    db.refresh(book)
    return book_out(db, book)


@app.delete("/api/books/{book_id}", status_code=204, tags=["books"])
def delete_book(book_id: int, db: Session = Depends(get_db)):
    book = get_or_404(db, Book, book_id, lock=True)
    copy_ids = select(Copy.id).where(Copy.book_id == book_id)
    if db.scalar(select(func.count()).select_from(Loan).where(Loan.copy_id.in_(copy_ids))):
        raise conflict("book has loan history; mark its copies lost or under maintenance instead")
    audit(db, "book", book.id, "deleted", book.title)
    db.delete(book)
    db.commit()
    return Response(status_code=204)


# --------------------------------------------------------------------------- copies

def copy_out(c: Copy) -> schemas.CopyOut:
    out = schemas.CopyOut.model_validate(c)
    out.book_title = c.book.title
    return out


@app.post("/api/books/{book_id}/copies", response_model=schemas.CopyOut, status_code=201, tags=["copies"])
def add_copy(book_id: int, body: schemas.CopyIn, db: Session = Depends(get_db)):
    book = get_or_404(db, Book, book_id)
    copy = Copy(book_id=book.id, barcode=body.barcode, shelf=body.shelf)
    db.add(copy)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise conflict(f"barcode {body.barcode} is already in use")
    audit(db, "copy", copy.id, "added", f"{body.barcode} of {book.title}")
    db.commit()
    db.refresh(copy)
    return copy_out(copy)


@app.get("/api/copies", response_model=list[schemas.CopyOut], tags=["copies"])
def list_copies(
    status_: str | None = Query(default=None, alias="status", pattern=r"^(available|on_loan|maintenance|lost)$"),
    book_id: int | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(Copy).order_by(Copy.barcode)
    if status_:
        stmt = stmt.where(Copy.status == status_)
    if book_id:
        stmt = stmt.where(Copy.book_id == book_id)
    return [copy_out(c) for c in db.scalars(stmt)]


@app.patch("/api/copies/{copy_id}", response_model=schemas.CopyOut, tags=["copies"])
def set_copy_status(copy_id: int, body: schemas.CopyStatusIn, db: Session = Depends(get_db)):
    copy = get_or_404(db, Copy, copy_id, lock=True)
    if copy.status in ("on_loan", "lost"):
        raise conflict(f"copy is {copy.status}; it can't be moved to {body.status}")
    copy.status = body.status
    audit(db, "copy", copy.id, body.status, copy.barcode)
    db.commit()
    db.refresh(copy)
    return copy_out(copy)


# --------------------------------------------------------------------------- members

@app.get("/api/members", response_model=list[schemas.MemberOut], tags=["members"])
def list_members(db: Session = Depends(get_db)):
    return [member_out(db, m) for m in db.scalars(select(Member).order_by(Member.name))]


@app.post("/api/members", response_model=schemas.MemberOut, status_code=201, tags=["members"])
def create_member(body: schemas.MemberIn, db: Session = Depends(get_db)):
    m = Member(name=body.name.strip(), email=body.email.lower(), max_loans=body.max_loans)
    db.add(m)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise conflict(f"a member with email {body.email} already exists")
    audit(db, "member", m.id, "joined", m.name)
    db.commit()
    db.refresh(m)
    return member_out(db, m)


@app.put("/api/members/{member_id}", response_model=schemas.MemberOut, tags=["members"])
def update_member(member_id: int, body: schemas.MemberIn, db: Session = Depends(get_db)):
    m = get_or_404(db, Member, member_id)
    m.name, m.email, m.max_loans = body.name.strip(), body.email.lower(), body.max_loans
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise conflict(f"a member with email {body.email} already exists")
    audit(db, "member", m.id, "updated", m.name)
    db.commit()
    db.refresh(m)
    return member_out(db, m)


@app.delete("/api/members/{member_id}", status_code=204, tags=["members"])
def delete_member(member_id: int, db: Session = Depends(get_db)):
    m = get_or_404(db, Member, member_id, lock=True)
    if db.scalar(select(func.count()).select_from(Loan).where(Loan.member_id == m.id)):
        raise conflict("member has loan history and can't be deleted")
    audit(db, "member", m.id, "deleted", m.name)
    db.delete(m)
    db.commit()
    return Response(status_code=204)


# --------------------------------------------------------------------------- loans

@app.get("/api/loans", response_model=list[schemas.LoanOut], tags=["loans"])
def list_loans(
    status_: str | None = Query(default=None, alias="status", pattern=r"^(active|overdue|returned|lost)$"),
    member_id: int | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(Loan).order_by(Loan.borrowed_at.desc())
    if status_ == "overdue":
        stmt = stmt.where(Loan.status == "active", Loan.due_at < now())
    elif status_:
        stmt = stmt.where(Loan.status == status_)
    if member_id:
        stmt = stmt.where(Loan.member_id == member_id)
    return [loan_out(l) for l in db.scalars(stmt.limit(500))]


@app.post("/api/loans", response_model=schemas.LoanOut, status_code=201, tags=["loans"])
def borrow(body: schemas.LoanIn, db: Session = Depends(get_db)):
    # Lock the member, then the copy, so two replicas handling concurrent
    # requests serialise here instead of both passing the checks.
    member = get_or_404(db, Member, body.member_id, lock=True)
    copy = get_or_404(db, Copy, body.copy_id, lock=True)

    if copy.status != "available":
        raise conflict(f"copy {copy.barcode} is {copy.status.replace('_', ' ')}")
    active = db.scalar(
        select(func.count()).select_from(Loan).where(Loan.member_id == member.id, Loan.status == "active")
    )
    if active >= member.max_loans:
        raise conflict(f"{member.name} already has {active} of {member.max_loans} loans")
    owed = unpaid_fines(db, member.id)
    if owed >= settings.fine_block_limit:
        raise conflict(f"{member.name} owes ₹{owed} in fines (limit ₹{settings.fine_block_limit})")

    start = now()
    loan = Loan(copy_id=copy.id, member_id=member.id, borrowed_at=start,
                due_at=start + timedelta(days=body.days or settings.loan_days))
    copy.status = "on_loan"
    db.add(loan)
    try:
        db.flush()
    except IntegrityError:  # partial unique index: last line of defence
        db.rollback()
        raise conflict(f"copy {copy.barcode} is already on loan")
    audit(db, "loan", loan.id, "borrowed", f"{copy.book.title} [{copy.barcode}] → {member.name}")
    db.commit()
    db.refresh(loan)
    return loan_out(loan)


def _active_loan(db: Session, loan_id: int, action: str) -> Loan:
    loan = get_or_404(db, Loan, loan_id, lock=True)
    if loan.status != "active":
        raise conflict(f"loan {loan.id} is {loan.status}; cannot {action}")
    return loan


@app.post("/api/loans/{loan_id}/return", response_model=schemas.LoanOut, tags=["loans"])
def return_loan(loan_id: int, db: Session = Depends(get_db)):
    loan = _active_loan(db, loan_id, "return")
    at = now()
    loan.status, loan.returned_at = "returned", at
    loan.fine = days_late(loan.due_at, at) * settings.fine_per_day
    loan.fine_paid = loan.fine == 0
    loan.copy.status = "available"
    detail = f"{loan.copy.book.title} [{loan.copy.barcode}] from {loan.member.name}"
    audit(db, "loan", loan.id, "returned", detail + (f", fine ₹{loan.fine}" if loan.fine else ""))
    db.commit()
    db.refresh(loan)
    return loan_out(loan)


@app.post("/api/loans/{loan_id}/renew", response_model=schemas.LoanOut, tags=["loans"])
def renew_loan(loan_id: int, db: Session = Depends(get_db)):
    loan = _active_loan(db, loan_id, "renew")
    if days_late(loan.due_at, now()):
        raise conflict("overdue loans can't be renewed; return the book first")
    if loan.renewals >= settings.max_renewals:
        raise conflict(f"loan already renewed {loan.renewals} times (max {settings.max_renewals})")
    loan.renewals += 1
    loan.due_at = as_utc(loan.due_at) + timedelta(days=settings.loan_days)
    audit(db, "loan", loan.id, "renewed", f"{loan.copy.book.title}, due {loan.due_at:%d %b}")
    db.commit()
    db.refresh(loan)
    return loan_out(loan)


@app.post("/api/loans/{loan_id}/lost", response_model=schemas.LoanOut, tags=["loans"])
def mark_lost(loan_id: int, db: Session = Depends(get_db)):
    loan = _active_loan(db, loan_id, "mark lost")
    loan.status, loan.returned_at = "lost", now()
    loan.fine = 500 + days_late(loan.due_at, loan.returned_at) * settings.fine_per_day
    loan.copy.status = "lost"
    audit(db, "loan", loan.id, "lost", f"{loan.copy.book.title} [{loan.copy.barcode}], fine ₹{loan.fine}")
    db.commit()
    db.refresh(loan)
    return loan_out(loan)


@app.post("/api/loans/{loan_id}/pay", response_model=schemas.LoanOut, tags=["loans"])
def pay_fine(loan_id: int, db: Session = Depends(get_db)):
    loan = get_or_404(db, Loan, loan_id, lock=True)
    if loan.status == "active":
        raise conflict("fines are settled after the loan is closed")
    if loan.fine_paid:
        raise conflict("fine already paid")
    loan.fine_paid = True
    audit(db, "loan", loan.id, "fine_paid", f"₹{loan.fine} by {loan.member.name}")
    db.commit()
    db.refresh(loan)
    return loan_out(loan)


# --------------------------------------------------------------------------- dashboard

@app.get("/api/stats", tags=["dashboard"])
def stats(db: Session = Depends(get_db)):
    copies = dict(db.execute(select(Copy.status, func.count()).group_by(Copy.status)).all())
    return {
        "books": db.scalar(select(func.count()).select_from(Book)),
        "members": db.scalar(select(func.count()).select_from(Member)),
        "copies": {s: copies.get(s, 0) for s in ("available", "on_loan", "maintenance", "lost")},
        "active_loans": db.scalar(select(func.count()).select_from(Loan).where(Loan.status == "active")),
        "overdue_loans": db.scalar(
            select(func.count()).select_from(Loan).where(Loan.status == "active", Loan.due_at < now())
        ),
        "fines_outstanding": db.scalar(
            select(func.coalesce(func.sum(Loan.fine), 0)).where(Loan.fine_paid.is_(False))
        ),
    }


@app.get("/api/activity", response_model=list[schemas.AuditOut], tags=["dashboard"])
def activity(limit: int = Query(default=20, ge=1, le=200), db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)).all()
    for r in rows:
        r.created_at = as_utc(r.created_at)
    return rows
