"""Block until the database accepts connections (container start-up)."""
import sys
import time

from sqlalchemy import create_engine, text

from app.config import settings


def main(timeout: int = 60) -> int:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    deadline = time.monotonic() + timeout
    while True:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("database is ready", flush=True)
            return 0
        except Exception as exc:  # noqa: BLE001
            if time.monotonic() > deadline:
                print(f"database not reachable after {timeout}s: {exc}", file=sys.stderr)
                return 1
            print(f"waiting for database ({type(exc).__name__})", flush=True)
            time.sleep(2)


if __name__ == "__main__":
    sys.exit(main())
