"""Business gauges, read from the database at scrape time.

A custom collector (instead of in-process counters) keeps the numbers correct
no matter how many backend replicas Prometheus scrapes: every replica reports
the same database truth.
"""
from datetime import datetime, timezone

from prometheus_client import REGISTRY
from prometheus_client.core import GaugeMetricFamily
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Copy, Loan

_registered = False


class LibraryCollector:
    def collect(self):
        copies = GaugeMetricFamily("shelflend_copies", "Physical copies by status", labels=["status"])
        active = GaugeMetricFamily("shelflend_loans_active", "Loans currently out")
        overdue = GaugeMetricFamily("shelflend_loans_overdue", "Active loans past their due date")
        fines = GaugeMetricFamily("shelflend_fines_outstanding_rupees", "Unpaid fines in rupees")
        up = GaugeMetricFamily("shelflend_db_up", "1 if the business metrics query succeeded")
        try:
            with SessionLocal() as db:
                by_status = dict(db.execute(select(Copy.status, func.count()).group_by(Copy.status)).all())
                for s in ("available", "on_loan", "maintenance", "lost"):
                    copies.add_metric([s], by_status.get(s, 0))
                active.add_metric([], db.scalar(select(func.count()).select_from(Loan).where(Loan.status == "active")))
                overdue.add_metric([], db.scalar(
                    select(func.count()).select_from(Loan)
                    .where(Loan.status == "active", Loan.due_at < datetime.now(timezone.utc))
                ))
                fines.add_metric([], db.scalar(
                    select(func.coalesce(func.sum(Loan.fine), 0)).where(Loan.fine_paid.is_(False))
                ))
            up.add_metric([], 1)
            yield from (copies, active, overdue, fines, up)
        except Exception:  # noqa: BLE001 - a scrape must never 500
            up.add_metric([], 0)
            yield up


def register_business_metrics() -> None:
    global _registered
    if not _registered:
        REGISTRY.register(LibraryCollector())
        _registered = True
