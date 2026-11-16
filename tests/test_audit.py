"""Lakebase audit log — contract tests that need no database."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import audit  # noqa: E402


def test_disabled_without_pghost(monkeypatch):
    monkeypatch.delenv("PGHOST", raising=False)
    assert audit.enabled() is False
    # Best-effort: no database bound → nothing written, nothing raised.
    assert audit.record("confirmed", session_id="s", question="q",
                        proposed_route="topline", final_route="topline") is False
    assert audit.stats() is None
    assert audit.status()["enabled"] is False


def test_rejects_unknown_decision():
    with pytest.raises(ValueError):
        audit.record("maybe", session_id=None, question=None, proposed_route=None, final_route=None)


def test_unreachable_db_is_swallowed(monkeypatch):
    monkeypatch.setenv("PGHOST", "127.0.0.1")
    monkeypatch.setenv("PGPORT", "1")          # nothing listens here
    monkeypatch.setenv("PGPASSWORD", "x")      # skip credential minting
    assert audit.record("cancelled", session_id="s", question="q",
                        proposed_route="topline", final_route=None) is False
    assert audit.status()["last_error"]


def test_ddl_constrains_decisions():
    for d in audit.DECISIONS:
        assert f"'{d}'" in audit.DDL
