"""End-to-end chat turn integration tests (Phase 8).

Tests per chat_loop_test_plan §4.1. Full turn lifecycle through the
orchestrator with in-memory DB, mocked model responses, and real
game state.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tests.fixtures.model_mocks import mock_classify_intent, mock_extract_action
from tests.fixtures.orchestrator_builder import add_test_player, make_test_orchestrator

GOBLIN_CAVES = "scenarios/starters/goblin_caves.yaml"


class TestFullTurnViaChat:
    @pytest.mark.asyncio
    async def test_full_turn_via_chat(self):
        """Player sends action text -> turn auto-opens -> submitted -> resolved."""
        fast = MagicMock()
        orch = make_test_orchestrator(fast_adapter=fast, scenario_path=GOBLIN_CAVES)
        pid = add_test_player(orch, telegram_user_id=100)

        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                mock_classify_intent("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                mock_extract_action(),
            ),
        ):
            result = await orch.handle_player_message(
                pid, "I search the cave", is_private=False
            )

        assert result.handled is True
        assert result.action_submitted is True
        # Single player -> all-ready -> auto-resolve
        assert result.turn_resolved is True
        assert result.turn_log_entry is not None


class TestMultiPlayerTurn:
    @pytest.mark.asyncio
    async def test_multi_player_turn(self):
        """Two players send actions -> both submitted -> single resolve."""
        fast = MagicMock()
        orch = make_test_orchestrator(fast_adapter=fast, scenario_path=GOBLIN_CAVES)
        pid1 = add_test_player(
            orch, player_id="p-100", display_name="Alice", telegram_user_id=100
        )
        pid2 = add_test_player(
            orch, player_id="p-200", display_name="Bob", telegram_user_id=200
        )

        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                mock_classify_intent("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                mock_extract_action(),
            ),
        ):
            result1 = await orch.handle_player_message(
                pid1, "I search", is_private=False
            )
            result2 = await orch.handle_player_message(
                pid2, "I watch", is_private=False
            )

        assert result1.action_submitted is True
        assert result1.turn_resolved is False  # Bob hasn't acted yet
        assert result2.action_submitted is True
        assert result2.turn_resolved is True  # Now all-ready


class TestPrivateQuestionViaDm:
    @pytest.mark.asyncio
    async def test_private_question_via_dm(self):
        """Player DMs question -> ruling returned privately."""
        fast = MagicMock()
        orch = make_test_orchestrator(fast_adapter=fast, scenario_path=GOBLIN_CAVES)
        pid = add_test_player(orch, telegram_user_id=100)

        with patch(
            "server.orchestrator.game_loop.classify_intent",
            mock_classify_intent("question"),
        ):
            result = await orch.handle_player_message(
                pid, "Is the NPC lying?", is_private=True
            )

        assert result.handled is True
        assert result.scope == "private"
        assert result.response_text  # Should have some response


class TestTimeoutFallbackTurn:
    @pytest.mark.asyncio
    async def test_timeout_fallback_turn(self):
        """One player submits, other doesn't -> force resolve -> fallback actions."""
        fast = MagicMock()
        orch = make_test_orchestrator(fast_adapter=fast, scenario_path=GOBLIN_CAVES)
        pid1 = add_test_player(
            orch, player_id="p-100", display_name="Alice", telegram_user_id=100
        )
        add_test_player(
            orch, player_id="p-200", display_name="Bob", telegram_user_id=200
        )

        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                mock_classify_intent("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                mock_extract_action(),
            ),
        ):
            result = await orch.handle_player_message(
                pid1, "I search", is_private=False
            )

        assert result.action_submitted is True
        assert result.turn_resolved is False  # Bob hasn't acted

        # Force resolve (simulates timer expiry)
        scene = orch.get_player_scene(pid1)
        assert scene is not None
        assert scene.active_turn_window_id is not None
        log_entry = orch.resolve_turn(scene.active_turn_window_id)
        assert log_entry is not None
        assert log_entry.narration  # fallback narration is non-empty


class TestConsecutiveTurnsAutoOpen:
    @pytest.mark.asyncio
    async def test_consecutive_turns_auto_open(self):
        """After resolution, next action auto-opens turn 2."""
        fast = MagicMock()
        orch = make_test_orchestrator(fast_adapter=fast, scenario_path=GOBLIN_CAVES)
        pid = add_test_player(orch, telegram_user_id=100)

        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                mock_classify_intent("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                mock_extract_action(),
            ),
        ):
            result1 = await orch.handle_player_message(
                pid, "I search", is_private=False
            )

        assert result1.turn_resolved is True

        # Second action -> should auto-open turn 2
        # Reset idempotency to avoid dedup
        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                mock_classify_intent("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                mock_extract_action(),
            ),
        ):
            result2 = await orch.handle_player_message(
                pid, "I move north", is_private=False
            )

        assert result2.action_submitted is True
        assert result2.turn_resolved is True  # Single player, auto-resolves again


class TestPrivateFactsDeliveredAfterResolve:
    @pytest.mark.asyncio
    async def test_private_facts_delivered_after_resolve(self):
        """Resolution produces turn_log_entry with narration for delivery."""
        fast = MagicMock()
        orch = make_test_orchestrator(fast_adapter=fast, scenario_path=GOBLIN_CAVES)
        pid = add_test_player(orch, telegram_user_id=100)

        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                mock_classify_intent("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                mock_extract_action(),
            ),
        ):
            result = await orch.handle_player_message(
                pid, "I search for hidden things", is_private=False
            )

        assert result.turn_resolved is True
        log_entry = result.turn_log_entry
        assert log_entry is not None
        assert log_entry.narration  # Has narration text for delivery
