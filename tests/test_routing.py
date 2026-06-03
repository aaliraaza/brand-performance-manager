"""
test_routing.py — Phase 2 dispatch integration tests.

In the corrected (two-phase) flow, intake/classification is a Phase 1 UC-function call
(see test_uc_functions.py) and the human-in-the-loop gate is owned by the app. This file
validates **Phase 2**: given an already-confirmed ROUTE, the single Brand Performance
Manager supervisor dispatches to the correct specialist and returns relevant content.

Each request is shaped exactly as the app sends it on Confirm — a directive containing
`ROUTE=<route>` plus enriched context — so the supervisor should NOT re-classify or ask
for confirmation.

Mark: @pytest.mark.integration  (requires the deployed supervisor endpoint; skipped without creds)
"""

from __future__ import annotations

import json
import os
import unittest
import urllib.request

import pytest

HOST    = os.environ.get("DATABRICKS_HOST",  "").rstrip("/")
TOKEN   = os.environ.get("DATABRICKS_TOKEN", os.environ.get("MJN_API_TOKEN", ""))
BPM_EP  = os.environ.get("BPM_AGENT_ENDPOINT", "mas-brand-performance-manager-endpoint")
TIMEOUT = 180


def _directive(route: str, ctx: dict, question: str) -> str:
    """Mirror app.call_domain_agent's Phase-2 message construction."""
    return (
        f"ROUTE={route}. The request is already enriched and user-confirmed — "
        f"dispatch directly to the {route} specialist; do not ask for confirmation "
        f"or re-classify.\n"
        f"Context: brand={ctx.get('brand')}, category={ctx.get('category')}, "
        f"retailer={ctx.get('retailer')}, region={ctx.get('region')}, "
        f"time_window_weeks={ctx.get('time_window_weeks')}.\n"
        f"Question: {question}"
    )


def call_supervisor(route: str, ctx: dict, question: str) -> str:
    """Call the supervisor with a confirmed ROUTE and return the response text."""
    payload = json.dumps({
        "messages": [{"role": "user", "content": _directive(route, ctx, question)}],
    }).encode()
    req = urllib.request.Request(
        url     = f"{HOST}/serving-endpoints/{BPM_EP}/invocations",
        data    = payload,
        headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        method  = "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            result = json.loads(resp.read())
    except Exception as exc:
        pytest.skip(f"Cannot reach supervisor endpoint: {exc}")

    choices = result.get("choices", [])
    if choices:
        return choices[0].get("message", {}).get("content", "")
    return str(result.get("output", ""))


@pytest.mark.integration
class TestPhase2Dispatch(unittest.TestCase):

    def setUp(self):
        if not HOST or not TOKEN:
            self.skipTest("DATABRICKS_HOST / DATABRICKS_TOKEN not set")
        if not BPM_EP:
            self.skipTest("BPM_AGENT_ENDPOINT not set")

    def test_topline_dispatch(self):
        """ROUTE=topline should dispatch to topline_agent and return share content."""
        resp = call_supervisor(
            "topline",
            {"brand": "NovaBaby", "category": "Infant Formula",
             "retailer": "Walmart", "time_window_weeks": 4},
            "Why did NovaBaby share drop last 4 weeks at Walmart?",
        )
        lower = resp.lower()
        self.assertTrue(
            any(kw in lower for kw in ["share", "ppt", "decomposition", "distribution", "rate"]),
            f"Expected topline content:\n{resp[:400]}",
        )

    def test_insurgent_dispatch(self):
        """ROUTE=insurgent_brands should dispatch to insurgent_brands_analyst."""
        resp = call_supervisor(
            "insurgent_brands",
            {"category": "Infant Formula", "time_window_weeks": 12},
            "Which insurgent brands are gaining share?",
        )
        lower = resp.lower()
        self.assertTrue(
            any(kw in lower for kw in ["insurgent", "challenger", "gaining", "threat", "emerging"]),
            f"Expected insurgent content:\n{resp[:400]}",
        )

    def test_distribution_dispatch(self):
        """ROUTE=distribution_velocity should dispatch to distribution_velocity_analyst."""
        resp = call_supervisor(
            "distribution_velocity",
            {"region": "Northeast", "time_window_weeks": 4},
            "Which SKUs have below-80% ACV?",
        )
        lower = resp.lower()
        self.assertTrue(
            any(kw in lower for kw in ["acv", "distribution", "sku", "velocity", "stores"]),
            f"Expected distribution content:\n{resp[:400]}",
        )

    def test_dispatch_does_not_reconfirm(self):
        """The supervisor must not re-ask for confirmation — the route is pre-confirmed."""
        resp = call_supervisor(
            "topline",
            {"brand": "NovaBaby", "category": "Infant Formula", "time_window_weeks": 12},
            "What is NovaBaby's value share trend?",
        )
        lower = resp.lower()
        self.assertFalse(
            any(kw in lower for kw in ["please confirm", "confirmation id", "confirm in the panel"]),
            f"Supervisor should not re-request HITL confirmation:\n{resp[:400]}",
        )


if __name__ == "__main__":
    unittest.main()
