# JQA -- Quality Analysis Platform: Architecture &amp; Build Log

This document is the single source of truth for understanding what this
application is, why it's built the way it is, and how to run it. It's written
so that another engineer, or another AI assistant picking this up cold, can
get productive without re-reading the whole codebase first.

For the original architecture plan this build follows, see
`C:\Users\PrasadD\.claude\plans\hi-we-are-planning-frolicking-garden.md`.
This document describes **what has actually been implemented**, which is the
plan's first two milestones (deterministic backend vertical slice + a simple
frontend), not the full end-state.

---

## 1. What this application does

JMAN's managed-services (MS) team takes over completed data projects (DBT +
Snowflake + Fivetran + Power BI + handover documentation) from a development
team. Before that handover, someone needs to check the project is actually
in good shape. JQA automates the first pass of that check:

1. An MS reviewer creates a **project** (one onboarding engagement).
2. They upload the project's code as a **zip** and its handover docs as
   **PDF/Word**.
3. JQA analyzes both and produces **findings** classified
   Critical/High/Medium/Low, each with an explanation and a suggested fix.
4. A scorecard rolls those findings up into a traffic light per category and
   one recommendation: onboard as-is, onboard with fix-ups, or bounce back
   to the dev team.

The guiding design principle (from the stakeholder): **do as much as possible
with deterministic code**, and reserve AI/LLM calls only for genuine judgment
calls that code can't make (e.g. "is this join logic actually correct given
the business context"). This keeps AI cost down and keeps the reasoning
auditable, since these findings feed a real business decision.

## 2. Current status vs. the full plan

| Layer | Status |
|---|---|
| Backend: DB schema, API, zip ingestion | **Done** |
| Backend: discovery (dbt / Snowflake-SQL / Power BI) | **Done** |
| Backend: deterministic rule engine (~19 rules) | **Done** |
| Backend: DB-polled job queue + worker | **Done** |
| Backend: scorecard/traffic-light aggregation | **Done** |
| Frontend: Next.js app (upload, run status, findings, scorecard) | **Done** (simplified -- see &sect;6) |
| Documentation ingestion (PDF/Word -&gt; Markdown) | Not built. Libraries already in `requirements.txt`. |
| AI orchestration layer (Azure OpenAI judgment calls) | Not built. `llm_assisted`/`hybrid` rule types exist in the schema but produce no AI findings yet. |
| Live Environment/connections analysis (Snowflake config, CI/CD execution, billing) | Deliberately deferred per v1 scope. Only a `connections` stub table/endpoint exists. |
| Auth | None (v1 scope: single internal tool, trusted network). |

Everything below documents what **is** built, in enough detail to extend it.

---

## 3. High-level architecture

```
                    ┌─────────────────────────┐
                    │   Next.js frontend      │
                    │   (localhost:3000)      │
                    │  - upload zip/docs      │
                    │  - poll run status      │
                    │  - findings dashboard   │
                    │  - scorecard            │
                    └───────────┬─────────────┘
                                │ REST (fetch)
                    ┌───────────▼─────────────┐
                    │   FastAPI app  (api)    │
                    │   (localhost:8000)      │
                    │  - projects/artifacts/  │
                    │    documents/runs/      │
                    │    findings/rules       │
                    └───────────┬─────────────┘
                                │ SQLAlchemy
                    ┌───────────▼─────────────┐         ┌─────────────────────┐
                    │  Postgres (docker) /    │         │ local volume /data  │
                    │  SQLite (local dev)     │         │ project zips, docs, │
                    │  projects, artifacts,   │◄────────┤ extracted trees,    │
                    │  runs, rules, findings  │         │ run inventory/plan  │
                    └───────────▲─────────────┘         └─────────▲───────────┘
                                │ polls "queued" runs               │
                    ┌───────────┴─────────────┐                    │
                    │   worker (worker)       │────────────────────┘
                    │  runs the pipeline:     │
                    │  extract → discover →   │
                    │  read-plan → evaluate   │
                    │  rules → aggregate      │
                    └─────────────────────────┘
```

Three deployable units: `api` (FastAPI), `worker` (same codebase, different
entrypoint, polls the DB for queued runs), and `frontend` (Next.js). They
share one Postgres DB and one filesystem volume for uploaded/extracted files.

**Why a DB-polled queue instead of Celery/Redis?** Local-docker, low-
concurrency, internal tool. A DB-polled table (`FOR UPDATE SKIP LOCKED` on
Postgres) needs no extra container, survives restarts, and is trivially
inspectable with a plain `SELECT`. See `backend/app/pipeline/queue.py`.

---

## 4. Backend

### 4.1 Directory map

```
backend/app/
  main.py                 FastAPI app, CORS, lifespan (init_db + sync rulebook)
  config.py               pydantic-settings; JQA_* env vars; DATABASE_URL defaults to SQLite
  db/
    base.py               SQLAlchemy DeclarativeBase + new_uuid() helper
    session.py            engine/SessionLocal/get_db; init_db() for dev/test create_all
  models/                 SQLAlchemy ORM: project, artifact, document (+DocSection),
                          connection, analysis_run, rule, finding
  schemas/                Pydantic request/response shapes (mirrors models/ 1:1-ish)
  storage/
    paths.py              All on-disk path layout lives here (single source of truth)
    zip_extract.py         safe_extract() -- guards zip-slip path traversal and zip bombs
  discovery/
    walker.py             SKIP-list recursive file walk (shared by everything below)
    classifiers.py        Finds dbt_project.yml / .pbip / .pbix / loose Snowflake SQL
    dbt.py                Deep dbt discovery (ported from the original PoC)
    dependencies.py       ref()/source() dependency graph, BFS upstream/downstream (ported)
    manifest_enrichment.py Optional: if target/manifest.json exists in the zip, enrich with it
    snowflake_sql.py       Regex DDL scan for loose (non-dbt) Snowflake SQL scripts
    powerbi.py             TMDL text parser for .pbip projects; .pbix recorded as opaque
    inventory.py           Orchestrates all of the above into one `ProjectInventory` dict
  pipeline/
    read_plan.py           Deterministic per-file tier: HIGH_PRIORITY_READ / FULL_BODY_ANALYSIS / METADATA_ONLY
    orchestrator.py        run_pipeline(): the actual stage-by-stage run execution
    queue.py               fetch_next_queued_run() -- the DB-polled dequeue
    worker.py               `python -m app.pipeline.worker` -- the poll loop entrypoint
  rules/
    definitions/*.yaml     THE RULEBOOK -- source of truth for every rule's metadata
    registry.py             Loads YAML, resolves detector_ref dotted paths, severity/confidence lookups
    loader.py               Mirrors YAML rulebook into the `rules` DB table on startup
    finding_draft.py        In-memory FindingDraft dataclass (pre-DB-persistence finding shape)
    detectors/               One module per rule area; each function returns list[FindingDraft]
    enrich.py                Adds dependency-graph context + rulebook verification text to drafts
    evaluate.py              Runs all applicable detectors, converts drafts -> DB Finding kwargs
  reporting/
    aggregation.py           Scorecard: traffic lights, readiness score, recommended action
  api/                       FastAPI routers: projects, artifacts, runs, findings, rules
backend/tests/                pytest: discovery, rule engine, full API end-to-end
```

### 4.2 Data model

One **Project** owns:
- N **Artifact** rows (each = one uploaded zip; `extraction_status`,
  `inventory_summary` JSON snapshot)
- N **Document** rows (PDF/Word; `conversion_status` -- pipeline for this
  isn't wired in yet) with child **DocSection** rows (for future doc-adequacy
  judgment calls)
- N **Connection** rows (stub only -- `connector_type`, `status:
  not_configured`; no live analysis)
- N **AnalysisRun** rows (one execution of the pipeline; re-running after a
  new zip upload creates a *new* run, so history is diffable, not overwritten)

Each **AnalysisRun** owns N **Finding** rows. A **Finding** carries the
PoC's original 4-part narrative (`evidence` / `impact` / `recommendation` /
`verification`) plus `severity`, `category`, `detection_type`,
dependency-graph context (`upstream_models`, `downstream_models`,
`transitive_downstream_count`), and a **review workflow** (`status`:
New/Acknowledged/Needs Dev Fix/False Positive/Won't Fix, plus
`reviewer_note`).

The **Rule** table mirrors the YAML rulebook (`app/rules/definitions/*.yaml`)
for FK integrity and API listing; the YAML files are the actual source of
truth and get re-synced into the DB on every app startup
(`app/rules/loader.py::sync_rules_to_db`).

### 4.3 Pipeline stages (`app/pipeline/orchestrator.py::run_pipeline`)

```
queued → extracting → discovering → evaluating_rules → llm_judgment → aggregating → done
                                                              ↑
                                                    (currently a no-op --
                                                     AI layer not built yet)
```

Any exception at any stage is caught, the run is marked `failed` with
`error_message` set, and **the worker loop keeps going** -- one bad run never
kills the worker process.

### 4.4 Discovery -- what happens to an uploaded zip

1. `zip_extract.safe_extract()` -- rejects zip-slip path traversal and caps
   total uncompressed size at 2 GiB.
2. `classifiers.classify()` walks the tree once and finds every
   `dbt_project.yml`, `.pbip`, `.pbix`, then `find_loose_snowflake_sql()`
   finds `.sql` files that look like raw Snowflake DDL and aren't already
   claimed by a dbt project's `models/`.
3. For each dbt project found: `dbt.discover_dbt_project()` walks it and
   builds the same style of inventory the original PoC produced (models,
   sources, tests, macros, snapshots, workflows), then
   `dependencies.build_dependency_graph()` regex-matches Jinja
   `{{ ref(...) }}` / `{{ source(...) }}` calls to build an upstream/
   downstream graph with transitive counts and "hotspot" ranking.
4. **Why not run `dbt parse`/`dbt compile` for a real manifest?** Handover
   repos are often incomplete or broken (missing adapter config, unresolved
   package pins) -- exactly the case this tool must still work on. Regex/YAML
   heuristics work on any zip, even a broken one. If a `target/manifest.json`
   happens to already be in the zip, `manifest_enrichment.py` opportunistically
   layers on authoritative materialization/test data -- enrichment only, never
   required.
5. Power BI: `.pbip` + its `*.SemanticModel/definition/*.tmdl` files are
   text, so they're parsed for tables/measures/relationships. A lone `.pbix`
   is a binary zip container -- **not** parsed, just recorded as present
   (`confidence: Low`, deep analysis explicitly skipped for v1).
6. `read_plan.build_read_plan()` classifies every file into
   `HIGH_PRIORITY_READ` (signature/config files), `FULL_BODY_ANALYSIS`
   (`.sql`/`.tmdl`), or `METADATA_ONLY` (everything else, including lock
   files and `.pbix` binaries). This is the gate the plan calls for: once
   the AI layer exists, no rule can send file content to an LLM that isn't
   `FULL_BODY_ANALYSIS`-tier here. Right now every file's `llm_eligible`
   flag is hardcoded `False` since there's no AI layer to gate yet.

### 4.5 Rule engine -- the rulebook

Every rule lives in `app/rules/definitions/{code,documentation,environment}.yaml`,
not in Python. Each entry has: `rule_id`, `category`, `subcategory`, `title`,
`description`, `severity_default`, `detection_type`, `detector_ref`,
`confidence_default`, `verification_template`. A detector function looks up
its own rule's severity/confidence/verification from the registry instead of
hardcoding it -- an analyst can retune a rule's severity by editing YAML, no
code change needed.

`detection_type` is one of:
- **`deterministic`** -- code decides and writes the finding directly. Every
  rule in this build is currently this type.
- **`llm_assisted`** -- (schema exists, not yet exercised) a cheap
  deterministic trigger would gate whether an LLM call happens at all.
- **`hybrid`** -- (schema exists, not yet exercised) a deterministic baseline
  finding always exists, optionally enriched by an LLM judgment.

Full rule catalog as currently implemented (all ported from the original
`Products\jqa` PoC, generalized and re-homed):

| rule_id | category / subcategory | severity | what it checks |
|---|---|---|---|
| JQA-CODE-001 | Code / Maintainability | Medium | `SELECT *` in a dbt model |
| JQA-ARCH-001 | Code / Architecture | Medium | Hardcoded qualified `db.schema.table` in FROM/JOIN |
| JQA-OPS-001 | Code / Operational Readiness | Medium | Incremental model with no `unique_key` |
| JQA-MNT-001 | Code / Maintainability | Medium | High complexity (joins&ge;8, CTEs&ge;15, or lines&ge;500) |
| JQA-DQ-001 | Code / Data Quality | Medium | Aggregate dbt test coverage is low |
| JQA-OPS-003 | Code / Operational Readiness | Low | Source named like it's "discontinued" but still referenced |
| JQA-SEC-001 | Code / Security | High | Hard-coded credential assignment / bearer token (regex) |
| JQA-SEC-002 | Code / Security | Critical | PEM private-key block found in source |
| JQA-SEC-003 | Code / Security | High | Credential-bearing connection string |
| JQA-SEC-004 | Code / Security | Medium | High-entropy string near a credential-shaped keyword |
| JQA-DOC-001 | Documentation | Medium | % of dbt models with a schema.yml description |
| JQA-DOC-002 | Documentation | Low | % of dbt sources with a description |
| JQA-OPS-002 | Environment / Operational Readiness | Medium | Sources with no dbt freshness block |
| JQA-CICD-001 | Environment / CI-CD | Medium | Multiple GitHub Actions workflow files (ambiguous authoritative path) |
| JQA-CICD-002 | Environment / CI-CD | High | `WITH:` casing bug in workflow YAML |
| JQA-CICD-003 | Environment / CI-CD | High | Deploy gated on `main` but trigger doesn't list `main` |
| JQA-CICD-004 | Environment / CI-CD | Medium | Unpinned `dbt-core`/`dbt-snowflake` pip install in CI |
| JQA-CICD-005 | Environment / Maintainability | Low | Hardcoded `/home/runner/work/...` path in a workflow |

Note on category placement: CI/CD and source-freshness checks are filed
under **Environment** even though they're evaluated statically from the zip
(no live connection needed) -- they're the subset of "environment" concerns
that don't require a live connector, per the v1 scope decision. Live
Snowflake config, billing, and orchestration checks (which *do* need a live
connection) are the ones actually deferred, represented only by the
`connections` stub table.

`security_checks.scan_security()` is the odd one out: it scans every text
file in the artifact directly (not the dbt inventory), since credentials can
appear in any file type, dbt or not.

### 4.6 Scorecard logic (`app/reporting/aggregation.py`)

Per category (Code, Documentation, Environment), computed **only from
findings whose review status is still "open"** (not False Positive/Won't
Fix -- a human dismissing a finding actually removes it from the score, by
design):

- **Traffic light**: Red if any open Critical; Amber if any open High, or
  more than 5 open Medium; Green otherwise.
- **Readiness score**: `100 - Σ(severity_weight × count)`, weights
  Critical=15/High=7/Medium=3/Low=1, floored at 0.
- **Recommended action**: any category Red &rarr; "Bounce back to
  development team"; all Green &rarr; "Onboard as-is"; otherwise &rarr;
  "Onboard with fix-ups" + an auto-generated punch list of open
  Critical/High findings.

This is intentionally 100% arithmetic, never AI-scored -- it's the
business-decision surface, and it has to be auditable.

### 4.7 API surface

| Method &amp; path | Purpose |
|---|---|
| `POST /projects` | Create a project |
| `GET /projects`, `GET /projects/{id}` | List / get |
| `POST /projects/{id}/artifacts` | Upload a code zip (multipart) |
| `GET /projects/{id}/artifacts` | List uploaded zips + inventory summary |
| `POST /projects/{id}/documents` | Upload a PDF/Word handover doc |
| `GET /projects/{id}/documents` | List uploaded docs |
| `POST /projects/{id}/connections` | Create a connections stub row |
| `GET /projects/{id}/connections` | List connection stubs |
| `POST /projects/{id}/runs` | Queue a new analysis run |
| `GET /projects/{id}/runs`, `.../runs/{run_id}` | List / poll run status |
| `GET /projects/{id}/runs/{run_id}/inventory` | Raw discovered inventory JSON |
| `GET /projects/{id}/runs/{run_id}/read-plan` | Raw read-plan JSON (audit: "what did JQA look at") |
| `GET /projects/{id}/runs/{run_id}/findings` | List findings (`?severity=&amp;category=&amp;detection_type=&amp;status=`) |
| `GET /projects/{id}/runs/{run_id}/summary` | Scorecard: counts, traffic lights, recommended action |
| `PATCH /projects/{id}/findings/{finding_id}` | Set review status + note |
| `GET /rules` | Read-only rulebook listing |
| `GET /health` | Liveness check |

---

## 5. Frontend

### 5.1 Directory map

```
frontend/
  app/
    layout.tsx                        Global shell (header/nav)
    page.tsx                          "/" -- project list + create form
    projects/[id]/page.tsx            Project detail: upload zip/docs, list runs, start a run
    projects/[id]/runs/[runId]/page.tsx  Run status polling -> scorecard + findings dashboard
  components/
    SeverityBadge.tsx                 Critical/High/Medium/Low colored badge
    TrafficLight.tsx                  Red/Amber/Green dot + label
    ScoreCard.tsx                     Renders RunSummary: traffic lights, readiness scores, punch list
    FindingCard.tsx                   Expandable finding: observed/impact/fix/verify + review-status control
  lib/
    api.ts                            Thin fetch wrapper around every backend endpoint
    types.ts                          TypeScript types mirroring the backend Pydantic schemas
```

### 5.2 User flow

1. `/` -- create a project, see the list of existing ones.
2. `/projects/[id]` -- upload a code zip (only `.zip` accepted) and/or a
   handover doc (`.pdf`/`.docx`); a **Connections** tab is shown but visibly
   disabled with a tooltip ("deferred to a future release") per the v1 scope
   decision -- it's a placeholder, not a dead end. "Start new analysis run"
   is disabled until at least one zip is uploaded.
3. `/projects/[id]/runs/[runId]` -- while the run is non-terminal, polls
   `GET .../runs/{id}` every 4 seconds and shows a progress bar +
   stage message. Once `done`, fetches the summary + findings once and
   renders the scorecard and a filterable findings dashboard (severity /
   category / detection-type chips + free-text search). Each finding is an
   expandable card; changing its review status/note calls
   `PATCH /findings/{id}` immediately.

### 5.3 Deliberate simplifications vs. the original architecture plan

The plan (see the linked plan file) recommended a richer frontend --
TanStack Query for data fetching/caching, a dedicated documentation-insights
page, more granular components. Since this iteration was scoped as **"a
simple frontend application"**, the following simplifications were made on
purpose and are easy to upgrade later without restructuring anything:

- **Plain `fetch` + `useEffect`/`setInterval` polling** instead of TanStack
  Query. No extra dependency; the whole app installs with just
  `next`/`react`/`react-dom`. Swapping in TanStack Query later is a
  contained change inside `lib/api.ts` call sites, not an architecture
  change.
- **No dedicated documentation-insights page** -- there's nothing to show
  yet since the documentation-ingestion pipeline isn't built (see &sect;2).
  The Documentation upload panel exists and works; the per-section adequacy
  view is future work.
- **Plain CSS** (`app/globals.css`), not Tailwind/a component library --
  keeps the dependency footprint minimal for a "simple" first pass.
- **No auth**, matching the backend's v1 scope decision.

None of these are structural: the API contract, data model, and page/route
layout already match the full plan, so extending this later means adding
pages/dependencies, not rearchitecting.

---

## 6. How to run it

### 6.1 Backend + worker (no Docker needed for dev/test)

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate            # source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
pytest -q                         # 7 tests: discovery, rule engine, full API e2e
uvicorn app.main:app --reload     # http://localhost:8000/docs
```

In a second terminal, the worker (required -- runs stay `queued` forever
without it):

```bash
cd backend && .venv/Scripts/activate
python -m app.pipeline.worker
```

Uses a local SQLite file (`backend/jqa_dev.db`) and stores uploads under
`backend/data/` by default -- no Postgres needed for local dev.

### 6.2 Frontend

```bash
cd frontend
npm install
npm run dev                       # http://localhost:3000
```

Set `NEXT_PUBLIC_API_URL` if the backend isn't at `http://localhost:8000`
(e.g. `NEXT_PUBLIC_API_URL=http://localhost:8010 npm run dev`).

`npm run build` type-checks and produces a production build -- verified
clean as of this writing.

### 6.3 Everything via Docker (matches the target deployment)

```bash
docker compose up --build
```

Brings up Postgres, `api` (port 8000), `worker`, and `frontend` (port 3000).
First run, apply the DB schema (Alembic is scaffolded but no migration has
been generated yet -- do this once):

```bash
docker compose exec api alembic revision --autogenerate -m "init"
docker compose exec api alembic upgrade head
```

### 6.4 Golden-path smoke test

1. Open `http://localhost:3000`, create a project.
2. Open the project, upload a dbt project as a `.zip`.
3. Click "Start new analysis run" -- you're redirected to the run page,
   which polls until the run finishes.
4. Review the scorecard and findings; change a finding's status to
   "Acknowledged" or "Needs Dev Fix" and confirm the scorecard's open counts
   update accordingly on next findings fetch.

This exact flow (via the API directly, and via the built frontend pages
returning 200 against a live run) was exercised while building this --
see `backend/tests/test_api_e2e.py` for the automated version.

---

## 7. Where to pick up next

Per the plan's recommended build order, in priority order:

1. **Documentation ingestion**: wire `pymupdf4llm` (PDF) and `markitdown`
   (DOCX) into a new pipeline stage that populates `DocSection` rows and
   flips `Document.conversion_status`. `requirements.txt` already lists both.
2. **AI orchestration layer**: an Azure OpenAI client
   (`app/ai/azure_openai_client.py`, not yet created) using structured
   outputs, plus the first two prompt templates the plan specifies
   (`prompts/code/dbt_incremental_soundness/`,
   `prompts/documentation/section_adequacy/`) to prove out the
   `llm_assisted`/`hybrid` rule paths end-to-end on `JQA-OPS-001` and a new
   `JQA-DOC-*` RCA-adequacy rule.
3. **Frontend**: a documentation-insights page once section-level data
   exists to show; optionally swap in TanStack Query if polling/caching
   needs grow past the current simple approach.
4. **Alembic**: generate and commit the first real migration
   (`alembic revision --autogenerate`) instead of relying on dev-only
   `create_all`.
