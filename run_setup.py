"""
Brand Performance Manager — Full setup runner.

Runs all schema/table DDL via Databricks Statement Execution API,
creates the Lakebase HITL table, and verifies the setup.

Usage:
    python3 run_setup.py

Prerequisites:
    pip install reportlab  (optional — only needed if generating PDFs locally)

Configuration:
    Edit the HOST, TOKEN, WH_ID, and CATALOG constants below before running.
    Or set environment variables: DATABRICKS_HOST, DATABRICKS_TOKEN, BPM_WAREHOUSE_ID.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import urllib.error

# ── Configuration — update these before running ───────────────────────────────

HOST    = os.environ.get("DATABRICKS_HOST",  "https://<your-workspace>.azuredatabricks.net").rstrip("/")
TOKEN   = os.environ.get("DATABRICKS_TOKEN", "<your-personal-access-token>")
WH_ID   = os.environ.get("BPM_WAREHOUSE_ID", "<your-sql-warehouse-id>")
CATALOG = os.environ.get("BPM_CATALOG",      "ar_dpcatalog")
SCHEMA  = "brand_performance"
UTILS   = "brand_perf_utils"

# Lakebase connection (PostgreSQL) — set these if you have a Lakebase project
LB_CATALOG = "brand_perf_lakebase"  # Lakebase catalog name in Unity Catalog
LB_SCHEMA  = "hitl"

# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _req(method: str, path: str, body: dict | None = None,
         raw_bytes: bytes | None = None, content_type: str = "application/json") -> dict:
    url  = f"{HOST}{path}"
    data = None
    if raw_bytes is not None:
        data = raw_bytes
    elif body is not None:
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body_txt = exc.read().decode()
        return {"_error": exc.code, "_body": body_txt}


def run_sql(statement: str, label: str = "", wait_secs: int = 90) -> bool:
    """Execute a SQL statement via Statement Execution API and wait for completion."""
    resp = _req("POST", "/api/2.0/sql/statements", {
        "statement":    statement,
        "warehouse_id": WH_ID,
        "wait_timeout": "50s",
    })
    if "_error" in resp:
        print(f"  ❌ {label}: HTTP {resp['_error']} — {resp['_body'][:300]}")
        return False

    stmt_id = resp.get("statement_id")
    state   = resp.get("status", {}).get("state", "UNKNOWN")

    deadline = time.time() + wait_secs
    while state in ("PENDING", "RUNNING") and time.time() < deadline:
        time.sleep(2)
        poll  = _req("GET", f"/api/2.0/sql/statements/{stmt_id}")
        state = poll.get("status", {}).get("state", "UNKNOWN")

    if state == "SUCCEEDED":
        print(f"  ✅ {label}")
        return True
    err = resp.get("status", {}).get("error", {}).get("message", "")[:300]
    print(f"  ❌ {label}: {state} — {err}")
    return False


def run_sql_select(statement: str, label: str = "") -> list[dict] | None:
    """Execute a SELECT and return rows as list of dicts."""
    resp = _req("POST", "/api/2.0/sql/statements", {
        "statement":    statement,
        "warehouse_id": WH_ID,
        "wait_timeout": "30s",
    })
    if "_error" in resp:
        print(f"  ❌ {label}: HTTP {resp['_error']}")
        return None
    state = resp.get("status", {}).get("state", "UNKNOWN")
    if state != "SUCCEEDED":
        print(f"  ❌ {label}: {state}")
        return None
    schema  = resp.get("manifest", {}).get("schema", {}).get("columns", [])
    rows    = resp.get("result", {}).get("data_array", [])
    col_names = [c["name"] for c in schema]
    return [dict(zip(col_names, row)) for row in rows]


# ── Step 1: Unity Catalog schema setup ───────────────────────────────────────

def setup_schemas() -> bool:
    print("\n[1/5] Creating Unity Catalog schemas...")
    ok = True
    ok &= run_sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}",  "brand_performance schema")
    ok &= run_sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{UTILS}",   "brand_perf_utils schema")
    ok &= run_sql(f"CREATE VOLUME  IF NOT EXISTS {CATALOG}.{SCHEMA}.raw_data", "raw_data volume")
    return ok


# ── Step 2: Delta table DDL ────────────────────────────────────────────────────

def create_tables() -> bool:
    print("\n[2/5] Creating Delta tables...")
    ok = True

    ok &= run_sql(f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.brand_topline_metrics (
            week_ending         DATE    NOT NULL COMMENT 'Week end date (Saturday)',
            brand               STRING  NOT NULL COMMENT 'Brand name',
            manufacturer        STRING  NOT NULL COMMENT 'Parent manufacturer',
            category            STRING  NOT NULL COMMENT 'Category (Infant Formula, Baby Food, Toddler Snacks)',
            subcategory         STRING           COMMENT 'Subcategory',
            retailer            STRING  NOT NULL COMMENT 'Retailer or Total US',
            region              STRING  NOT NULL COMMENT 'Nielsen geographic region',
            dollar_sales        DOUBLE  NOT NULL COMMENT 'Total dollar sales ($)',
            unit_sales          BIGINT  NOT NULL COMMENT 'Total unit volume',
            value_share_pct     DOUBLE  NOT NULL COMMENT 'Dollar share of category (%)',
            volume_share_pct    DOUBLE  NOT NULL COMMENT 'Unit share of category (%)',
            yoy_dollar_chg_pct  DOUBLE           COMMENT 'YoY dollar change (%)',
            yoy_volume_chg_pct  DOUBLE           COMMENT 'YoY volume change (%)',
            l4w_value_share     DOUBLE           COMMENT 'Rolling 4-week avg value share (%)',
            l12w_value_share    DOUBLE           COMMENT 'Rolling 12-week avg value share (%)',
            l52w_value_share    DOUBLE           COMMENT 'Rolling 52-week avg value share (%)'
        )
        COMMENT 'Weekly brand-level sales and share metrics (synthetic CPG data)'
        TBLPROPERTIES ('delta.autoOptimize.optimizeWrite' = 'true')
    """, "brand_topline_metrics DDL")

    ok &= run_sql(f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.market_share_decomposition (
            week_ending                    DATE    NOT NULL,
            brand                          STRING  NOT NULL,
            category                       STRING  NOT NULL,
            retailer                       STRING  NOT NULL,
            region                         STRING  NOT NULL,
            share_change_ppt               DOUBLE  COMMENT 'Total share change (ppt)',
            distribution_contribution_ppt  DOUBLE  COMMENT 'Distribution driver (ppt)',
            rate_contribution_ppt          DOUBLE  COMMENT 'Rate/mix driver (ppt)',
            penetration_contribution_ppt   DOUBLE  COMMENT 'Penetration driver (ppt)',
            frequency_contribution_ppt     DOUBLE  COMMENT 'Frequency driver (ppt)',
            basket_size_contribution_ppt   DOUBLE  COMMENT 'Basket size driver (ppt)',
            price_index_vs_category        DOUBLE  COMMENT 'Price index vs. category avg (100=parity)',
            promotion_support_pct          DOUBLE  COMMENT '% ACV on promotion'
        )
        COMMENT 'Weekly brand share change decomposition into rate and distribution drivers'
        TBLPROPERTIES ('delta.autoOptimize.optimizeWrite' = 'true')
    """, "market_share_decomposition DDL")

    ok &= run_sql(f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.insurgent_brand_tracker (
            week_ending           DATE    NOT NULL,
            brand                 STRING  NOT NULL,
            parent_company        STRING           COMMENT 'Parent company of insurgent brand',
            category              STRING  NOT NULL,
            subcategory           STRING           COMMENT 'Subcategory',
            retailer              STRING  NOT NULL,
            region                STRING  NOT NULL,
            value_share_pct       DOUBLE  NOT NULL COMMENT 'Dollar share (%)',
            volume_share_pct      DOUBLE           COMMENT 'Volume share (%)',
            acv_pct               DOUBLE  NOT NULL COMMENT 'ACV weighted distribution (%)',
            velocity_per_mm_acv   DOUBLE           COMMENT 'Velocity per $1M ACV',
            share_gain_4w_ppt     DOUBLE           COMMENT '4-week share gain (ppt)',
            share_gain_12w_ppt    DOUBLE           COMMENT '12-week share gain (ppt)',
            share_gain_52w_ppt    DOUBLE           COMMENT '52-week share gain (ppt)',
            is_direct_competitor  BOOLEAN          COMMENT 'True if direct category competitor',
            threat_score          DOUBLE           COMMENT 'Composite threat score (0-100)'
        )
        COMMENT 'Weekly insurgent and challenger brand performance tracker'
        TBLPROPERTIES ('delta.autoOptimize.optimizeWrite' = 'true')
    """, "insurgent_brand_tracker DDL")

    ok &= run_sql(f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.distribution_velocity (
            week_ending           DATE    NOT NULL,
            sku_id                STRING  NOT NULL COMMENT 'SKU identifier',
            sku_name              STRING  NOT NULL COMMENT 'SKU display name',
            brand                 STRING  NOT NULL,
            category              STRING  NOT NULL,
            retailer              STRING  NOT NULL,
            region                STRING  NOT NULL,
            acv_pct               DOUBLE  NOT NULL COMMENT 'ACV weighted distribution (%)',
            stores_selling        INT              COMMENT 'Number of stores selling',
            total_stores          INT              COMMENT 'Total stores in retailer/region',
            velocity_per_mm_acv   DOUBLE           COMMENT 'Velocity per $1M ACV',
            out_of_stock_rate_pct DOUBLE           COMMENT 'Out-of-stock rate (%)',
            yoy_acv_chg_ppt       DOUBLE           COMMENT 'YoY ACV change (ppt)',
            yoy_velocity_chg_pct  DOUBLE           COMMENT 'YoY velocity change (%)',
            facings               INT              COMMENT 'Shelf facings count',
            shelf_position        STRING           COMMENT 'Shelf position (Eye Level, Top, Bottom)'
        )
        COMMENT 'Weekly SKU-level ACV distribution and velocity metrics'
        TBLPROPERTIES ('delta.autoOptimize.optimizeWrite' = 'true')
    """, "distribution_velocity DDL")

    ok &= run_sql(f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.category_benchmarks (
            week_ending                    DATE    NOT NULL,
            category                       STRING  NOT NULL,
            retailer                       STRING  NOT NULL,
            region                         STRING  NOT NULL,
            total_category_dollar_sales    DOUBLE  COMMENT 'Total weekly category dollar sales',
            yoy_category_growth_pct        DOUBLE  COMMENT 'YoY category growth (%)',
            avg_velocity_per_mm_acv        DOUBLE  COMMENT 'Category avg velocity per $1M ACV',
            leader_value_share_pct         DOUBLE  COMMENT 'Category leader dollar share (%)',
            top3_concentration_pct         DOUBLE  COMMENT 'Top-3 brand share concentration (%)',
            private_label_share_pct        DOUBLE  COMMENT 'Private label share (%)',
            avg_price_per_unit             DOUBLE  COMMENT 'Category avg price per unit ($)',
            promotional_pressure_pct       DOUBLE  COMMENT '% category volume on promotion'
        )
        COMMENT 'Weekly category-level benchmarks and norms'
        TBLPROPERTIES ('delta.autoOptimize.optimizeWrite' = 'true')
    """, "category_benchmarks DDL")

    return ok


# ── Step 3: Lakebase HITL table ───────────────────────────────────────────────

def create_lakebase_table() -> bool:
    """Create the HITL pending_confirmations table in Lakebase.
    Note: This assumes the Lakebase project is already provisioned and registered
    as a catalog in Unity Catalog. Update LB_CATALOG if needed.
    """
    print("\n[3/5] Creating Lakebase HITL table...")

    # Create the hitl schema in Lakebase (via UC)
    ok = run_sql(
        f"CREATE SCHEMA IF NOT EXISTS {LB_CATALOG}.{LB_SCHEMA}",
        f"Lakebase schema {LB_CATALOG}.{LB_SCHEMA}"
    )
    if not ok:
        print("  ⚠️  Lakebase schema creation failed — Lakebase may not be provisioned yet.")
        print("     Set up a Lakebase project and update LB_CATALOG in run_setup.py, then re-run.")
        return False

    ok = run_sql(f"""
        CREATE TABLE IF NOT EXISTS {LB_CATALOG}.{LB_SCHEMA}.pending_confirmations (
            confirmation_id   STRING  NOT NULL COMMENT 'Unique confirmation record ID (UUID)',
            query_id          STRING  NOT NULL COMMENT 'Agent query ID (from validate_routing_decision)',
            session_id        STRING  NOT NULL COMMENT 'User session ID from Streamlit',
            query_text        STRING           COMMENT 'Original user question text',
            question_type     STRING           COMMENT 'topline | insurgent_brands | distribution_velocity',
            proposed_route    STRING           COMMENT 'Agent or resource to route to',
            route_explanation STRING           COMMENT 'Human-readable routing rationale',
            status            STRING  NOT NULL DEFAULT 'PENDING' COMMENT 'PENDING | CONFIRMED | REJECTED',
            created_at        TIMESTAMP        DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
            resolved_at       TIMESTAMP        COMMENT 'Time user confirmed or rejected',
            CONSTRAINT pk_confirmation_id PRIMARY KEY (confirmation_id)
        )
    """, "Lakebase pending_confirmations table")

    return ok


# ── Step 4: Verify row counts (after data notebooks run) ─────────────────────

def verify_data() -> bool:
    """Check that data notebooks have been run and tables are populated."""
    print("\n[4/5] Verifying data layer...")
    tables = {
        "brand_topline_metrics":       10_000,
        "market_share_decomposition":   5_000,
        "insurgent_brand_tracker":     15_000,
        "distribution_velocity":       40_000,
        "category_benchmarks":          1_000,
    }

    all_ok = True
    for table, min_rows in tables.items():
        rows = run_sql_select(
            f"SELECT COUNT(*) AS cnt FROM {CATALOG}.{SCHEMA}.{table}",
            f"count {table}"
        )
        if rows is None:
            print(f"  ⚠️  Could not query {table} — run notebook 01 first.")
            all_ok = False
            continue
        n = int(rows[0]["cnt"])
        status = "✅" if n >= min_rows else "⚠️ "
        if n < min_rows:
            all_ok = False
        print(f"  {status} {CATALOG}.{SCHEMA}.{table:<35} → {n:>8,} rows  (min {min_rows:>7,})")

    return all_ok


# ── Step 5: Print summary ─────────────────────────────────────────────────────

def print_summary(all_ok: bool) -> None:
    print("\n" + "=" * 65)
    print("  BRAND PERFORMANCE MANAGER — SETUP COMPLETE" if all_ok else
          "  BRAND PERFORMANCE MANAGER — SETUP COMPLETED WITH WARNINGS")
    print("=" * 65)
    print(f"""
  Catalog   : {CATALOG}
  Schema    : {CATALOG}.{SCHEMA}
  Utils     : {CATALOG}.{UTILS}
  Lakebase  : {LB_CATALOG}.{LB_SCHEMA}.pending_confirmations

  Next steps:
    1. Run notebooks/01_generate_brand_data.py   (populate Delta tables)
    2. Run notebooks/02_generate_brand_docs.py   (upload KA PDFs)
    3. Run notebooks/03_create_uc_functions.py   (register UC Functions)
    4. Run notebooks/04_create_agentbricks.py    (create Genie + KA + MAS agents)
    5. Copy BPM_AGENT_ENDPOINT from notebook 04 output into app/app.yaml
    6. databricks bundle deploy --target dev
    7. Open the Databricks Apps URL in the browser
""")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 65)
    print("  BRAND PERFORMANCE MANAGER — SETUP")
    print("=" * 65)
    print(f"\n  Host    : {HOST}")
    print(f"  Catalog : {CATALOG}")
    print(f"  WH ID   : {WH_ID}")

    if HOST.startswith("https://<your") or TOKEN.startswith("<your") or WH_ID.startswith("<your"):
        print("""
  ❌  Configuration incomplete. Update the following before running:
      HOST    — your Databricks workspace URL
      TOKEN   — a Databricks Personal Access Token (or set DATABRICKS_TOKEN env var)
      WH_ID   — a running SQL warehouse ID (or set BPM_WAREHOUSE_ID env var)
      CATALOG — the Unity Catalog catalog name

  Or export environment variables:
      export DATABRICKS_HOST=https://your-workspace.azuredatabricks.net
      export DATABRICKS_TOKEN=dapiXXXXXXXXXXXXXXXX
      export BPM_WAREHOUSE_ID=your_warehouse_id
""")
        sys.exit(1)

    ok = True
    ok &= setup_schemas()
    ok &= create_tables()
    lakebase_ok = create_lakebase_table()
    data_ok     = verify_data()

    print_summary(ok and lakebase_ok and data_ok)

    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
