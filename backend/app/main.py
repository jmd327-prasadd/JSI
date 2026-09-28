from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import artifacts, findings, projects, rules, runs
from app.db.session import SessionLocal, init_db
from app.rules.loader import sync_rules_to_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        sync_rules_to_db(db)
    finally:
        db.close()
    yield


app = FastAPI(title="JQA - Quality Analysis API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # single internal tool, no auth, local docker network -- see plan's v1 scope
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(artifacts.router)
app.include_router(runs.router)
app.include_router(findings.router)
app.include_router(rules.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
