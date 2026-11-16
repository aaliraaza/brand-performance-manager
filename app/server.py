"""
Brand Performance Manager — FastAPI server.

Serves the React single-page app (built into ./static) and exposes the backend
(`bpm_core`) as a small JSON API. This replaces the former Streamlit front end; all
data access, the Phase-1 enrichment call, the two-phase HITL flow, and the Phase-2
supervisor invocation are unchanged — they now live in `bpm_core` and are reached
over HTTP instead of being rendered server-side.

Two-phase HITL is preserved exactly:
    POST /api/enrich   → Phase 1 (classify + completeness). Returns a "gate" decision.
    (user confirms / changes route in the React UI — no agent involved)
    POST /api/analyze  → Phase 2 (single supervisor call carrying the confirmed ROUTE).

Run locally:   uvicorn server:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import app as core
import audit
import metrics

app = FastAPI(title=core.APP_TITLE, docs_url="/api/docs", openapi_url="/api/openapi.json")

STATIC_DIR = Path(__file__).parent / "static"

# Lakebase audit log: create the table in the background at startup (best-effort).
audit.warm_up()


# ── Metrics middleware ─────────────────────────────────────────────────────────
# Emits the custom OTel metrics defined in metrics.py for every request: a total
# counter, a latency histogram, and an in-flight ("queue depth") up-down counter.
# The FastAPI auto-instrumentor records equivalent HTTP server metrics too; these
# named instruments give the demo explicit, self-documenting series in otel_metrics.

def _route_template(request: Request) -> str:
    """Low-cardinality route label — the matched path template, not the raw URL.

    Must be read *after* the app has run (Starlette populates `scope["route"]` during
    routing, inside `call_next`). The matched route collapses the SPA catch-all
    `/{full_path:path}` to a single series; without it every client-routed URL would
    create its own. Falls back to the raw path for unmatched routes (e.g. 404s), with
    static assets collapsed to "/assets/*" to avoid one series per file.
    """
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    path = request.url.path
    if path.startswith("/assets/"):
        return "/assets/*"
    return path


@app.middleware("http")
async def _record_metrics(request: Request, call_next):
    # In-flight gauge keyed by method only — routing hasn't happened yet, and this keeps
    # the +1/-1 pair on the same series so it always nets back to zero.
    in_flight_attrs = {"http.method": request.method}
    metrics.REQUESTS_IN_FLIGHT.add(1, attributes=in_flight_attrs)
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        # Read the matched route now that routing has run (see _route_template).
        labels = {
            "http.method": request.method,
            "http.route": _route_template(request),
            "http.status_code": status,
        }
        metrics.REQUEST_DURATION.record(elapsed_ms, attributes=labels)
        metrics.REQUESTS_TOTAL.add(1, attributes=labels)
        metrics.REQUESTS_IN_FLIGHT.add(-1, attributes=in_flight_attrs)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _df_records(df) -> list[dict]:
    """DataFrame → list of JSON-safe dict rows (numeric strings coerced, NaN → None)."""
    import math
    import pandas as pd

    if df is None or df.empty:
        return []
    out = df.copy()
    for col in out.columns:
        # Coerce numeric-looking columns so the client gets numbers, not strings.
        try:
            out[col] = pd.to_numeric(out[col])
        except (ValueError, TypeError):
            pass

    def _clean(v):
        # NaN/NaT/None → None (assigning None into a float column reverts to NaN,
        # so we scrub at the value level instead).
        if v is None:
            return None
        if isinstance(v, float) and math.isnan(v):
            return None
        if v is pd.NaT:
            return None
        return v

    return [{k: _clean(v) for k, v in row.items()} for row in out.to_dict(orient="records")]


# ── Request models ─────────────────────────────────────────────────────────────

class EnrichBody(BaseModel):
    question: str


class AnalyzeBody(BaseModel):
    question: str
    route: str
    ctx: dict
    session_id: str | None = None
    proposed_route: str | None = None   # what the app proposed at the gate (for the audit log)


class GateDecisionBody(BaseModel):
    decision: str                        # "cancelled" | "timed_out"
    question: str | None = None
    proposed_route: str | None = None
    ctx: dict | None = None
    session_id: str | None = None


# ── Meta / config ────────────────────────────────────────────────────────────

@app.get("/api/config")
def config() -> dict:
    """UI bootstrap: titles, theme, route metadata, suggested questions, env summary."""
    return {
        "title":      core.APP_TITLE,
        "icon":       core.APP_ICON,
        "navy":       core.NAVY,
        "orange":     core.ORANGE,
        "agent":      core.BPM_AGENT_EP or "not configured",
        "catalog":    f"{core.BPM_CATALOG}.{core.BPM_SCHEMA}",
        "routeLabel": core.ROUTE_LABEL,
        "routeWhy":   core.ROUTE_WHY,
        "suggested":  core.SUGGESTED_QUESTIONS,
        "hitlTimeoutSecs": core.HITL_TIMEOUT_SECS,
    }


# ── Dashboard / chart data ─────────────────────────────────────────────────────

@app.get("/api/kpis")
def kpis() -> dict:
    df = core.load_brand_summary_kpis(core.BPM_CATALOG, core.BPM_SCHEMA)
    return {"rows": _df_records(df), "error": core.last_sql_error() if df is None else None}


@app.get("/api/share-trend")
def share_trend(brand: str = "NovaBaby", weeks: int = 52) -> dict:
    df = core.load_share_trend(core.BPM_CATALOG, core.BPM_SCHEMA, brand, weeks)
    return {"rows": _df_records(df)}


@app.get("/api/insurgents")
def insurgents(category: str = "Infant Formula") -> dict:
    df = core.load_top_insurgent_brands(core.BPM_CATALOG, core.BPM_SCHEMA, category)
    return {"rows": _df_records(df), "error": core.last_sql_error() if df is None else None}


@app.get("/api/distribution")
def distribution() -> dict:
    df = core.load_distribution_overview(core.BPM_CATALOG, core.BPM_SCHEMA)
    return {"rows": _df_records(df), "error": core.last_sql_error() if df is None else None}


@app.post("/api/refresh")
def refresh() -> dict:
    core.clear_caches()
    return {"ok": True}


# ── Two-phase HITL ──────────────────────────────────────────────────────────────

@app.post("/api/enrich")
def enrich(body: EnrichBody) -> dict:
    """
    Phase 1 — classify + enrich. Returns the gate decision the React UI acts on:
      status = "error"     → enrichment service unreachable
               "out_of_scope"
               "incomplete" → needs more params (missing list)
               "gate"       → complete; UI shows Confirm / Change route / Cancel
    """
    with metrics.timed(metrics.ENRICH_DURATION):
        ctx = core.enrich_request(body.question)
    if ctx is None:
        reason = core.last_sql_error() or "no detail"
        return {"status": "error", "detail": reason}
    qtype = ctx.get("question_type")
    if qtype == "out_of_scope":
        return {"status": "out_of_scope", "ctx": ctx}
    if not ctx.get("is_complete"):
        return {
            "status":  "incomplete",
            "ctx":     ctx,
            "missing": ctx.get("missing_params") or ["brand", "category"],
        }
    return {
        "status":     "gate",
        "ctx":        ctx,
        "route":      qtype,
        "routeLabel": core.ROUTE_LABEL.get(qtype, qtype),
        "routeWhy":   core.ROUTE_WHY.get(qtype, ""),
        "sessionId":  str(uuid.uuid4()),
    }


@app.post("/api/analyze")
def analyze(body: AnalyzeBody, background: BackgroundTasks) -> dict:
    """Phase 2 — one supervisor call carrying the confirmed ROUTE + context."""
    sid = body.session_id or str(uuid.uuid4())
    t0 = time.perf_counter()
    with metrics.timed(metrics.AGENT_CALL_DURATION, route=body.route):
        text, viz_hint = core.call_domain_agent(body.question, body.ctx, body.route, sid)
    latency_ms = int((time.perf_counter() - t0) * 1000)
    chart = core.chart_data(text, route=body.route, ctx=body.ctx) if viz_hint else None
    # Lakebase audit row, written after the response is sent (off the critical path).
    proposed = body.proposed_route or body.route
    background.add_task(
        audit.record, "confirmed" if proposed == body.route else "overridden",
        session_id=sid, question=body.question, proposed_route=proposed,
        final_route=body.route, ctx=body.ctx, agent_latency_ms=latency_ms)
    return {"text": text, "vizHint": viz_hint, "chart": chart, "route": body.route}


@app.post("/api/hitl/decision")
def hitl_decision(body: GateDecisionBody, background: BackgroundTasks) -> dict:
    """Record a gate outcome that never reaches Phase 2 (cancel / timeout)."""
    if body.decision not in ("cancelled", "timed_out"):
        return JSONResponse({"error": "decision must be 'cancelled' or 'timed_out'"}, status_code=400)
    background.add_task(
        audit.record, body.decision, session_id=body.session_id, question=body.question,
        proposed_route=body.proposed_route, final_route=None, ctx=body.ctx)
    return {"ok": True}


@app.get("/api/hitl/stats")
def hitl_stats(days: int = 30) -> dict:
    """HITL confirmation rate computed from the Lakebase audit log."""
    return {"lakebase": audit.status(), "stats": audit.stats(days)}


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "lakebase": audit.status()}


# ── Static React app (mounted last so /api/* wins) ───────────────────────────────

if (STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    """Serve static files if present; otherwise fall back to the SPA entry (client routing)."""
    candidate = STATIC_DIR / full_path
    if candidate.is_file():
        return FileResponse(candidate)
    index_html = STATIC_DIR / "index.html"
    if index_html.is_file():
        return FileResponse(index_html)
    return JSONResponse(
        {"detail": "React build not found. Run `npm run build` in ./frontend."},
        status_code=503,
    )
