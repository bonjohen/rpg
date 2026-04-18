"""Model call instrumentation.

Records one ModelCallLog per inference call. Callers collect and persist these
however they see fit (append to a list, write to a log file, send to a metrics
sink). The instrumentation layer never blocks a turn.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelCallLog:
    """Structured record of a single model call."""

    trace_id: str
    tier: str  # "fast" | "gemma"
    task_type: str
    prompt_token_count: int
    output_token_count: int
    latency_ms: float
    success: bool
    failure_reason: str = ""
    fallback_triggered: bool = False
