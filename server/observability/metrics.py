"""Metrics collection for latency, routing, and failures.

In-memory metrics aggregator with counters and histograms.
Thread-safe via simple locking. All stdlib.
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Pre-defined metric names
# ---------------------------------------------------------------------------

METRIC_MODEL_CALLS = "model.calls"
METRIC_MODEL_LATENCY = "model.latency_ms"
METRIC_MODEL_FALLBACKS = "model.fallbacks"
METRIC_DELIVERY_ATTEMPTS = "delivery.attempts"
METRIC_DELIVERY_LATENCY = "delivery.latency_ms"
METRIC_TURN_DURATION = "turn.duration_ms"
METRIC_TURN_TIMEOUTS = "turn.timeouts"
METRIC_ACTIONS_SUBMITTED = "actions.submitted"
METRIC_DUPLICATE_BLOCKED = "idempotency.blocked"


# ---------------------------------------------------------------------------
# Stats types
# ---------------------------------------------------------------------------


@dataclass
class MetricStats:
    """Statistical summary of a histogram."""

    count: int = 0
    min: float = 0.0
    max: float = 0.0
    mean: float = 0.0
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0


@dataclass
class MetricsSnapshot:
    """Point-in-time snapshot of all metrics."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    counters: dict[str, int] = field(default_factory=dict)
    histograms: dict[str, MetricStats] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Key construction
# ---------------------------------------------------------------------------


def _make_key(name: str, tags: dict[str, str] | None) -> str:
    """Construct a metric key from name and optional tags."""
    if not tags:
        return name
    tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
    return f"{name}:{tag_str}"


# ---------------------------------------------------------------------------
# MetricsCollector
# ---------------------------------------------------------------------------


class MetricsCollector:
    """In-memory metrics aggregator with counters and histograms."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = {}
        self._histograms: dict[str, list[float]] = {}

    # --- Counters ---

    def increment(
        self, name: str, value: int = 1, tags: dict[str, str] | None = None
    ) -> None:
        """Increment a named counter."""
        key = _make_key(name, tags)
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + value

    def get_counter(self, name: str, tags: dict[str, str] | None = None) -> int:
        """Get current value of a counter."""
        key = _make_key(name, tags)
        with self._lock:
            return self._counters.get(key, 0)

    # --- Histograms ---

    def record(
        self, name: str, value: float, tags: dict[str, str] | None = None
    ) -> None:
        """Record a value in a named histogram."""
        key = _make_key(name, tags)
        with self._lock:
            if key not in self._histograms:
                self._histograms[key] = []
            self._histograms[key].append(value)

    def get_percentile(
        self, name: str, percentile: float, tags: dict[str, str] | None = None
    ) -> float:
        """Return the Nth percentile of recorded values.

        percentile should be 0-100 (e.g., 50 for median, 95 for p95).
        Returns 0.0 if no values recorded.
        """
        key = _make_key(name, tags)
        with self._lock:
            values = self._histograms.get(key, [])
            if not values:
                return 0.0
            return _percentile(values, percentile)

    def get_stats(self, name: str, tags: dict[str, str] | None = None) -> MetricStats:
        """Return statistical summary of a histogram."""
        key = _make_key(name, tags)
        with self._lock:
            values = self._histograms.get(key, [])
            if not values:
                return MetricStats()
            return MetricStats(
                count=len(values),
                min=min(values),
                max=max(values),
                mean=sum(values) / len(values),
                p50=_percentile(values, 50),
                p95=_percentile(values, 95),
                p99=_percentile(values, 99),
            )

    # --- Snapshot ---

    def snapshot(self) -> MetricsSnapshot:
        """Return a point-in-time snapshot of all metrics."""
        with self._lock:
            counters = dict(self._counters)
            histograms: dict[str, MetricStats] = {}
            for key, values in self._histograms.items():
                if values:
                    histograms[key] = MetricStats(
                        count=len(values),
                        min=min(values),
                        max=max(values),
                        mean=sum(values) / len(values),
                        p50=_percentile(values, 50),
                        p95=_percentile(values, 95),
                        p99=_percentile(values, 99),
                    )
        return MetricsSnapshot(counters=counters, histograms=histograms)

    def reset(self) -> None:
        """Clear all metrics (for testing)."""
        with self._lock:
            self._counters.clear()
            self._histograms.clear()


# ---------------------------------------------------------------------------
# Percentile calculation
# ---------------------------------------------------------------------------


def _percentile(values: list[float], pct: float) -> float:
    """Calculate the pct-th percentile using linear interpolation.

    pct is 0-100. Returns 0.0 for empty list.
    """
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]

    # Use the "inclusive" percentile method
    rank = (pct / 100.0) * (n - 1)
    lower = int(math.floor(rank))
    upper = int(math.ceil(rank))
    if lower == upper:
        return sorted_vals[lower]
    fraction = rank - lower
    return sorted_vals[lower] + fraction * (sorted_vals[upper] - sorted_vals[lower])
