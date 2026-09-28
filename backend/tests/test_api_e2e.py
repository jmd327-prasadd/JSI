from __future__ import annotations

from app.models.analysis_run import AnalysisRun
from app.pipeline.orchestrator import run_pipeline
from tests.fixtures.builder import write_good_dbt_project, zip_dir


def test_full_pipeline_via_api(client, db_session, tmp_path):
    project_root = write_good_dbt_project(tmp_path / "src" / "good")
    zip_path = zip_dir(project_root, tmp_path / "good.zip")

    resp = client.post("/projects", json={"name": "Acme Analytics", "client_name": "Acme"})
    assert resp.status_code == 200
    project_id = resp.json()["id"]

    with zip_path.open("rb") as f:
        resp = client.post(
            f"/projects/{project_id}/artifacts",
            files={"file": ("good.zip", f, "application/zip")},
        )
    assert resp.status_code == 200
    assert resp.json()["extraction_status"] == "pending"

    resp = client.post(f"/projects/{project_id}/runs")
    assert resp.status_code == 200
    run_id = resp.json()["id"]
    assert resp.json()["status"] == "queued"

    # Simulate what the worker container does: dequeue and run the pipeline
    # synchronously against the same test DB session.
    run = db_session.get(AnalysisRun, run_id)
    run.status = "extracting"
    run_pipeline(db_session, run)

    resp = client.get(f"/projects/{project_id}/runs/{run_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "done", resp.json()

    resp = client.get(f"/projects/{project_id}/runs/{run_id}/findings")
    assert resp.status_code == 200
    findings = resp.json()
    assert len(findings) > 0
    rule_ids = {f["rule_id"] for f in findings}
    assert "JQA-CODE-001" in rule_ids
    assert "JQA-SEC-001" in rule_ids

    resp = client.get(f"/projects/{project_id}/runs/{run_id}/summary")
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["total_findings"] == len(findings)
    assert summary["recommended_action"] in {
        "Onboard as-is", "Onboard with fix-ups", "Bounce back to development team",
    }

    # Review workflow: acknowledge one finding
    finding_id = findings[0]["id"]
    resp = client.patch(
        f"/projects/{project_id}/findings/{finding_id}",
        json={"status": "Acknowledged", "reviewer_note": "Looks fine for now."},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "Acknowledged"


def test_run_with_no_artifacts_fails_cleanly(client, db_session):
    resp = client.post("/projects", json={"name": "Empty Project"})
    project_id = resp.json()["id"]

    resp = client.post(f"/projects/{project_id}/runs")
    run_id = resp.json()["id"]

    run = db_session.get(AnalysisRun, run_id)
    run_pipeline(db_session, run)

    resp = client.get(f"/projects/{project_id}/runs/{run_id}")
    assert resp.json()["status"] == "failed"
