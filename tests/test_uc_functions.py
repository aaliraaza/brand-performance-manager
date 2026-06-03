"""
test_uc_functions.py — Unit tests for Brand Performance Manager UC Functions.

Tests enrich_user_request, validate_routing_decision, and format_visualization_spec.
Requires Databricks Statement Execution API access.

Set environment variables before running:
    export DATABRICKS_HOST=https://your-workspace.azuredatabricks.net
    export DATABRICKS_TOKEN=dapi...
    export BPM_WAREHOUSE_ID=your_warehouse_id
    export BPM_CATALOG=ar_dpcatalog
"""

from __future__ import annotations

import json
import os
import time
import unittest
import urllib.request
import urllib.error
import uuid

import pytest

CATALOG  = os.environ.get("BPM_CATALOG",      "ar_dpcatalog")
HOST     = os.environ.get("DATABRICKS_HOST",  "").rstrip("/")
TOKEN    = os.environ.get("DATABRICKS_TOKEN", os.environ.get("MJN_API_TOKEN", ""))
WH_ID    = os.environ.get("BPM_WAREHOUSE_ID", "")
UTILS    = f"{CATALOG}.brand_perf_utils"


# ── SQL helper ────────────────────────────────────────────────────────────────

def run_sql(statement: str, timeout: int = 60) -> list[dict] | None:
    """Execute SQL via Statement Execution API and return result rows."""
    body = json.dumps({
        "statement":    statement,
        "warehouse_id": WH_ID,
        "wait_timeout": f"{min(timeout, 50)}s",
    }).encode()
    req = urllib.request.Request(
        url     = f"{HOST}/api/2.0/sql/statements",
        data    = body,
        headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        method  = "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout + 5) as resp:
            result = json.loads(resp.read())
    except Exception as exc:
        pytest.skip(f"Cannot reach Databricks: {exc}")
        return None

    state = result.get("status", {}).get("state", "UNKNOWN")
    deadline = time.time() + timeout
    stmt_id  = result.get("statement_id")
    while state in ("PENDING", "RUNNING") and time.time() < deadline:
        time.sleep(2)
        try:
            with urllib.request.urlopen(
                urllib.request.Request(
                    f"{HOST}/api/2.0/sql/statements/{stmt_id}",
                    headers={"Authorization": f"Bearer {TOKEN}"},
                ), timeout=15
            ) as r:
                result = json.loads(r.read())
            state = result.get("status", {}).get("state", "UNKNOWN")
        except Exception:
            break

    if state != "SUCCEEDED":
        err = result.get("status", {}).get("error", {}).get("message", state)
        raise AssertionError(f"SQL failed ({state}): {err}\nStatement: {statement[:200]}")

    cols = [c["name"] for c in result.get("manifest", {}).get("schema", {}).get("columns", [])]
    rows = result.get("result", {}).get("data_array", [])
    return [dict(zip(cols, row)) for row in rows]


def call_enrich(query: str) -> dict:
    rows = run_sql(f"SELECT {UTILS}.enrich_user_request('{query}') AS r")
    assert rows, "enrich_user_request returned no rows"
    r = rows[0]["r"]
    if isinstance(r, str):
        r = json.loads(r)
    return r


# ── enrich_user_request tests ─────────────────────────────────────────────────

class TestEnrichUserRequest(unittest.TestCase):

    def setUp(self):
        if not HOST or not TOKEN or not WH_ID:
            self.skipTest("DATABRICKS_HOST / DATABRICKS_TOKEN / BPM_WAREHOUSE_ID not set")

    def test_enrich_complete(self):
        """Complete query with brand + retailer + time window."""
        r = call_enrich("Why did NovaBaby share drop last 4 weeks at Walmart?")
        self.assertTrue(
            r.get("is_complete"), f"Expected is_complete=True, got: {r}"
        )
        self.assertIn(
            "novababy", (r.get("brand") or "").lower(),
            f"Expected brand=NovaBaby, got: {r.get('brand')}"
        )
        self.assertEqual(
            r.get("time_window_weeks"), 4,
            f"Expected time_window_weeks=4, got: {r.get('time_window_weeks')}"
        )
        self.assertEqual(
            r.get("question_type"), "topline",
            f"Expected question_type=topline, got: {r.get('question_type')}"
        )

    def test_enrich_incomplete(self):
        """Query missing brand should return is_complete=False with 'brand' in missing_params."""
        r = call_enrich("What is our share trend this quarter?")
        self.assertFalse(
            r.get("is_complete"), f"Expected is_complete=False, got: {r}"
        )
        missing = r.get("missing_params") or []
        self.assertIn("brand", missing, f"Expected 'brand' in missing_params, got: {missing}")

    def test_enrich_insurgent(self):
        """Insurgent brand question should classify as insurgent_brands."""
        r = call_enrich("Which insurgent brands are gaining share in Baby Food?")
        self.assertEqual(
            r.get("question_type"), "insurgent_brands",
            f"Expected insurgent_brands, got: {r.get('question_type')}"
        )

    def test_enrich_distribution(self):
        """Distribution question should classify as distribution_velocity."""
        r = call_enrich("Which SKUs have below 80% ACV in the Northeast?")
        self.assertEqual(
            r.get("question_type"), "distribution_velocity",
            f"Expected distribution_velocity, got: {r.get('question_type')}"
        )

    def test_enrich_out_of_scope(self):
        """Weather question should be out_of_scope with is_complete=False."""
        r = call_enrich("What is the weather forecast for Chicago today?")
        self.assertEqual(
            r.get("question_type"), "out_of_scope",
            f"Expected out_of_scope, got: {r.get('question_type')}"
        )
        self.assertFalse(
            r.get("is_complete"), f"Expected is_complete=False for out_of_scope"
        )

    def test_enrich_default_time_window(self):
        """Query without time window should default to 12 weeks."""
        r = call_enrich("Show me NovaBaby share in Infant Formula")
        self.assertEqual(
            r.get("time_window_weeks"), 12,
            f"Expected default time_window_weeks=12, got: {r.get('time_window_weeks')}"
        )

    def test_enrich_default_retailer(self):
        """Query without retailer should default to 'Total US'."""
        r = call_enrich("Show me NovaBaby share in Infant Formula last 8 weeks")
        self.assertEqual(
            r.get("retailer"), "Total US",
            f"Expected retailer='Total US', got: {r.get('retailer')}"
        )
        self.assertEqual(
            r.get("time_window_weeks"), 8,
            f"Expected time_window_weeks=8, got: {r.get('time_window_weeks')}"
        )


# ── format_visualization_spec tests (OPTIONAL — off the default path) ─────────
# The app renders charts deterministically (see test_visualization.py); this UC
# Function is kept only as an optional LLM fallback. Enable with BPM_TEST_OPTIONAL=1.

class TestFormatVisualizationSpec(unittest.TestCase):

    def setUp(self):
        if os.environ.get("BPM_TEST_OPTIONAL") != "1":
            self.skipTest("optional function — set BPM_TEST_OPTIONAL=1 to test format_visualization_spec")
        if not HOST or not TOKEN or not WH_ID:
            self.skipTest("DATABRICKS_HOST / DATABRICKS_TOKEN / BPM_WAREHOUSE_ID not set")

    def test_returns_valid_plotly_json(self):
        """format_visualization_spec should return valid JSON with 'data' key."""
        test_data = '[{"week":"W1","share":35.2},{"week":"W2","share":34.8},{"week":"W3","share":34.1}]'
        rows = run_sql(f"""
            SELECT {UTILS}.format_visualization_spec(
                '{test_data}',
                'line',
                'NovaBaby Value Share Trend'
            ) AS viz_spec
        """)
        self.assertIsNotNone(rows)
        viz_json = rows[0]["viz_spec"]
        self.assertTrue(
            viz_json.strip().startswith("{"),
            f"Expected JSON object, got: {viz_json[:100]}"
        )
        parsed = json.loads(viz_json)
        self.assertIn("data", parsed, f"Expected 'data' key in Plotly JSON, got keys: {list(parsed.keys())}")

    def test_bar_chart_spec(self):
        """Should handle bar chart type."""
        test_data = '[{"brand":"NovaBaby","share":35.2},{"brand":"PuraMilk","share":30.1},{"brand":"BabyFirst","share":10.8}]'
        rows = run_sql(f"""
            SELECT {UTILS}.format_visualization_spec(
                '{test_data}',
                'bar',
                'Brand Value Share Comparison'
            ) AS viz_spec
        """)
        self.assertIsNotNone(rows)
        parsed = json.loads(rows[0]["viz_spec"])
        self.assertIn("data", parsed)


# ── validate_routing_decision tests (OPTIONAL — audit log only) ───────────────
# The corrected HITL gate is app-owned (session_state); this function is no longer on
# the critical path and is retained only as an optional routing audit log.
# Enable with BPM_TEST_OPTIONAL=1.

class TestValidateRoutingDecision(unittest.TestCase):

    def setUp(self):
        if os.environ.get("BPM_TEST_OPTIONAL") != "1":
            self.skipTest("optional function — set BPM_TEST_OPTIONAL=1 to test validate_routing_decision")
        if not HOST or not TOKEN or not WH_ID:
            self.skipTest("DATABRICKS_HOST / DATABRICKS_TOKEN / BPM_WAREHOUSE_ID not set")

    def test_returns_query_id(self):
        """validate_routing_decision should return the query_id on success (not ERROR:)."""
        test_qid = f"smoke-test-{uuid.uuid4().hex[:8]}"
        rows = run_sql(f"""
            SELECT {UTILS}.validate_routing_decision(
                '{test_qid}',
                'test-session-unit-001',
                'Unit test routing decision',
                'topline',
                'topline_agent',
                'Routing to topline agent because question is about brand share'
            ) AS result
        """)
        self.assertIsNotNone(rows)
        result = rows[0]["result"]
        self.assertFalse(
            str(result).startswith("ERROR:"),
            f"Expected query_id, got error: {result}"
        )
        self.assertEqual(
            result, test_qid,
            f"Expected returned query_id='{test_qid}', got: '{result}'"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
