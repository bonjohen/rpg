"""Canonical Turn Engine — pure domain logic, no DB calls.

All methods accept and return domain entities. Persistence is the caller's
responsibility. The engine enforces:
  - TurnWindow lifecycle: open → all_ready → locked → resolving → committed → aborted
  - One authoritative committed action per player per turn
  - Action validation and rejection
  - Late-submission rejection after lock
  - All-ready early-close
  - Timeout fallback hooks
  - Deterministic turn commit ordering (stable sort by player_id)
  - Append-only turn log production (returns a TurnLogEntry; caller persists it)
  - Replay support from committed records

No imports from server.storage. Everything here is pure Python on domain types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from server.domain.entities import (
    CommittedAction,
    TurnLogEntry,
    TurnWindow,
)
from server.domain.enums import (
    ActionState,
    ActionType,
    ReadyState,
    TurnWindowState,
    ValidationStatus,
)
from server.domain.helpers import new_id, utc_now


# ---------------------------------------------------------------------------
# Result / Error types
# ---------------------------------------------------------------------------


@dataclass
class SubmitResult:
    """Returned by TurnEngine.submit_action()."""

    accepted: bool
    action: CommittedAction
    # Populated when accepted=False
    rejection_reason: str = ""


@dataclass
class LockResult:
    """Returned by TurnEngine.lock_window()."""

    locked: bool
    window: TurnWindow
    reason: str = ""  # why lock was refused, if locked=False


@dataclass
class ResolveResult:
    """Returned by TurnEngine.resolve_window()."""

    resolved: bool
    window: TurnWindow
    # Actions sorted in deterministic commit order (by player_id)
    ordered_actions: list[CommittedAction] = field(default_factory=list)
    reason: str = ""


@dataclass
class CommitResult:
    """Returned by TurnEngine.commit_window()."""

    committed: bool
    window: TurnWindow
    log_entry: Optional[TurnLogEntry] = None
    reason: str = ""


@dataclass
class AbortResult:
    """Returned by TurnEngine.abort_window()."""

    aborted: bool
    window: TurnWindow
    reason: str = ""


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TurnEngineError(Exception):
    """Base class for turn engine errors."""


class InvalidTransitionError(TurnEngineError):
    """Raised when a state transition is not allowed from the current state."""


class DuplicateActionError(TurnEngineError):
    """Raised when a player already has a committed action for this window."""


class LateSubmissionError(TurnEngineError):
    """Raised when a submission arrives after the window is locked."""


class WindowNotOpenError(TurnEngineError):
    """Raised when an operation requires the window to be in a specific state."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_OPEN_STATES = {TurnWindowState.open, TurnWindowState.all_ready}

_VALID_TRANSITIONS: dict[TurnWindowState, set[TurnWindowState]] = {
    TurnWindowState.open: {
        TurnWindowState.all_ready,
        TurnWindowState.locked,
        TurnWindowState.aborted,
    },
    TurnWindowState.all_ready: {TurnWindowState.locked, TurnWindowState.aborted},
    TurnWindowState.locked: {TurnWindowState.resolving, TurnWindowState.aborted},
    TurnWindowState.resolving: {TurnWindowState.committed, TurnWindowState.aborted},
    TurnWindowState.committed: set(),  # terminal
    TurnWindowState.aborted: set(),  # terminal
}


def _assert_transition(window: TurnWindow, target: TurnWindowState) -> None:
    allowed = _VALID_TRANSITIONS.get(window.state, set())
    if target not in allowed:
        raise InvalidTransitionError(
            f"Cannot transition TurnWindow {window.turn_window_id!r} "
            f"from {window.state.value!r} to {target.value!r}."
        )


# ---------------------------------------------------------------------------
# TurnEngine
# ---------------------------------------------------------------------------


class TurnEngine:
    """Stateless engine that operates on TurnWindow and CommittedAction entities.

    Callers are responsible for:
      - Loading entities from the repository before calling engine methods.
      - Persisting the returned (mutated) entities and new log entries.
      - Providing the current list of committed actions for the window where
        needed (e.g. to check all-ready state).

    The engine never calls any storage layer directly.
    """

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------

    def check_all_ready(
        self,
        window: TurnWindow,
        actions: list[CommittedAction],
        expected_player_ids: list[str],
    ) -> TurnWindow:
        """Transition window open → all_ready if every expected player is ready.

        Returns the (possibly updated) window. If the transition fires, the
        window state is set to all_ready. Caller must persist.

        No-op if the window is not in the ``open`` state.
        """
        if window.state != TurnWindowState.open:
            return window

        if not expected_player_ids:
            return window

        ready_player_ids = {
            a.player_id
            for a in actions
            if a.state in {ActionState.submitted, ActionState.validated}
            and a.ready_state in {ReadyState.ready, ReadyState.passed}
        }
        if ready_player_ids >= set(expected_player_ids):
            window.state = TurnWindowState.all_ready
        return window

    def lock_window(self, window: TurnWindow) -> LockResult:
        """Advance the window from open or all_ready → locked.

        This is called when the timer expires or an early-close is triggered.
        After locking, no new submissions are accepted.
        """
        if window.state not in _OPEN_STATES:
            return LockResult(
                locked=False,
                window=window,
                reason=f"Window is {window.state.value!r}; must be open or all_ready to lock.",
            )
        _assert_transition(window, TurnWindowState.locked)
        window.state = TurnWindowState.locked
        window.locked_at = utc_now()
        return LockResult(locked=True, window=window)

    def resolve_window(
        self,
        window: TurnWindow,
        actions: list[CommittedAction],
        characters_by_player: dict[
            str, str
        ],  # player_id → character.timeout_fallback_action
        timeout_player_ids: list[str] | None = None,
    ) -> ResolveResult:
        """Advance window locked → resolving and apply timeout fallbacks.

        ``timeout_player_ids`` is the list of player_ids who did NOT submit
        before the lock and therefore need a fallback action injected.
        ``characters_by_player`` maps player_id → timeout_fallback_action label
        (e.g. "hold") so the engine can synthesise fallback CommittedActions.

        Returns a ResolveResult with:
          - The updated window (state=resolving, resolved_at set)
          - ``ordered_actions``: all actions (including fallbacks) sorted
            deterministically by player_id (stable sort).

        Caller must persist the window, all original actions, and any new
        fallback actions returned inside ordered_actions.
        """
        if window.state != TurnWindowState.locked:
            return ResolveResult(
                resolved=False,
                window=window,
                reason=f"Window must be locked to resolve; is {window.state.value!r}.",
            )
        _assert_transition(window, TurnWindowState.resolving)

        # Synthesise fallback actions for players who timed out
        timeout_player_ids = timeout_player_ids or []
        fallbacks: list[CommittedAction] = []
        existing_player_ids = {a.player_id for a in actions}

        for player_id in timeout_player_ids:
            if player_id in existing_player_ids:
                continue  # already has an action
            fallback_label = characters_by_player.get(player_id, window.timeout_policy)
            fallback_action_type = _label_to_action_type(fallback_label)
            fallback = CommittedAction(
                action_id=new_id(),
                turn_window_id=window.turn_window_id,
                player_id=player_id,
                character_id="",  # caller may patch after the fact
                scope_id=window.public_scope_id,
                declared_action_type=fallback_action_type,
                public_text=f"[timeout: {fallback_label}]",
                private_ref_text="",
                ready_state=ReadyState.passed,
                submitted_at=utc_now(),
                state=ActionState.submitted,
                validation_status=ValidationStatus.valid,
                is_timeout_fallback=True,
            )
            fallbacks.append(fallback)

        all_actions = list(actions) + fallbacks

        # Deterministic order: stable sort by player_id
        ordered = sorted(all_actions, key=lambda a: a.player_id)

        # Update window committed_action_ids
        window.committed_action_ids = [a.action_id for a in ordered]
        window.state = TurnWindowState.resolving
        window.resolved_at = utc_now()

        return ResolveResult(
            resolved=True,
            window=window,
            ordered_actions=ordered,
        )

    def commit_window(
        self,
        window: TurnWindow,
        ordered_actions: list[CommittedAction],
        narration: str = "",
        state_snapshot: dict | None = None,
    ) -> CommitResult:
        """Advance window resolving → committed and produce a TurnLogEntry.

        Returns a CommitResult with:
          - The updated window (state=committed, committed_at set)
          - A new TurnLogEntry ready to be appended to the turn log.

        Caller must persist both.
        """
        if window.state != TurnWindowState.resolving:
            return CommitResult(
                committed=False,
                window=window,
                reason=f"Window must be resolving to commit; is {window.state.value!r}.",
            )
        _assert_transition(window, TurnWindowState.committed)

        now = utc_now()
        window.state = TurnWindowState.committed
        window.committed_at = now
        window.committed_action_ids = [a.action_id for a in ordered_actions]

        # Mark each action as resolved
        for action in ordered_actions:
            action.state = ActionState.resolved

        log_entry = TurnLogEntry(
            log_entry_id=new_id(),
            campaign_id=window.campaign_id,
            scene_id=window.scene_id,
            turn_window_id=window.turn_window_id,
            turn_number=window.turn_number,
            committed_at=now,
            action_ids=[a.action_id for a in ordered_actions],
            narration=narration,
            state_snapshot=state_snapshot or {},
        )

        return CommitResult(
            committed=True,
            window=window,
            log_entry=log_entry,
        )

    def abort_window(self, window: TurnWindow, reason: str = "") -> AbortResult:
        """Abort the window from any non-terminal state.

        Aborted windows cannot be restarted. A new TurnWindow must be created.
        """
        terminal = {TurnWindowState.committed, TurnWindowState.aborted}
        if window.state in terminal:
            return AbortResult(
                aborted=False,
                window=window,
                reason=f"Window is already in terminal state {window.state.value!r}.",
            )
        window.state = TurnWindowState.aborted
        return AbortResult(aborted=True, window=window, reason=reason)

    # ------------------------------------------------------------------
    # Action submission
    # ------------------------------------------------------------------

    def submit_action(
        self,
        window: TurnWindow,
        action: CommittedAction,
        existing_actions: list[CommittedAction],
    ) -> SubmitResult:
        """Submit a player's action into an open window.

        Enforces:
          - Late-submission rejection (window must be open or all_ready)
          - One committed action per player per window
          - Basic validation

        The caller is responsible for persisting the returned action and
        (if check_all_ready is wanted) calling check_all_ready afterwards.

        Does NOT mutate the window. Call check_all_ready separately if needed.
        """
        # --- Late submission check ---
        if window.state not in _OPEN_STATES:
            action.state = ActionState.rejected
            action.validation_status = ValidationStatus.invalid
            action.rejection_reason = (
                f"Window is {window.state.value!r}; submissions are closed."
            )
            return SubmitResult(
                accepted=False,
                action=action,
                rejection_reason=action.rejection_reason,
            )

        # --- Uniqueness check: one committed action per player per window ---
        for existing in existing_actions:
            if existing.player_id == action.player_id and existing.state not in {
                ActionState.rejected,
                ActionState.draft,
            }:
                action.state = ActionState.rejected
                action.validation_status = ValidationStatus.invalid
                action.rejection_reason = (
                    "Player already has a committed action for this window. "
                    "Revise the existing action instead of submitting a new one."
                )
                return SubmitResult(
                    accepted=False,
                    action=action,
                    rejection_reason=action.rejection_reason,
                )

        # --- Accept ---
        action.state = ActionState.submitted
        action.validation_status = ValidationStatus.pending
        action.submitted_at = action.submitted_at or utc_now()
        if action.ready_state == ReadyState.not_ready:
            action.ready_state = ReadyState.ready

        return SubmitResult(accepted=True, action=action)

    def validate_action(
        self,
        action: CommittedAction,
        allowed_action_types: list[ActionType] | None = None,
    ) -> CommittedAction:
        """Validate a submitted action and update its validation_status.

        ``allowed_action_types`` is the whitelist for the current scene/game
        state. If None, all action types are allowed.

        Returns the (mutated) action. Caller must persist.
        """
        if action.state != ActionState.submitted:
            return action  # only validate submitted actions

        if allowed_action_types is not None:
            if action.declared_action_type not in allowed_action_types:
                action.validation_status = ValidationStatus.invalid
                action.rejection_reason = (
                    f"Action type {action.declared_action_type.value!r} is not "
                    "allowed in the current scene state."
                )
                action.state = ActionState.rejected
                return action

        action.validation_status = ValidationStatus.valid
        action.state = ActionState.validated
        return action

    def reject_action(
        self,
        action: CommittedAction,
        reason: str,
    ) -> CommittedAction:
        """Explicitly reject an action with a reason (referee override).

        Returns the mutated action. Caller must persist.
        """
        action.state = ActionState.rejected
        action.validation_status = ValidationStatus.invalid
        action.rejection_reason = reason
        return action

    # ------------------------------------------------------------------
    # Replay
    # ------------------------------------------------------------------

    def replay_turn(
        self,
        log_entry: TurnLogEntry,
        actions: list[CommittedAction],
    ) -> list[CommittedAction]:
        """Return committed actions in deterministic order for replay.

        ``actions`` should be all CommittedActions whose action_id appears in
        ``log_entry.action_ids``. The engine re-sorts them by player_id for
        strict determinism, matching the order used at commit time.

        The returned list is safe to iterate for re-applying effects; nothing
        is mutated.
        """
        action_map = {a.action_id: a for a in actions}
        # Reconstruct using log_entry.action_ids to respect original set,
        # then sort for determinism.
        committed = [
            action_map[aid] for aid in log_entry.action_ids if aid in action_map
        ]
        return sorted(committed, key=lambda a: a.player_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _label_to_action_type(label: str) -> ActionType:
    """Map a timeout_fallback_action label string to an ActionType enum value.

    Falls back to ActionType.hold for unknown labels.
    """
    mapping = {
        "hold": ActionType.hold,
        "defend": ActionType.defend,
        "pass": ActionType.pass_turn,
        "pass_turn": ActionType.pass_turn,
        "move": ActionType.move,
        "inspect": ActionType.inspect,
        "search": ActionType.search,
    }
    return mapping.get(label.lower(), ActionType.hold)
