from __future__ import annotations

import math
import re
from pathlib import Path

from app.discovery.walker import iter_files
from app.rules.finding_draft import FindingDraft
from app.rules.detectors._common import draft

PATTERNS = [
    ("JQA-SEC-001", "Hard-coded credential assignment", re.compile(
        r'(?i)\b(?:api[_-]?key|password|passwd|pwd|secret|client[_-]?secret|access[_-]?token|auth[_-]?token)\b'
        r'\s*[:=]\s*["\']([^"\']{8,})["\']'
    )),
    ("JQA-SEC-001", "Bearer token", re.compile(
        r'(?i)\bAuthorization\b\s*[:=]\s*["\']?\s*Bearer\s+([A-Za-z0-9._~+/=-]{12,})'
    )),
    ("JQA-SEC-002", "Private-key material", re.compile(
        r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'
    )),
    ("JQA-SEC-003", "Credential-bearing connection string", re.compile(
        r'(?i)(?:password|pwd|user(?:name)?)\s*=\s*[^;\s]+;.*(?:server|data source)=|'
        r'(?:server|data source)=.*(?:password|pwd)\s*='
    )),
]

_ENTROPY_CANDIDATE_RE = re.compile(
    r'(?i)\b(?:key|token|secret|credential)\b\s*[:=]\s*["\']([A-Za-z0-9+/=_\-.]{20,})["\']'
)


def _entropy(s: str) -> float:
    n = len(s)
    if not n:
        return 0.0
    return -sum((s.count(c) / n) * math.log2(s.count(c) / n) for c in set(s))


def scan_security(root: Path) -> list[FindingDraft]:
    """Regex-based secret scan over every text file in the artifact -- runs
    independently of dbt/Snowflake/Power BI classification since credentials
    can appear in any file type. Ported from the JQA PoC (jqa/rules/security.py).
    """
    out: list[FindingDraft] = []
    for path in iter_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = path.relative_to(root).as_posix()

        for rule_id, kind, pattern in PATTERNS:
            for m in pattern.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                out.append(draft(
                    rule_id, rel, f"Potential hard-coded credential: {kind}",
                    f"Line {line}; suspected value is [REDACTED].",
                    "Credential exposure can enable unauthorised access and complicate rotation and incident response.",
                    "Verify locally; if confirmed, revoke/rotate the credential, remove it from source control/history "
                    "as appropriate, and use approved secret management.",
                    evidence_lines=[line],
                ))

        for m in _ENTROPY_CANDIDATE_RE.finditer(text):
            if _entropy(m.group(1)) >= 3.5:
                line = text.count("\n", 0, m.start()) + 1
                out.append(draft(
                    "JQA-SEC-004", rel, "Suspicious high-entropy credential-like string",
                    f"Line {line}; value is [REDACTED].",
                    "Long random-looking values may represent credentials that evade simple keyword checks.",
                    "Verify locally and rotate/store securely if it is a credential.",
                    evidence_lines=[line],
                ))

    seen = set()
    uniq = []
    for f in out:
        key = (f.rule_id, f.component, tuple(f.evidence_lines), f.title)
        if key not in seen:
            seen.add(key)
            uniq.append(f)
    return uniq
