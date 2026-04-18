"""Timer message update policy.

Telegram rate-limits message edits (roughly 20 edits/minute per message).
The UpdatePolicy decides whether the control message should be re-edited on
a given tick, balancing freshness against rate-limit risk.

Default policy: edit every 15 seconds, plus always on state changes
(lock, pause, early-close, expiry).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from server.timer.controller import TimerRecord, TimerState


# Seconds between routine timer-countdown edits
DEFAULT_UPDATE_INTERVAL_SECONDS = 15


@dataclass
class UpdateDecision:
    """Whether to edit the control message and why."""

    should_update: bool
    reason: str = ""


class UpdatePolicy:
    """Decides when the turn-control message should be edited."""

    def __init__(self, interval_seconds: int = DEFAULT_UPDATE_INTERVAL_SECONDS):
        self._interval = interval_seconds

    def should_update(
        self,
        timer: TimerRecord,
        last_update_at: datetime | None,
        now: datetime,
        state_changed: bool = False,
    ) -> UpdateDecision:
        """Return an UpdateDecision for the current tick.

        Args:
            timer:           Current TimerRecord.
            last_update_at:  When the message was last edited (None = never).
            now:             Current time.
            state_changed:   True if the timer state changed this tick
                             (expiry, early-close, pause, stop).
        """
        # Always update on state transitions
        if state_changed:
            return UpdateDecision(should_update=True, reason="state_changed")

        # Always update if message was never sent
        if last_update_at is None:
            return UpdateDecision(should_update=True, reason="first_update")

        # Don't update terminal timers unless state just changed (handled above)
        if timer.state in {
            TimerState.expired,
            TimerState.early_closed,
            TimerState.stopped,
        }:
            return UpdateDecision(should_update=False, reason="terminal_no_change")

        # Interval-based update
        elapsed = (now - last_update_at).total_seconds()
        if elapsed >= self._interval:
            return UpdateDecision(
                should_update=True,
                reason=f"interval ({elapsed:.0f}s >= {self._interval}s)",
            )

        return UpdateDecision(should_update=False, reason="too_soon")
