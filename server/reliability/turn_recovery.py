"""Crash-safe turn recovery.

Diagnoses and recovers turn windows that were interrupted mid-lifecycle
(e.g., server crash during resolution). All recovery actions are deterministic
and logged for audit.

All stdlib — no external dependencies.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from server.domain.entities import (
    CommittedAction,
    Player,
    Scene,
    TurnWindow,
)
from server.domain.enums import (
    ActionState,
    ActionType,
    ReadyState,
    TurnWindowState,
    ValidationStatus,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class TurnRecoveryState:
    """Diagnosis of a turn window's state at recovery time."""

    turn_window_id: str
    campaign_id: str
    scene_id: str
    state_at_crash: str
    committed_actions: list[str] = field(default_factory=list)
    pending_players: list[str] = field(default_factory=list)
    recovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    recovery_action: str = ""  # "resumed" | "force_resolved" | "redeliver" | "aborted"


@dataclass
class TurnRecoveryResult:
    """Result of a recovery operation."""

    success: bool
    turn_window: TurnWindow
    recovery_action: str = ""
    new_actions_synthesized: int = 0
    narration_redelivered: bool = False
    trace_id: str = ""


# ---------------------------------------------------------------------------
# TurnRecoveryEngine
# ---------------------------------------------------------------------------


class TurnRecoveryEngine:
    """Diagnoses and recovers interrupted turn windows."""

    def diagnose(
        self,
        turn_window: TurnWindow,
        scene: Scene,
        players: list[Player],
        committed_actions: list[CommittedAction] | None = None,
    ) -> TurnRecoveryState:
        """Inspect a turn window and determine recovery action.

        Returns a TurnRecoveryState describing the situation and recommended action.
        """
        actions = committed_actions or []
        committed_ids = [a.action_id for a in actions]

        # Determine which players haven't submitted
        submitted_player_ids = {a.player_id for a in actions}
        all_player_ids = set(scene.player_ids)
        pending = list(all_player_ids - submitted_player_ids)

        state_str = turn_window.state.value

        if turn_window.state in {TurnWindowState.open, TurnWindowState.all_ready}:
            recovery_action = "resumed"
        elif turn_window.state in {TurnWindowState.locked, TurnWindowState.resolving}:
            recovery_action = "force_resolved"
        elif turn_window.state == TurnWindowState.committed:
            recovery_action = "redeliver"
        elif turn_window.state == TurnWindowState.aborted:
            recovery_action = "none"
        else:
            recovery_action = "aborted"

        return TurnRecoveryState(
            turn_window_id=turn_window.turn_window_id,
            campaign_id=turn_window.campaign_id,
            scene_id=turn_window.scene_id,
            state_at_crash=state_str,
            committed_actions=committed_ids,
            pending_players=pending,
            recovery_action=recovery_action,
        )

    def recover(
        self,
        turn_window: TurnWindow,
        scene: Scene,
        players: list[Player],
        committed_actions: list[CommittedAction] | None = None,
        trace_id: str = "",
    ) -> TurnRecoveryResult:
        """Execute the recovery action determined by diagnose().

        Modifies the turn_window in place.
        """
        diagnosis = self.diagnose(turn_window, scene, players, committed_actions)
        actions = committed_actions or []

        if diagnosis.recovery_action == "resumed":
            return self._recover_open(turn_window, scene, players, actions, trace_id)
        elif diagnosis.recovery_action == "force_resolved":
            return self._recover_resolving(turn_window, actions, trace_id)
        elif diagnosis.recovery_action == "redeliver":
            return self._recover_committed(turn_window, trace_id)
        elif diagnosis.recovery_action == "none":
            return TurnRecoveryResult(
                success=True,
                turn_window=turn_window,
                recovery_action="none",
                trace_id=trace_id,
            )
        else:
            # Unknown state — abort
            turn_window.state = TurnWindowState.aborted
            return TurnRecoveryResult(
                success=True,
                turn_window=turn_window,
                recovery_action="aborted",
                trace_id=trace_id,
            )

    def _recover_open(
        self,
        turn_window: TurnWindow,
        scene: Scene,
        players: list[Player],
        actions: list[CommittedAction],
        trace_id: str,
    ) -> TurnRecoveryResult:
        """Recover a turn that was open/all_ready at crash.

        Synthesize fallback actions for pending players, lock, resolve.
        """
        submitted_pids = {a.player_id for a in actions}
        pending_pids = [pid for pid in scene.player_ids if pid not in submitted_pids]
        synthesized = 0

        for pid in pending_pids:
            fallback = CommittedAction(
                action_id=str(uuid.uuid4()),
                turn_window_id=turn_window.turn_window_id,
                player_id=pid,
                character_id="",
                scope_id=turn_window.public_scope_id,
                declared_action_type=ActionType.hold,
                public_text="[recovery: hold]",
                ready_state=ReadyState.passed,
                submitted_at=datetime.now(timezone.utc),
                state=ActionState.submitted,
                validation_status=ValidationStatus.valid,
                is_timeout_fallback=True,
            )
            actions.append(fallback)
            synthesized += 1

        # Lock and move to resolving
        now = datetime.now(timezone.utc)
        turn_window.state = TurnWindowState.resolving
        turn_window.locked_at = now
        turn_window.resolved_at = now
        turn_window.committed_action_ids = [a.action_id for a in actions]

        logger.info(
            "Recovered open turn %s: synthesized %d fallback actions [trace=%s]",
            turn_window.turn_window_id,
            synthesized,
            trace_id,
        )

        return TurnRecoveryResult(
            success=True,
            turn_window=turn_window,
            recovery_action="resumed",
            new_actions_synthesized=synthesized,
            trace_id=trace_id,
        )

    def _recover_resolving(
        self,
        turn_window: TurnWindow,
        actions: list[CommittedAction],
        trace_id: str,
    ) -> TurnRecoveryResult:
        """Recover a turn that was locked/resolving at crash.

        Re-resolve from existing committed actions. Deterministic and idempotent.
        """
        now = datetime.now(timezone.utc)
        turn_window.state = TurnWindowState.resolving
        turn_window.resolved_at = now
        turn_window.committed_action_ids = [a.action_id for a in actions]

        logger.info(
            "Force-resolved turn %s with %d existing actions [trace=%s]",
            turn_window.turn_window_id,
            len(actions),
            trace_id,
        )

        return TurnRecoveryResult(
            success=True,
            turn_window=turn_window,
            recovery_action="force_resolved",
            trace_id=trace_id,
        )

    def _recover_committed(
        self, turn_window: TurnWindow, trace_id: str
    ) -> TurnRecoveryResult:
        """Recover a committed turn where narration may not have been delivered."""
        logger.info(
            "Re-delivering narration for committed turn %s [trace=%s]",
            turn_window.turn_window_id,
            trace_id,
        )
        return TurnRecoveryResult(
            success=True,
            turn_window=turn_window,
            recovery_action="redeliver",
            narration_redelivered=True,
            trace_id=trace_id,
        )

    def find_stuck_turns(
        self,
        all_turn_windows: list[TurnWindow],
        max_age_minutes: int = 30,
    ) -> list[TurnWindow]:
        """Return turn windows stuck in non-terminal states too long.

        A turn is "stuck" if it has been in open, all_ready, locked, or resolving
        state for longer than max_age_minutes.
        """
        now = datetime.now(timezone.utc)
        stuck_states = {
            TurnWindowState.open,
            TurnWindowState.all_ready,
            TurnWindowState.locked,
            TurnWindowState.resolving,
        }
        stuck: list[TurnWindow] = []

        for tw in all_turn_windows:
            if tw.state not in stuck_states:
                continue
            # Use opened_at as the reference time
            opened = tw.opened_at
            # Both now and opened should be naive UTC (via utc_now())
            now_naive = now.replace(tzinfo=None) if now.tzinfo else now
            opened_naive = opened.replace(tzinfo=None) if opened.tzinfo else opened
            age_seconds = (now_naive - opened_naive).total_seconds()
            age_minutes = age_seconds / 60.0
            if age_minutes > max_age_minutes:
                stuck.append(tw)

        return stuck
