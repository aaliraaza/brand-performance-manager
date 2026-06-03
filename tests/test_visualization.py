"""
test_visualization.py — visualization unit tests (deterministic, app-side).

The corrected design renders charts deterministically in the app from a SQL query keyed
on the confirmed route + context — there is NO LLM "Visualization Adapter" endpoint. These
tests therefore exercise the app's own helpers (no Databricks, no model serving):

  - extract_visualization(): parses the agent's "VISUALIZATION: type|x|y|title" hint
  - render_visualization(): builds a Plotly figure from a (mocked) SQL loader

They use the `app` fixture from conftest.py, which fakes `streamlit` so the module imports
off-runtime. Tests skip automatically if the app's runtime deps (pandas/plotly) are absent.
"""

from __future__ import annotations


# ── extract_visualization (pure parsing) ───────────────────────────────────────

def test_extract_visualization_parses_hint(app):
    text = (
        "NovaBaby share fell 1.3 ppt last 4 weeks, driven by distribution loss.\n"
        "VISUALIZATION: line|week_ending|value_share_pct|NovaBaby Value Share — L4W"
    )
    result = app.extract_visualization(text)
    assert result == ("line", "week_ending", "value_share_pct",
                      "NovaBaby Value Share — L4W")


def test_extract_visualization_returns_none_without_hint(app):
    assert app.extract_visualization("No chart requested here.") is None


# ── render_visualization (deterministic Plotly from a mocked loader) ────────────

def _capture_plotly(monkeypatch, app):
    captured = {}
    monkeypatch.setattr(app.st, "plotly_chart",
                        lambda fig, **k: captured.update(fig=fig), raising=False)
    return captured


def test_render_topline_builds_figure(app, monkeypatch):
    import pandas as pd

    df = pd.DataFrame({
        "week_ending":     ["2025-01-04", "2025-01-11", "2025-01-18"],
        "value_share_pct": [32.1, 31.8, 31.5],
    })
    monkeypatch.setattr(app, "load_share_trend", lambda *a, **k: df)
    captured = _capture_plotly(monkeypatch, app)

    text = "Share down 0.6 ppt.\nVISUALIZATION: line|week_ending|value_share_pct|NovaBaby Share"
    app.render_visualization(text, route="topline",
                             ctx={"brand": "NovaBaby", "time_window_weeks": 52})

    assert "fig" in captured, "expected a Plotly figure to be rendered"
    assert len(captured["fig"].data) == 1


def test_render_noop_without_context(app, monkeypatch):
    """No enriched context → nothing rendered (guards against blank/garbage charts)."""
    captured = _capture_plotly(monkeypatch, app)
    app.render_visualization("VISUALIZATION: line|x|y|t", route="topline", ctx=None)
    assert "fig" not in captured


def test_render_swallows_loader_errors(app, monkeypatch):
    """A loader failure must degrade to a caption, never raise into the chat flow."""
    def _boom(*_a, **_k):
        raise RuntimeError("warehouse down")

    monkeypatch.setattr(app, "load_share_trend", _boom)
    monkeypatch.setattr(app.st, "caption", lambda *a, **k: None, raising=False)

    # Should not raise
    app.render_visualization("VISUALIZATION: line|x|y|t", route="topline",
                             ctx={"brand": "NovaBaby", "time_window_weeks": 4})
