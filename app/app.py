"""
Brand Performance Manager — backend module (framework-agnostic).

This module holds ALL backend logic for the Brand Performance Manager demo:
Databricks M2M/OBO auth, SQL via the Statement Execution API, the Phase-1
`enrich_user_request` UC-function call, the Phase-2 supervisor invocation, the
KPI/chart data loaders, and the deterministic chart-spec builder.

The front end is now a React single-page app served by `server.py` (FastAPI); the
former Streamlit UI has been removed. This module has **no UI dependency** — the React
client reaches it over JSON. The same functions are exercised directly by the unit
tests (which `import app`), so the data/agent contracts are pinned independently of the
frontend.
"""

from __future__ import annotations

import base64
import functools
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Callable

import pandas as pd

# ── Constants & Config ────────────────────────────────────────────────────────

APP_TITLE       = "Brand Performance Manager"
APP_ICON        = "📊"
BPM_AGENT_EP    = os.environ.get("BPM_AGENT_ENDPOINT", "")
BPM_WAREHOUSE   = os.environ.get("BPM_WAREHOUSE_ID",   "")
BPM_CATALOG     = os.environ.get("BPM_CATALOG",        "main")
BPM_SCHEMA      = "brand_performance"
DB_HOST         = os.environ.get("DATABRICKS_HOST",     "").rstrip("/")
# Databricks Apps injects DATABRICKS_HOST without a scheme (e.g. "adb-….net");
# urllib needs an absolute URL, so ensure https:// is present.
if DB_HOST and not DB_HOST.startswith(("http://", "https://")):
    DB_HOST = "https://" + DB_HOST

TIMEOUT_AGENT_CALL_SECS = 180
HITL_POLL_INTERVAL_SECS = 3
HITL_TIMEOUT_SECS       = 300

NAVY   = "#003087"
ORANGE = "#E87722"

# Route metadata — used by the app-owned HITL gate (no agent involved)
ROUTE_LABEL = {
    "topline":               "Topline Performance",
    "insurgent_brands":      "Insurgent Brands",
    "distribution_velocity": "Distribution & Velocity",
}
ROUTE_WHY = {
    "topline":               "share / sales trend and share-decomposition analysis",
    "insurgent_brands":      "emerging / challenger brand tracking",
    "distribution_velocity": "ACV distribution and velocity metrics",
}

SUGGESTED_QUESTIONS = [
    "Why did NovaBaby share drop in Infant Formula last 4 weeks at Walmart?",
    "Which insurgent brands are gaining share in Infant Formula?",
    "Which SKUs have below 80% ACV in the Northeast?",
    "What is NovaBaby's value share trend in Infant Formula over the last 52 weeks?",
    "Show me the share decomposition for NovaBaby in Baby Food last 12 weeks",
]

# Last SQL error message, surfaced to the client for diagnostics (replaces the
# former st.session_state["_sql_err"]).
_LAST_SQL_ERR: str | None = None


def last_sql_error() -> str | None:
    return _LAST_SQL_ERR


# ── Tiny TTL cache (replaces @st.cache_data / @st.cache_resource) ───────────────

def ttl_cache(ttl_secs: int) -> Callable:
    """Memoize a function's result by its args for `ttl_secs` seconds."""
    def decorate(fn: Callable) -> Callable:
        store: dict[tuple, tuple[float, Any]] = {}

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.time()
            hit = store.get(key)
            if hit is not None and now - hit[0] < ttl_secs:
                return hit[1]
            value = fn(*args, **kwargs)
            store[key] = (now, value)
            return value

        wrapper.cache_clear = store.clear  # type: ignore[attr-defined]
        return wrapper

    return decorate


class _CircuitBreaker:
    """Supervisor-call circuit breaker (replaces the former st.session_state flags)."""

    def __init__(self) -> None:
        self.fails = 0
        self.open = False
        self.open_until = 0.0


CIRCUIT_BREAKER = _CircuitBreaker()


def clear_caches() -> None:
    """Clear all TTL-cached loaders (used by the UI's Refresh action)."""
    for fn in (load_brand_summary_kpis, load_share_trend,
               load_top_insurgent_brands, load_distribution_overview):
        getattr(fn, "cache_clear", lambda: None)()


# ── Auth helpers ──────────────────────────────────────────────────────────────

@ttl_cache(3300)
def _m2m_token() -> str:
    """Obtain a Databricks M2M OAuth token via client credentials flow."""
    client_id     = os.environ.get("DATABRICKS_CLIENT_ID", "")
    client_secret = os.environ.get("DATABRICKS_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return ""
    payload = "grant_type=client_credentials&scope=all-apis".encode()
    req = urllib.request.Request(
        url     = f"{DB_HOST}/oidc/v1/token",
        data    = payload,
        headers = {"Content-Type": "application/x-www-form-urlencoded"},
        method  = "POST",
    )
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    req.add_header("Authorization", f"Basic {credentials}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read()).get("access_token", "")
    except Exception:
        return ""


def _auth_token(user_token: str = "") -> str:
    """
    Token priority chain. The app's **service principal (M2M)** is tried first because it
    holds the explicit grants (warehouse CAN_USE, UC SELECT/EXECUTE, endpoint CAN_QUERY).
    The forwarded user token is not scoped to call the SQL/Serving APIs unless on-behalf-of
    user authorization is configured, so it is only a fallback.
    """
    m2m = _m2m_token()
    if m2m:
        return m2m
    if user_token:
        return user_token
    return os.environ.get("MJN_API_TOKEN", "")


# ── SQL helpers ───────────────────────────────────────────────────────────────

def query_sql(statement: str, max_rows: int = 500) -> pd.DataFrame | None:
    """Execute SQL via Statement Execution API and return a DataFrame."""
    global _LAST_SQL_ERR
    if not DB_HOST or not BPM_WAREHOUSE:
        return None
    token = _auth_token()
    body  = json.dumps({
        "statement":    statement,
        "warehouse_id": BPM_WAREHOUSE,
        "wait_timeout": "30s",
        "row_limit":    max_rows,
    }).encode()
    req = urllib.request.Request(
        url     = f"{DB_HOST}/api/2.0/sql/statements",
        data    = body,
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method  = "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            result = json.loads(resp.read())
        state = result.get("status", {}).get("state")
        if state != "SUCCEEDED":
            err = (result.get("status", {}).get("error") or {}).get("message", "")
            _LAST_SQL_ERR = f"state={state} {err}"[:300]
            return None
        cols = [c["name"] for c in result.get("manifest", {}).get("schema", {}).get("columns", [])]
        rows = result.get("result", {}).get("data_array", [])
        _LAST_SQL_ERR = None
        return pd.DataFrame(rows, columns=cols)
    except urllib.error.HTTPError as exc:
        _LAST_SQL_ERR = f"HTTP {exc.code}: {exc.read().decode()[:200]}"
        return None
    except Exception as exc:
        _LAST_SQL_ERR = f"{type(exc).__name__}: {exc}"[:300]
        return None


def enrich_request(question: str) -> dict | None:
    """
    Phase 1 — classify + enrich the question via the enrich_user_request UC Function,
    called directly (this replaces the former MAS #1 Intake supervisor).
    Returns a dict with: brand, category, time_window_weeks, retailer, region,
    question_type, is_complete, missing_params. None if the warehouse is unreachable.
    """
    q  = question.replace("'", "''")
    df = query_sql(f"SELECT {BPM_CATALOG}.brand_perf_utils.enrich_user_request('{q}') AS r")
    if df is None or df.empty:
        return None
    r = df.iloc[0]["r"]
    try:
        return json.loads(r) if isinstance(r, str) else dict(r)   # struct → dict
    except (TypeError, ValueError):
        return None


# ── Agent call helpers ────────────────────────────────────────────────────────

def _db_post(endpoint_name: str, payload: dict, token: str) -> dict:
    """POST to a Databricks Model Serving endpoint."""
    url = f"{DB_HOST}/serving-endpoints/{endpoint_name}/invocations"
    body = json.dumps(payload).encode()
    req  = urllib.request.Request(
        url     = url,
        data    = body,
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method  = "POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_AGENT_CALL_SECS) as resp:
        return json.loads(resp.read())


def _extract_output_text(response: dict) -> str:
    """Extract the text content from an agent invocation response."""
    choices = response.get("choices", [])
    if choices:
        msg = choices[0].get("message", {})
        content = msg.get("content", "")
        if isinstance(content, list):
            parts = [p.get("text", "") for p in content if isinstance(p, dict)]
            return " ".join(parts).strip()
        return str(content).strip()
    # Responses API: `output` is a list of message items with content blocks.
    out = response.get("output")
    if isinstance(out, list):
        parts: list[str] = []
        for item in out:
            content = item.get("content") if isinstance(item, dict) else None
            if isinstance(content, list):
                parts += [p.get("text", "") for p in content if isinstance(p, dict)]
            elif isinstance(content, str):
                parts.append(content)
        text = "".join(parts).strip()
        if text:
            return text
    if response.get("outputs"):
        return str(response["outputs"][0]).strip()
    return str(out or "").strip()


def call_domain_agent(
    question: str, ctx: dict, route: str, session_id: str
) -> tuple[str, str | None]:
    """
    Phase 2 — invoke the single Brand Performance Manager supervisor ONCE with an
    already-enriched, user-confirmed request and an explicit ROUTE. The supervisor
    dispatches to the matching specialist (topline / insurgent / distribution); it
    no longer performs intake, classification, or confirmation.
    Returns (response_text, viz_hint_or_none).
    """
    cb = CIRCUIT_BREAKER
    if cb.open:
        if time.time() < cb.open_until:
            return (
                "The agent is currently unavailable due to repeated errors. "
                "Please try again in a few minutes.",
                None,
            )
        cb.open  = False
        cb.fails = 0

    directive = (
        f"ROUTE={route}. The request is already enriched and user-confirmed — "
        f"dispatch directly to the {route} specialist; do not ask for confirmation "
        f"or re-classify.\n"
        f"Context: brand={ctx.get('brand')}, category={ctx.get('category')}, "
        f"retailer={ctx.get('retailer')}, region={ctx.get('region')}, "
        f"time_window_weeks={ctx.get('time_window_weeks')}.\n"
        f"Question: {question}"
    )
    # AgentBricks supervisor endpoints use the Responses API (`input`, not `messages`).
    payload = {"input": [{"role": "user", "content": directive}]}

    try:
        response   = _db_post(BPM_AGENT_EP, payload, _auth_token())
        err        = response.get("error")
        error_code = response.get("error_code") or (err.get("code") if isinstance(err, dict) else None)
        if error_code:
            cb.fails += 1
            if cb.fails >= 3:
                cb.open       = True
                cb.open_until = time.time() + 120
            return f"Agent error: {error_code} — {response.get('message', '')}", None

        text = _extract_output_text(response)
        if not text:
            return "The agent returned an empty response. Please rephrase your question.", None

        cb.fails = 0

        viz_hint = None
        for line in text.splitlines():
            if line.strip().startswith("VISUALIZATION:"):
                viz_hint = line.split("VISUALIZATION:")[-1].strip()
                break

        return text, viz_hint

    except TimeoutError:
        cb.fails += 1
        return (
            "The agent is warming up and took longer than expected. "
            "Please try again in 30 seconds.",
            None,
        )
    except Exception as exc:
        cb.fails += 1
        return f"Unexpected error: {exc}", None


# ── Visualization helpers ─────────────────────────────────────────────────────

def extract_visualization(agent_text: str) -> tuple[str, str, str, str] | None:
    """
    Parse VISUALIZATION: chart_type|x_axis|y_axis|title from agent response.
    Returns (chart_type, x_axis, y_axis, title) or None.
    """
    for line in agent_text.splitlines():
        line = line.strip()
        if line.startswith("VISUALIZATION:"):
            parts = line.split("VISUALIZATION:")[-1].strip().split("|")
            if len(parts) >= 4:
                return parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()
    return None


def chart_data(agent_text: str, route: str | None = None,
               ctx: dict | None = None) -> dict | None:
    """
    Build a JSON-serializable chart spec deterministically from the enriched context —
    no LLM and no external serving endpoint. The agent's VISUALIZATION hint only supplies
    the title; the data comes from a SQL query keyed on the confirmed route + context (the
    same loaders the dashboard tabs use). The React client renders the returned spec.

    Returns a dict like:
        {"kind": "line"|"bar", "title", "xTitle", "yTitle",
         "x": [...], "y": [...], "color"|"colors", "threshold"?, "orientation"?}
    or None when there is nothing to chart.
    """
    info = extract_visualization(agent_text)
    if info is None or not ctx:
        return None
    _chart_type, _x, _y, title = info

    try:
        if route == "topline":
            df = load_share_trend(BPM_CATALOG, BPM_SCHEMA,
                                  ctx.get("brand", "NovaBaby"),
                                  int(ctx.get("time_window_weeks") or 52))
            if df is not None and not df.empty:
                return {
                    "kind":   "line",
                    "title":  title,
                    "xTitle": "Week Ending",
                    "yTitle": "Value Share (%)",
                    "x":      df["week_ending"].astype(str).tolist(),
                    "y":      df["value_share_pct"].astype(float).round(3).tolist(),
                    "color":  NAVY,
                }

        elif route == "insurgent_brands":
            df = load_top_insurgent_brands(BPM_CATALOG, BPM_SCHEMA,
                                           ctx.get("category", "Infant Formula"))
            if df is not None and not df.empty:
                gains = df["gain_52w"].astype(float).round(3)
                return {
                    "kind":        "bar",
                    "orientation": "h",
                    "title":       title,
                    "xTitle":      "52W Share Gain (ppt)",
                    "yTitle":      "",
                    "x":           gains.tolist(),
                    "y":           df["brand"].tolist(),
                    "color":       ORANGE,
                }

        elif route == "distribution_velocity":
            df = load_distribution_overview(BPM_CATALOG, BPM_SCHEMA)
            if df is not None and not df.empty:
                df = df[df["retailer"] == "Total US"].sort_values("avg_acv_pct")
                if not df.empty:
                    acv = df["avg_acv_pct"].astype(float).round(2)
                    return {
                        "kind":        "bar",
                        "orientation": "h",
                        "title":       title,
                        "xTitle":      "ACV %",
                        "yTitle":      "",
                        "x":           acv.tolist(),
                        "y":           df["brand"].tolist(),
                        "colors":      [NAVY if v >= 60 else ORANGE for v in acv],
                        "threshold":   60,
                    }
    except Exception:
        return None
    return None


# ── KPI / dashboard data loaders ──────────────────────────────────────────────

@ttl_cache(300)
def load_brand_summary_kpis(catalog: str, schema: str) -> pd.DataFrame | None:
    """Load latest brand KPIs for the KPI card row."""
    return query_sql(f"""
        WITH latest AS (
            SELECT brand, retailer, value_share_pct, l4w_value_share, l12w_value_share, yoy_dollar_chg_pct,
                   ROW_NUMBER() OVER (PARTITION BY brand, retailer ORDER BY week_ending DESC) AS rn
            FROM {catalog}.{schema}.brand_topline_metrics
            WHERE retailer = 'Total US'
        )
        SELECT brand, value_share_pct, l4w_value_share, l12w_value_share,
               l4w_value_share - l12w_value_share AS share_trend_ppt,
               yoy_dollar_chg_pct
        FROM latest WHERE rn = 1
        ORDER BY value_share_pct DESC
        LIMIT 10
    """)


@ttl_cache(300)
def load_share_trend(catalog: str, schema: str, brand: str = "NovaBaby", weeks: int = 52) -> pd.DataFrame | None:
    """Load weekly value share trend for a single brand."""
    return query_sql(f"""
        SELECT week_ending, AVG(value_share_pct) AS value_share_pct
        FROM {catalog}.{schema}.brand_topline_metrics
        WHERE brand = '{brand}' AND retailer = 'Total US'
          AND week_ending >= DATEADD(WEEK, -{weeks},
              (SELECT MAX(week_ending) FROM {catalog}.{schema}.brand_topline_metrics))
        GROUP BY week_ending
        ORDER BY week_ending
    """)


@ttl_cache(300)
def load_top_insurgent_brands(catalog: str, schema: str, category: str = "Infant Formula") -> pd.DataFrame | None:
    """Load top insurgent brands by 52-week share gain."""
    return query_sql(f"""
        SELECT brand, AVG(value_share_pct) AS avg_share,
               AVG(share_gain_52w_ppt) AS gain_52w,
               AVG(threat_score) AS threat_score,
               AVG(acv_pct) AS avg_acv
        FROM {catalog}.{schema}.insurgent_brand_tracker
        WHERE category = '{category}' AND retailer = 'Total US'
          AND week_ending >= DATEADD(WEEK, -12,
              (SELECT MAX(week_ending) FROM {catalog}.{schema}.insurgent_brand_tracker))
        GROUP BY brand
        ORDER BY gain_52w DESC
        LIMIT 8
    """)


@ttl_cache(300)
def load_distribution_overview(catalog: str, schema: str) -> pd.DataFrame | None:
    """Load ACV distribution summary by brand and retailer."""
    return query_sql(f"""
        SELECT brand, retailer,
               ROUND(AVG(acv_pct), 1) AS avg_acv_pct,
               ROUND(AVG(velocity_per_mm_acv), 0) AS avg_velocity,
               ROUND(AVG(out_of_stock_rate_pct), 2) AS avg_oos_pct
        FROM {catalog}.{schema}.distribution_velocity
        WHERE week_ending >= DATEADD(WEEK, -4,
              (SELECT MAX(week_ending) FROM {catalog}.{schema}.distribution_velocity))
          AND region = 'Total US'
        GROUP BY brand, retailer
        ORDER BY brand, avg_acv_pct DESC
    """)
