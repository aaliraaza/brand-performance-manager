"""
Lakebase (Postgres) routing audit log for the human-in-the-loop gate.

Every routing decision the user makes at the HITL gate is written to
`bpm_audit.routing_decisions` in the Lakebase database bound to the app:

    confirmed   — user ran the route the app proposed
    overridden  — user changed the route before running
    cancelled   — user cancelled at the gate
    timed_out   — the confirmation window expired

That gives the PRD's "HITL confirmation rate" metric (target > 80%) a real,
transactional system of record: `stats()` computes it straight from Postgres.

Off the critical path by design: every call here is best-effort. If Lakebase is
unbound, suspended or unreachable, the user's analysis still runs and the failure
is only reported via `status()` / `/api/health`.

Connection: the Databricks Apps runtime injects PGHOST / PGPORT / PGDATABASE /
PGUSER / PGSSLMODE for the bound `postgres` resource. The password is a short-lived
OAuth database credential minted for the app's own service principal (M2M), so no
secret is stored anywhere.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.request

log = logging.getLogger("bpm.audit")

SCHEMA = "bpm_audit"
TABLE = f"{SCHEMA}.routing_decisions"
DECISIONS = ("confirmed", "overridden", "cancelled", "timed_out")

# Autoscaling endpoint used to mint the DB credential (overridable per environment).
LAKEBASE_ENDPOINT = os.environ.get(
    "LAKEBASE_ENDPOINT",
    "projects/brand-performance-manager/branches/production/endpoints/primary",
)

_lock = threading.Lock()
_state = {"token": "", "expires_at": 0.0, "initialised": False, "last_error": None}

DDL = f"""
CREATE SCHEMA IF NOT EXISTS {SCHEMA};
CREATE TABLE IF NOT EXISTS {TABLE} (
    id               BIGSERIAL PRIMARY KEY,
    decided_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    session_id       TEXT,
    question         TEXT,
    proposed_route   TEXT,
    final_route      TEXT,
    decision         TEXT NOT NULL CHECK (decision IN {DECISIONS}),
    brand            TEXT,
    category         TEXT,
    retailer         TEXT,
    agent_latency_ms INTEGER
);
CREATE INDEX IF NOT EXISTS routing_decisions_decided_at_idx ON {TABLE} (decided_at);
"""


def enabled() -> bool:
    """True when a Lakebase database is bound to the app (PGHOST injected)."""
    return bool(os.environ.get("PGHOST"))


# ── Credentials ──────────────────────────────────────────────────────────────

def _host() -> str:
    h = os.environ.get("DATABRICKS_HOST", "").rstrip("/")
    return h if h.startswith("http") else f"https://{h}"


def _m2m_token() -> str:
    """Workspace OAuth token for the app's service principal."""
    import urllib.parse
    cid = os.environ.get("DATABRICKS_CLIENT_ID", "")
    secret = os.environ.get("DATABRICKS_CLIENT_SECRET", "")
    if not (cid and secret and os.environ.get("DATABRICKS_HOST")):
        return ""
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials", "client_id": cid,
        "client_secret": secret, "scope": "all-apis",
    }).encode()
    req = urllib.request.Request(f"{_host()}/oidc/v1/token", data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read()).get("access_token", "")


def _db_credential(ws_token: str) -> str:
    """Short-lived Postgres password scoped to the Lakebase endpoint."""
    req = urllib.request.Request(
        f"{_host()}/api/2.0/postgres/credentials",
        data=json.dumps({"endpoint": LAKEBASE_ENDPOINT}).encode(),
        headers={"Authorization": f"Bearer {ws_token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read()).get("token", "")


def _password() -> str:
    if os.environ.get("PGPASSWORD"):
        return os.environ["PGPASSWORD"]
    if _state["token"] and time.time() < _state["expires_at"] - 120:
        return _state["token"]
    ws = _m2m_token()
    try:
        tok = _db_credential(ws) or ws
    except Exception as e:  # fall back to the workspace token, which Lakebase also accepts
        log.warning("postgres credential mint failed, using workspace token: %s", e)
        tok = ws
    _state["token"], _state["expires_at"] = tok, time.time() + 50 * 60
    return tok


def _connect():
    import psycopg2
    return psycopg2.connect(
        host=os.environ["PGHOST"],
        port=int(os.environ.get("PGPORT", 5432)),
        dbname=os.environ.get("PGDATABASE", "databricks_postgres"),
        user=os.environ.get("PGUSER", ""),
        password=_password(),
        sslmode=os.environ.get("PGSSLMODE", "require"),
        connect_timeout=10,
    )


def _run(fn):
    """Open a connection, ensure the schema exists, run fn(cursor). Best-effort."""
    if not enabled():
        return None
    try:
        with _lock:
            conn = _connect()
            try:
                with conn, conn.cursor() as cur:
                    if not _state["initialised"]:
                        cur.execute(DDL)
                        _state["initialised"] = True
                    out = fn(cur)
            finally:
                conn.close()
        _state["last_error"] = None
        return out
    except Exception as e:
        _state["last_error"] = f"{type(e).__name__}: {e}"[:300]
        _state["expires_at"] = 0  # force a fresh credential next time
        log.warning("lakebase audit failed: %s", _state["last_error"])
        return None


# ── Public API ───────────────────────────────────────────────────────────────

def record(decision: str, *, session_id: str | None, question: str | None,
           proposed_route: str | None, final_route: str | None, ctx: dict | None = None,
           agent_latency_ms: int | None = None) -> bool:
    """Write one routing decision. Returns True if it was persisted."""
    if decision not in DECISIONS:
        raise ValueError(f"unknown decision {decision!r}")
    ctx = ctx or {}

    def _ins(cur):
        cur.execute(
            f"INSERT INTO {TABLE} (session_id, question, proposed_route, final_route, decision,"
            f" brand, category, retailer, agent_latency_ms) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (session_id, (question or "")[:2000], proposed_route, final_route, decision,
             ctx.get("brand"), ctx.get("category"), ctx.get("retailer"), agent_latency_ms),
        )
        return True

    return bool(_run(_ins))


def stats(days: int = 30) -> dict | None:
    """HITL confirmation rate + decision counts over the last `days` days."""
    def _q(cur):
        cur.execute(
            f"SELECT decision, count(*) FROM {TABLE} "
            f"WHERE decided_at > now() - make_interval(days => %s) GROUP BY decision", (days,))
        counts = {d: 0 for d in DECISIONS}
        counts.update({d: int(n) for d, n in cur.fetchall()})
        total = sum(counts.values())
        return {
            "days": days,
            "total": total,
            "counts": counts,
            # PRD metric: share of gate decisions where the user accepted the first suggestion.
            "confirmation_rate": round(counts["confirmed"] / total, 3) if total else None,
        }

    return _run(_q)


def warm_up() -> None:
    """Create the audit schema/table at startup (in a thread) so a deploy proves connectivity."""
    if enabled():
        threading.Thread(target=_run, args=(lambda cur: True,), daemon=True).start()


def status() -> dict:
    return {
        "enabled": enabled(),
        "host": os.environ.get("PGHOST", ""),
        "table": TABLE,
        "last_error": _state["last_error"],
    }
