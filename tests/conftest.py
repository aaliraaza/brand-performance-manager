"""
Shared test fixtures for the Brand Performance Manager test suite.

The app-side unit tests import `app/app.py`, which imports `streamlit`. We inject a
minimal fake `streamlit` module into `sys.modules` *before* importing the app so the
pure helper functions (enrich_request, call_domain_agent, extract_visualization,
render_visualization) can be exercised without a Streamlit runtime.

Integration tests (live Databricks) do not use these fixtures; they skip on missing creds.
"""

from __future__ import annotations

import os
import sys
import types

import pytest

APP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app")


class _SessionState(dict):
    """dict that also supports attribute access, like st.session_state."""

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc

    def __setattr__(self, key, value):
        self[key] = value


def _install_fake_streamlit() -> types.ModuleType:
    """Inject a minimal fake `streamlit` so `import app` succeeds off-runtime."""
    if "streamlit" in sys.modules:
        return sys.modules["streamlit"]

    st = types.ModuleType("streamlit")
    st.session_state = _SessionState()
    st.context = types.SimpleNamespace(headers={})

    def _decorator_factory(*_a, **_k):
        def _decorate(fn):
            return fn
        return _decorate

    # Applied at import time on _m2m_token / the load_* helpers.
    st.cache_resource = _decorator_factory
    st.cache_data = _decorator_factory

    # Everything else app touches only at call time → return a harmless no-op stub.
    def _noop(*_a, **_k):
        return None

    def __getattr__(_name):          # PEP 562 module-level __getattr__
        return _noop

    st.__getattr__ = __getattr__
    sys.modules["streamlit"] = st
    return st


@pytest.fixture(scope="session")
def app():
    """Import the Streamlit app module with a faked streamlit; skip if deps absent."""
    _install_fake_streamlit()
    if APP_DIR not in sys.path:
        sys.path.insert(0, APP_DIR)
    try:
        import app as app_module  # noqa: WPS433
    except ModuleNotFoundError as exc:
        pytest.skip(f"app dependencies not installed ({exc.name}); skipping app-side unit tests")
    return app_module


@pytest.fixture
def fake_st(app):
    """Reset the fake streamlit session_state between tests."""
    st = sys.modules["streamlit"]
    st.session_state.clear()
    return st
