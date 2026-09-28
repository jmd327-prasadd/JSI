from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis_run import AnalysisRun


def fetch_next_queued_run(db: Session) -> AnalysisRun | None:
    """DB-polled job dequeue. Uses `FOR UPDATE SKIP LOCKED` on Postgres so
    multiple worker replicas never grab the same run; on SQLite (local/dev/test,
    which has no such clause) this degrades to a plain read, which is fine
    since dev/test runs a single worker.
    """
    query = (
        select(AnalysisRun)
        .where(AnalysisRun.status == "queued")
        .order_by(AnalysisRun.created_at)
        .limit(1)
    )
    if db.bind.dialect.name != "sqlite":
        query = query.with_for_update(skip_locked=True)

    run = db.execute(query).scalar_one_or_none()
    if run is not None:
        run.status = "extracting"
        run.started_at = dt.datetime.utcnow()
        db.commit()
        db.refresh(run)
    return run
