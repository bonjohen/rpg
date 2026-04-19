"""Fixtures for reliability, recovery, and observability tests.

Provides builders for stuck turn windows, failed deliveries, model call logs,
and crash recovery scenarios.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from models.fast.instrumentation import ModelCallLog
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
    SceneState,
    TurnWindowState,
    ValidationStatus,
)
from server.reliability.telegram_retry import DeliveryAttempt, DeliveryResult


# ---------------------------------------------------------------------------
# Fixed IDs
# ---------------------------------------------------------------------------

CAMPAIGN_ID = "campaign-rel-001"
SCENE_ID = "scene-rel-001"
SCOPE_ID = "scope-rel-001"
TURN_WINDOW_ID = "tw-rel-001"
PLAYER_A_ID = "player-rel-a"
PLAYER_B_ID = "player-rel-b"
PLAYER_C_ID = "player-rel-c"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_ago(minutes: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(minutes=minutes)


# ---------------------------------------------------------------------------
# Turn window builders
# ---------------------------------------------------------------------------


def make_stuck_turn_window(
    state: str = "resolving",
    age_minutes: int = 45,
    turn_window_id: str = TURN_WINDOW_ID,
) -> TurnWindow:
    """A turn window stuck in the given state for the given duration."""
    tw_state = TurnWindowState(state)
    return TurnWindow(
        turn_window_id=turn_window_id,
        campaign_id=CAMPAIGN_ID,
        scene_id=SCENE_ID,
        public_scope_id=SCOPE_ID,
        opened_at=_utc_ago(age_minutes),
        expires_at=_utc_ago(age_minutes - 5),  # expired before the age
        state=tw_state,
        turn_number=1,
    )


def make_committed_turn_window() -> TurnWindow:
    """A turn window in committed state (terminal, not stuck)."""
    return TurnWindow(
        turn_window_id="tw-committed-001",
        campaign_id=CAMPAIGN_ID,
        scene_id=SCENE_ID,
        public_scope_id=SCOPE_ID,
        opened_at=_utc_ago(60),
        expires_at=_utc_ago(55),
        state=TurnWindowState.committed,
        committed_at=_utc_ago(50),
        turn_number=1,
    )


def make_open_turn_window(age_minutes: int = 5) -> TurnWindow:
    """A turn window in open state (not stuck if young)."""
    return TurnWindow(
        turn_window_id="tw-open-001",
        campaign_id=CAMPAIGN_ID,
        scene_id=SCENE_ID,
        public_scope_id=SCOPE_ID,
        opened_at=_utc_ago(age_minutes),
        expires_at=_utc_ago(age_minutes - 10) if age_minutes > 10 else _utc_now(),
        state=TurnWindowState.open,
        turn_number=1,
    )


# ---------------------------------------------------------------------------
# Scene and player builders
# ---------------------------------------------------------------------------


def make_scene() -> Scene:
    """A scene with three players."""
    return Scene(
        scene_id=SCENE_ID,
        campaign_id=CAMPAIGN_ID,
        name="Test Scene",
        description="A test scene for reliability.",
        created_at=_utc_ago(120),
        state=SceneState.awaiting_actions,
        player_ids=[PLAYER_A_ID, PLAYER_B_ID, PLAYER_C_ID],
    )


def make_players() -> list[Player]:
    """Three test players."""
    return [
        Player(
            player_id=PLAYER_A_ID,
            campaign_id=CAMPAIGN_ID,
            telegram_user_id=100001,
            telegram_username="alice",
            display_name="Alice",
            joined_at=_utc_ago(1000),
            has_dm_open=True,
        ),
        Player(
            player_id=PLAYER_B_ID,
            campaign_id=CAMPAIGN_ID,
            telegram_user_id=100002,
            telegram_username="bob",
            display_name="Bob",
            joined_at=_utc_ago(1000),
            has_dm_open=True,
        ),
        Player(
            player_id=PLAYER_C_ID,
            campaign_id=CAMPAIGN_ID,
            telegram_user_id=100003,
            telegram_username="carol",
            display_name="Carol",
            joined_at=_utc_ago(1000),
            has_dm_open=False,
        ),
    ]


# ---------------------------------------------------------------------------
# Committed action builders
# ---------------------------------------------------------------------------


def make_committed_actions(
    player_ids: list[str] | None = None,
) -> list[CommittedAction]:
    """Actions for the given player IDs (default: A and B, not C)."""
    pids = player_ids or [PLAYER_A_ID, PLAYER_B_ID]
    actions = []
    for i, pid in enumerate(pids):
        actions.append(
            CommittedAction(
                action_id=f"action-rel-{i}",
                turn_window_id=TURN_WINDOW_ID,
                player_id=pid,
                character_id=f"char-{pid}",
                scope_id=SCOPE_ID,
                declared_action_type=ActionType.attack,
                public_text=f"Player {pid} attacks!",
                ready_state=ReadyState.ready,
                submitted_at=_utc_ago(10),
                state=ActionState.submitted,
                validation_status=ValidationStatus.valid,
            )
        )
    return actions


# ---------------------------------------------------------------------------
# Delivery result builders
# ---------------------------------------------------------------------------


def make_failed_delivery_results(count: int = 3) -> list[DeliveryResult]:
    """Delivery results with various failure modes."""
    results: list[DeliveryResult] = []
    error_modes = [
        (429, "Rate limited", 5.0),
        (500, "Internal server error", 0.0),
        (403, "Bot blocked by user", 0.0),
        (502, "Bad gateway", 0.0),
        (504, "Gateway timeout", 0.0),
    ]
    for i in range(count):
        status, error, retry_after = error_modes[i % len(error_modes)]
        attempts = [
            DeliveryAttempt(
                attempt_number=j + 1,
                success=False,
                error=error,
                http_status=status,
                retry_after_seconds=retry_after,
            )
            for j in range(3)
        ]
        results.append(
            DeliveryResult(
                success=False,
                attempts=attempts,
                total_duration_ms=3000.0 + i * 100,
                trace_id=f"trace-fail-{i}",
            )
        )
    return results


def make_successful_delivery_result() -> DeliveryResult:
    """A successful delivery result."""
    return DeliveryResult(
        success=True,
        message_id=12345,
        attempts=[
            DeliveryAttempt(attempt_number=1, success=True),
        ],
        total_duration_ms=150.0,
        trace_id="trace-ok-001",
    )


# ---------------------------------------------------------------------------
# Model call log builders
# ---------------------------------------------------------------------------


def make_model_call_logs(failures: int = 2, fallbacks: int = 1) -> list[ModelCallLog]:
    """Mix of successful and failed model calls."""
    logs: list[ModelCallLog] = []

    # Successful fast calls
    for i in range(5):
        logs.append(
            ModelCallLog(
                trace_id=f"trace-fast-ok-{i}",
                tier="fast",
                task_type="intent_classification",
                prompt_token_count=200,
                output_token_count=50,
                latency_ms=80.0 + i * 10,
                success=True,
            )
        )

    # Successful main calls
    for i in range(3):
        logs.append(
            ModelCallLog(
                trace_id=f"trace-main-ok-{i}",
                tier="main",
                task_type="scene_narration",
                prompt_token_count=2000,
                output_token_count=500,
                latency_ms=2000.0 + i * 100,
                success=True,
            )
        )

    # Failed calls
    for i in range(failures):
        logs.append(
            ModelCallLog(
                trace_id=f"trace-fail-{i}",
                tier="fast" if i % 2 == 0 else "main",
                task_type="intent_classification" if i % 2 == 0 else "scene_narration",
                prompt_token_count=200,
                output_token_count=0,
                latency_ms=5000.0,
                success=False,
                failure_reason="timeout",
            )
        )

    # Fallback calls
    for i in range(fallbacks):
        logs.append(
            ModelCallLog(
                trace_id=f"trace-fallback-{i}",
                tier="main",
                task_type="npc_dialogue",
                prompt_token_count=1500,
                output_token_count=200,
                latency_ms=30000.0,
                success=True,
                fallback_triggered=True,
            )
        )

    return logs


# ---------------------------------------------------------------------------
# Crash recovery scenario
# ---------------------------------------------------------------------------


def make_crash_recovery_scenario() -> dict:
    """Turn window in 'resolving' state with 2 of 3 actions committed.

    Simulates a crash mid-resolution.
    """
    tw = make_stuck_turn_window(state="resolving", age_minutes=5)
    scene = make_scene()
    players = make_players()
    actions = make_committed_actions([PLAYER_A_ID, PLAYER_B_ID])
    # Player C has not submitted

    return {
        "turn_window": tw,
        "scene": scene,
        "players": players,
        "committed_actions": actions,
        "pending_player_ids": [PLAYER_C_ID],
    }
