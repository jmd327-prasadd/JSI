from __future__ import annotations

from collections import Counter

from app.models.finding import Finding

SEVERITY_WEIGHT = {"Critical": 15, "High": 7, "Medium": 3, "Low": 1}
CLOSED_STATUSES = {"False Positive", "Won't Fix"}
CATEGORIES = ["Code", "Documentation", "Environment"]


def _is_open(f: Finding) -> bool:
    return f.status not in CLOSED_STATUSES


def summarize(findings: list[Finding]) -> dict:
    counts_by_severity = Counter(f.severity for f in findings)
    counts_by_category = Counter(f.category for f in findings)

    traffic_light: dict[str, str] = {}
    readiness_score: dict[str, int] = {}
    for category in CATEGORIES:
        open_in_cat = [f for f in findings if f.category == category and _is_open(f)]
        if not open_in_cat:
            traffic_light[category] = "Green"
            readiness_score[category] = 100
            continue
        sev_counts = Counter(f.severity for f in open_in_cat)
        if sev_counts.get("Critical", 0) > 0:
            traffic_light[category] = "Red"
        elif sev_counts.get("High", 0) > 0 or sev_counts.get("Medium", 0) > 5:
            traffic_light[category] = "Amber"
        else:
            traffic_light[category] = "Green"
        penalty = sum(SEVERITY_WEIGHT.get(sev, 0) * n for sev, n in sev_counts.items())
        readiness_score[category] = max(0, 100 - penalty)

    if "Red" in traffic_light.values():
        recommended_action = "Bounce back to development team"
        open_blockers = [
            f for f in findings
            if _is_open(f) and f.severity in {"Critical", "High"}
        ]
        punch_list = [f"[{f.rule_id}] {f.title} ({f.component})" for f in open_blockers]
    elif all(v == "Green" for v in traffic_light.values()):
        recommended_action = "Onboard as-is"
        punch_list = []
    else:
        recommended_action = "Onboard with fix-ups"
        open_blockers = [
            f for f in findings
            if _is_open(f) and f.severity in {"Critical", "High"}
        ]
        punch_list = [f"[{f.rule_id}] {f.title} ({f.component})" for f in open_blockers]

    return {
        "counts_by_severity": dict(counts_by_severity),
        "counts_by_category": dict(counts_by_category),
        "total_findings": len(findings),
        "traffic_light_by_category": traffic_light,
        "readiness_score_by_category": readiness_score,
        "recommended_action": recommended_action,
        "punch_list": punch_list,
    }
