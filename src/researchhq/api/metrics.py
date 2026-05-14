"""Prometheus metrics for the ResearchHQ API.

Exposes an ASGI app at /metrics for Prometheus scraping.

Metrics emitted:
  rhq_pipeline_executions_total   — counter  [mode, status]
  rhq_pipeline_latency_seconds    — histogram [mode]
  rhq_tokens_used_total           — counter  [provider, direction]
  rhq_estimated_cost_usd_total    — counter  [provider]
  rhq_confidence_score            — histogram [ensemble_mode]
  rhq_active_queries              — gauge    (currently processing)
  rhq_provider_errors_total       — counter  [provider, error_type]
  rhq_circuit_breaker_open        — gauge    [provider] (1=open, 0=closed/half-open)

Integration: call record_*() helpers from runner.py on pipeline events.
The /metrics ASGI mount is added in main.py.
"""

from __future__ import annotations

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    make_asgi_app,
)

# ── Counters ──────────────────────────────────────────────────────────────────

pipeline_executions = Counter(
    "rhq_pipeline_executions_total",
    "Total pipeline runs by mode and final status",
    ["mode", "status"],  # status: success | failed | canceled
)

tokens_used = Counter(
    "rhq_tokens_used_total",
    "LLM tokens consumed by provider and direction",
    ["provider", "direction"],  # direction: input | output
)

cost_usd = Counter(
    "rhq_estimated_cost_usd_total",
    "Estimated LLM cost in USD by provider",
    ["provider"],
)

provider_errors = Counter(
    "rhq_provider_errors_total",
    "LLM provider failures by provider and error type",
    ["provider", "error_type"],  # error_type: timeout | error | empty | circuit_open
)

# ── Histograms ────────────────────────────────────────────────────────────────

pipeline_latency = Histogram(
    "rhq_pipeline_latency_seconds",
    "End-to-end pipeline execution time in seconds",
    ["mode"],
    buckets=[5, 15, 30, 60, 120, 180, 300, 600],
)

confidence_scores = Histogram(
    "rhq_confidence_score",
    "Final answer confidence scores (0–1)",
    ["ensemble_mode"],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

# ── Gauges ────────────────────────────────────────────────────────────────────

active_queries = Gauge(
    "rhq_active_queries",
    "Number of queries currently being processed by the pipeline",
)

circuit_breaker_open = Gauge(
    "rhq_circuit_breaker_open",
    "1 if the provider circuit breaker is OPEN (rejecting requests), 0 otherwise",
    ["provider"],
)


# ── Helper functions called from runner.py ────────────────────────────────────

def record_run_started() -> None:
    active_queries.inc()


def record_run_finished(
    mode: str,
    status: str,  # "success" | "failed" | "canceled"
    elapsed_s: float,
    ensemble_mode: str,
    confidence: float,
    stage_costs: list,
) -> None:
    active_queries.dec()
    pipeline_executions.labels(mode=mode, status=status).inc()
    pipeline_latency.labels(mode=mode).observe(elapsed_s)

    if status == "success":
        confidence_scores.labels(ensemble_mode=ensemble_mode).observe(confidence)

    for sc in stage_costs:
        provider = getattr(sc, "provider", "unknown") or "unknown"
        in_tok = getattr(sc, "input_tokens", 0) or 0
        out_tok = getattr(sc, "output_tokens", 0) or 0
        cost = getattr(sc, "equivalent_cost_usd", 0.0) or 0.0
        if in_tok:
            tokens_used.labels(provider=provider, direction="input").inc(in_tok)
        if out_tok:
            tokens_used.labels(provider=provider, direction="output").inc(out_tok)
        if cost:
            cost_usd.labels(provider=provider).inc(cost)


def record_provider_error(provider: str, error_type: str) -> None:
    """error_type: timeout | error | empty | circuit_open"""
    provider_errors.labels(provider=provider, error_type=error_type).inc()


def update_circuit_breaker_gauge(provider: str, is_open: bool) -> None:
    circuit_breaker_open.labels(provider=provider).set(1 if is_open else 0)


# ── ASGI app mounted at /metrics ──────────────────────────────────────────────

metrics_app = make_asgi_app()
