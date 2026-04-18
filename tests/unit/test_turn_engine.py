"""Unit tests for server.engine.turn_engine.

Tests cover:
  - TurnWindow lifecycle: open → all_ready → locked → resolving → committed → aborted
  - One authoritative committed action per player per turn
  - Action validation and rejection flow
  - Late-submission rejection after turn lock
  - All-ready early-close behavior
  - Timeout fallback behavior
  - Append-only turn log production
  - Deterministic turn commit ordering
  - Turn replay support from committed records
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from server.domain.enums import (
    ActionState,
    ActionType,
    ReadyState,
    TurnWindowState,
    ValidationStatus,
)
from server.engine.turn_engine import (
    InvalidTransitionError,
    TurnEngine,
    _assert_transition,
    _label_to_action_type,
)
from tests.fixtures.builders import (
    make_committed_action,
    make_turn_log_entry,
    make_turn_window,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uid() -> str:
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _window(state: TurnWindowState = TurnWindowState.open, **kwargs):
    return make_turn_window(state=state, **kwargs)


def _action(player_id: str | None = None, **kwargs):
    kwargs.setdefault("state", ActionState.submitted)
    return make_committed_action(
        player_id=player_id or _uid(),
        **kwargs,
    )


ENGINE = TurnEngine()


# ---------------------------------------------------------------------------
# _assert_transition helper
# ---------------------------------------------------------------------------


class TestAssertTransition:
    def test_valid_open_to_locked(self):
        w = _window(state=TurnWindowState.open)
        _assert_transition(w, TurnWindowState.locked)  # no raise

    def test_valid_locked_to_resolving(self):
        w = _window(state=TurnWindowState.locked)
        _assert_transition(w, TurnWindowState.resolving)

    def test_invalid_open_to_committed(self):
        w = _window(state=TurnWindowState.open)
        with pytest.raises(InvalidTransitionError):
            _assert_transition(w, TurnWindowState.committed)

    def test_committed_is_terminal(self):
        w = _window(state=TurnWindowState.committed)
        with pytest.raises(InvalidTransitionError):
            _assert_transition(w, TurnWindowState.aborted)

    def test_aborted_is_terminal(self):
        w = _window(state=TurnWindowState.aborted)
        with pytest.raises(InvalidTransitionError):
            _assert_transition(w, TurnWindowState.open)


# ---------------------------------------------------------------------------
# check_all_ready
# ---------------------------------------------------------------------------


class TestCheckAllReady:
    def test_transitions_when_all_ready(self):
        p1, p2 = _uid(), _uid()
        w = _window(state=TurnWindowState.open)
        a1 = _action(
            player_id=p1, ready_state=ReadyState.ready, state=ActionState.submitted
        )
        a2 = _action(
            player_id=p2, ready_state=ReadyState.passed, state=ActionState.submitted
        )
        result = ENGINE.check_all_ready(w, [a1, a2], [p1, p2])
        assert result.state == TurnWindowState.all_ready

    def test_no_transition_when_some_not_ready(self):
        p1, p2 = _uid(), _uid()
        w = _window(state=TurnWindowState.open)
        a1 = _action(
            player_id=p1, ready_state=ReadyState.ready, state=ActionState.submitted
        )
        result = ENGINE.check_all_ready(w, [a1], [p1, p2])
        assert result.state == TurnWindowState.open

    def test_no_transition_when_action_draft(self):
        p1 = _uid()
        w = _window(state=TurnWindowState.open)
        a1 = _action(
            player_id=p1, ready_state=ReadyState.ready, state=ActionState.draft
        )
        result = ENGINE.check_all_ready(w, [a1], [p1])
        assert result.state == TurnWindowState.open

    def test_no_op_when_window_not_open(self):
        p1 = _uid()
        w = _window(state=TurnWindowState.locked)
        a1 = _action(
            player_id=p1, ready_state=ReadyState.ready, state=ActionState.submitted
        )
        result = ENGINE.check_all_ready(w, [a1], [p1])
        assert result.state == TurnWindowState.locked

    def test_no_op_when_no_expected_players(self):
        w = _window(state=TurnWindowState.open)
        result = ENGINE.check_all_ready(w, [], [])
        assert result.state == TurnWindowState.open


# ---------------------------------------------------------------------------
# lock_window
# ---------------------------------------------------------------------------


class TestLockWindow:
    def test_lock_from_open(self):
        w = _window(state=TurnWindowState.open)
        result = ENGINE.lock_window(w)
        assert result.locked is True
        assert result.window.state == TurnWindowState.locked
        assert result.window.locked_at is not None

    def test_lock_from_all_ready(self):
        w = _window(state=TurnWindowState.all_ready)
        result = ENGINE.lock_window(w)
        assert result.locked is True
        assert result.window.state == TurnWindowState.locked

    def test_cannot_lock_from_locked(self):
        w = _window(state=TurnWindowState.locked)
        result = ENGINE.lock_window(w)
        assert result.locked is False
        assert result.window.state == TurnWindowState.locked

    def test_cannot_lock_from_committed(self):
        w = _window(state=TurnWindowState.committed)
        result = ENGINE.lock_window(w)
        assert result.locked is False

    def test_cannot_lock_from_aborted(self):
        w = _window(state=TurnWindowState.aborted)
        result = ENGINE.lock_window(w)
        assert result.locked is False


# ---------------------------------------------------------------------------
# resolve_window
# ---------------------------------------------------------------------------


class TestResolveWindow:
    def test_resolve_from_locked(self):
        p1, p2 = _uid(), _uid()
        w = _window(state=TurnWindowState.locked)
        a1 = _action(player_id=p1, turn_window_id=w.turn_window_id)
        a2 = _action(player_id=p2, turn_window_id=w.turn_window_id)
        result = ENGINE.resolve_window(w, [a1, a2], {}, [])
        assert result.resolved is True
        assert result.window.state == TurnWindowState.resolving
        assert result.window.resolved_at is not None
        assert len(result.ordered_actions) == 2

    def test_resolve_requires_locked_state(self):
        w = _window(state=TurnWindowState.open)
        result = ENGINE.resolve_window(w, [], {}, [])
        assert result.resolved is False
        assert result.window.state == TurnWindowState.open

    def test_deterministic_order_by_player_id(self):
        # Use fixed UUIDs so sort order is predictable
        p_a = "aaaaaaaa-0000-0000-0000-000000000001"
        p_b = "bbbbbbbb-0000-0000-0000-000000000002"
        p_c = "cccccccc-0000-0000-0000-000000000003"
        w = _window(state=TurnWindowState.locked)
        # Submit in reverse order
        a_c = _action(player_id=p_c, turn_window_id=w.turn_window_id)
        a_a = _action(player_id=p_a, turn_window_id=w.turn_window_id)
        a_b = _action(player_id=p_b, turn_window_id=w.turn_window_id)
        result = ENGINE.resolve_window(w, [a_c, a_a, a_b], {}, [])
        ordered_ids = [a.player_id for a in result.ordered_actions]
        assert ordered_ids == [p_a, p_b, p_c]

    def test_timeout_fallback_injected_for_missing_players(self):
        p1, p2 = _uid(), _uid()
        w = _window(state=TurnWindowState.locked, timeout_policy="hold")
        a1 = _action(player_id=p1, turn_window_id=w.turn_window_id)
        # p2 did not submit
        chars = {p2: "defend"}
        result = ENGINE.resolve_window(w, [a1], chars, timeout_player_ids=[p2])
        assert result.resolved is True
        fallbacks = [a for a in result.ordered_actions if a.is_timeout_fallback]
        assert len(fallbacks) == 1
        fb = fallbacks[0]
        assert fb.player_id == p2
        assert fb.declared_action_type == ActionType.defend
        assert fb.state == ActionState.submitted

    def test_no_duplicate_fallback_when_player_has_action(self):
        p1 = _uid()
        w = _window(state=TurnWindowState.locked)
        a1 = _action(player_id=p1, turn_window_id=w.turn_window_id)
        result = ENGINE.resolve_window(w, [a1], {p1: "hold"}, timeout_player_ids=[p1])
        non_fallbacks = [a for a in result.ordered_actions if not a.is_timeout_fallback]
        fallbacks = [a for a in result.ordered_actions if a.is_timeout_fallback]
        assert len(non_fallbacks) == 1
        assert len(fallbacks) == 0

    def test_window_committed_action_ids_updated(self):
        p1, p2 = _uid(), _uid()
        w = _window(state=TurnWindowState.locked)
        a1 = _action(player_id=p1, turn_window_id=w.turn_window_id)
        a2 = _action(player_id=p2, turn_window_id=w.turn_window_id)
        result = ENGINE.resolve_window(w, [a1, a2], {}, [])
        assert set(result.window.committed_action_ids) == {a1.action_id, a2.action_id}


# ---------------------------------------------------------------------------
# commit_window
# ---------------------------------------------------------------------------


class TestCommitWindow:
    def _resolved_window_and_actions(self):
        p1, p2 = _uid(), _uid()
        w = _window(state=TurnWindowState.locked)
        a1 = _action(
            player_id=p1, turn_window_id=w.turn_window_id, state=ActionState.submitted
        )
        a2 = _action(
            player_id=p2, turn_window_id=w.turn_window_id, state=ActionState.submitted
        )
        resolve = ENGINE.resolve_window(w, [a1, a2], {}, [])
        return resolve.window, resolve.ordered_actions

    def test_commit_from_resolving(self):
        w, actions = self._resolved_window_and_actions()
        result = ENGINE.commit_window(
            w, actions, narration="Heroes advance.", state_snapshot={"scene": "dungeon"}
        )
        assert result.committed is True
        assert result.window.state == TurnWindowState.committed
        assert result.window.committed_at is not None
        assert result.log_entry is not None
        assert result.log_entry.narration == "Heroes advance."
        assert result.log_entry.state_snapshot == {"scene": "dungeon"}
        assert len(result.log_entry.action_ids) == 2

    def test_commit_marks_actions_resolved(self):
        w, actions = self._resolved_window_and_actions()
        ENGINE.commit_window(w, actions)
        for action in actions:
            assert action.state == ActionState.resolved

    def test_commit_requires_resolving_state(self):
        w = _window(state=TurnWindowState.locked)
        result = ENGINE.commit_window(w, [])
        assert result.committed is False

    def test_commit_produces_log_entry_with_correct_metadata(self):
        w, actions = self._resolved_window_and_actions()
        result = ENGINE.commit_window(w, actions)
        le = result.log_entry
        assert le.campaign_id == w.campaign_id
        assert le.scene_id == w.scene_id
        assert le.turn_window_id == w.turn_window_id
        assert le.turn_number == w.turn_number
        assert le.log_entry_id  # non-empty UUID


# ---------------------------------------------------------------------------
# abort_window
# ---------------------------------------------------------------------------


class TestAbortWindow:
    def test_abort_from_open(self):
        w = _window(state=TurnWindowState.open)
        result = ENGINE.abort_window(w, reason="GM cancelled")
        assert result.aborted is True
        assert result.window.state == TurnWindowState.aborted
        assert result.reason == "GM cancelled"

    def test_abort_from_locked(self):
        w = _window(state=TurnWindowState.locked)
        result = ENGINE.abort_window(w)
        assert result.aborted is True
        assert result.window.state == TurnWindowState.aborted

    def test_abort_from_resolving(self):
        w = _window(state=TurnWindowState.resolving)
        result = ENGINE.abort_window(w)
        assert result.aborted is True

    def test_cannot_abort_committed(self):
        w = _window(state=TurnWindowState.committed)
        result = ENGINE.abort_window(w)
        assert result.aborted is False
        assert result.window.state == TurnWindowState.committed

    def test_cannot_abort_already_aborted(self):
        w = _window(state=TurnWindowState.aborted)
        result = ENGINE.abort_window(w)
        assert result.aborted is False


# ---------------------------------------------------------------------------
# submit_action
# ---------------------------------------------------------------------------


class TestSubmitAction:
    def test_accept_in_open_window(self):
        p1 = _uid()
        w = _window(state=TurnWindowState.open)
        a = make_committed_action(
            player_id=p1, turn_window_id=w.turn_window_id, state=ActionState.draft
        )
        result = ENGINE.submit_action(w, a, existing_actions=[])
        assert result.accepted is True
        assert result.action.state == ActionState.submitted

    def test_accept_in_all_ready_window(self):
        p1 = _uid()
        w = _window(state=TurnWindowState.all_ready)
        a = make_committed_action(
            player_id=p1, turn_window_id=w.turn_window_id, state=ActionState.draft
        )
        result = ENGINE.submit_action(w, a, existing_actions=[])
        assert result.accepted is True

    def test_reject_late_submission_after_lock(self):
        p1 = _uid()
        w = _window(state=TurnWindowState.locked)
        a = make_committed_action(
            player_id=p1, turn_window_id=w.turn_window_id, state=ActionState.draft
        )
        result = ENGINE.submit_action(w, a, existing_actions=[])
        assert result.accepted is False
        assert result.action.state == ActionState.rejected
        assert "closed" in result.rejection_reason.lower()

    def test_reject_late_submission_after_resolving(self):
        p1 = _uid()
        w = _window(state=TurnWindowState.resolving)
        a = make_committed_action(
            player_id=p1, turn_window_id=w.turn_window_id, state=ActionState.draft
        )
        result = ENGINE.submit_action(w, a, existing_actions=[])
        assert result.accepted is False

    def test_reject_duplicate_submitted_action(self):
        p1 = _uid()
        w = _window(state=TurnWindowState.open)
        existing = _action(
            player_id=p1, turn_window_id=w.turn_window_id, state=ActionState.submitted
        )
        new_action = make_committed_action(
            player_id=p1, turn_window_id=w.turn_window_id, state=ActionState.draft
        )
        result = ENGINE.submit_action(w, new_action, existing_actions=[existing])
        assert result.accepted is False
        assert result.action.state == ActionState.rejected

    def test_reject_duplicate_validated_action(self):
        p1 = _uid()
        w = _window(state=TurnWindowState.open)
        existing = _action(
            player_id=p1, turn_window_id=w.turn_window_id, state=ActionState.validated
        )
        new_action = make_committed_action(
            player_id=p1, turn_window_id=w.turn_window_id, state=ActionState.draft
        )
        result = ENGINE.submit_action(w, new_action, existing_actions=[existing])
        assert result.accepted is False

    def test_allow_second_submission_if_first_was_rejected(self):
        p1 = _uid()
        w = _window(state=TurnWindowState.open)
        existing = _action(
            player_id=p1, turn_window_id=w.turn_window_id, state=ActionState.rejected
        )
        new_action = make_committed_action(
            player_id=p1, turn_window_id=w.turn_window_id, state=ActionState.draft
        )
        result = ENGINE.submit_action(w, new_action, existing_actions=[existing])
        assert result.accepted is True

    def test_different_players_can_each_submit(self):
        p1, p2 = _uid(), _uid()
        w = _window(state=TurnWindowState.open)
        a1 = _action(
            player_id=p1, turn_window_id=w.turn_window_id, state=ActionState.submitted
        )
        new_action = make_committed_action(
            player_id=p2, turn_window_id=w.turn_window_id, state=ActionState.draft
        )
        result = ENGINE.submit_action(w, new_action, existing_actions=[a1])
        assert result.accepted is True

    def test_submit_sets_ready_state(self):
        p1 = _uid()
        w = _window(state=TurnWindowState.open)
        a = make_committed_action(
            player_id=p1,
            turn_window_id=w.turn_window_id,
            state=ActionState.draft,
            ready_state=ReadyState.not_ready,
        )
        result = ENGINE.submit_action(w, a, existing_actions=[])
        assert result.action.ready_state == ReadyState.ready


# ---------------------------------------------------------------------------
# validate_action
# ---------------------------------------------------------------------------


class TestValidateAction:
    def test_validate_accepted_action_type(self):
        a = _action(state=ActionState.submitted)
        a.declared_action_type = ActionType.move
        result = ENGINE.validate_action(
            a, allowed_action_types=[ActionType.move, ActionType.inspect]
        )
        assert result.state == ActionState.validated
        assert result.validation_status == ValidationStatus.valid

    def test_reject_disallowed_action_type(self):
        a = _action(state=ActionState.submitted)
        a.declared_action_type = ActionType.attack
        result = ENGINE.validate_action(a, allowed_action_types=[ActionType.move])
        assert result.state == ActionState.rejected
        assert result.validation_status == ValidationStatus.invalid
        assert "not allowed" in result.rejection_reason

    def test_no_op_on_non_submitted_action(self):
        a = _action(state=ActionState.draft)
        result = ENGINE.validate_action(a)
        assert result.state == ActionState.draft  # unchanged

    def test_allow_all_when_no_filter(self):
        a = _action(state=ActionState.submitted)
        a.declared_action_type = ActionType.attack
        result = ENGINE.validate_action(a, allowed_action_types=None)
        assert result.state == ActionState.validated


# ---------------------------------------------------------------------------
# reject_action
# ---------------------------------------------------------------------------


class TestRejectAction:
    def test_reject_sets_state_and_reason(self):
        a = _action(state=ActionState.submitted)
        result = ENGINE.reject_action(a, reason="Action conflicts with scene rules.")
        assert result.state == ActionState.rejected
        assert result.validation_status == ValidationStatus.invalid
        assert result.rejection_reason == "Action conflicts with scene rules."


# ---------------------------------------------------------------------------
# replay_turn
# ---------------------------------------------------------------------------


class TestReplayTurn:
    def test_replay_returns_actions_in_deterministic_order(self):
        p_a = "aaaaaaaa-0000-0000-0000-000000000001"
        p_b = "bbbbbbbb-0000-0000-0000-000000000002"
        a1 = _action(player_id=p_b, state=ActionState.resolved)
        a2 = _action(player_id=p_a, state=ActionState.resolved)
        log = make_turn_log_entry(
            action_ids=[a1.action_id, a2.action_id],
        )
        replayed = ENGINE.replay_turn(log, [a1, a2])
        assert [a.player_id for a in replayed] == [p_a, p_b]

    def test_replay_ignores_missing_action_ids(self):
        p1 = _uid()
        a1 = _action(player_id=p1, state=ActionState.resolved)
        missing_id = _uid()
        log = make_turn_log_entry(action_ids=[a1.action_id, missing_id])
        replayed = ENGINE.replay_turn(log, [a1])
        assert len(replayed) == 1
        assert replayed[0].action_id == a1.action_id

    def test_replay_does_not_mutate_actions(self):
        p1 = _uid()
        a1 = _action(player_id=p1, state=ActionState.resolved)
        log = make_turn_log_entry(action_ids=[a1.action_id])
        ENGINE.replay_turn(log, [a1])
        assert a1.state == ActionState.resolved


# ---------------------------------------------------------------------------
# Full lifecycle integration test
# ---------------------------------------------------------------------------


class TestFullLifecycle:
    def test_open_to_committed(self):
        """Walk a TurnWindow all the way from open → committed."""
        p1, p2 = _uid(), _uid()
        tw_id = _uid()
        campaign_id = _uid()
        scene_id = _uid()

        # 1. Open window
        w = make_turn_window(
            turn_window_id=tw_id,
            campaign_id=campaign_id,
            scene_id=scene_id,
            state=TurnWindowState.open,
            turn_number=3,
        )
        assert w.state == TurnWindowState.open

        # 2. Players submit actions
        a1 = make_committed_action(
            player_id=p1,
            turn_window_id=tw_id,
            state=ActionState.draft,
            declared_action_type=ActionType.move,
        )
        a2 = make_committed_action(
            player_id=p2,
            turn_window_id=tw_id,
            state=ActionState.draft,
            declared_action_type=ActionType.inspect,
        )
        r1 = ENGINE.submit_action(w, a1, existing_actions=[])
        assert r1.accepted
        r2 = ENGINE.submit_action(w, a2, existing_actions=[r1.action])
        assert r2.accepted

        # 3. Check all-ready (p1 and p2 both ready)
        r1.action.ready_state = ReadyState.ready
        r2.action.ready_state = ReadyState.ready
        w = ENGINE.check_all_ready(w, [r1.action, r2.action], [p1, p2])
        assert w.state == TurnWindowState.all_ready

        # 4. Lock window (early close)
        lock_result = ENGINE.lock_window(w)
        assert lock_result.locked
        w = lock_result.window
        assert w.state == TurnWindowState.locked

        # 5. Validate actions
        r1.action = ENGINE.validate_action(r1.action)
        r2.action = ENGINE.validate_action(r2.action)

        # 6. Resolve
        resolve_result = ENGINE.resolve_window(w, [r1.action, r2.action], {}, [])
        assert resolve_result.resolved
        w = resolve_result.window
        assert w.state == TurnWindowState.resolving

        # 7. Commit
        commit_result = ENGINE.commit_window(
            w,
            resolve_result.ordered_actions,
            narration="The heroes explore the chamber.",
            state_snapshot={"turn": 3},
        )
        assert commit_result.committed
        w = commit_result.window
        assert w.state == TurnWindowState.committed

        # 8. Log entry is well-formed
        le = commit_result.log_entry
        assert le.turn_number == 3
        assert le.narration == "The heroes explore the chamber."
        assert len(le.action_ids) == 2

        # 9. Replay produces same deterministic order
        replayed = ENGINE.replay_turn(le, resolve_result.ordered_actions)
        assert [a.player_id for a in replayed] == sorted([p1, p2])

    def test_timeout_fallback_in_full_lifecycle(self):
        """p2 does not submit; timeout fallback should appear in commit."""
        p1, p2 = _uid(), _uid()
        tw_id = _uid()

        w = make_turn_window(
            turn_window_id=tw_id,
            state=TurnWindowState.open,
            timeout_policy="hold",
        )
        a1 = make_committed_action(
            player_id=p1,
            turn_window_id=tw_id,
            state=ActionState.draft,
        )
        r1 = ENGINE.submit_action(w, a1, existing_actions=[])
        assert r1.accepted

        # Lock (timer expired)
        lock_result = ENGINE.lock_window(w)
        assert lock_result.locked

        # Resolve with p2 timed out, using "defend" fallback
        resolve_result = ENGINE.resolve_window(
            lock_result.window,
            [r1.action],
            characters_by_player={p2: "defend"},
            timeout_player_ids=[p2],
        )
        assert resolve_result.resolved
        assert len(resolve_result.ordered_actions) == 2
        fallback = next(a for a in resolve_result.ordered_actions if a.player_id == p2)
        assert fallback.is_timeout_fallback is True
        assert fallback.declared_action_type == ActionType.defend

        # Commit
        commit_result = ENGINE.commit_window(
            resolve_result.window,
            resolve_result.ordered_actions,
        )
        assert commit_result.committed
        assert len(commit_result.log_entry.action_ids) == 2


# ---------------------------------------------------------------------------
# _label_to_action_type helper
# ---------------------------------------------------------------------------


class TestLabelToActionType:
    def test_hold(self):
        assert _label_to_action_type("hold") == ActionType.hold

    def test_defend(self):
        assert _label_to_action_type("defend") == ActionType.defend

    def test_pass(self):
        assert _label_to_action_type("pass") == ActionType.pass_turn

    def test_unknown_falls_back_to_hold(self):
        assert _label_to_action_type("gibberish") == ActionType.hold

    def test_case_insensitive(self):
        assert _label_to_action_type("DEFEND") == ActionType.defend
