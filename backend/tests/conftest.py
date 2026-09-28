from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Set before any `app.*` import happens anywhere in the test session, so the
# module-level engine in app/db/session.py (used by the FastAPI startup event,
# not by test assertions -- those use the per-test db_session override below)
# never touches a real dev DB file in the repo.
_tmp_root = Path(tempfile.mkdtemp(prefix="jqa_test_"))
os.environ.setdefault("JQA_DATABASE_URL", f"sqlite:///{(_tmp_root / 'jqa_test.db').as_posix()}")
os.environ.setdefault("JQA_DATA_DIR", str(_tmp_root / "data"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def db_session(tmp_path):
    """Fresh SQLite-backed DB per test, with the YAML rulebook synced in --
    mirrors what app startup does for the real DB."""
    from app.db.base import Base
    import app.models  # noqa: F401
    from app.rules.loader import sync_rules_to_db

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    sync_rules_to_db(session)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(tmp_path, monkeypatch, db_session):
    from app.api.deps import get_db
    from app.config import settings
    from app.main import app

    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
