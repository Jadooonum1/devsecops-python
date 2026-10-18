"""Test setup: a throwaway SQLite database, never the real Postgres.

DATABASE_URL must be set before anything imports the app, and the schema is
built by the real Alembic migrations so the migrations are tested too.
"""
import os
import tempfile
from pathlib import Path

os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{tempfile.mkdtemp()}/test.db"
os.environ.setdefault("APP_VERSION", "test")

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def clean_tables():
    from app.db import SessionLocal
    from app.models import AuditEvent, Book, Copy, Loan, Member

    with SessionLocal() as db:
        for model in (Loan, Copy, Book, Member, AuditEvent):
            db.execute(delete(model))
        db.commit()
    yield


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def book(client):
    r = client.post("/api/books", json={
        "isbn": "978-0-13-468599-1", "title": "The Pragmatic Programmer",
        "author": "David Thomas", "genre": "Software", "published_year": 2019,
    })
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def copy(client, book):
    r = client.post(f"/api/books/{book['id']}/copies", json={"barcode": "LIB-0001", "shelf": "A3"})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def member(client):
    r = client.post("/api/members", json={"name": "Asha Rao", "email": "asha@example.com", "max_loans": 2})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def make_overdue():
    """Move a loan's dates into the past so it is `days` days late."""
    from datetime import datetime, timedelta, timezone

    from app.db import SessionLocal
    from app.models import Loan

    def _apply(loan_id: int, days: int) -> None:
        with SessionLocal() as db:
            loan = db.get(Loan, loan_id)
            now = datetime.now(timezone.utc)
            loan.borrowed_at = now - timedelta(days=14 + days)
            loan.due_at = now - timedelta(days=days, hours=1)
            db.commit()

    return _apply
