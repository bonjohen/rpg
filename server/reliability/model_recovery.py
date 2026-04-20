"""Model timeout and recovery behavior.

Wraps model calls in asyncio.wait_for with a configurable timeout.
On timeout or exception, falls back to a deterministic fallback function
so the turn is never blocked.

All stdlib — uses asyncio.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Policy and result types
# ---------------------------------------------------------------------------


@dataclass
class ModelTimeoutPolicy:
    """Timeout configuration for each model tier."""

    fast_timeout_seconds: float = 5.0
    main_timeout_seconds: float = 30.0
    repair_timeout_seconds: float = 10.0


@dataclass
class ModelCallResult:
    """Result of a model call with timeout protection."""

    success: bool
    data: dict | None = None
    fallback_used: bool = False
    timeout: bool = False
    error: str = ""
    duration_ms: float = 0.0
    trace_id: str = ""


# ---------------------------------------------------------------------------
# Timeout-protected model call
# ---------------------------------------------------------------------------


async def call_with_timeout(
    call_fn: Callable,
    timeout_seconds: float,
    fallback_fn: Callable,
    trace_id: str = "",
) -> ModelCallResult:
    """Execute call_fn with a timeout, falling back on timeout or exception.

    call_fn: async callable that returns a dict.
    timeout_seconds: max time to wait for call_fn.
    fallback_fn: callable (sync or async) that returns a dict. Always produces
        a usable result so the turn is never blocked.
    trace_id: for logging correlation.

    Returns ModelCallResult with the outcome.
    """
    start = time.monotonic()

    try:
        result = await asyncio.wait_for(call_fn(), timeout=timeout_seconds)
        elapsed = (time.monotonic() - start) * 1000
        return ModelCallResult(
            success=True,
            data=result,
            duration_ms=elapsed,
            trace_id=trace_id,
        )
    except asyncio.TimeoutError:
        elapsed = (time.monotonic() - start) * 1000
        logger.warning(
            "Model call timed out after %.0fms (limit=%.1fs) [trace=%s]",
            elapsed,
            timeout_seconds,
            trace_id,
        )
        fallback_data = _invoke_fallback(fallback_fn)
        return ModelCallResult(
            success=fallback_data is not None,
            data=fallback_data,
            fallback_used=True,
            timeout=True,
            error="" if fallback_data is not None else "async fallback discarded",
            duration_ms=elapsed,
            trace_id=trace_id,
        )
    except Exception as exc:
        elapsed = (time.monotonic() - start) * 1000
        logger.error(
            "Model call failed with %s: %s [trace=%s]",
            type(exc).__name__,
            exc,
            trace_id,
        )
        fallback_data = _invoke_fallback(fallback_fn)
        return ModelCallResult(
            success=fallback_data is not None,
            data=fallback_data,
            fallback_used=True,
            timeout=False,
            error=str(exc)
            if fallback_data is not None
            else f"{exc}; async fallback discarded",
            duration_ms=elapsed,
            trace_id=trace_id,
        )


def _invoke_fallback(fallback_fn: Callable) -> dict | None:
    """Call the fallback function, handling both sync and async variants.

    Returns the fallback dict on success, or None if the fallback could
    not be invoked (e.g. async fallback in sync context).
    """
    result = fallback_fn()
    # If the fallback returned a coroutine (async def), we can't await it here
    # in a sync context. Fallbacks should be sync for reliability.
    if asyncio.iscoroutine(result):
        logger.warning(
            "Async fallback function discarded — fallbacks must be synchronous."
        )
        result.close()
        return None
    return result
