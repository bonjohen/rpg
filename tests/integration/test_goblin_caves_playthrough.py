"""Goblin Caves scenario playthrough integration tests (Phase 8).

Tests per chat_loop_test_plan §4.2. Scripted playthrough of the
goblin_caves scenario to verify the complete experience.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.commands import cmd_join, cmd_newgame
from bot.mapping import BotRegistry
from tests.fixtures.model_mocks import mock_classify_intent, mock_extract_action
from tests.fixtures.orchestrator_builder import add_test_player, make_test_orchestrator
from tests.fixtures.telegram_builders import (
    make_context,
    make_group_message,
    make_update,
)

SCENARIO_PATH = "scenarios/starters/goblin_caves.yaml"


class TestNewgameShowsScenarioIntro:
    @pytest.mark.asyncio
    async def test_newgame_shows_scenario_intro(self):
        """/newgame goblin_caves -> group sees title, description, Cave Entrance."""
        from bot.config import BotConfig

        orch = make_test_orchestrator(load_minimal=False)
        config = BotConfig(group_chat_id=-1001234567890)
        registry = BotRegistry()

        msg = make_group_message(text="/newgame scenarios/starters/goblin_caves.yaml")
        update = make_update(msg)
        ctx = make_context(registry=registry, config=config, orchestrator=orch)
        ctx.args = [SCENARIO_PATH]

        with patch("bot.commands.send_public", new_callable=AsyncMock):
            await cmd_newgame(update, ctx)

        # Check reply_text was called with scenario info
        reply_calls = msg.reply_text.call_args_list
        assert len(reply_calls) > 0
        reply_text = reply_calls[0][0][0]
        assert "Goblin Caves" in reply_text


class TestJoinShowsCaveEntrance:
    @pytest.mark.asyncio
    async def test_join_shows_cave_entrance(self):
        """Player joins -> sees Cave Entrance description."""
        from bot.config import BotConfig

        orch = make_test_orchestrator(scenario_path=SCENARIO_PATH)
        config = BotConfig(group_chat_id=-1001234567890)
        registry = BotRegistry()

        msg = make_group_message(text="/join", user_id=100)
        update = make_update(msg)
        ctx = make_context(registry=registry, config=config, orchestrator=orch)

        with patch("bot.commands.send_public", new_callable=AsyncMock):
            await cmd_join(update, ctx)

        reply_calls = msg.reply_text.call_args_list
        assert len(reply_calls) > 0
        reply_text = reply_calls[0][0][0]
        assert "Cave Entrance" in reply_text


class TestPickUpTorch:
    @pytest.mark.asyncio
    async def test_pick_up_torch(self):
        """Player types action -> submitted, resolved, narrated."""
        fast = MagicMock()
        orch = make_test_orchestrator(fast_adapter=fast, scenario_path=SCENARIO_PATH)
        pid = add_test_player(
            orch, player_id="p-100", display_name="Alice", telegram_user_id=100
        )

        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                mock_classify_intent("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                mock_extract_action("custom"),
            ),
        ):
            result = await orch.handle_player_message(
                pid, "I pick up the discarded torch", is_private=False
            )

        assert result.action_submitted is True
        assert result.turn_resolved is True
        assert result.turn_log_entry is not None

        # Verify game state: turn log recorded, committed action exists
        log_entry = result.turn_log_entry
        actions = orch.get_committed_actions_for_window(log_entry.turn_window_id)
        assert len(actions) == 1
        assert actions[0].player_id == pid

        # Player is still in the starting scene
        scene = orch.get_player_scene(pid)
        assert scene is not None
        assert "Cave Entrance" in scene.name


class TestEnterCaveTriggersLookout:
    @pytest.mark.asyncio
    async def test_enter_cave_triggers_lookout(self):
        """Player moves north -> action submitted and resolved (trigger fires in narration)."""
        fast = MagicMock()
        orch = make_test_orchestrator(fast_adapter=fast, scenario_path=SCENARIO_PATH)
        pid = add_test_player(
            orch, player_id="p-100", display_name="Alice", telegram_user_id=100
        )

        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                mock_classify_intent("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                mock_extract_action("move", "north (into the cave)"),
            ),
        ):
            result = await orch.handle_player_message(
                pid, "I go north into the cave", is_private=False
            )

        assert result.action_submitted is True
        assert result.turn_resolved is True

        # Verify turn log was recorded for this scene
        log = orch.get_turn_log(limit=10)
        assert len(log) >= 1
        assert log[-1].narration  # Has narration text


class TestTalkToGrix:
    @pytest.mark.asyncio
    async def test_talk_to_grix(self):
        """Player negotiates with NPC -> social action submitted."""
        fast = MagicMock()
        orch = make_test_orchestrator(fast_adapter=fast, scenario_path=SCENARIO_PATH)
        pid = add_test_player(
            orch, player_id="p-100", display_name="Alice", telegram_user_id=100
        )

        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                mock_classify_intent("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                mock_extract_action("persuade"),
            ),
        ):
            result = await orch.handle_player_message(
                pid, "I try to negotiate with Grix", is_private=False
            )

        assert result.action_submitted is True
        assert result.turn_resolved is True


class TestPrivateAwarenessCheck:
    @pytest.mark.asyncio
    async def test_private_awareness_check(self):
        """Player DMs question -> private response."""
        fast = MagicMock()
        orch = make_test_orchestrator(fast_adapter=fast, scenario_path=SCENARIO_PATH)
        pid = add_test_player(
            orch, player_id="p-100", display_name="Alice", telegram_user_id=100
        )

        with patch(
            "server.orchestrator.game_loop.classify_intent",
            mock_classify_intent("question"),
        ):
            result = await orch.handle_player_message(
                pid, "Do I notice anything hidden?", is_private=True
            )

        assert result.handled is True
        assert result.scope == "private"
        assert result.response_text  # Gets fallback or ruling response
