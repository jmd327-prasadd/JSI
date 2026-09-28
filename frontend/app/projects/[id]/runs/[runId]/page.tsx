"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { getRun, getRunFindings, getRunSummary } from "@/lib/api";
import { RUN_TERMINAL_STATUSES, type AnalysisRun, type Finding, type RunSummary } from "@/lib/types";
import { FindingCard } from "@/components/FindingCard";
import { ScoreCard } from "@/components/ScoreCard";

const SEVERITIES = ["Critical", "High", "Medium", "Low"];
const CATEGORIES = ["Code", "Documentation", "Environment"];
const DETECTION_TYPES = ["deterministic", "llm_assisted", "hybrid"];

export default function RunDetailPage() {
  const params = useParams<{ id: string; runId: string }>();
  const { id: projectId, runId } = params;

  const [run, setRun] = useState<AnalysisRun | null>(null);
  const [summary, setSummary] = useState<RunSummary | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [severity, setSeverity] = useState<string | null>(null);
  const [category, setCategory] = useState<string | null>(null);
  const [detectionType, setDetectionType] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      const r = await getRun(projectId, runId);
      if (cancelled) return;
      setRun(r);
      if (RUN_TERMINAL_STATUSES.has(r.status)) {
        if (pollRef.current) clearInterval(pollRef.current);
        if (r.status === "done") {
          const [s, f] = await Promise.all([
            getRunSummary(projectId, runId),
            getRunFindings(projectId, runId),
          ]);
          if (!cancelled) {
            setSummary(s);
            setFindings(f);
          }
        }
      }
    }

    poll();
    pollRef.current = setInterval(poll, 4000);
    return () => {
      cancelled = true;
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [projectId, runId]);

  async function refetchFindings() {
    const f = await getRunFindings(projectId, runId, {
      severity: severity || undefined,
      category: category || undefined,
      detection_type: detectionType || undefined,
    });
    setFindings(f);
  }

  useEffect(() => {
    if (run?.status === "done") refetchFindings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [severity, category, detectionType]);

  function handleFindingChanged(updated: Finding) {
    setFindings((prev) => prev.map((f) => (f.id === updated.id ? updated : f)));
  }

  if (!run) return <p className="muted">Loading...</p>;

  if (!RUN_TERMINAL_STATUSES.has(run.status)) {
    return (
      <div className="panel">
        <h1>Analysis in progress</h1>
        <p>{run.status_message || run.status}</p>
        <div className="progress-bar">
          <div className="progress-bar-fill" style={{ width: `${run.progress_pct}%` }} />
        </div>
        <p className="muted">{run.progress_pct}% - stage: {run.status}</p>
      </div>
    );
  }

  if (run.status === "failed") {
    return (
      <div className="panel">
        <h1>Analysis failed</h1>
        <p className="error-text">{run.error_message}</p>
      </div>
    );
  }

  const visibleFindings = findings.filter((f) =>
    search ? (f.title + f.component + f.evidence).toLowerCase().includes(search.toLowerCase()) : true
  );

  return (
    <div>
      <h1>Run results</h1>
      {summary && <ScoreCard summary={summary} />}

      <div className="panel">
        <h2>Findings</h2>
        <div className="form-row">
          {SEVERITIES.map((s) => (
            <span
              key={s}
              className={`chip ${severity === s ? "active" : ""}`}
              onClick={() => setSeverity(severity === s ? null : s)}
            >
              {s}
            </span>
          ))}
        </div>
        <div className="form-row">
          {CATEGORIES.map((c) => (
            <span
              key={c}
              className={`chip ${category === c ? "active" : ""}`}
              onClick={() => setCategory(category === c ? null : c)}
            >
              {c}
            </span>
          ))}
        </div>
        <div className="form-row">
          {DETECTION_TYPES.map((d) => (
            <span
              key={d}
              className={`chip ${detectionType === d ? "active" : ""}`}
              onClick={() => setDetectionType(detectionType === d ? null : d)}
            >
              {d === "deterministic" ? "Confirmed" : d}
            </span>
          ))}
          <input
            type="text"
            placeholder="Search title / file / evidence"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ flex: 1, minWidth: 200 }}
          />
        </div>

        <p className="muted">{visibleFindings.length} of {findings.length} findings shown</p>

        {visibleFindings.map((f) => (
          <FindingCard key={f.id} projectId={projectId} finding={f} onChanged={handleFindingChanged} />
        ))}
      </div>
    </div>
  );
}
