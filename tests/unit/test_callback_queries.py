"""Unit tests for inline keyboard and callback queries (Phase 5).

Tests per chat_loop_test_plan §3.7.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.config import BotConfig
from bot.handlers import _handle_callback_query
from bot.mapping import BotRegistry
from bot.turn_controls import CALLBACK_PASS, CALLBACK_READY, build_turn_keyboard
from tests.fixtures.telegram_builders import (
    make_callback_query,
    make_callback_update,
    make_context,
)


def _make_config() -> BotConfig:
    return BotConfig(group_chat_id=-1001234567890)


def _make_orchestrator(
    player_id: str = "p-1",
    scene_name: str = "Cave",
    turn_window_id: str = "tw-1",
    tw_state: str = "open",
    turn_number: int = 1,
    submit_returns_action: bool = True,
) -> MagicMock:
    """Build a mock orchestrator with configurable turn state."""
    from server.domain.enums import TurnWindowState

    orch = MagicMock()

    scene = MagicMock()
    scene.scene_id = "s-1"
    scene.name = scene_name
    scene.active_turn_window_id = turn_window_id
    orch.get_player_scene.return_value = scene

    tw = MagicMock()
    tw.turn_window_id = turn_window_id
    tw.turn_number = turn_number
    tw.state = TurnWindowState(tw_state)
    orch.get_turn_window.return_value = tw

    if submit_returns_action:
        action = MagicMock()
        action.declared_action_type = MagicMock()
        action.declared_action_type.value = "hold"
        orch.submit_action.return_value = action
    else:
        orch.submit_action.return_value = None

    orch.turn_control_message_ids = {}

    return orch


class TestTurnControlMessagePosted:
    def test_turn_open_posts_control_message_with_keyboard(self):
        """Turn opens -> message posted with InlineKeyboard containing Ready/Pass."""
        kb = build_turn_keyboard()
        buttons = kb.inline_keyboard
        assert len(buttons) == 1
        row = buttons[0]
        assert len(row) == 2
        assert row[0].text == "Ready"
        assert row[0].callback_data == CALLBACK_READY
        assert row[1].text == "Pass"
        assert row[1].callback_data == CALLBACK_PASS


class TestReadyButton:
    @pytest.mark.asyncio
    async def test_ready_button_submits_hold_action(self):
        """Player presses Ready -> submit_action called with hold."""
        from server.domain.enums import ActionType

        registry = BotRegistry()
        registry.register_player(100, "p-1")
        config = _make_config()
        orch = _make_orchestrator()

        query = make_callback_query(data=CALLBACK_READY, user_id=100)
        update = make_callback_update(query)
        ctx = make_context(registry=registry, config=config, orchestrator=orch)

        await _handle_callback_query(update, ctx)

        orch.submit_action.assert_called_once()
        call_kwargs = orch.submit_action.call_args
        assert call_kwargs.kwargs.get("action_type") == ActionType.hold


class TestPassButton:
    @pytest.mark.asyncio
    async def test_pass_button_submits_pass_action(self):
        """Player presses Pass -> hold action with pass_turn type."""
        from server.domain.enums import ActionType

        registry = BotRegistry()
        registry.register_player(100, "p-1")
        config = _make_config()
        orch = _make_orchestrator()

        query = make_callback_query(data=CALLBACK_PASS, user_id=100)
        update = make_callback_update(query)
        ctx = make_context(registry=registry, config=config, orchestrator=orch)

        await _handle_callback_query(update, ctx)

        orch.submit_action.assert_called_once()
        call_kwargs = orch.submit_action.call_args
        assert call_kwargs.kwargs.get("action_type") == ActionType.pass_turn


class TestNonPlayerRejected:
    @pytest.mark.asyncio
    async def test_button_press_from_non_player_rejected(self):
        """Unregistered user presses button -> callback answered with error."""
        registry = BotRegistry()  # No players registered
        config = _make_config()
        orch = _make_orchestrator()

        query = make_callback_query(data=CALLBACK_READY, user_id=999)
        update = make_callback_update(query)
        ctx = make_context(registry=registry, config=config, orchestrator=orch)

        await _handle_callback_query(update, ctx)

        query.answer.assert_called_once()
        answer_text = query.answer.call_args[0][0]
        assert "join" in answer_text.lower()
        orch.submit_action.assert_not_called()


class TestPostResolveRejected:
    @pytest.mark.asyncio
    async def test_button_press_after_turn_resolved_rejected(self):
        """Button pressed after turn committed -> answered with 'already resolved'."""
        registry = BotRegistry()
        registry.register_player(100, "p-1")
        config = _make_config()
        orch = _make_orchestrator(tw_state="committed")

        query = make_callback_query(data=CALLBACK_READY, user_id=100)
        update = make_callback_update(query)
        ctx = make_context(registry=registry, config=config, orchestrator=orch)

        await _handle_callback_query(update, ctx)

        query.answer.assert_called_once()
        answer_text = query.answer.call_args[0][0]
        assert "resolved" in answer_text.lower()
        orch.submit_action.assert_not_called()


class TestControlMessageUpdates:
    @pytest.mark.asyncio
    async def test_control_message_updates_on_submission(self):
        """Player submits action -> control message edited to show remaining."""
        registry = BotRegistry()
        registry.register_player(100, "p-1")
        config = _make_config()
        orch = _make_orchestrator()
        orch.turn_control_message_ids["tw-1"] = 42

        # Mock remaining players
        player2 = MagicMock()
        player2.player_id = "p-2"
        player2.display_name = "Bob"
        orch.get_scene_players.return_value = [player2]
        orch.get_committed_actions_for_window.return_value = [
            MagicMock(player_id="p-1")
        ]

        query = make_callback_query(data=CALLBACK_READY, user_id=100)
        update = make_callback_update(query)
        ctx = make_context(registry=registry, config=config, orchestrator=orch)

        with patch(
            "bot.turn_controls.update_turn_control", new_callable=AsyncMock
        ) as mock_update:
            await _handle_callback_query(update, ctx)

            mock_update.assert_called_once()
            call_args = mock_update.call_args
            # Positional args: bot, config, msg_id, scene_name, turn_number, remaining_names
            remaining = call_args[0][5]
            assert "Bob" in remaining


class TestCallbackAnswered:
    @pytest.mark.asyncio
    async def test_callback_query_answered(self):
        """Every button press -> callback_query.answer() called."""
        registry = BotRegistry()
        registry.register_player(100, "p-1")
        config = _make_config()
        orch = _make_orchestrator()

        query = make_callback_query(data=CALLBACK_READY, user_id=100)
        update = make_callback_update(query)
        ctx = make_context(registry=registry, config=config, orchestrator=orch)

        await _handle_callback_query(update, ctx)

        query.answer.assert_called_once()
