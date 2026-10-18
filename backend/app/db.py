from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

_url = settings.database_url
_kwargs = {"pool_pre_ping": True}
if _url.startswith("sqlite"):
    _kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(_url, **_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
