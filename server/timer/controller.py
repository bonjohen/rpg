"""Turn Timer Controller — pure domain logic, no async I/O.

Manages the countdown lifecycle for a TurnWindow:

  created → running → expired (normal path)
                    → early_closed (all-ready trigger)
                    → paused → running (resume)
                    → stopped (admin halt)

The controller is stateless: it evaluates state from a TimerRecord entity
and returns results.  Callers persist the TimerRecord and act on results
(e.g. locking the TurnWindow, editing the Telegram control message).

Integration:
  - Timer creation: call create_timer() after TurnEngine opens a window.
  - Expiry check: call check_expiry() on each scheduler tick.
  - Early close: call trigger_early_close() when TurnEngine transitions
    to all_ready and the policy is to close immediately.
  - Pause/stop: call pause() / stop() from admin commands.
  - Resume: call resume() after a pause.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Timer state machine
# ---------------------------------------------------------------------------


class TimerState(str, Enum):
    created = "created"
    running = "running"
    paused = "paused"
    expired = "expired"
    early_closed = "early_closed"
    stopped = "stopped"


_TERMINAL_STATES = {TimerState.expired, TimerState.early_closed, TimerState.stopped}

_VALID_TIMER_TRANSITIONS: dict[TimerState, set[TimerState]] = {
    TimerState.created: {TimerState.running, TimerState.stopped},
    TimerState.running: {
        TimerState.paused,
        TimerState.expired,
        TimerState.early_closed,
        TimerState.stopped,
    },
    TimerState.paused: {
        TimerState.running,
        TimerState.early_closed,
        TimerState.stopped,
    },
    TimerState.expired: set(),
    TimerState.early_closed: set(),
    TimerState.stopped: set(),
}


# ---------------------------------------------------------------------------
# TimerRecord entity (domain object; persisted by the caller)
# ---------------------------------------------------------------------------


@dataclass
class TimerRecord:
    """Persistent timer state for one TurnWindow."""

    timer_id: str
    turn_window_id: str
    campaign_id: str
    duration_seconds: int
    state: TimerState = TimerState.created
    started_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    # Cumulative seconds already elapsed before the current running period
    elapsed_before_pause: int = 0
    closed_at: Optional[datetime] = None
    # Telegram message ID of the public turn-control message
    control_message_id: Optional[int] = None
    # Reason for stop (admin use)
    stop_reason: str = ""


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class TimerResult:
    """Generic result from a timer operation."""

    success: bool
    timer: TimerRecord
    reason: str = ""


@dataclass
class ExpiryCheckResult:
    """Result of check_expiry()."""

    has_expired: bool
    timer: TimerRecord
    # Seconds remaining (0 if expired or terminal)
    seconds_remaining: int = 0


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class TimerError(Exception):
    """Raised when a timer operation is invalid."""


# ---------------------------------------------------------------------------
# TimerController
# ---------------------------------------------------------------------------


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _assert_timer_transition(timer: TimerRecord, target: TimerState) -> None:
    allowed = _VALID_TIMER_TRANSITIONS.get(timer.state, set())
    if target not in allowed:
        raise TimerError(
            f"Cannot transition timer {timer.timer_id!r} "
            f"from {timer.state.value!r} to {target.value!r}."
        )


class TimerController:
    """Stateless controller for TurnWindow timers.

    All methods accept and return TimerRecord objects.
    Callers must persist the returned TimerRecord.
    """

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    def create_timer(
        self,
        turn_window_id: str,
        campaign_id: str,
        duration_seconds: int,
    ) -> TimerRecord:
        """Create a new timer for a TurnWindow (state=created, not yet running).

        Call start() to begin the countdown.
        """
        if duration_seconds <= 0:
            raise TimerError(
                f"duration_seconds must be positive; got {duration_seconds}"
            )
        return TimerRecord(
            timer_id=str(uuid.uuid4()),
            turn_window_id=turn_window_id,
            campaign_id=campaign_id,
            duration_seconds=duration_seconds,
        )

    def start(self, timer: TimerRecord, now: datetime | None = None) -> TimerRecord:
        """Start or restart a created timer.  Sets state=running."""
        _assert_timer_transition(timer, TimerState.running)
        t = now or _now_utc()
        remaining = timer.duration_seconds - timer.elapsed_before_pause
        timer.started_at = timer.started_at or t
        timer.expires_at = t + timedelta(seconds=remaining)
        timer.state = TimerState.running
        return timer

    # ------------------------------------------------------------------
    # Expiry check
    # ------------------------------------------------------------------

    def check_expiry(
        self, timer: TimerRecord, now: datetime | None = None
    ) -> ExpiryCheckResult:
        """Check whether the timer has expired.

        If the timer is running and the current time is past expires_at,
        transitions it to expired.

        Returns ExpiryCheckResult with has_expired=True and the updated timer
        if the timer just expired; otherwise has_expired=False.
        """
        if timer.state in _TERMINAL_STATES:
            return ExpiryCheckResult(
                has_expired=False, timer=timer, seconds_remaining=0
            )

        if timer.state != TimerState.running:
            return ExpiryCheckResult(
                has_expired=False, timer=timer, seconds_remaining=timer.duration_seconds
            )

        t = now or _now_utc()
        if timer.expires_at is None:
            raise ValueError(
                f"Timer {timer.timer_id!r} is running but expires_at is None."
            )
        if t < timer.expires_at:
            delta = (timer.expires_at - t).total_seconds()
            return ExpiryCheckResult(
                has_expired=False,
                timer=timer,
                seconds_remaining=max(0, int(delta)),
            )

        # Timer has expired
        timer.state = TimerState.expired
        timer.closed_at = t
        return ExpiryCheckResult(has_expired=True, timer=timer, seconds_remaining=0)

    # ------------------------------------------------------------------
    # Early close (all-ready)
    # ------------------------------------------------------------------

    def trigger_early_close(
        self, timer: TimerRecord, now: datetime | None = None
    ) -> TimerResult:
        """Close the timer early because all players are ready.

        Only valid when the timer is running or paused.
        """
        if timer.state not in {TimerState.running, TimerState.paused}:
            return TimerResult(
                success=False,
                timer=timer,
                reason=f"Cannot early-close timer in state {timer.state.value!r}.",
            )
        timer.state = TimerState.early_closed
        timer.closed_at = now or _now_utc()
        return TimerResult(success=True, timer=timer)

    # ------------------------------------------------------------------
    # Pause / resume / stop
    # ------------------------------------------------------------------

    def pause(self, timer: TimerRecord, now: datetime | None = None) -> TimerResult:
        """Pause a running timer.  Preserves elapsed time for resume."""
        if timer.state != TimerState.running:
            return TimerResult(
                success=False,
                timer=timer,
                reason=f"Cannot pause timer in state {timer.state.value!r}.",
            )
        t = now or _now_utc()
        # elapsed = total duration - remaining (computed below)
        if timer.expires_at:
            remaining = max(0, (timer.expires_at - t).total_seconds())
            timer.elapsed_before_pause = timer.duration_seconds - int(remaining)
        timer.paused_at = t
        timer.expires_at = None
        timer.state = TimerState.paused
        return TimerResult(success=True, timer=timer)

    def resume(self, timer: TimerRecord, now: datetime | None = None) -> TimerResult:
        """Resume a paused timer from where it left off."""
        if timer.state != TimerState.paused:
            return TimerResult(
                success=False,
                timer=timer,
                reason=f"Cannot resume timer in state {timer.state.value!r}.",
            )
        _assert_timer_transition(timer, TimerState.running)
        t = now or _now_utc()
        remaining = timer.duration_seconds - timer.elapsed_before_pause
        timer.expires_at = t + timedelta(seconds=max(1, remaining))
        timer.paused_at = None
        timer.state = TimerState.running
        return TimerResult(success=True, timer=timer)

    def stop(
        self, timer: TimerRecord, reason: str = "", now: datetime | None = None
    ) -> TimerResult:
        """Admin-stop the timer from any non-terminal state."""
        if timer.state in _TERMINAL_STATES:
            return TimerResult(
                success=False,
                timer=timer,
                reason=f"Timer is already in terminal state {timer.state.value!r}.",
            )
        timer.state = TimerState.stopped
        timer.closed_at = now or _now_utc()
        timer.stop_reason = reason
        return TimerResult(success=True, timer=timer)

    # ------------------------------------------------------------------
    # Seconds remaining helper
    # ------------------------------------------------------------------

    def seconds_remaining(self, timer: TimerRecord, now: datetime | None = None) -> int:
        """Return integer seconds remaining on the timer (0 if terminal)."""
        if timer.state in _TERMINAL_STATES:
            return 0
        if timer.state == TimerState.paused:
            return max(0, timer.duration_seconds - timer.elapsed_before_pause)
        if timer.state == TimerState.running and timer.expires_at:
            t = now or _now_utc()
            return max(0, int((timer.expires_at - t).total_seconds()))
        return timer.duration_seconds
