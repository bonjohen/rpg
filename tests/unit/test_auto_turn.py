"""Unit tests for auto-turn management (Phase 3).

Tests per chat_loop_test_plan §3.3:
- ensure_turn_open creates turn when none active
- ensure_turn_open returns existing when active
- ensure_turn_open race condition guard (open_turn re-checks inside session)
- auto-resolve on all-ready
- auto-resolve posts narration (turn_resolved flag set)
- /nextturn still works as override
- no fast adapter: auto-open + submit works end-to-end
"""

from __future__ import annotations

import pytest

from server.domain.enums import TurnWindowState
from tests.fixtures.orchestrator_builder import add_test_player, make_test_orchestrator


class TestEnsureTurnOpen:
    def test_creates_turn_when_none_active(self):
        orch = make_test_orchestrator()
        add_test_player(orch)

        tw = orch.ensure_turn_open("scene1")
        assert tw is not None
        assert tw.state == TurnWindowState.open

    def test_returns_existing_when_active(self):
        orch = make_test_orchestrator()
        add_test_player(orch)

        tw1 = orch.ensure_turn_open("scene1")
        tw2 = orch.ensure_turn_open("scene1")
        assert tw1 is not None
        assert tw2 is not None
        assert tw1.turn_window_id == tw2.turn_window_id

    def test_race_condition_guard_in_open_turn(self):
        """open_turn re-checks for existing turn inside its session."""
        orch = make_test_orchestrator()
        add_test_player(orch)

        tw1 = orch.open_turn("scene1")
        # Calling open_turn again should return the existing one (race guard)
        tw2 = orch.open_turn("scene1")
        assert tw1 is not None
        assert tw2 is not None
        assert tw1.turn_window_id == tw2.turn_window_id

    def test_ensure_turn_open_nonexistent_scene_returns_none(self):
        """ensure_turn_open with a scene_id that doesn't exist returns None."""
        orch = make_test_orchestrator()
        add_test_player(orch)

        tw = orch.ensure_turn_open("nonexistent_scene_id")
        assert tw is None

    def test_nextturn_still_works_as_override(self):
        """open_turn explicitly works even when auto-open would do it."""
        orch = make_test_orchestrator()
        add_test_player(orch)

        tw = orch.open_turn("scene1")
        assert tw is not None
        assert tw.state == TurnWindowState.open


class TestAutoResolve:
    @pytest.mark.asyncio
    async def test_auto_resolve_on_all_ready(self):
        """Single player submits -> all_ready -> auto-resolves."""
        orch = make_test_orchestrator()
        pid = add_test_player(orch)

        # With no fast adapter, _handle_as_action is called directly
        result = await orch.handle_player_message(pid, "I search", False)
        assert result.action_submitted is True
        assert result.turn_resolved is True

    @pytest.mark.asyncio
    async def test_auto_resolve_sets_turn_log_entry(self):
        """After auto-resolve, turn_log_entry is populated."""
        orch = make_test_orchestrator()
        pid = add_test_player(orch)

        result = await orch.handle_player_message(pid, "I attack", False)
        assert result.turn_resolved is True
        assert result.turn_log_entry is not None

    @pytest.mark.asyncio
    async def test_auto_open_then_submit_works(self):
        """No active turn, player submits -> turn auto-opens, action submits."""
        orch = make_test_orchestrator()
        pid = add_test_player(orch)

        # No open_turn call — ensure_turn_open in _handle_as_action does it
        result = await orch.handle_player_message(pid, "I look around", False)
        assert result.action_submitted is True
        assert result.handled is True
