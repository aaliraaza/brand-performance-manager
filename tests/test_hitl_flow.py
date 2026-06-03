"""
test_hitl_flow.py — corrected two-phase, app-owned HITL flow.

The HITL gate is no longer a Lakebase PENDING→CONFIRMED state machine polled from the app.
It is owned by the Streamlit app:

  Phase 1  enrich_request()  → classify + completeness (UC function call)
  GATE     session_state     → propose route; user Confirm / Change / Cancel
  Phase 2  call_domain_agent() → ONE supervisor call carrying the confirmed ROUTE

These unit tests pin the two contracts that the old design got wrong:
  1. Phase 2 sends the confirmed ROUTE + enriched context to the supervisor in a single call
     (the old flow dead-ended at confirmation and never executed the route).
  2. Phase 1 returns structured context the gate uses to decide clarify / scope / proceed.

The gate's button wiring (Confirm → call_domain_agent) is UI and is covered by
test_routing.py (integration) + manual verification. These tests use the `app` fixture from
conftest.py and skip if app deps (pandas/plotly) are absent.
"""

from __future__ import annotations


# ── Phase 2 — call_domain_agent builds a single ROUTE-carrying supervisor call ──

def test_phase2_sends_route_and_context(app, fake_st, monkeypatch):
    fake_st.session_state.update(
        circuit_breaker_open=False, circuit_breaker_fails=0, cb_open_until=0.0,
    )
    monkeypatch.setattr(app, "_auth_token", lambda: "tok")

    captured = {}

    def fake_post(endpoint, payload, token):
        captured["endpoint"] = endpoint
        captured["payload"] = payload
        return {"choices": [{"message": {"content":
                "NovaBaby share fell 1.3 ppt.\nVISUALIZATION: line|week_ending|value_share_pct|Share"}}]}

    monkeypatch.setattr(app, "_db_post", fake_post)

    ctx = {"brand": "NovaBaby", "category": "Infant Formula",
           "retailer": "Walmart", "region": "Total US", "time_window_weeks": 4}
    text, viz = app.call_domain_agent(
        "Why did NovaBaby share drop last 4 weeks at Walmart?", ctx, "topline", "sess-1",
    )

    # Exactly one supervisor call, to the configured endpoint
    assert captured["endpoint"] == app.BPM_AGENT_EP
    content = captured["payload"]["messages"][0]["content"]
    assert "ROUTE=topline" in content
    assert "brand=NovaBaby" in content and "time_window_weeks=4" in content
    assert "Why did NovaBaby share drop" in content
    assert captured["payload"]["databricks_options"]["session_id"] == "sess-1"

    # Response text + parsed viz hint are returned to the chat layer
    assert "1.3 ppt" in text
    assert viz == "line|week_ending|value_share_pct|Share"


def test_phase2_circuit_breaker_blocks_when_open(app, fake_st, monkeypatch):
    import time as _time
    fake_st.session_state.update(
        circuit_breaker_open=True, circuit_breaker_fails=3,
        cb_open_until=_time.time() + 120,
    )
    # _db_post must NOT be called while the breaker is open
    monkeypatch.setattr(app, "_db_post",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")))
    monkeypatch.setattr(app, "_auth_token", lambda: "tok")

    text, viz = app.call_domain_agent("q", {}, "topline", "s")
    assert viz is None
    assert "unavailable" in text.lower()


# ── Phase 1 — enrich_request parses the UC-function struct the gate consumes ────

def _fake_df(value):
    import pandas as pd
    return pd.DataFrame({"r": [value]})


def test_enrich_parses_complete_struct(app, monkeypatch):
    import json
    struct = json.dumps({
        "brand": "NovaBaby", "category": "Infant Formula", "time_window_weeks": 4,
        "retailer": "Walmart", "region": "Total US",
        "question_type": "topline", "is_complete": True, "missing_params": [],
    })
    monkeypatch.setattr(app, "query_sql", lambda *a, **k: _fake_df(struct))

    ctx = app.enrich_request("Why did NovaBaby share drop last 4 weeks at Walmart?")
    assert ctx["question_type"] == "topline"
    assert ctx["is_complete"] is True
    assert ctx["brand"] == "NovaBaby"


def test_enrich_flags_incomplete(app, monkeypatch):
    import json
    struct = json.dumps({
        "brand": None, "category": None, "time_window_weeks": 12,
        "retailer": "Total US", "region": "Total US",
        "question_type": "topline", "is_complete": False,
        "missing_params": ["brand", "category"],
    })
    monkeypatch.setattr(app, "query_sql", lambda *a, **k: _fake_df(struct))

    ctx = app.enrich_request("What is our share trend?")
    assert ctx["is_complete"] is False
    assert "brand" in ctx["missing_params"]


def test_enrich_returns_none_when_warehouse_unreachable(app, monkeypatch):
    monkeypatch.setattr(app, "query_sql", lambda *a, **k: None)
    assert app.enrich_request("anything") is None
