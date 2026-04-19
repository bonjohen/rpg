"""Retry handling for Telegram delivery failures.

Implements exponential backoff with special handling for 429 (rate limit)
responses. All stdlib — uses asyncio for async delays.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Policy and result types
# ---------------------------------------------------------------------------


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    retryable_errors: set[int] = field(
        default_factory=lambda: {429, 500, 502, 503, 504}
    )


@dataclass
class DeliveryAttempt:
    """Record of a single delivery attempt."""

    attempt_number: int
    success: bool
    error: str = ""
    http_status: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    retry_after_seconds: float = 0.0


@dataclass
class DeliveryResult:
    """Overall result of a delivery operation (possibly with retries)."""

    success: bool
    message_id: int | None = None
    attempts: list[DeliveryAttempt] = field(default_factory=list)
    total_duration_ms: float = 0.0
    trace_id: str = ""


# ---------------------------------------------------------------------------
# Exception for extracting HTTP status from send failures
# ---------------------------------------------------------------------------


class DeliveryError(Exception):
    """Wraps a delivery failure with optional HTTP status code."""

    def __init__(self, message: str, http_status: int = 0, retry_after: float = 0.0):
        super().__init__(message)
        self.http_status = http_status
        self.retry_after = retry_after


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------


async def send_with_retry(
    send_fn: Callable,
    retry_policy: RetryPolicy | None = None,
    trace_id: str = "",
) -> DeliveryResult:
    """Execute send_fn with retry logic according to retry_policy.

    send_fn should be an async callable that:
      - Returns an int (message_id) on success.
      - Raises DeliveryError with http_status on failure.

    For 429 responses, respects the retry_after field instead of
    exponential backoff.
    """
    policy = retry_policy or RetryPolicy()
    attempts: list[DeliveryAttempt] = []
    start_time = time.monotonic()

    for attempt_num in range(1, policy.max_retries + 2):  # +2: first try + retries
        try:
            message_id = await send_fn()
            attempts.append(
                DeliveryAttempt(
                    attempt_number=attempt_num,
                    success=True,
                )
            )
            elapsed = (time.monotonic() - start_time) * 1000
            return DeliveryResult(
                success=True,
                message_id=message_id,
                attempts=attempts,
                total_duration_ms=elapsed,
                trace_id=trace_id,
            )
        except DeliveryError as exc:
            retry_after = exc.retry_after
            attempts.append(
                DeliveryAttempt(
                    attempt_number=attempt_num,
                    success=False,
                    error=str(exc),
                    http_status=exc.http_status,
                    retry_after_seconds=retry_after,
                )
            )

            # Non-retryable error — fail immediately
            if exc.http_status not in policy.retryable_errors:
                logger.warning(
                    "Non-retryable delivery error (status=%d): %s [trace=%s]",
                    exc.http_status,
                    exc,
                    trace_id,
                )
                elapsed = (time.monotonic() - start_time) * 1000
                return DeliveryResult(
                    success=False,
                    attempts=attempts,
                    total_duration_ms=elapsed,
                    trace_id=trace_id,
                )

            # All retries exhausted
            if attempt_num > policy.max_retries:
                logger.error(
                    "All %d retries exhausted for delivery [trace=%s]",
                    policy.max_retries,
                    trace_id,
                )
                elapsed = (time.monotonic() - start_time) * 1000
                return DeliveryResult(
                    success=False,
                    attempts=attempts,
                    total_duration_ms=elapsed,
                    trace_id=trace_id,
                )

            # Calculate delay
            if exc.http_status == 429 and retry_after > 0:
                delay = min(retry_after, policy.max_delay_seconds)
            else:
                delay = min(
                    policy.base_delay_seconds * (2 ** (attempt_num - 1)),
                    policy.max_delay_seconds,
                )

            logger.warning(
                "Delivery attempt %d failed (status=%d), retrying in %.1fs [trace=%s]",
                attempt_num,
                exc.http_status,
                delay,
                trace_id,
            )
            await asyncio.sleep(delay)

    # Should not reach here, but safety net
    elapsed = (time.monotonic() - start_time) * 1000
    return DeliveryResult(
        success=False,
        attempts=attempts,
        total_duration_ms=elapsed,
        trace_id=trace_id,
    )
