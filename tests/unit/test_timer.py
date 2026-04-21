"""Unit tests for server.timer — TimerController, integration helpers,
control message builder, and update policy.

Covers:
  - Timer creation and start
  - Expiry on tick
  - Early close (all-ready)
  - Pause / resume / stop
  - Timeout fallback integration with TurnEngine
  - Late submission (window locked after timer expiry)
  - Control message text and keyboard rendering
  - Update policy interval and state-change triggers
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest

from server.domain.enums import ActionState, ActionType, ReadyState, TurnWindowState
from server.engine.turn_engine import TurnEngine
from server.timer.control_message import (
    ACTION_READY,
    ACTION_SUBMIT,
    ControlMessageBuilder,
    ControlMessageData,
    PlayerReadinessEntry,
)
from server.timer.controller import TimerController, TimerError, TimerRecord, TimerState
from server.timer.integration import process_early_close, process_tick
from server.timer.update_policy import UpdatePolicy
from tests.fixtures.builders import make_committed_action, make_turn_window


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uid() -> str:
    return str(uuid.uuid4())


def _t(offset_seconds: int = 0) -> datetime:
    base = datetime(2026, 4, 19, 0, 0, 0)
    return base + timedelta(seconds=offset_seconds)


def _running_timer(
    ctrl: TimerController, duration: int = 120, start_offset: int = 0
) -> TimerRecord:
    t = ctrl.create_timer(_uid(), "c1", duration)
    return ctrl.start(t, now=_t(start_offset))


# ---------------------------------------------------------------------------
# TimerController — creation and start
# ---------------------------------------------------------------------------


class TestTimerCreation:
    def setup_method(self):
        self.ctrl = TimerController()

    def test_create_timer_state_created(self):
        t = self.ctrl.create_timer("w1", "c1", 60)
        assert t.state == TimerState.created
        assert t.duration_seconds == 60

    def test_create_negative_duration_raises(self):
        with pytest.raises(TimerError):
            self.ctrl.create_timer("w1", "c1", 0)

    def test_start_sets_running(self):
        t = self.ctrl.create_timer("w1", "c1", 60)
        t = self.ctrl.start(t, now=_t())
        assert t.state == TimerState.running
        assert t.expires_at is not None

    def test_start_sets_correct_expiry(self):
        t = self.ctrl.create_timer("w1", "c1", 120)
        now = _t()
        t = self.ctrl.start(t, now=now)
        assert t.expires_at == now + timedelta(seconds=120)


# ---------------------------------------------------------------------------
# TimerController — expiry
# ---------------------------------------------------------------------------


class TestTimerExpiry:
    def setup_method(self):
        self.ctrl = TimerController()

    def test_not_expired_before_deadline(self):
        t = _running_timer(self.ctrl, duration=120)
        result = self.ctrl.check_expiry(t, now=_t(60))
        assert result.has_expired is False
        assert result.seconds_remaining == 60

    def test_expired_at_deadline(self):
        t = _running_timer(self.ctrl, duration=120)
        result = self.ctrl.check_expiry(t, now=_t(120))
        assert result.has_expired is True
        assert result.timer.state == TimerState.expired

    def test_expired_past_deadline(self):
        t = _running_timer(self.ctrl, duration=120)
        result = self.ctrl.check_expiry(t, now=_t(200))
        assert result.has_expired is True
        assert result.seconds_remaining == 0

    def test_check_expiry_on_terminal_timer_is_noop(self):
        t = _running_timer(self.ctrl, duration=120)
        self.ctrl.stop(t)
        result = self.ctrl.check_expiry(t, now=_t(200))
        assert result.has_expired is False

    def test_seconds_remaining_counts_down(self):
        t = _running_timer(self.ctrl, duration=100)
        assert self.ctrl.seconds_remaining(t, now=_t(40)) == 60


# ---------------------------------------------------------------------------
# TimerController — early close
# ---------------------------------------------------------------------------


class TestEarlyClose:
    def setup_method(self):
        self.ctrl = TimerController()

    def test_early_close_from_running(self):
        t = _running_timer(self.ctrl, duration=120)
        result = self.ctrl.trigger_early_close(t, now=_t(30))
        assert result.success is True
        assert result.timer.state == TimerState.early_closed

    def test_early_close_from_created_fails(self):
        t = self.ctrl.create_timer("w1", "c1", 60)
        result = self.ctrl.trigger_early_close(t)
        assert result.success is False

    def test_early_close_from_expired_fails(self):
        t = _running_timer(self.ctrl, duration=10)
        self.ctrl.check_expiry(t, now=_t(20))
        result = self.ctrl.trigger_early_close(t)
        assert result.success is False


# ---------------------------------------------------------------------------
# TimerController — pause / resume / stop
# ---------------------------------------------------------------------------


class TestPauseResumeStop:
    def setup_method(self):
        self.ctrl = TimerController()

    def test_pause_and_resume(self):
        t = _running_timer(self.ctrl, duration=120)
        # Pause after 40 seconds
        r_pause = self.ctrl.pause(t, now=_t(40))
        assert r_pause.success
        assert t.state == TimerState.paused
        assert t.elapsed_before_pause == 40

        # Resume: 80 seconds should remain
        r_resume = self.ctrl.resume(t, now=_t(50))
        assert r_resume.success
        assert t.state == TimerState.running
        remaining = self.ctrl.seconds_remaining(t, now=_t(50))
        assert remaining == 80

    def test_pause_non_running_fails(self):
        t = self.ctrl.create_timer("w1", "c1", 60)
        result = self.ctrl.pause(t)
        assert result.success is False

    def test_resume_non_paused_fails(self):
        t = _running_timer(self.ctrl)
        result = self.ctrl.resume(t)
        assert result.success is False

    def test_stop_from_running(self):
        t = _running_timer(self.ctrl)
        result = self.ctrl.stop(t, reason="admin halt")
        assert result.success
        assert t.state == TimerState.stopped
        assert t.stop_reason == "admin halt"

    def test_stop_from_terminal_fails(self):
        t = _running_timer(self.ctrl, duration=10)
        self.ctrl.check_expiry(t, now=_t(20))
        result = self.ctrl.stop(t)
        assert result.success is False

    def test_seconds_remaining_when_paused(self):
        t = _running_timer(self.ctrl, duration=120)
        self.ctrl.pause(t, now=_t(40))
        assert self.ctrl.seconds_remaining(t) == 80


# ---------------------------------------------------------------------------
# Integration — process_tick (expiry → lock → fallback)
# ---------------------------------------------------------------------------


class TestProcessTick:
    def setup_method(self):
        self.ctrl = TimerController()
        self.engine = TurnEngine()

    def test_tick_before_expiry_does_nothing(self):
        w = make_turn_window(state=TurnWindowState.open)
        t = _running_timer(self.ctrl, duration=120)
        result = process_tick(t, w, [], ["p1"], {}, now=_t(60))
        assert result.timer_expired is False
        assert result.window_locked is False

    def test_tick_at_expiry_locks_and_resolves(self):
        w = make_turn_window(state=TurnWindowState.open)
        t = _running_timer(self.ctrl, duration=120)
        p1 = _uid()
        a1 = make_committed_action(
            player_id=p1,
            turn_window_id=w.turn_window_id,
            state=ActionState.submitted,
        )
        result = process_tick(t, w, [a1], [p1], {}, now=_t(120))
        assert result.timer_expired is True
        assert result.window_locked is True
        assert result.resolve_result is not None
        assert result.resolve_result.resolved is True

    def test_timeout_fallback_injected_for_missing_player(self):
        p1, p2 = _uid(), _uid()
        w = make_turn_window(state=TurnWindowState.open, timeout_policy="hold")
        t = _running_timer(self.ctrl, duration=60)
        a1 = make_committed_action(
            player_id=p1,
            turn_window_id=w.turn_window_id,
            state=ActionState.submitted,
        )
        # p2 did not submit
        result = process_tick(t, w, [a1], [p1, p2], {p2: "defend"}, now=_t(60))
        assert result.timer_expired is True
        assert len(result.new_fallback_actions) == 1
        fb = result.new_fallback_actions[0]
        assert fb.player_id == p2
        assert fb.declared_action_type == ActionType.defend
        assert fb.is_timeout_fallback is True

    def test_late_submission_rejected_after_expiry(self):
        """After tick expires and locks the window, new submissions are rejected."""
        p1 = _uid()
        w = make_turn_window(state=TurnWindowState.open)
        t = _running_timer(self.ctrl, duration=60)
        # Tick expires the timer and locks the window
        tick = process_tick(t, w, [], [p1], {}, now=_t(60))
        assert tick.window_locked is True

        # Now try to submit after lock
        late_action = make_committed_action(
            player_id=p1,
            turn_window_id=w.turn_window_id,
            state=ActionState.draft,
        )
        submit = self.engine.submit_action(
            tick.window, late_action, existing_actions=[]
        )
        assert submit.accepted is False
        assert "closed" in submit.rejection_reason.lower()


# ---------------------------------------------------------------------------
# Integration — process_early_close
# ---------------------------------------------------------------------------


class TestProcessEarlyClose:
    def setup_method(self):
        self.ctrl = TimerController()

    def test_early_close_locks_and_resolves(self):
        p1, p2 = _uid(), _uid()
        w = make_turn_window(state=TurnWindowState.open)
        t = _running_timer(self.ctrl, duration=120)
        a1 = make_committed_action(
            player_id=p1, turn_window_id=w.turn_window_id, state=ActionState.submitted
        )
        a2 = make_committed_action(
            player_id=p2, turn_window_id=w.turn_window_id, state=ActionState.submitted
        )
        result = process_early_close(t, w, [a1, a2], {}, now=_t(45))
        assert result.early_closed is True
        assert result.window_locked is True
        assert result.resolve_result.resolved is True
        assert len(result.new_fallback_actions) == 0


# ---------------------------------------------------------------------------
# ControlMessageBuilder
# ---------------------------------------------------------------------------


class TestControlMessageBuilder:
    def setup_method(self):
        self.builder = ControlMessageBuilder()

    def _data(self, **kwargs) -> ControlMessageData:
        defaults = dict(
            turn_window_id="tw-1",
            turn_number=3,
            seconds_remaining=75,
            players=[
                PlayerReadinessEntry("p1", "Alice", ReadyState.ready),
                PlayerReadinessEntry("p2", "Bob", ReadyState.not_ready),
            ],
        )
        defaults.update(kwargs)
        return ControlMessageData(**defaults)

    def test_text_contains_turn_number(self):
        text = self.builder.build_text(self._data())
        assert "Turn 3" in text

    def test_text_contains_timer(self):
        text = self.builder.build_text(self._data(seconds_remaining=75))
        assert "01:15" in text

    def test_text_shows_locked(self):
        text = self.builder.build_text(self._data(is_locked=True))
        assert "locked" in text.lower()

    def test_text_shows_paused(self):
        text = self.builder.build_text(self._data(is_paused=True))
        assert "paused" in text.lower()

    def test_text_shows_player_names(self):
        text = self.builder.build_text(self._data())
        assert "Alice" in text
        assert "Bob" in text

    def test_keyboard_has_five_actions(self):
        rows = self.builder.build_keyboard("tw-1", is_locked=False)
        buttons = [b for row in rows for b in row]
        actions = {b.callback_data.split(":")[0] for b in buttons}
        assert {ACTION_READY, ACTION_SUBMIT, "pass", "askref", "revise"} == actions

    def test_keyboard_empty_when_locked(self):
        assert self.builder.build_keyboard("tw-1", is_locked=True) == []

    def test_callback_data_format(self):
        rows = self.builder.build_keyboard("tw-abc")
        buttons = [b for row in rows for b in row]
        for btn in buttons:
            action, wid = self.builder.parse_callback_data(btn.callback_data)
            assert wid == "tw-abc"
            assert action in {ACTION_READY, ACTION_SUBMIT, "pass", "askref", "revise"}

    def test_parse_invalid_callback_raises(self):
        with pytest.raises(ValueError):
            self.builder.parse_callback_data("bad-format")


# ---------------------------------------------------------------------------
# UpdatePolicy
# ---------------------------------------------------------------------------


class TestUpdatePolicy:
    def setup_method(self):
        self.ctrl = TimerController()

    def test_first_update_always_triggers(self):
        policy = UpdatePolicy(interval_seconds=15)
        t = _running_timer(self.ctrl)
        d = policy.should_update(t, last_update_at=None, now=_t())
        assert d.should_update is True

    def test_interval_triggers_after_elapsed(self):
        policy = UpdatePolicy(interval_seconds=15)
        t = _running_timer(self.ctrl)
        last = _t(0)
        d = policy.should_update(t, last_update_at=last, now=_t(20))
        assert d.should_update is True

    def test_no_update_before_interval(self):
        policy = UpdatePolicy(interval_seconds=15)
        t = _running_timer(self.ctrl)
        last = _t(0)
        d = policy.should_update(t, last_update_at=last, now=_t(10))
        assert d.should_update is False

    def test_state_change_always_triggers(self):
        policy = UpdatePolicy(interval_seconds=15)
        t = _running_timer(self.ctrl)
        last = _t(0)
        d = policy.should_update(t, last_update_at=last, now=_t(1), state_changed=True)
        assert d.should_update is True

    def test_terminal_state_no_update_without_state_change(self):
        policy = UpdatePolicy(interval_seconds=15)
        t = _running_timer(self.ctrl, duration=10)
        self.ctrl.check_expiry(t, now=_t(20))
        last = _t(0)
        d = policy.should_update(t, last_update_at=last, now=_t(25))
        assert d.should_update is False
