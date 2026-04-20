"""Timer-to-TurnEngine integration helpers.

On each scheduler tick the bot calls process_tick().  This function:
  1. Checks the timer for expiry.
  2. If expired: locks the TurnWindow and applies timeout fallbacks via TurnEngine.
  3. Returns a TickResult describing what happened.

This is pure domain logic — no async, no I/O.  The caller is responsible
for persisting all returned entities and triggering Telegram sends.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from server.domain.entities import CommittedAction, TurnWindow
from server.engine.turn_engine import TurnEngine, ResolveResult
from server.timer.controller import TimerController, TimerRecord


@dataclass
class TickResult:
    """Describes what process_tick() did."""

    timer_expired: bool = False
    early_closed: bool = False
    window_locked: bool = False
    resolve_result: ResolveResult | None = None
    # Updated entities to persist (timer, window, new fallback actions)
    timer: TimerRecord | None = None
    window: TurnWindow | None = None
    new_fallback_actions: list[CommittedAction] = field(default_factory=list)


def process_tick(
    timer: TimerRecord,
    window: TurnWindow,
    existing_actions: list[CommittedAction],
    expected_player_ids: list[str],
    characters_by_player: dict[str, str],
    now: datetime | None = None,
    *,
    controller: TimerController | None = None,
    engine: TurnEngine | None = None,
) -> TickResult:
    """Evaluate one scheduler tick for a running timer.

    Args:
        timer:                The TimerRecord to check.
        window:               The associated TurnWindow.
        existing_actions:     All CommittedActions already in the window.
        expected_player_ids:  All players expected to act this turn.
        characters_by_player: player_id → timeout_fallback_action label.
        now:                  Override for current time (tests).

    Returns:
        TickResult with timer_expired=True and resolve_result populated
        if the timer expired and the window was locked + resolved.
        Otherwise all flags are False.
    """
    ctrl = controller or TimerController()
    eng = engine or TurnEngine()

    result = TickResult(timer=timer, window=window)

    expiry = ctrl.check_expiry(timer, now=now)
    result.timer = expiry.timer

    if not expiry.has_expired:
        return result

    result.timer_expired = True

    # Determine which players timed out
    submitted_player_ids = {
        a.player_id
        for a in existing_actions
        if a.state.value in {"submitted", "validated"}
    }
    timeout_player_ids = [
        pid for pid in expected_player_ids if pid not in submitted_player_ids
    ]

    # Lock the window
    lock = eng.lock_window(window)
    if not lock.locked:
        return result  # window was already locked by another path
    result.window_locked = True
    result.window = lock.window

    # Resolve with timeout fallbacks
    resolve = eng.resolve_window(
        lock.window,
        existing_actions,
        characters_by_player,
        timeout_player_ids=timeout_player_ids,
    )
    result.resolve_result = resolve

    # Collect newly synthesised fallback actions for the caller to persist
    if resolve.resolved:
        original_ids = {a.action_id for a in existing_actions}
        result.new_fallback_actions = [
            a for a in resolve.ordered_actions if a.action_id not in original_ids
        ]

    return result


def process_early_close(
    timer: TimerRecord,
    window: TurnWindow,
    existing_actions: list[CommittedAction],
    characters_by_player: dict[str, str],
    now: datetime | None = None,
    *,
    controller: TimerController | None = None,
    engine: TurnEngine | None = None,
) -> TickResult:
    """Trigger early close (all players ready).

    Closes the timer, locks the window, and resolves with no timeout fallbacks
    (all players already submitted).
    """
    ctrl = controller or TimerController()
    eng = engine or TurnEngine()

    result = TickResult(timer=timer, window=window)

    close = ctrl.trigger_early_close(timer, now=now)
    if not close.success:
        result.timer = timer
        return result

    result.early_closed = True
    result.timer = close.timer

    lock = eng.lock_window(window)
    if not lock.locked:
        return result
    result.window_locked = True
    result.window = lock.window

    resolve = eng.resolve_window(
        lock.window,
        existing_actions,
        characters_by_player,
        timeout_player_ids=[],
    )
    result.resolve_result = resolve
    return result
