"""Unit tests for orchestrator message handling (Phase 2).

Tests per chat_loop_test_plan §3.2:
- Action intent submits to turn
- Question intent calls ruling (placeholder — full implementation in Phase 7)
- Question private stays private
- Chat intent returns empty
- Unknown intent falls back to action
- Duplicate message deduped
- Identical text different turns not deduped
- No fast adapter treats as action
- Action extraction failure fallback
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


from server.domain.enums import ActionType
from tests.fixtures.model_mocks import mock_classify_intent, mock_extract_action
from tests.fixtures.orchestrator_builder import add_test_player, make_test_orchestrator


class TestHandlePlayerMessage:
    @pytest.mark.asyncio
    async def test_action_intent_submits_to_turn(self):
        """Text classified as 'action' -> submit_action called."""
        fast = MagicMock()
        orch = make_test_orchestrator(fast_adapter=fast)
        pid = add_test_player(orch)

        # Open a turn so submit_action works
        orch.open_turn("scene1")

        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                mock_classify_intent("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                mock_extract_action("search"),
            ),
        ):
            result = await orch.handle_player_message(pid, "I search the pit", False)

        assert result.action_submitted is True
        assert result.handled is True

    @pytest.mark.asyncio
    async def test_question_intent_returns_response(self):
        """Text classified as 'question' -> fallback when no main adapter."""
        fast = MagicMock()
        orch = make_test_orchestrator(fast_adapter=fast)
        pid = add_test_player(orch)

        with patch(
            "server.orchestrator.game_loop.classify_intent",
            mock_classify_intent("question"),
        ):
            result = await orch.handle_player_message(pid, "Can I see the door?", True)

        assert result.handled is True
        assert result.scope == "private"
        assert "referee" in result.response_text.lower()

    @pytest.mark.asyncio
    async def test_question_intent_calls_ruling(self):
        """Text classified as 'question' with main_adapter -> propose_ruling called."""
        fast = MagicMock()
        main = MagicMock()
        orch = make_test_orchestrator(fast_adapter=fast, main_adapter=main)
        pid = add_test_player(orch)

        ruling_output = MagicMock()
        ruling_output.reason = "Yes, you can see the door."
        ruling_output.ruling = "allow"

        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                mock_classify_intent("question"),
            ),
            patch(
                "models.main.tasks.propose_ruling",
                new_callable=AsyncMock,
                return_value=(ruling_output, MagicMock()),
            ) as mock_ruling,
        ):
            result = await orch.handle_player_message(pid, "Can I see the door?", True)

        mock_ruling.assert_called_once()
        assert result.response_text == "Yes, you can see the door."

    @pytest.mark.asyncio
    async def test_question_private_stays_private(self):
        """Private question -> response scope is 'private'."""
        fast = MagicMock()
        orch = make_test_orchestrator(fast_adapter=fast)
        pid = add_test_player(orch)

        with patch(
            "server.orchestrator.game_loop.classify_intent",
            mock_classify_intent("question"),
        ):
            result = await orch.handle_player_message(pid, "Is the NPC lying?", True)

        assert result.scope == "private"

    @pytest.mark.asyncio
    async def test_chat_intent_returns_empty(self):
        """Text classified as 'chat' -> handled=True, response_text=''."""
        fast = MagicMock()
        orch = make_test_orchestrator(fast_adapter=fast)
        pid = add_test_player(orch)

        with patch(
            "server.orchestrator.game_loop.classify_intent",
            mock_classify_intent("chat"),
        ):
            result = await orch.handle_player_message(pid, "lol nice", False)

        assert result.handled is True
        assert result.response_text == ""

    @pytest.mark.asyncio
    async def test_unknown_intent_handled_gracefully(self):
        """Unknown/ambiguous intent -> handled without error (drops as chat)."""
        fast = MagicMock()
        orch = make_test_orchestrator(fast_adapter=fast)
        pid = add_test_player(orch)

        with patch(
            "server.orchestrator.game_loop.classify_intent",
            mock_classify_intent("unknown_gibberish"),
        ):
            result = await orch.handle_player_message(pid, "hmm", False)

        # Unknown intents fall through to the else branch — handled, empty response
        assert result.handled is True
        assert result.response_text == ""
        assert result.action_submitted is False

    @pytest.mark.asyncio
    async def test_duplicate_message_deduped(self):
        """Same player+text+turn -> second call returns handled=True, empty response."""
        fast = MagicMock()
        orch = make_test_orchestrator(fast_adapter=fast)
        pid = add_test_player(orch)
        # Add a second player so the first submission doesn't auto-resolve
        add_test_player(orch, "player-2")
        orch.open_turn("scene1")

        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                mock_classify_intent("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                mock_extract_action("search"),
            ),
        ):
            r1 = await orch.handle_player_message(pid, "I attack", False)
            r2 = await orch.handle_player_message(pid, "I attack", False)

        assert r1.action_submitted is True
        assert r2.handled is True
        assert r2.response_text == ""

    @pytest.mark.asyncio
    async def test_identical_text_different_turns_not_deduped(self):
        """Same text in turn 1 and turn 2 -> both processed."""
        fast = MagicMock()
        orch = make_test_orchestrator(fast_adapter=fast)
        pid = add_test_player(orch)

        # Turn 1
        orch.open_turn("scene1")
        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                mock_classify_intent("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                mock_extract_action("attack"),
            ),
        ):
            r1 = await orch.handle_player_message(pid, "I attack", False)

        assert r1.action_submitted is True

        # Resolve turn 1 so we can open turn 2
        scene = orch.get_scene("scene1")
        if scene and scene.active_turn_window_id:
            orch.resolve_turn(scene.active_turn_window_id)

        # Turn 2
        orch.open_turn("scene1")
        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                mock_classify_intent("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                mock_extract_action("attack"),
            ),
        ):
            r2 = await orch.handle_player_message(pid, "I attack", False)

        assert r2.action_submitted is True

    @pytest.mark.asyncio
    async def test_no_fast_adapter_treats_as_action(self):
        """Fast adapter is None -> message treated as action directly."""
        orch = make_test_orchestrator(fast_adapter=None)
        pid = add_test_player(orch)
        orch.open_turn("scene1")

        result = await orch.handle_player_message(pid, "I search", False)
        assert result.action_submitted is True

    @pytest.mark.asyncio
    async def test_action_extraction_failure_fallback(self):
        """Fast model returns garbage -> action_type falls back to 'custom'."""
        fast = MagicMock()
        orch = make_test_orchestrator(fast_adapter=fast)
        pid = add_test_player(orch)
        orch.open_turn("scene1")

        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                mock_classify_intent("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                mock_extract_action("totally_invalid_type"),
            ),
        ):
            result = await orch.handle_player_message(pid, "I do something", False)

        # Should still submit (falls back to custom action type)
        assert result.action_submitted is True

        # Verify the invalid type was normalized to 'custom'
        assert result.turn_log_entry is not None
        tw_id = result.turn_log_entry.turn_window_id
        actions = orch.get_committed_actions_for_window(tw_id)
        assert len(actions) == 1
        assert actions[0].declared_action_type == ActionType.custom
