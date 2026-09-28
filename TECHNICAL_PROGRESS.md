# JQA -- Technical Progress Documentation

This document answers, specifically and honestly, "what actually happens when
you use this app, mechanically, step by step" -- including what's real,
what's still a placeholder, and what was done by hand rather than by the
system itself. For the higher-level architecture and design rationale, see
[`ARCHITECTURE.md`](./ARCHITECTURE.md); this document is the detailed,
warts-and-all companion to it.

---

## 1. How the ZIP is extracted

**Code**: `backend/app/api/artifacts.py::upload_artifact` (receives the
upload) &rarr; `backend/app/storage/zip_extract.py::safe_extract` (does the
extraction) &rarr; called from `backend/app/pipeline/orchestrator.py::run_pipeline`
during the `extracting` stage.

Step by step:

1. **Upload**: `POST /projects/{id}/artifacts` accepts a multipart file,
   rejects anything not ending in `.zip`, streams it to disk in 1 MiB chunks
   (rejecting anything over 500 MiB), and records an `Artifact` row with
   `extraction_status = "pending"`. The original zip is saved untouched at
   `data/projects/{project_id}/artifacts/{artifact_id}/original.zip` --
   this is the permanent source of truth; nothing ever mutates it.
2. **Extraction happens later**, when a run is actually started (`POST
   /projects/{id}/runs`), not at upload time. The worker's pipeline calls
   `safe_extract(zip_path, extracted_dir)` where `extracted_dir` is
   `data/projects/{project_id}/artifacts/{artifact_id}/extracted/`.
3. Inside `safe_extract`:
   - Every entry in the zip is checked for **zip-slip path traversal**
     (a malicious `../../etc/passwd`-style entry name) and rejected if its
     resolved path would land outside `extracted_dir`.
   - Every entry whose path contains a "noise" directory --
     `.git`, `node_modules`, `dbt_packages`, `.venv`, `venv`, `__pycache__`,
     `.next`, `dist`, `build`, `.terraform` (the same list used later for
     analysis, defined once in `app/discovery/walker.py::SKIP`) -- is
     **filtered out before extraction**, not just skipped when later reading
     files. This was a **real bug found and fixed during this build**: `.git`
     contains deeply-nested, long-hash-named object files
     (`.git/objects/xx/<38-char-hash>`), and combined with this app's
     `data/projects/{uuid}/artifacts/{uuid}/extracted/...` path prefix, the
     full path exceeded Windows' 260-character `MAX_PATH` limit, causing a
     misleading `[Errno 2] No such file or directory` error even though the
     file genuinely existed in the zip. Since `.git`/`node_modules`/etc. are
     never analyzed anyway, the fix was to never extract them, not to work
     around the path limit.
   - As defense in depth, the destination path is also prefixed with
     Windows' `\\?\` extended-length-path marker before extraction, so even
     a legitimately deep (non-noise) folder structure won't hit `MAX_PATH`.
   - Total uncompressed size is capped at 2 GiB as a zip-bomb guard.
4. After a run finishes successfully, `extracted/` is deleted
   (`clear_dir`, with a small retry loop for transient Windows file locks --
   a second real bug: a OneDrive-synced project folder can briefly hold a
   file handle open right after extraction, and the very first version of
   this cleanup step let that failure incorrectly flip an already-successful
   run to "failed"; fixed so cleanup failures are now logged and swallowed,
   never able to change a run's outcome). The original `.zip` is never
   deleted while the project is active -- a re-run always re-extracts from
   it fresh.

## 2. How PDF/Word documentation is converted -- **not yet implemented**

Be direct about this: **no PDF/Word conversion happens today.**

What exists right now:
- `POST /projects/{id}/documents` (`backend/app/api/artifacts.py::upload_document`)
  accepts a `.pdf` or `.docx`, validates the extension, saves the original
  file to `data/projects/{project_id}/documents/{document_id}/original.{pdf|docx}`,
  and creates a `Document` row with `conversion_status = "pending"`.
- That status **never changes** -- there is no pipeline stage that reads it,
  converts it, or populates `DocSection` rows. The `converted_markdown_path`
  and `conversion_tool` fields on `Document` exist in the schema but are
  never written to.
- The frontend's "Documentation" upload panel works (file lands on disk,
  shows up in the list, shows `conversion_status: pending` forever), but
  there's no documentation-insights page yet because there's nothing to show.

What's planned (per the architecture plan, not yet built):
- `pymupdf4llm` for PDF &rarr; Markdown, `markitdown` for DOCX &rarr; Markdown --
  both already listed in `backend/requirements.txt` but **not imported
  anywhere in `app/`** yet.
- A `section_extractor.py` module (doesn't exist yet) would walk the
  converted Markdown's heading tree and classify each section against a
  fixed taxonomy (`architecture`, `business_logic`, `rca`, `runbook`, etc.),
  populating `DocSection` rows and setting `llm_eligible = True` only on the
  high-relevance sections -- this is the token-optimization gate for the AI
  layer described in &sect;4.

## 3. How the analysis is actually done (the deterministic pipeline)

**Code**: `backend/app/pipeline/orchestrator.py::run_pipeline` is the single
place this all happens, run by the worker process
(`backend/app/pipeline/worker.py`) after it dequeues a `queued` run from the
`analysis_runs` table (`backend/app/pipeline/queue.py::fetch_next_queued_run`,
using Postgres `FOR UPDATE SKIP LOCKED` -- degrades to a plain read on
SQLite for local dev).

Pipeline stages, in order, each committed to the DB as it happens so the
frontend's polling (`GET /projects/{id}/runs/{run_id}`) sees live progress:

1. **`extracting`** -- see &sect;1 above, once per uploaded zip artifact.
2. **`discovering`** (`app/discovery/inventory.py::build_inventory`):
   - `classifiers.py` walks the extracted tree once and finds every
     `dbt_project.yml`, `.pbip` (Power BI project), `.pbix` (opaque binary --
     recorded as present, never parsed), and any loose `.sql` file that looks
     like raw Snowflake DDL (`CREATE TABLE/VIEW/PROCEDURE/...`) and isn't
     already part of a dbt project's `models/`.
   - For each dbt project found, `dbt.py::discover_dbt_project` (logic
     ported near-verbatim from the original PoC at `Products\jqa`) walks it
     and extracts: every model's path/layer/domain (inferred from the
     `models/<layer>/<domain>/...` folder convention), whether it does
     `SELECT *`, whether it hardcodes a qualified `db.schema.table`
     reference, join/CTE counts, whether it's incremental and whether it has
     a `unique_key`; plus `schema.yml`/`source.yml` metadata (descriptions,
     tests, freshness blocks) and `.github/workflows/*.yml` contents.
   - `dependencies.py` then regex-matches every `{{ ref(...) }}` and
     `{{ source(...) }}` Jinja call across all models to build an
     upstream/downstream graph (BFS for transitive counts, "hotspot"
     ranking by downstream fan-out). **This is regex over the raw SQL, not
     a real dbt manifest/compile** -- deliberately, because handover repos
     are often incomplete or unbuildable (missing adapter config, unresolved
     package pins), which is exactly the case this tool has to still work
     on. If a `target/manifest.json` happens to already be in the zip,
     `manifest_enrichment.py` opportunistically layers on authoritative
     materialization data, but this is enrichment only, never required.
   - `read_plan.py::build_read_plan` classifies every single discovered file
     into `HIGH_PRIORITY_READ` (config/signature files), `FULL_BODY_ANALYSIS`
     (`.sql`/`.tmdl`), or `METADATA_ONLY` (everything else) and persists it
     to `data/.../runs/{run_id}/read_plan.json` -- an audit trail of "what
     did JQA actually look at." Every file's `llm_eligible` flag is
     hardcoded `False` right now (see &sect;4).
   - The full discovered inventory (minus raw SQL text, to keep the file
     readable) is persisted to `data/.../runs/{run_id}/inventory.json`.
3. **`evaluating_rules`** (`app/rules/evaluate.py::evaluate_inventory`): runs
   every deterministic rule (see &sect;5 for the rulebook itself) against
   the discovered inventory, plus a separate filesystem-wide secret scan
   (`security_checks.scan_security`, which reads every text file directly --
   not just dbt files -- since credentials can appear anywhere). Each
   detector returns `FindingDraft` objects, which then get **enriched**
   (`rules/enrich.py`) with dependency-graph context (upstream/downstream
   models, a plain-English impact note) and the rulebook's `verification`
   text, then converted to real `Finding` DB rows
   (`rules/evaluate.py::draft_to_finding_kwargs`).
4. **`llm_judgment`** -- currently a **no-op label only**. See &sect;4.
5. **`aggregating`** -- currently just a status-message stage; the actual
   scorecard math (`app/reporting/aggregation.py`) runs on-demand when the
   frontend calls `GET /projects/{id}/runs/{run_id}/summary`, not during the
   pipeline itself. It computes, per category (Code/Documentation/
   Environment), a traffic light (Red if any open Critical finding, Amber if
   any open High or &gt;5 open Medium, else Green), a weighted readiness
   score (`100 - Σ(severity_weight × open_count)`), and one recommended
   action (Bounce back / Onboard with fix-ups / Onboard as-is) -- computed
   only from findings whose review status is still "open" (not dismissed as
   False Positive/Won't Fix), and entirely arithmetic, never AI-influenced.
6. **`done`** -- run marked complete; `extracted/` cleaned up (see &sect;1).

Any exception at any stage is caught, the run is marked `failed` with the
real exception message stored in `error_message`, and the worker loop
**keeps running** -- one bad run never takes down the worker process. Two
real failures were hit and fixed this way during this build (see &sect;1 and
the retry note there).

## 4. How AI is working here -- **not implemented yet; here's the honest state**

There are no LLM calls anywhere in this codebase today. To be specific about
what exists vs. what doesn't:

**What exists** (schema/plumbing, unused):
- Every `Finding` row has `ai_reasoning`, `ai_evidence_cited`, `ai_model_used`,
  `ai_prompt_version` columns (`app/models/finding.py`) -- always empty right
  now.
- Every rule in the YAML rulebook has a `detection_type` field that can be
  `deterministic`, `llm_assisted`, or `hybrid`, and a `judgment_ref` field
  for a future prompt reference (`app/rules/registry.py`).
- The frontend's `FindingCard` component already renders a "Confirmed" vs.
  "AI Assessment" badge based on `detection_type`, and has a collapsed panel
  for AI reasoning/evidence -- ready to display real data the moment it
  exists.
- The pipeline has an `llm_judgment` stage in its state machine.

**What does NOT exist**:
- Every single rule currently defined in `app/rules/definitions/*.yaml` has
  `detection_type: deterministic`. Not one rule is `llm_assisted` or
  `hybrid` yet.
- There is no `app/ai/` module, no Azure OpenAI client, no `openai` SDK call
  anywhere in the code (the `openai` package is listed in
  `requirements.txt` but never imported).
- There are no prompt template files (no `prompts/` directory exists yet).
- The `llm_judgment` pipeline stage literally just sets a status message
  ("AI judgment layer not yet enabled for this build") and moves on -- it
  does not call out to anything.

**What's planned** (per the architecture plan, not yet built): an Azure
OpenAI client using structured outputs (JSON-schema-constrained responses
mapped to a `LLMJudgment` Pydantic model), reserved only for judgment calls
deterministic code can't make -- e.g. "given this specific join and
incremental config, is the duplicate-handling actually sound" or "does this
documentation section genuinely cover the RCA given the real complexity
behind it" -- gated by a cheap deterministic trigger per rule so tokens are
only spent when a rule's precondition actually fires. Severity would always
be clamped to a deterministic ceiling; the AI could only confirm or
downgrade, never invent a worse verdict than the rule allows.

**Bottom line**: everything the app currently flags -- all 18 rule types,
all severities, all recommendations -- is produced by plain Python
regex/YAML logic, with zero AI cost and zero AI involvement. The "AI"
framing in the product's original brief is a target for the next phase of
work, not a description of the current behavior.

## 5. Where the rulebook is

**Location**: `backend/app/rules/definitions/` -- three YAML files,
`code.yaml`, `documentation.yaml`, `environment.yaml`. These files are the
single source of truth for every rule; nothing about a rule (its severity,
its verification text, which function detects it) is hardcoded in Python.

**How it's loaded**:
- `app/rules/registry.py::RuleRegistry.load()` reads all three YAML files at
  import time into an in-memory registry, keyed by `rule_id`.
- `app/rules/loader.py::sync_rules_to_db` mirrors that registry into the
  Postgres/SQLite `rules` table on every app startup (`app/main.py`'s
  lifespan handler) -- this is for foreign-key integrity (`Finding.rule_id`
  references it) and so `GET /rules` can list the rulebook for the UI. The
  YAML is still the actual source of truth; the DB copy is just a mirror.
- Each detector function (`app/rules/detectors/*.py`) looks up its own
  rule's severity/confidence/verification text from the registry at
  evaluation time (`registry.severity_for(rule_id)` etc.) instead of
  hardcoding it -- so retuning a rule's severity is a one-line YAML edit,
  no code change or redeploy of logic needed.

**What's in it right now** -- 18 rules, all `deterministic`:

| rule_id | file | category / subcategory | severity |
|---|---|---|---|
| JQA-CODE-001 | code.yaml | Code / Maintainability | Medium |
| JQA-ARCH-001 | code.yaml | Code / Architecture | Medium |
| JQA-OPS-001 | code.yaml | Code / Operational Readiness | Medium |
| JQA-MNT-001 | code.yaml | Code / Maintainability | Medium |
| JQA-DQ-001 | code.yaml | Code / Data Quality | Medium |
| JQA-OPS-003 | code.yaml | Code / Operational Readiness | Low |
| JQA-SEC-001 | code.yaml | Code / Security | High |
| JQA-SEC-002 | code.yaml | Code / Security | Critical |
| JQA-SEC-003 | code.yaml | Code / Security | High |
| JQA-SEC-004 | code.yaml | Code / Security | Medium |
| JQA-DOC-001 | documentation.yaml | Documentation | Medium |
| JQA-DOC-002 | documentation.yaml | Documentation | Low |
| JQA-OPS-002 | environment.yaml | Environment / Operational Readiness | Medium |
| JQA-CICD-001 | environment.yaml | Environment / CI-CD | Medium |
| JQA-CICD-002 | environment.yaml | Environment / CI-CD | High |
| JQA-CICD-003 | environment.yaml | Environment / CI-CD | High |
| JQA-CICD-004 | environment.yaml | Environment / CI-CD | Medium |
| JQA-CICD-005 | environment.yaml | Environment / Maintainability | Low |

(Full description of what each one checks is in `ARCHITECTURE.md` &sect;4.5.)

## 6. Manual work done during this build (not automated by the app itself)

Important distinction: this section is about **what I (the assistant) did
by hand while building and debugging this**, as opposed to what a normal
user running the finished app does. A normal user does not need to do any
of this.

- **Environment setup was manual, not containerized**: because Docker
  Desktop is not installed on this machine, the backend venv
  (`python -m venv .venv` + `pip install -r requirements.txt`) and frontend
  dependencies (`npm install`) were set up and run directly on the host,
  not via `docker compose up`. The `docker-compose.yml`/`Dockerfile`s were
  written correctly per the target deployment but **have never actually
  been run or verified in this environment**.
- **Alembic migrations are unverified**: `alembic.ini`/`alembic/env.py` are
  scaffolded, but `alembic revision --autogenerate` has never actually been
  executed against a real Postgres DB. Local dev/test instead relies on
  SQLAlchemy's `Base.metadata.create_all()` (`app/db/session.py::init_db`),
  which is fine for SQLite dev but is not the migration path the Postgres/
  Docker deployment is supposed to use.
- **A port-8000 binding failure was worked around, not fixed**: on this
  machine, `uvicorn` cannot bind to port 8000 (`WinError 10048`) even though
  Windows reports no process listening there -- most likely a Hyper-V/WSL/
  Docker-Desktop-networking port reservation quirk specific to this machine.
  Rather than debug Windows networking internals, the backend was simply
  moved to port 8010 for all local runs. This is an environment quirk, not
  an application bug, and isn't "fixed" in code.
- **Process management was manual and hit a Git-Bash-on-Windows quirk**:
  starting the backend/worker via a backgrounded (`&`) command in this
  session's Bash tool sometimes spawned two `python.exe` processes per
  command instead of one (visible via `Get-CimInstance Win32_Process`).
  This was diagnosed and cleaned up by hand (`Stop-Process`) each time
  processes needed restarting after a code change; it did not affect
  correctness (only one process ever actually held the listening socket)
  but is worth knowing about if you see duplicate processes in Task Manager.
- **Two real bugs were found and fixed via live debugging, not
  anticipated up front**: the `.git`/`MAX_PATH` extraction failure and the
  cleanup-triggered false-failure (both detailed in &sect;1) were both found
  by actually running the app against a real uploaded project, reading the
  exact error text reported, reproducing the reasoning behind it, patching
  the code, adding a regression test for each
  (`backend/tests/test_storage.py`), and re-verifying against the same live
  project before declaring it fixed.
- **The frontend was verified via `curl` and Next.js build output, not a
  real browser**: no browser automation tool was available in this session,
  so pages were checked for HTTP 200 and correct HTML content via `curl`,
  and the full data flow was verified by driving the real API directly
  (create project &rarr; upload &rarr; run &rarr; findings &rarr; summary) and confirming
  the frontend pages that consume that data load without error. Nobody has
  visually clicked through the UI in an actual browser yet.
- **Test fixtures are hand-written, not real customer data**: the automated
  test suite (`backend/tests/fixtures/builder.py`) generates a small
  synthetic dbt project in-memory for every test run; it is not derived from
  any real project.
