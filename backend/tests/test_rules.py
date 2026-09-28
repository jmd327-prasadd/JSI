from __future__ import annotations

from app.discovery.inventory import build_inventory
from app.rules.evaluate import evaluate_inventory
from tests.fixtures.builder import write_good_dbt_project


def _rule_ids(drafts) -> set[str]:
    return {d.rule_id for d in drafts}


def test_deterministic_rules_fire_as_expected(tmp_path):
    root = write_good_dbt_project(tmp_path / "good")
    inv = build_inventory(root)
    drafts = evaluate_inventory(inv, root)
    ids = _rule_ids(drafts)

    # select * in stg_orders_enriched
    assert "JQA-CODE-001" in ids
    # incremental without unique_key
    assert "JQA-OPS-001" in ids
    # doc/test coverage aggregates always reported when models exist
    assert "JQA-DOC-001" in ids
    assert "JQA-DQ-001" in ids
    # source missing description/freshness
    assert "JQA-DOC-002" in ids
    assert "JQA-OPS-002" in ids
    # CI/CD workflow issues baked into the fixture
    assert "JQA-CICD-002" in ids  # WITH: casing
    assert "JQA-CICD-003" in ids  # branch mismatch
    assert "JQA-CICD-004" in ids  # unpinned dbt install
    # secret scan
    assert "JQA-SEC-001" in ids

    # rules that should NOT fire on this clean-ish fixture
    assert "JQA-ARCH-001" not in ids
    assert "JQA-MNT-001" not in ids


def test_findings_carry_dependency_context(tmp_path):
    root = write_good_dbt_project(tmp_path / "good")
    inv = build_inventory(root)
    drafts = evaluate_inventory(inv, root)

    select_star_finding = next(d for d in drafts if d.rule_id == "JQA-CODE-001")
    assert select_star_finding.component == "models/staging/orders/stg_orders_enriched.sql"
    assert "fct_orders" in select_star_finding.downstream_models
    assert select_star_finding.verification  # populated from the rulebook's verification_template
