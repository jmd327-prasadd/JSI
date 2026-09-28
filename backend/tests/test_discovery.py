from __future__ import annotations

from app.discovery.inventory import build_inventory
from tests.fixtures.builder import write_broken_dbt_project, write_good_dbt_project


def test_discovers_dbt_project_and_models(tmp_path):
    root = write_good_dbt_project(tmp_path / "good")
    inv = build_inventory(root)

    assert len(inv["dbt_projects"]) == 1
    project = inv["dbt_projects"][0]
    model_names = {m["name"] for m in project["models"]}
    assert model_names == {"stg_orders", "stg_orders_enriched", "stg_order_line_items", "fct_orders"}
    assert len(project["workflows"]) == 1


def test_dependency_graph_links_models(tmp_path):
    root = write_good_dbt_project(tmp_path / "good")
    inv = build_inventory(root)
    project = inv["dbt_projects"][0]

    nodes = project["dependencies"]["nodes"]
    assert "stg_orders" in nodes["stg_orders_enriched"]["upstream"]
    assert "stg_order_line_items" in nodes["stg_orders_enriched"]["upstream"]
    assert "fct_orders" in nodes["stg_orders_enriched"]["downstream"]
    assert nodes["stg_orders_enriched"]["transitive_downstream_count"] >= 1


def test_broken_dbt_project_degrades_gracefully(tmp_path):
    root = write_broken_dbt_project(tmp_path / "broken")
    inv = build_inventory(root)

    project = inv["dbt_projects"][0]
    assert project["models"][0]["name"] == "orphan"
    unresolved = project["dependencies"]["unresolved_refs"]
    assert any(u["reference"] == "does_not_exist" for u in unresolved)
    # no schema.yml at all -- aggregates must not crash, just report zero coverage
    assert project["models_meta"] == []
