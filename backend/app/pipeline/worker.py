from __future__ import annotations

import logging
import time

from app.config import settings
from app.db.session import SessionLocal, init_db
from app.pipeline.orchestrator import run_pipeline
from app.pipeline.queue import fetch_next_queued_run
from app.rules.loader import sync_rules_to_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s worker %(message)s")
log = logging.getLogger(__name__)


def run_once() -> bool:
    """Dequeue and process a single run. Returns True if a run was processed."""
    db = SessionLocal()
    try:
        run = fetch_next_queued_run(db)
        if run is None:
            return False
        log.info("picked up run %s (project %s)", run.id, run.project_id)
        run_pipeline(db, run)
        log.info("run %s finished with status=%s", run.id, run.status)
        return True
    finally:
        db.close()


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        sync_rules_to_db(db)
    finally:
        db.close()

    log.info("worker started, polling every %.1fs", settings.worker_poll_interval_seconds)
    while True:
        try:
            processed = run_once()
        except Exception:  # noqa: BLE001 -- keep the worker loop alive across unexpected errors
            log.exception("worker loop iteration failed")
            processed = False
        if not processed:
            time.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    main()
