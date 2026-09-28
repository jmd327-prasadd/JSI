from __future__ import annotations

from collections import defaultdict
import re

# Ported near-verbatim from the JQA PoC (jqa/dependencies.py) -- this regex-based
# ref()/source() graph over raw dbt Jinja is deliberately not a real dbt manifest
# parse; see discovery/dbt.py for the rationale.

REF_RE = re.compile(r"\{\{\s*ref\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}", re.I)
SOURCE_RE = re.compile(r"\{\{\s*source\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}", re.I)


def build_dependency_graph(inv: dict) -> dict:
    model_names = {m["name"] for m in inv.get("models", [])}
    source_keys = set()
    for s in inv.get("sources", []):
        for t in s.get("tables") or []:
            if isinstance(t, dict) and t.get("name"):
                source_keys.add((s["name"], str(t["name"])))
            elif isinstance(t, str):
                source_keys.add((s["name"], t))

    nodes: dict = {}
    edges: list = []
    upstream = defaultdict(list)
    downstream = defaultdict(list)
    unresolved_refs = []
    unresolved_sources = []

    for m in inv.get("models", []):
        name = m["name"]
        nodes[name] = {
            "name": name,
            "path": m["path"],
            "layer": m.get("layer", ""),
            "domain": m.get("domain", ""),
        }
        text = m.get("text", "")
        refs: list = []
        for ref in REF_RE.findall(text):
            if ref not in refs:
                refs.append(ref)
                if ref in model_names:
                    edges.append({"from": ref, "to": name, "type": "ref"})
                    upstream[name].append(ref)
                    downstream[ref].append(name)
                else:
                    unresolved_refs.append({"model": name, "reference": ref})
        srcs: list = []
        for src_name, table_name in SOURCE_RE.findall(text):
            key = (src_name, table_name)
            if key not in srcs:
                srcs.append(key)
                node = f"source:{src_name}.{table_name}"
                edges.append({"from": node, "to": name, "type": "source"})
                upstream[name].append(node)
                downstream[node].append(name)
                if key not in source_keys:
                    unresolved_sources.append({"model": name, "source": src_name, "table": table_name})
        nodes[name]["upstream"] = list(upstream[name])
        nodes[name]["downstream"] = []
        nodes[name]["upstream_model_count"] = sum(1 for x in upstream[name] if x in model_names)

    for name in model_names:
        nodes[name]["downstream"] = list(downstream[name])
        nodes[name]["downstream_model_count"] = len([x for x in downstream[name] if x in model_names])

    def walk(start: str, direction: dict) -> list[str]:
        seen: set = set()
        q = list(direction.get(start, []))
        while q:
            cur = q.pop(0)
            if cur in seen:
                continue
            seen.add(cur)
            q.extend(direction.get(cur, []))
        return sorted(seen)

    for name in model_names:
        nodes[name]["transitive_downstream"] = walk(name, downstream)
        nodes[name]["transitive_downstream_count"] = len(
            [x for x in nodes[name]["transitive_downstream"] if x in model_names]
        )
        nodes[name]["transitive_upstream"] = walk(name, upstream)
        nodes[name]["transitive_upstream_count"] = len(
            [x for x in nodes[name]["transitive_upstream"] if x in model_names]
        )

    hotspots = sorted(
        [
            {
                "name": n, "path": nodes[n]["path"],
                "direct_downstream": nodes[n]["downstream_model_count"],
                "transitive_downstream": nodes[n]["transitive_downstream_count"],
                "layer": nodes[n]["layer"], "domain": nodes[n]["domain"],
            }
            for n in model_names
            if nodes[n]["downstream_model_count"] or nodes[n]["transitive_downstream_count"]
        ],
        key=lambda x: (-x["transitive_downstream"], -x["direct_downstream"], x["name"]),
    )

    inv["dependencies"] = {
        "nodes": nodes,
        "edges": edges,
        "model_edges": [e for e in edges if e["type"] == "ref"],
        "source_edges": [e for e in edges if e["type"] == "source"],
        "unresolved_refs": unresolved_refs,
        "unresolved_sources": unresolved_sources,
        "hotspots": hotspots,
        "model_count": len(model_names),
        "model_edge_count": len([e for e in edges if e["type"] == "ref"]),
        "source_edge_count": len([e for e in edges if e["type"] == "source"]),
        "models_with_downstream": sum(1 for n in model_names if nodes[n]["downstream_model_count"]),
    }
    return inv["dependencies"]
