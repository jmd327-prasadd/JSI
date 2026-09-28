"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  createRun,
  getProject,
  listArtifacts,
  listDocuments,
  listRuns,
  uploadArtifact,
  uploadDocument,
} from "@/lib/api";
import type { AnalysisRun, Artifact, DocumentUpload, Project } from "@/lib/types";

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const [project, setProject] = useState<Project | null>(null);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [documents, setDocuments] = useState<DocumentUpload[]>([]);
  const [runs, setRuns] = useState<AnalysisRun[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function refresh() {
    const [p, a, d, r] = await Promise.all([
      getProject(projectId),
      listArtifacts(projectId),
      listDocuments(projectId),
      listRuns(projectId),
    ]);
    setProject(p);
    setArtifacts(a);
    setDocuments(d);
    setRuns(r);
  }

  useEffect(() => {
    refresh().catch((e) => setError(String(e)));
  }, [projectId]);

  async function handleZipUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      await uploadArtifact(projectId, file);
      await refresh();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  async function handleDocUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      await uploadDocument(projectId, file);
      await refresh();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  async function handleStartRun() {
    setBusy(true);
    setError("");
    try {
      const run = await createRun(projectId);
      await refresh();
      window.location.href = `/projects/${projectId}/runs/${run.id}`;
    } catch (err) {
      setError(String(err));
      setBusy(false);
    }
  }

  if (!project) {
    return <p className="muted">Loading...</p>;
  }

  return (
    <div>
      <h1>{project.name}</h1>
      <p className="muted">{project.client_name || "no client set"}</p>
      {error && <p className="error-text">{error}</p>}

      <div className="tabs">
        <span className="tab">Code</span>
        <span className="tab">Documentation</span>
        <span className="tab disabled" title="Environment/connections analysis is deferred to a future release">
          Connections
        </span>
      </div>

      <div className="panel">
        <h2>Code (.zip)</h2>
        <div className="upload-box">
          <input type="file" accept=".zip" onChange={handleZipUpload} disabled={busy} />
        </div>
        <ul className="project-list">
          {artifacts.map((a) => (
            <li key={a.id}>
              {a.original_filename} - {(a.size_bytes / 1024).toFixed(0)} KB - {a.extraction_status}
              {a.inventory_summary?.dbt_project_count !== undefined && (
                <div className="project-meta">
                  dbt projects: {String(a.inventory_summary.dbt_project_count)} - files:{" "}
                  {String(a.inventory_summary.file_count)}
                </div>
              )}
            </li>
          ))}
          {artifacts.length === 0 && <li className="muted">No code uploaded yet.</li>}
        </ul>
      </div>

      <div className="panel">
        <h2>Documentation (.pdf / .docx)</h2>
        <div className="upload-box">
          <input type="file" accept=".pdf,.docx" onChange={handleDocUpload} disabled={busy} />
        </div>
        <ul className="project-list">
          {documents.map((d) => (
            <li key={d.id}>
              {d.original_filename} - {d.conversion_status}
            </li>
          ))}
          {documents.length === 0 && <li className="muted">No documentation uploaded yet.</li>}
        </ul>
      </div>

      <div className="panel">
        <h2>Analysis runs</h2>
        <button onClick={handleStartRun} disabled={busy || artifacts.length === 0}>
          Start new analysis run
        </button>
        {artifacts.length === 0 && (
          <p className="muted">Upload a code zip before starting a run.</p>
        )}
        <ul className="project-list">
          {runs.map((r) => (
            <li key={r.id}>
              <Link href={`/projects/${projectId}/runs/${r.id}`}>
                Run {r.id.slice(0, 8)} - {r.status}
              </Link>
              <div className="project-meta">{new Date(r.created_at).toLocaleString()}</div>
            </li>
          ))}
          {runs.length === 0 && <li className="muted">No runs yet.</li>}
        </ul>
      </div>
    </div>
  );
}
