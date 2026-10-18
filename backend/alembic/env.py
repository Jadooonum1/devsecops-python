from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool, text

from app import models  # noqa: F401 - registers tables on Base.metadata
from app.config import settings
from app.db import Base

config = context.config
if config.config_file_name and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata
URL = settings.database_url
# Any constant works; every replica must use the same one.
MIGRATION_LOCK_ID = 7_350_211


def run_migrations_offline() -> None:
    context.configure(url=URL, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(URL, poolclass=pool.NullPool)
    is_pg = engine.dialect.name == "postgresql"
    with engine.connect() as connection:
        if is_pg:
            # Several replicas start at once; this makes them migrate one at a time.
            print("waiting for migration lock", flush=True)
            connection.execute(text("SELECT pg_advisory_lock(:id)"), {"id": MIGRATION_LOCK_ID})
            connection.commit()
            print("acquired migration lock", flush=True)
        try:
            context.configure(connection=connection, target_metadata=target_metadata,
                              render_as_batch=not is_pg)
            with context.begin_transaction():
                context.run_migrations()
        finally:
            if is_pg:
                connection.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": MIGRATION_LOCK_ID})
                connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
