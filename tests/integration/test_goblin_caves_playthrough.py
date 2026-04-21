"""Goblin Caves scenario playthrough integration tests (Phase 8).

Tests per chat_loop_test_plan §4.2. Scripted playthrough of the
goblin_caves scenario to verify the complete experience.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.commands import cmd_join, cmd_newgame
from bot.mapping import BotRegistry
from models.fast.tasks import ActionPacketResult, IntentClassificationResult
from server.orchestrator.game_loop import GameOrchestrator
from tests.fixtures.db_helpers import create_test_session_factory
from tests.fixtures.telegram_builders import (
    make_context,
    make_group_message,
    make_update,
)

SCENARIO_PATH = "scenarios/starters/goblin_caves.yaml"


def _mock_classify(intent: str):
    async def _classify(adapter, text, **kwargs):
        return IntentClassificationResult(
            intent=intent, confidence="high", raw=intent
        ), MagicMock()

    return _classify


def _mock_extract(action_type: str = "custom", target: str = ""):
    async def _extract(adapter, text, available_types, **kwargs):
        return ActionPacketResult(
            action_type=action_type,
            target=target,
            item_ids=[],
            notes="",
            raw=action_type,
        ), MagicMock()

    return _extract


def _make_orchestrator(fast_adapter=None) -> GameOrchestrator:
    session_factory = create_test_session_factory()
    return GameOrchestrator(
        fast_adapter=fast_adapter,
        session_factory=session_factory,
    )


class TestNewgameShowsScenarioIntro:
    @pytest.mark.asyncio
    async def test_newgame_shows_scenario_intro(self):
        """/newgame goblin_caves -> group sees title, description, Cave Entrance."""
        from bot.config import BotConfig

        orch = _make_orchestrator()
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
        full_text = " ".join(str(c) for c in reply_calls)
        assert "Goblin Caves" in full_text or "goblin" in full_text.lower()


class TestJoinShowsCaveEntrance:
    @pytest.mark.asyncio
    async def test_join_shows_cave_entrance(self):
        """Player joins -> sees Cave Entrance description."""
        from bot.config import BotConfig

        orch = _make_orchestrator()
        config = BotConfig(group_chat_id=-1001234567890)
        registry = BotRegistry()

        # Load scenario first
        result = orch.load_scenario(SCENARIO_PATH)
        assert result is not None

        msg = make_group_message(text="/join", user_id=100)
        update = make_update(msg)
        ctx = make_context(registry=registry, config=config, orchestrator=orch)

        with patch("bot.commands.send_public", new_callable=AsyncMock):
            await cmd_join(update, ctx)

        reply_calls = msg.reply_text.call_args_list
        full_text = " ".join(str(c) for c in reply_calls)
        assert "Cave Entrance" in full_text or "cave" in full_text.lower()


class TestPickUpTorch:
    @pytest.mark.asyncio
    async def test_pick_up_torch(self):
        """Player types action -> submitted, resolved, narrated."""
        fast = MagicMock()
        orch = _make_orchestrator(fast_adapter=fast)
        result = orch.load_scenario(SCENARIO_PATH)
        assert result is not None

        pid = "p-100"
        orch.add_player(player_id=pid, display_name="Alice", telegram_user_id=100)

        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                _mock_classify("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                _mock_extract("custom"),
            ),
        ):
            result = await orch.handle_player_message(
                pid, "I pick up the discarded torch", is_private=False
            )

        assert result.action_submitted is True
        assert result.turn_resolved is True
        assert result.turn_log_entry is not None


class TestEnterCaveTriggersLookout:
    @pytest.mark.asyncio
    async def test_enter_cave_triggers_lookout(self):
        """Player moves north -> action submitted and resolved (trigger fires in narration)."""
        fast = MagicMock()
        orch = _make_orchestrator(fast_adapter=fast)
        result = orch.load_scenario(SCENARIO_PATH)
        assert result is not None

        pid = "p-100"
        orch.add_player(player_id=pid, display_name="Alice", telegram_user_id=100)

        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                _mock_classify("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                _mock_extract("move", "north (into the cave)"),
            ),
        ):
            result = await orch.handle_player_message(
                pid, "I go north into the cave", is_private=False
            )

        assert result.action_submitted is True
        assert result.turn_resolved is True


class TestTalkToGrix:
    @pytest.mark.asyncio
    async def test_talk_to_grix(self):
        """Player negotiates with NPC -> social action submitted."""
        fast = MagicMock()
        orch = _make_orchestrator(fast_adapter=fast)
        result = orch.load_scenario(SCENARIO_PATH)
        assert result is not None

        pid = "p-100"
        orch.add_player(player_id=pid, display_name="Alice", telegram_user_id=100)

        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                _mock_classify("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                _mock_extract("persuade"),
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
        orch = _make_orchestrator(fast_adapter=fast)
        result = orch.load_scenario(SCENARIO_PATH)
        assert result is not None

        pid = "p-100"
        orch.add_player(player_id=pid, display_name="Alice", telegram_user_id=100)

        with patch(
            "server.orchestrator.game_loop.classify_intent",
            _mock_classify("question"),
        ):
            result = await orch.handle_player_message(
                pid, "Do I notice anything hidden?", is_private=True
            )

        assert result.handled is True
        assert result.scope == "private"
        assert result.response_text  # Gets fallback or ruling response
