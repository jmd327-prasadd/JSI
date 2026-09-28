# JQA -- Quality Analysis Platform

Analyzes a completed data project (DBT, Snowflake, Fivetran, Power BI, handover
docs) before it's onboarded to managed services, and flags Critical/High/
Medium/Low findings with suggested fixes.

- **Full architecture, design rationale, rulebook reference, and "what's
  built vs. not"**: see [`ARCHITECTURE.md`](./ARCHITECTURE.md) -- read this
  first if you're new to the codebase (human or AI).
- **Detailed build/debug log** (exactly how extraction, discovery, rules,
  and the current AI/documentation gaps work, plus what was done by hand):
  see [`TECHNICAL_PROGRESS.md`](./TECHNICAL_PROGRESS.md).
- **JMAN-branded slide summary** of the above, as `.pptx` and `.pdf`:
  [`JQA_Technical_Documentation.pptx`](./JQA_Technical_Documentation.pptx) /
  [`.pdf`](./JQA_Technical_Documentation.pdf) -- an 11-slide condensed version
  for sharing outside the codebase.
- **Original architecture plan** this build follows:
  `C:\Users\PrasadD\.claude\plans\hi-we-are-planning-frolicking-garden.md`

## Status

Backend deterministic vertical slice + a simple Next.js frontend are both
built and tested: zip upload -> extraction -> dbt/Snowflake/Power BI
discovery -> dependency graph -> ~19 deterministic rule checks (ported from
the original JQA PoC) -> persisted findings -> review workflow -> scorecard,
with a working UI to drive all of it end to end. No AI calls yet, no
documentation ingestion yet -- see `ARCHITECTURE.md` &sect;7 for what's next.

## Running locally (no Docker required)

Backend:

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate           # or: source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
pytest -q                        # 7 tests: discovery, rule engine, full API pipeline
uvicorn app.main:app --reload    # http://localhost:8000/docs
```

The worker must also be running for uploaded runs to actually process (it
polls `analysis_runs` and executes the pipeline) -- run it in a second
terminal:

```bash
cd backend && .venv/Scripts/activate
python -m app.pipeline.worker
```

By default both use a local SQLite file (`backend/jqa_dev.db`) and store
uploads/extracted artifacts under `backend/data/`. No Postgres/Docker needed.

Frontend, in a third terminal:

```bash
cd frontend
npm install
npm run dev                      # http://localhost:3000
```

If the backend isn't at `http://localhost:8000`, set
`NEXT_PUBLIC_API_URL` when starting the dev server.

## Running with Docker (Postgres, matches the target deployment)

```bash
docker compose up --build
```

Brings up Postgres, `api` (port 8000), `worker`, and `frontend` (port 3000).
On first run, apply the DB schema once dependencies are installed:

```bash
docker compose exec api alembic revision --autogenerate -m "init"
docker compose exec api alembic upgrade head
```

## Golden-path smoke test

Via the UI: open `http://localhost:3000`, create a project, upload a dbt
project zip, start a run, watch it complete, review findings, change a
finding's review status.

Via the API directly:

1. `POST /projects` `{"name": "Acme Analytics", "client_name": "Acme"}`
2. `POST /projects/{id}/artifacts` -- multipart upload of a dbt project zip
3. `POST /projects/{id}/runs` -- creates a queued run; the worker picks it up
4. Poll `GET /projects/{id}/runs/{run_id}` until `status == "done"`
5. `GET /projects/{id}/runs/{run_id}/findings` and `.../summary`

## Repo layout

```
backend/app/
  api/            FastAPI routers (projects, artifacts, runs, findings, rules)
  models/         SQLAlchemy models
  schemas/        Pydantic request/response shapes
  discovery/      dbt / Snowflake-SQL / Power BI classification + discovery
  pipeline/       read_plan, orchestrator (pipeline stages), DB-polled worker
  rules/          YAML rulebook (definitions/) + detectors (ported from PoC)
  reporting/      scorecard/traffic-light aggregation
  storage/        local-volume path layout + safe zip extraction
backend/tests/    pytest suite (discovery, rule engine, full API e2e)
frontend/app/     Next.js pages (projects list, project detail, run/findings view)
frontend/components/  SeverityBadge, TrafficLight, ScoreCard, FindingCard
frontend/lib/     API client + shared TypeScript types
docker-compose.yml
ARCHITECTURE.md   Full design write-up -- read this for anything beyond quick-start
```
