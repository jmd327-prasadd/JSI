"use client";

import { useState } from "react";
import { updateFindingStatus } from "@/lib/api";
import { FINDING_STATUSES, type Finding } from "@/lib/types";
import { SeverityBadge } from "./SeverityBadge";

export function FindingCard({
  projectId,
  finding,
  onChanged,
}: {
  projectId: string;
  finding: Finding;
  onChanged: (updated: Finding) => void;
}) {
  const [note, setNote] = useState(finding.reviewer_note);
  const [saving, setSaving] = useState(false);

  async function setStatus(status: string) {
    setSaving(true);
    try {
      const updated = await updateFindingStatus(projectId, finding.id, status, note);
      onChanged(updated);
    } finally {
      setSaving(false);
    }
  }

  return (
    <details className="finding-card">
      <summary>
        <SeverityBadge severity={finding.severity} />
        <span className="finding-title">{finding.title}</span>
        <span className="finding-component">{finding.component}</span>
        <span className="muted">
          {finding.rule_id} - {finding.category}
          {finding.subcategory ? ` / ${finding.subcategory}` : ""} -{" "}
          {finding.detection_type === "deterministic" ? "Confirmed" : "AI Assessment"}
        </span>
        <span className="muted">status: {finding.status}</span>
      </summary>

      <div className="finding-body">
        <div>
          <div className="finding-section-label">What JQA observed</div>
          <div>{finding.evidence}</div>
        </div>
        <div>
          <div className="finding-section-label">Why it matters</div>
          <div>{finding.impact}</div>
          {finding.impact_note && <div className="muted">{finding.impact_note}</div>}
        </div>
        <div>
          <div className="finding-section-label">Recommended solution</div>
          <div>{finding.recommendation}</div>
        </div>
        {finding.verification && (
          <div>
            <div className="finding-section-label">How to verify</div>
            <div>{finding.verification}</div>
          </div>
        )}
        {finding.detection_type !== "deterministic" && finding.ai_reasoning && (
          <div>
            <div className="finding-section-label">AI reasoning &amp; evidence cited</div>
            <div>{finding.ai_reasoning}</div>
            {finding.ai_evidence_cited.length > 0 && (
              <ul className="muted">
                {finding.ai_evidence_cited.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div className="form-row" style={{ marginTop: 8 }}>
          <select
            value={finding.status}
            disabled={saving}
            onChange={(e) => setStatus(e.target.value)}
          >
            {FINDING_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Reviewer note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            onBlur={() => setStatus(finding.status)}
            style={{ flex: 1, minWidth: 200 }}
          />
        </div>
      </div>
    </details>
  );
}
