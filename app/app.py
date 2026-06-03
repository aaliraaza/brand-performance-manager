"""
Brand Performance Manager — Streamlit Application

Multi-agent CPG brand analytics assistant powered by Databricks AgentBricks.
Provides KPI dashboards, AI-driven brand performance analysis with Human-in-the-Loop
routing confirmation, and interactive Plotly visualizations.
"""

from __future__ import annotations

import json
import os
import time
import uuid
import urllib.request
import urllib.error
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Constants & Config ────────────────────────────────────────────────────────

APP_TITLE       = "Brand Performance Manager"
APP_ICON        = "📊"
BPM_AGENT_EP    = os.environ.get("BPM_AGENT_ENDPOINT", "")
BPM_WAREHOUSE   = os.environ.get("BPM_WAREHOUSE_ID",   "")
BPM_CATALOG     = os.environ.get("BPM_CATALOG",        "main")
BPM_SCHEMA      = "brand_performance"
DB_HOST         = os.environ.get("DATABRICKS_HOST",     "").rstrip("/")

TIMEOUT_AGENT_CALL_SECS = 180
HITL_POLL_INTERVAL_SECS = 3
HITL_TIMEOUT_SECS       = 300

NAVY   = "#003087"
ORANGE = "#E87722"

SESSION_STATE_DEFAULTS: dict[str, Any] = {
    "messages":              [],
    "enriched_context":      {},
    "awaiting_confirmation": False,
    "hitl_start_time":       None,
    "pending_route":         None,
    "pending_question":      None,
    "circuit_breaker_fails": 0,
    "circuit_breaker_open":  False,
    "cb_open_until":         0.0,
}

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
    "Why did NovaBaby share drop last 4 weeks at Walmart?",
    "Which insurgent brands are gaining share in Infant Formula?",
    "Which SKUs have below 80% ACV in the Northeast?",
    "What is NovaBaby's value share trend over the last 52 weeks?",
    "Show me the share decomposition for NovaBaby in Baby Food last 12 weeks",
]

# ── Auth helpers ──────────────────────────────────────────────────────────────

@st.cache_resource(ttl=3300)
def _m2m_token() -> str:
    """Obtain a Databricks M2M OAuth token via client credentials flow."""
    client_id     = os.environ.get("DATABRICKS_CLIENT_ID", "")
    client_secret = os.environ.get("DATABRICKS_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return ""
    payload = f"grant_type=client_credentials&scope=all-apis".encode()
    req = urllib.request.Request(
        url     = f"{DB_HOST}/oidc/v1/token",
        data    = payload,
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method  = "POST",
    )
    import base64
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    req.add_header("Authorization", f"Basic {credentials}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read()).get("access_token", "")
    except Exception:
        return ""


def _auth_token() -> str:
    """
    Token priority chain (SDD §9.1):
    1. x-forwarded-access-token from Databricks Apps (user JWT)
    2. MJN_API_TOKEN PAT (dev/testing)
    3. M2M OAuth token
    """
    user_token = st.context.headers.get("x-forwarded-access-token", "")
    if user_token:
        return user_token
    pat = os.environ.get("MJN_API_TOKEN", "")
    if pat:
        return pat
    return _m2m_token()


# ── SQL helpers ───────────────────────────────────────────────────────────────

def query_sql(statement: str, max_rows: int = 500) -> pd.DataFrame | None:
    """Execute SQL via Statement Execution API and return a DataFrame."""
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
        if result.get("status", {}).get("state") != "SUCCEEDED":
            return None
        cols = [c["name"] for c in result.get("manifest", {}).get("schema", {}).get("columns", [])]
        rows = result.get("result", {}).get("data_array", [])
        return pd.DataFrame(rows, columns=cols)
    except Exception:
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
    outputs = response.get("outputs", [])
    if outputs:
        return str(outputs[0]).strip()
    return str(response.get("output", "")).strip()


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
    if st.session_state.circuit_breaker_open:
        if time.time() < st.session_state.cb_open_until:
            return (
                "The agent is currently unavailable due to repeated errors. "
                "Please try again in a few minutes.",
                None,
            )
        st.session_state.circuit_breaker_open  = False
        st.session_state.circuit_breaker_fails = 0

    directive = (
        f"ROUTE={route}. The request is already enriched and user-confirmed — "
        f"dispatch directly to the {route} specialist; do not ask for confirmation "
        f"or re-classify.\n"
        f"Context: brand={ctx.get('brand')}, category={ctx.get('category')}, "
        f"retailer={ctx.get('retailer')}, region={ctx.get('region')}, "
        f"time_window_weeks={ctx.get('time_window_weeks')}.\n"
        f"Question: {question}"
    )
    payload = {
        "messages": [{"role": "user", "content": directive}],
        "databricks_options": {"session_id": session_id},
    }

    try:
        response   = _db_post(BPM_AGENT_EP, payload, _auth_token())
        error_code = response.get("error_code") or response.get("error", {}).get("code")
        if error_code:
            st.session_state.circuit_breaker_fails += 1
            if st.session_state.circuit_breaker_fails >= 3:
                st.session_state.circuit_breaker_open = True
                st.session_state.cb_open_until        = time.time() + 120
            return f"Agent error: {error_code} — {response.get('message', '')}", None

        text = _extract_output_text(response)
        if not text:
            return "The agent returned an empty response. Please rephrase your question.", None

        st.session_state.circuit_breaker_fails = 0

        viz_hint = None
        for line in text.splitlines():
            if line.strip().startswith("VISUALIZATION:"):
                viz_hint = line.split("VISUALIZATION:")[-1].strip()
                break

        return text, viz_hint

    except TimeoutError:
        st.session_state.circuit_breaker_fails += 1
        return (
            "The agent is warming up and took longer than expected. "
            "Please try again in 30 seconds.",
            None,
        )
    except Exception as exc:
        st.session_state.circuit_breaker_fails += 1
        return f"Unexpected error: {exc}", None


# ── Visualization helpers ─────────────────────────────────────────────────────

def extract_visualization(agent_text: str) -> tuple[str, str, str] | None:
    """
    Parse VISUALIZATION: chart_type|x_axis|y_axis|title from agent response.
    Returns (chart_type, axes_desc, title) or None.
    """
    for line in agent_text.splitlines():
        line = line.strip()
        if line.startswith("VISUALIZATION:"):
            parts = line.split("VISUALIZATION:")[-1].strip().split("|")
            if len(parts) >= 4:
                return parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()
    return None


def render_visualization(agent_text: str, route: str | None = None,
                         ctx: dict | None = None) -> None:
    """
    Render a Plotly chart deterministically from the enriched context — no LLM and
    no external serving endpoint. The agent's VISUALIZATION hint only supplies the
    title; the data comes from a SQL query keyed on the confirmed route + context
    (the same loaders the dashboard tabs use).
    """
    info = extract_visualization(agent_text)
    if info is None or not ctx:
        return
    _chart_type, _x, _y, title = info

    try:
        if route == "topline":
            df = load_share_trend(BPM_CATALOG, BPM_SCHEMA,
                                  ctx.get("brand", "NovaBaby"),
                                  int(ctx.get("time_window_weeks") or 52))
            if df is not None and not df.empty:
                fig = go.Figure(go.Scatter(
                    x=df["week_ending"], y=df["value_share_pct"].astype(float),
                    mode="lines+markers", line=dict(color=NAVY, width=2)))
                fig.update_layout(title=title, xaxis_title="Week Ending",
                                  yaxis_title="Value Share (%)", height=350,
                                  paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
                st.plotly_chart(fig, use_container_width=True)

        elif route == "insurgent_brands":
            df = load_top_insurgent_brands(BPM_CATALOG, BPM_SCHEMA,
                                           ctx.get("category", "Infant Formula"))
            if df is not None and not df.empty:
                df["gain_52w"] = df["gain_52w"].astype(float)
                fig = go.Figure(go.Bar(
                    x=df["gain_52w"], y=df["brand"], orientation="h",
                    marker_color=ORANGE,
                    text=[f"{v:+.2f} ppt" for v in df["gain_52w"]],
                    textposition="outside"))
                fig.update_layout(title=title, xaxis_title="52W Share Gain (ppt)",
                                  height=350, paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
                st.plotly_chart(fig, use_container_width=True)

        elif route == "distribution_velocity":
            df = load_distribution_overview(BPM_CATALOG, BPM_SCHEMA)
            if df is not None and not df.empty:
                df = df[df["retailer"] == "Total US"].sort_values("avg_acv_pct")
                if not df.empty:
                    acv = df["avg_acv_pct"].astype(float)
                    fig = go.Figure(go.Bar(
                        x=acv, y=df["brand"], orientation="h",
                        marker_color=[NAVY if v >= 60 else ORANGE for v in acv]))
                    fig.add_vline(x=60, line_dash="dash", line_color="red",
                                  annotation_text="60% threshold")
                    fig.update_layout(title=title, xaxis_title="ACV %", height=350,
                                      paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
                    st.plotly_chart(fig, use_container_width=True)
    except Exception as exc:
        st.caption(f"(chart unavailable: {exc})")


# ── HITL helpers ──────────────────────────────────────────────────────────────

def render_hitl_panel() -> None:
    """
    Render the HITL routing-confirmation panel in the sidebar. State lives entirely
    in st.session_state — no Lakebase round-trip, no polling, no LLM-generated id.
    Confirm invokes Phase 2 (call_domain_agent) in the same run; Change lets the user
    override the route the classifier proposed.
    """
    if not st.session_state.awaiting_confirmation:
        return

    ctx       = st.session_state.get("enriched_context", {})
    route     = st.session_state.get("pending_route")
    question  = st.session_state.get("pending_question", "")
    start     = st.session_state.get("hitl_start_time", time.time())
    elapsed   = time.time() - start
    remaining = max(0, HITL_TIMEOUT_SECS - elapsed)

    if elapsed > HITL_TIMEOUT_SECS:
        st.session_state.awaiting_confirmation = False
        st.sidebar.warning("⏰ Routing confirmation timed out. Please re-send your question.")
        return

    with st.sidebar:
        st.markdown("---")
        st.markdown("### 🔀 Confirm Routing")
        st.markdown(f"**Question:** {question[:120]}{'...' if len(question) > 120 else ''}")
        st.markdown(f"**Proposed route:** `{ROUTE_LABEL.get(route, route)}`")
        st.caption(f"Why: {ROUTE_WHY.get(route, '')}")
        st.caption(
            f"Context — {ctx.get('brand')} · {ctx.get('category')} · "
            f"{ctx.get('retailer')} · {ctx.get('time_window_weeks')}W"
        )
        st.caption(f"⏱ {remaining:.0f}s remaining")
        st.progress(1 - elapsed / HITL_TIMEOUT_SECS)

        # Change-route override — the actual purpose of the HITL gate
        routes    = list(ROUTE_LABEL)
        new_route = st.selectbox(
            "Route", routes,
            index=routes.index(route) if route in routes else 0,
            format_func=lambda r: ROUTE_LABEL[r], key="hitl_route_sel",
        )

        col1, col2 = st.columns(2)
        if col1.button("✅ Confirm & Run", key="hitl_confirm",
                       use_container_width=True, type="primary"):
            st.session_state.awaiting_confirmation = False
            sid = st.session_state.get("_session_id", "default-session")
            with st.spinner("Analysing…"):
                text, viz_hint = call_domain_agent(question, ctx, new_route, sid)   # Phase 2
            _record_hitl_outcome(question, ctx, new_route, "CONFIRMED")
            _assistant(text, viz_hint=viz_hint, route=new_route, ctx=ctx)
            st.rerun()
        if col2.button("✖ Cancel", key="hitl_cancel", use_container_width=True):
            st.session_state.awaiting_confirmation = False
            _record_hitl_outcome(question, ctx, route, "REJECTED")
            _assistant("Cancelled. Rephrase your question or ask a new one.")
            st.rerun()


def _record_hitl_outcome(question: str, ctx: dict, route: str, status: str) -> None:
    """
    Optional audit write — records the routing decision for the HITL confirmation-rate
    metric. Best-effort: failures never block the flow. (Wire to Lakebase via psycopg2
    using PGHOST/PGDATABASE if an audit trail is required; no-op by default.)
    """
    return


# ── KPI dashboard helpers ─────────────────────────────────────────────────────

@st.cache_data(ttl=300)
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


@st.cache_data(ttl=300)
def load_share_trend(catalog: str, schema: str, brand: str = "NovaBaby", weeks: int = 52) -> pd.DataFrame | None:
    """Load weekly value share trend for a single brand."""
    return query_sql(f"""
        SELECT week_ending, AVG(value_share_pct) AS value_share_pct
        FROM {catalog}.{schema}.brand_topline_metrics
        WHERE brand = '{brand}' AND retailer = 'Total US'
          AND week_ending >= DATEADD(WEEK, -{weeks}, CURRENT_DATE)
        GROUP BY week_ending
        ORDER BY week_ending
    """)


@st.cache_data(ttl=300)
def load_top_insurgent_brands(catalog: str, schema: str, category: str = "Infant Formula") -> pd.DataFrame | None:
    """Load top insurgent brands by 52-week share gain."""
    return query_sql(f"""
        SELECT brand, AVG(value_share_pct) AS avg_share,
               AVG(share_gain_52w_ppt) AS gain_52w,
               AVG(threat_score) AS threat_score,
               AVG(acv_pct) AS avg_acv
        FROM {catalog}.{schema}.insurgent_brand_tracker
        WHERE category = '{category}' AND retailer = 'Total US'
          AND week_ending >= DATEADD(WEEK, -12, CURRENT_DATE)
        GROUP BY brand
        ORDER BY gain_52w DESC
        LIMIT 8
    """)


@st.cache_data(ttl=300)
def load_distribution_overview(catalog: str, schema: str) -> pd.DataFrame | None:
    """Load ACV distribution summary by brand and retailer."""
    return query_sql(f"""
        SELECT brand, retailer,
               ROUND(AVG(acv_pct), 1) AS avg_acv_pct,
               ROUND(AVG(velocity_per_mm_acv), 0) AS avg_velocity,
               ROUND(AVG(out_of_stock_rate_pct), 2) AS avg_oos_pct
        FROM {catalog}.{schema}.distribution_velocity
        WHERE week_ending >= DATEADD(WEEK, -4, CURRENT_DATE)
          AND region = 'Total US'
        GROUP BY brand, retailer
        ORDER BY brand, avg_acv_pct DESC
    """)


# ── UI components ─────────────────────────────────────────────────────────────

def render_header() -> None:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(
            f"<h1 style='color:{NAVY};margin-bottom:0'>{APP_ICON} {APP_TITLE}</h1>"
            "<p style='color:gray;margin-top:4px'>Multi-Agent CPG Brand Analytics — Powered by Databricks AgentBricks</p>",
            unsafe_allow_html=True,
        )
    with col2:
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()


def render_context_pills() -> None:
    """Render Brand / Retailer / Time Window context pills above tabs."""
    ctx  = st.session_state.get("enriched_context", {})
    pill = lambda k, v, color: (
        f"<span style='background:{color};color:white;padding:4px 12px;border-radius:12px;"
        f"font-size:0.8rem;margin-right:8px'><b>{k}:</b> {v}</span>"
    )
    pills = ""
    if ctx.get("brand"):
        pills += pill("Brand",    ctx["brand"],                          NAVY)
    if ctx.get("retailer"):
        pills += pill("Retailer", ctx.get("retailer", "Total US"),       "#555")
    if ctx.get("time_window_weeks"):
        pills += pill("Window",   f"{ctx['time_window_weeks']}W",        ORANGE)
    if pills:
        st.markdown(pills, unsafe_allow_html=True)
        st.markdown("")


def render_kpi_cards(df: pd.DataFrame | None) -> None:
    """Render KPI metric cards row."""
    if df is None or df.empty:
        st.info("📊 KPI data is loading... Run notebook 01 to populate the data tables.")
        return

    top_brands = df.head(4)
    cols = st.columns(len(top_brands))
    for i, (_, row) in enumerate(top_brands.iterrows()):
        share      = float(row["value_share_pct"])
        trend      = float(row.get("share_trend_ppt", 0) or 0)
        yoy        = float(row.get("yoy_dollar_chg_pct", 0) or 0)
        trend_icon = "▲" if trend > 0 else "▼" if trend < 0 else "—"
        trend_col  = NAVY if trend > 0 else "red" if trend < 0 else "gray"
        with cols[i]:
            st.metric(
                label  = str(row["brand"]),
                value  = f"{share:.1f}%",
                delta  = f"{trend:+.2f} ppt (4W trend)",
                delta_color = "normal" if trend >= 0 else "inverse",
            )


def render_dashboard_tab() -> None:
    """Render the 📊 Dashboard tab with KPI cards and charts."""
    kpi_df = load_brand_summary_kpis(BPM_CATALOG, BPM_SCHEMA)
    render_kpi_cards(kpi_df)

    st.markdown("---")
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("Value Share Trend — Top Brands")
        if kpi_df is not None and not kpi_df.empty:
            top_brands = kpi_df["brand"].head(3).tolist()
            fig = go.Figure()
            for brand in top_brands:
                trend_df = load_share_trend(BPM_CATALOG, BPM_SCHEMA, brand, weeks=52)
                if trend_df is not None and not trend_df.empty:
                    fig.add_trace(go.Scatter(
                        x    = trend_df["week_ending"],
                        y    = trend_df["value_share_pct"].astype(float),
                        mode = "lines+markers",
                        name = brand,
                        line = dict(width=2),
                    ))
            fig.update_layout(
                xaxis_title = "Week Ending",
                yaxis_title = "Value Share (%)",
                height      = 350,
                paper_bgcolor = "#FFFFFF",
                plot_bgcolor  = "#FFFFFF",
                legend        = dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Run notebook 01 to populate share trend data.")

    with chart_col2:
        st.subheader("Top Insurgent Brands — 52W Share Gain")
        ins_df = load_top_insurgent_brands(BPM_CATALOG, BPM_SCHEMA)
        if ins_df is not None and not ins_df.empty:
            ins_df["gain_52w"]   = ins_df["gain_52w"].astype(float)
            ins_df["avg_share"]  = ins_df["avg_share"].astype(float)
            colors = [ORANGE if float(g) > 0 else "#AAA" for g in ins_df["gain_52w"]]
            fig = go.Figure(go.Bar(
                x           = ins_df["gain_52w"],
                y           = ins_df["brand"],
                orientation = "h",
                marker_color = colors,
                text        = [f"{v:+.2f} ppt" for v in ins_df["gain_52w"]],
                textposition = "outside",
            ))
            fig.update_layout(
                xaxis_title  = "52W Share Gain (ppt)",
                height       = 350,
                paper_bgcolor = "#FFFFFF",
                plot_bgcolor  = "#FFFFFF",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Run notebook 01 to populate insurgent brand data.")


def render_chat_tab() -> None:
    """Render the 💬 AI Advisor chat tab."""
    render_context_pills()

    # Suggested questions
    if not st.session_state.messages:
        st.markdown("**Suggested questions:**")
        cols = st.columns(len(SUGGESTED_QUESTIONS))
        for i, q in enumerate(SUGGESTED_QUESTIONS):
            if cols[i].button(q[:45] + ("…" if len(q) > 45 else ""), key=f"sq_{i}"):
                st.session_state.messages.append({"role": "user", "content": q})
                st.rerun()

    # Chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("viz_hint") and msg["role"] == "assistant":
                render_visualization(msg["content"], msg.get("route"), msg.get("ctx"))

    # Chat input
    if not st.session_state.awaiting_confirmation:
        prompt = st.chat_input("Ask about brand performance, insurgent brands, or distribution…")
        if prompt:
            if "_session_id" not in st.session_state:
                st.session_state["_session_id"] = str(uuid.uuid4())

            st.session_state.messages.append({"role": "user", "content": prompt})

            # Phase 1 — enrich + classify directly via the UC Function (no supervisor)
            with st.spinner("Understanding your question…"):
                ctx = enrich_request(prompt)

            if ctx is None:
                _assistant("Couldn't reach the enrichment service — check that the SQL "
                           "warehouse is running and BPM_WAREHOUSE_ID is set.")
            elif ctx.get("question_type") == "out_of_scope":
                _assistant("I can only help with brand performance — share trends, insurgent "
                           "brand analysis, and distribution/velocity. Please name a brand and "
                           "category.")
            elif not ctx.get("is_complete"):
                st.session_state.enriched_context = ctx
                miss = ", ".join(ctx.get("missing_params") or ["brand", "category"])
                _assistant(f"I need a bit more to route this accurately — please specify: "
                           f"**{miss}**.")
            else:
                # Complete → open the app-owned HITL gate (rendered in the sidebar)
                st.session_state.enriched_context      = ctx
                st.session_state.pending_question      = prompt
                st.session_state.pending_route         = ctx["question_type"]
                st.session_state.awaiting_confirmation = True
                st.session_state.hitl_start_time       = time.time()

            st.rerun()
    else:
        st.info("⏳ Confirm the routing in the sidebar panel to run the analysis.")


def _assistant(text: str, viz_hint: str | None = None,
               route: str | None = None, ctx: dict | None = None) -> None:
    """Append an assistant message, carrying route + context for deterministic charts."""
    st.session_state.messages.append({
        "role":     "assistant",
        "content":  text,
        "viz_hint": viz_hint,
        "route":    route,
        "ctx":      ctx,
    })


def render_insurgent_tab() -> None:
    """Render the 🏃 Insurgent Brands tab."""
    render_context_pills()

    cat_options = ["Infant Formula", "Baby Food", "Toddler Snacks"]
    sel_cat = st.selectbox("Category", cat_options, key="insurgent_cat_sel")

    ins_df = load_top_insurgent_brands(BPM_CATALOG, BPM_SCHEMA, sel_cat)
    if ins_df is None or ins_df.empty:
        st.info("No insurgent brand data available. Run notebook 01 first.")
        return

    ins_df = ins_df.copy()
    for col in ["avg_share", "gain_52w", "threat_score", "avg_acv"]:
        ins_df[col] = ins_df[col].astype(float).round(2)

    st.markdown("#### Insurgent Brand Performance Summary")
    display_df = ins_df.rename(columns={
        "brand":        "Brand",
        "avg_share":    "Avg Share %",
        "gain_52w":     "52W Gain (ppt)",
        "threat_score": "Threat Score",
        "avg_acv":      "Avg ACV %",
    })

    def _color_threat(val):
        if val >= 60: return f"background-color:#FFE0DC;color:#cc0000"
        if val >= 40: return f"background-color:#FFF3CC;color:#cc7700"
        return ""

    styled = display_df.style.applymap(_color_threat, subset=["Threat Score"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # Bar chart
    fig = go.Figure(go.Bar(
        y    = ins_df["brand"],
        x    = ins_df["threat_score"],
        orientation  = "h",
        marker_color = [ORANGE if v >= 40 else NAVY for v in ins_df["threat_score"]],
        text         = [f"{v:.0f}" for v in ins_df["threat_score"]],
        textposition = "outside",
    ))
    fig.update_layout(
        title        = f"Insurgent Brand Threat Scores — {sel_cat}",
        xaxis_title  = "Threat Score (0–100)",
        height       = 350,
        paper_bgcolor = "#FFFFFF",
        plot_bgcolor  = "#FFFFFF",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_distribution_tab() -> None:
    """Render the 📦 Distribution tab."""
    render_context_pills()

    dist_df = load_distribution_overview(BPM_CATALOG, BPM_SCHEMA)
    if dist_df is None or dist_df.empty:
        st.info("No distribution data available. Run notebook 01 first.")
        return

    st.markdown("#### ACV Distribution & Velocity by Brand & Retailer")
    for col in ["avg_acv_pct", "avg_velocity", "avg_oos_pct"]:
        dist_df[col] = dist_df[col].astype(float)

    display_df = dist_df.rename(columns={
        "brand":       "Brand",
        "retailer":    "Retailer",
        "avg_acv_pct": "Avg ACV %",
        "avg_velocity":"Velocity / $1M ACV",
        "avg_oos_pct": "OOS Rate %",
    })

    def _flag_low_acv(val):
        try:
            return "background-color:#FFEEDD" if float(val) < 60 else ""
        except Exception:
            return ""

    styled = display_df.style.applymap(_flag_low_acv, subset=["Avg ACV %"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # Velocity bar chart for Total US
    total_us = dist_df[dist_df["retailer"] == "Total US"].sort_values("avg_acv_pct", ascending=True)
    if not total_us.empty:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x    = total_us["avg_acv_pct"],
            y    = total_us["brand"],
            orientation  = "h",
            name = "ACV %",
            marker_color = [NAVY if v >= 60 else ORANGE for v in total_us["avg_acv_pct"]],
        ))
        fig.add_vline(x=60, line_dash="dash", line_color="red", annotation_text="60% threshold")
        fig.update_layout(
            title        = "ACV Distribution % — Total US (Latest 4W)",
            xaxis_title  = "ACV %",
            height       = 350,
            paper_bgcolor = "#FFFFFF",
            plot_bgcolor  = "#FFFFFF",
        )
        st.plotly_chart(fig, use_container_width=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title = APP_TITLE,
        page_icon  = APP_ICON,
        layout     = "wide",
        initial_sidebar_state = "expanded",
    )

    # Initialize session state
    for key, default in SESSION_STATE_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default

    # Sidebar — branding + HITL panel
    with st.sidebar:
        st.markdown(
            f"<div style='text-align:center;padding:12px 0'>"
            f"<span style='font-size:2rem'>{APP_ICON}</span><br/>"
            f"<b style='color:{NAVY}'>{APP_TITLE}</b><br/>"
            f"<small style='color:gray'>Databricks AgentBricks</small>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown("---")

        ctx = st.session_state.get("enriched_context", {})
        if ctx:
            st.markdown("**Active Context**")
            for k, v in ctx.items():
                st.caption(f"{k.replace('_', ' ').title()}: **{v}**")
            if st.button("Clear Context", key="clear_ctx"):
                st.session_state.enriched_context = {}
                st.rerun()
            st.markdown("---")

        render_hitl_panel()

        st.caption(f"Agent: `{BPM_AGENT_EP or 'not configured'}`")
        st.caption(f"Catalog: `{BPM_CATALOG}.{BPM_SCHEMA}`")

    render_header()
    st.markdown("")

    # Main tabs
    tab_dash, tab_chat, tab_insurgent, tab_dist = st.tabs([
        "📊 Dashboard",
        "💬 AI Advisor",
        "🏃 Insurgent Brands",
        "📦 Distribution",
    ])

    with tab_dash:
        render_dashboard_tab()

    with tab_chat:
        render_chat_tab()

    with tab_insurgent:
        render_insurgent_tab()

    with tab_dist:
        render_distribution_tab()


if __name__ == "__main__":
    main()
