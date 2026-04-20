"""Tests for P2 Phase 2: Timer arithmetic, orchestrator edge cases, diagnostics accuracy."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from server.domain.enums import ActionState, TurnWindowState
from server.observability.diagnostics import DiagnosticsEngine
from server.timer.controller import TimerController


# -------------------------------------------------------------------
# BUG-040: Timer pause uses round() instead of int()
# -------------------------------------------------------------------


class TestBUG040PauseRounding:
    def test_pause_uses_round_not_truncate(self):
        ctrl = TimerController()
        timer = ctrl.create_timer("tw-1", "camp-1", duration_seconds=60)
        start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        timer = ctrl.start(timer, now=start)

        # Pause at 30.7s elapsed → remaining = 29.3s
        pause_time = start + timedelta(seconds=30.7)
        result = ctrl.pause(timer, now=pause_time)
        assert result.success

        # round(29.3) = 29, so elapsed = 60 - 29 = 31
        # int(29.3) would be 29, so elapsed = 60 - 29 = 31 too
        # But with 29.6s remaining: round(29.6)=30, int(29.6)=29
        # Let's test at 30.4s elapsed → remaining=29.6
        timer2 = ctrl.create_timer("tw-2", "camp-1", duration_seconds=60)
        timer2 = ctrl.start(timer2, now=start)
        pause_time2 = start + timedelta(seconds=30.4)
        result2 = ctrl.pause(timer2, now=pause_time2)
        assert result2.success
        # remaining = 29.6, round(29.6)=30, elapsed = 60 - 30 = 30
        # int(29.6)=29 would give elapsed=31 (drift)
        assert result2.timer.elapsed_before_pause == 30


# -------------------------------------------------------------------
# BUG-041: Timer resume with 0 remaining uses max(0, ...) not max(1, ...)
# -------------------------------------------------------------------


class TestBUG041ResumeZeroRemaining:
    def test_resume_with_zero_remaining_expires_immediately(self):
        ctrl = TimerController()
        timer = ctrl.create_timer("tw-1", "camp-1", duration_seconds=60)
        start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        timer = ctrl.start(timer, now=start)

        # Pause exactly at expiry
        pause_time = start + timedelta(seconds=60)
        result = ctrl.pause(timer, now=pause_time)
        assert result.success
        assert result.timer.elapsed_before_pause == 60

        # Resume — remaining = 60 - 60 = 0, so expires_at = now + 0
        resume_time = datetime(2026, 1, 1, 0, 5, 0, tzinfo=timezone.utc)
        result = ctrl.resume(result.timer, now=resume_time)
        assert result.success
        # With max(0, ...), expires_at should equal resume_time (immediate expiry)
        assert result.timer.expires_at == resume_time


# -------------------------------------------------------------------
# BUG-042: ActionState enum in timer integration
# -------------------------------------------------------------------


class TestBUG042ActionStateEnum:
    def test_integration_uses_enum_comparison(self):
        """Verify the import exists and the comparison works with enum values."""
        from server.timer.integration import ActionState as ImportedActionState

        assert ImportedActionState is ActionState
        assert ActionState.submitted in {ActionState.submitted, ActionState.validated}
        assert ActionState.draft not in {ActionState.submitted, ActionState.validated}


# -------------------------------------------------------------------
# BUG-044: Diagnostics filters pending players by submitted actions
# -------------------------------------------------------------------


class TestBUG044DiagnosticsPendingFilter:
    def _make_turn_window(self, tw_id: str, scene_id: str, age_minutes: float = 45):
        from server.domain.entities import TurnWindow

        now = datetime.now(timezone.utc)
        opened = now - timedelta(minutes=age_minutes)
        return TurnWindow(
            turn_window_id=tw_id,
            campaign_id="camp-1",
            scene_id=scene_id,
            public_scope_id="scope-1",
            opened_at=opened,
            expires_at=opened + timedelta(minutes=5),
            state=TurnWindowState.open,
            turn_number=1,
        )

    def _make_scene(self, scene_id: str, player_ids: list[str]):
        from server.domain.entities import Scene
        from server.domain.helpers import utc_now

        return Scene(
            scene_id=scene_id,
            campaign_id="camp-1",
            name="Test Scene",
            description="A test.",
            created_at=utc_now(),
            player_ids=player_ids,
        )

    def _make_action(self, player_id: str, tw_id: str):
        from server.domain.entities import CommittedAction
        from server.domain.enums import ActionType
        from server.domain.helpers import utc_now

        return CommittedAction(
            action_id=f"act-{player_id}",
            player_id=player_id,
            character_id=f"char-{player_id}",
            turn_window_id=tw_id,
            scope_id="scope-1",
            declared_action_type=ActionType.hold,
            state=ActionState.submitted,
            submitted_at=utc_now(),
        )

    def test_pending_excludes_submitted_players(self):
        engine = DiagnosticsEngine()
        tw = self._make_turn_window("tw-1", "scene-1", age_minutes=45)
        scene = self._make_scene("scene-1", ["p1", "p2", "p3"])
        actions = [self._make_action("p1", "tw-1"), self._make_action("p2", "tw-1")]

        stuck = engine._find_stuck_turns([tw], [scene], [], committed_actions=actions)
        assert len(stuck) == 1
        assert stuck[0].pending_players == ["p3"]

    def test_pending_all_when_no_actions(self):
        engine = DiagnosticsEngine()
        tw = self._make_turn_window("tw-1", "scene-1", age_minutes=45)
        scene = self._make_scene("scene-1", ["p1", "p2"])

        stuck = engine._find_stuck_turns([tw], [scene], [])
        assert len(stuck) == 1
        assert stuck[0].pending_players == ["p1", "p2"]


# -------------------------------------------------------------------
# BUG-045: Tighter fast_model_responsive threshold
# -------------------------------------------------------------------


class TestBUG045ModelHealthThreshold:
    def _make_log(self, tier: str, success: bool, fallback: bool = False):
        from models.fast.instrumentation import ModelCallLog

        return ModelCallLog(
            trace_id="t1",
            tier=tier,
            task_type="narration",
            prompt_token_count=100,
            output_token_count=50,
            latency_ms=100.0,
            success=success,
            fallback_triggered=fallback,
        )

    def test_one_success_out_of_ten_is_not_responsive(self):
        """Previously, 1 success out of 10 was 'responsive'. Now requires < 50% failure."""
        engine = DiagnosticsEngine()
        logs = [self._make_log("fast", success=False) for _ in range(9)]
        logs.append(self._make_log("fast", success=True))
        health = engine._compute_model_health(logs)
        # 9/10 = 90% failure rate → not responsive
        assert health.fast_model_responsive is False

    def test_below_50_percent_failure_is_responsive(self):
        engine = DiagnosticsEngine()
        logs = [self._make_log("fast", success=True) for _ in range(6)]
        logs.extend(self._make_log("fast", success=False) for _ in range(4))
        health = engine._compute_model_health(logs)
        # 4/10 = 40% failure rate → responsive
        assert health.fast_model_responsive is True

    def test_exactly_50_percent_failure_is_not_responsive(self):
        engine = DiagnosticsEngine()
        logs = [self._make_log("fast", success=True) for _ in range(5)]
        logs.extend(self._make_log("fast", success=False) for _ in range(5))
        health = engine._compute_model_health(logs)
        # 5/10 = 50% failure rate → not responsive (< 0.5 is strict)
        assert health.fast_model_responsive is False
