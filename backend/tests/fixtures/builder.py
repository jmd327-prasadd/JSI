from __future__ import annotations

import shutil
from pathlib import Path

GOOD_FILES: dict[str, str] = {
    "dbt_project.yml": "name: 'analytics'\nversion: '1.0.0'\nprofile: 'analytics'\n",

    "models/staging/orders/schema.yml": """
version: 2
models:
  - name: stg_orders
    description: "Cleaned raw orders, 1 row per order."
    tests: []
    columns: []
sources:
  - name: raw
    database: RAW
    schema: RAW
    tables:
      - name: orders
      - name: order_line_items
""".strip() + "\n",

    "models/staging/orders/stg_orders.sql": """
select
    order_id,
    customer_id,
    order_ts,
    status
from {{ source('raw', 'orders') }}
""".strip() + "\n",

    "models/staging/orders/stg_orders_enriched.sql": """
{{ config(materialized='incremental') }}
select *
from {{ ref('stg_orders') }} o
join {{ ref('stg_order_line_items') }} li on o.order_id = li.order_id
{% if is_incremental() %}
where o.order_ts > (select max(order_ts) from {{ this }})
{% endif %}
""".strip() + "\n",

    "models/staging/orders/stg_order_line_items.sql": """
select
    order_id,
    sku,
    qty,
    line_total
from {{ source('raw', 'order_line_items') }}
""".strip() + "\n",

    "models/marts/orders/fct_orders.sql": """
select
    o.order_id,
    o.customer_id,
    o.status
from {{ ref('stg_orders_enriched') }} o
""".strip() + "\n",

    ".github/workflows/ci.yml": """
name: CI
on:
  push:
    branches:
      - develop
jobs:
  deploy:
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - run: pip install dbt-core dbt-snowflake
      - uses: actions/checkout@v4
        WITH:
          fetch-depth: 0
""".strip() + "\n",

    "config/settings.py": 'password = "hunter2_super_secret_pw"\n',
}


def write_fixture_project(root: Path, files: dict[str, str]) -> Path:
    for rel_path, content in files.items():
        target = root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


def write_good_dbt_project(root: Path) -> Path:
    return write_fixture_project(root, GOOD_FILES)


def write_broken_dbt_project(root: Path) -> Path:
    """A deliberately incomplete/broken dbt project: no schema.yml at all, a
    model referencing a ref() that doesn't exist, no CI workflow. Discovery
    must degrade gracefully (empty aggregates, unresolved_refs entry) rather
    than crash.
    """
    files = {
        "dbt_project.yml": "name: 'broken'\nversion: '1.0.0'\nprofile: 'broken'\n",
        "models/orphan.sql": "select * from {{ ref('does_not_exist') }}\n",
    }
    return write_fixture_project(root, files)


def zip_dir(src_dir: Path, dest_zip: Path) -> Path:
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    archive = shutil.make_archive(str(dest_zip.with_suffix("")), "zip", root_dir=src_dir)
    return Path(archive)
