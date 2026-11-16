"""
Custom OpenTelemetry metrics for the Brand Performance Manager app.

Auto-instrumentation (`opentelemetry-instrument` in app.yaml + the FastAPI
instrumentor) already emits per-route HTTP server spans and duration/count metrics.
This module adds *named, app-owned* metrics so the demo has explicit, easy-to-query
instruments in the `otel_metrics` Unity Catalog table:

    bpm.http.requests.total      Counter        total requests (method, route, status)
    bpm.http.request.duration    Histogram      request latency, milliseconds
    bpm.http.requests.in_flight  UpDownCounter  concurrent in-flight requests ("queue")
    bpm.enrich.duration          Histogram      Phase-1 enrich_user_request latency, ms
    bpm.agent.call.duration      Histogram      Phase-2 supervisor call latency, ms

Everything goes through the OpenTelemetry metrics *API* (`opentelemetry.metrics`).
When the SDK is configured (i.e. under `opentelemetry-instrument` in the Databricks
Apps runtime) these record and export via the injected OTLP exporter. When it is not
— local `uvicorn` runs, unit tests — the API falls back to a no-op meter, so importing
and calling these is always safe and dependency-light.
"""

from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter

try:
    from opentelemetry import metrics as _otel_metrics
    _meter = _otel_metrics.get_meter("brand-performance-manager")
except Exception:  # pragma: no cover - OTel API always present once deps install
    _meter = None


class _NoopInstrument:
    """Stand-in used when the OTel API is unavailable, so callers never branch."""

    def add(self, *_args, **_kwargs) -> None:  # Counter / UpDownCounter
        pass

    def record(self, *_args, **_kwargs) -> None:  # Histogram
        pass


def _counter(name: str, unit: str, description: str):
    if _meter is None:
        return _NoopInstrument()
    return _meter.create_counter(name, unit=unit, description=description)


def _updown(name: str, unit: str, description: str):
    if _meter is None:
        return _NoopInstrument()
    return _meter.create_up_down_counter(name, unit=unit, description=description)


def _histogram(name: str, unit: str, description: str):
    if _meter is None:
        return _NoopInstrument()
    return _meter.create_histogram(name, unit=unit, description=description)


# ── Instruments ────────────────────────────────────────────────────────────────

REQUESTS_TOTAL = _counter(
    "bpm.http.requests.total", "1", "Total HTTP requests handled, by route and status."
)
REQUEST_DURATION = _histogram(
    "bpm.http.request.duration", "ms", "HTTP request latency in milliseconds."
)
REQUESTS_IN_FLIGHT = _updown(
    "bpm.http.requests.in_flight", "1", "Requests currently being processed (queue depth)."
)
ENRICH_DURATION = _histogram(
    "bpm.enrich.duration", "ms", "Phase-1 enrich_user_request latency in milliseconds."
)
AGENT_CALL_DURATION = _histogram(
    "bpm.agent.call.duration", "ms", "Phase-2 supervisor (domain agent) call latency in milliseconds."
)


@contextmanager
def timed(histogram, **attributes):
    """Record wall-clock duration (ms) of the wrapped block into `histogram`.

    Usage:
        with timed(ENRICH_DURATION, route="enrich"):
            ctx = core.enrich_request(q)
    """
    start = perf_counter()
    try:
        yield
    finally:
        histogram.record((perf_counter() - start) * 1000.0, attributes=attributes or None)
