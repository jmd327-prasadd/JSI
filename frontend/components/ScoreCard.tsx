import type { RunSummary } from "@/lib/types";
import { TrafficLight } from "./TrafficLight";

export function ScoreCard({ summary }: { summary: RunSummary }) {
  const categories = Object.keys(summary.traffic_light_by_category);

  return (
    <div className="panel">
      <h2>Onboarding readiness</h2>
      <div className="recommended-action">{summary.recommended_action}</div>

      <div className="scorecard-grid">
        {categories.map((cat) => (
          <div className="scorecard-cell" key={cat}>
            <div className="muted">{cat}</div>
            <TrafficLight
              color={summary.traffic_light_by_category[cat]}
              label={`${summary.readiness_score_by_category[cat]}/100`}
            />
          </div>
        ))}
        <div className="scorecard-cell">
          <div className="muted">Total findings</div>
          <div>{summary.total_findings}</div>
        </div>
      </div>

      <div className="form-row">
        {Object.entries(summary.counts_by_severity).map(([sev, count]) => (
          <span className="chip" key={sev}>
            {sev}: {count}
          </span>
        ))}
      </div>

      {summary.punch_list.length > 0 && (
        <div>
          <div className="finding-section-label">Open Critical / High punch list</div>
          <ul>
            {summary.punch_list.map((item, i) => (
              <li key={i} className="muted">
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
