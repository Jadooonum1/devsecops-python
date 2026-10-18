"""All runtime settings come from environment variables.

In Kubernetes, host/port/name/user come from a ConfigMap and the password from
a Secret. A full DATABASE_URL (tests, Compose) overrides the individual parts.
"""
import os
import socket

from sqlalchemy.engine import URL


class Settings:
    def __init__(self) -> None:
        self.app_name = "ShelfLend"
        self.app_version = os.getenv("APP_VERSION", "dev")
        self.pod_name = os.getenv("POD_NAME", socket.gethostname())
        self.loan_days = int(os.getenv("LOAN_DAYS", "14"))
        self.max_renewals = int(os.getenv("MAX_RENEWALS", "2"))
        self.fine_per_day = int(os.getenv("FINE_PER_DAY", "10"))  # rupees
        self.fine_block_limit = int(os.getenv("FINE_BLOCK_LIMIT", "100"))  # rupees
        self.default_max_loans = int(os.getenv("DEFAULT_MAX_LOANS", "3"))

    @property
    def database_url(self) -> str:
        url = os.getenv("DATABASE_URL")
        if url:
            return url
        return URL.create(
            "postgresql+psycopg",
            username=os.getenv("DB_USER", "shelflend"),
            password=os.getenv("DB_PASSWORD", ""),
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "shelflend"),
        ).render_as_string(hide_password=False)


settings = Settings()
