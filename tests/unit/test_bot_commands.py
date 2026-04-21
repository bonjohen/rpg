"""Unit tests for bot.commands (/start, /join, /help, /status)."""

from __future__ import annotations

from unittest.mock import MagicMock

from bot.commands import cmd_help, cmd_join, cmd_start, cmd_status
from bot.mapping import BotRegistry
from tests.fixtures.telegram_builders import (
    make_context,
    make_group_message,
    make_private_message,
    make_update,
)


def _make_mock_orchestrator():
    """Build a mock orchestrator that supports add_player and get_player_scene."""
    orch = MagicMock()
    orch.campaign_id = "test-campaign"

    scene = MagicMock()
    scene.name = "Entrance Hall"

    player = MagicMock()
    char = MagicMock()
    char.name = "Alice"

    orch.add_player = MagicMock(return_value=(player, char))
    orch.get_player_scene = MagicMock(return_value=scene)
    return orch


class TestCmdStart:
    async def test_unregistered_user_sees_onboarding_prompt(self):
        registry = BotRegistry()
        msg = make_private_message(user_id=1)
        update = make_update(msg)
        ctx = make_context(registry=registry)
        await cmd_start(update, ctx)
        msg.reply_text.assert_called_once()
        text = msg.reply_text.call_args[0][0]
        assert "/join" in text

    async def test_registered_user_sees_welcome_back(self):
        registry = BotRegistry()
        registry.register_player(2, "p-uuid")
        msg = make_private_message(user_id=2)
        update = make_update(msg)
        ctx = make_context(registry=registry)
        await cmd_start(update, ctx)
        msg.reply_text.assert_called_once()
        text = msg.reply_text.call_args[0][0]
        assert "Welcome back" in text


class TestCmdJoin:
    async def test_join_from_private_chat_is_rejected(self):
        registry = BotRegistry()
        msg = make_private_message(user_id=10)
        update = make_update(msg)
        ctx = make_context(registry=registry)
        await cmd_join(update, ctx)
        msg.reply_text.assert_called_once()
        assert "group" in msg.reply_text.call_args[0][0]
        assert not registry.is_known_player(10)

    async def test_join_from_group_registers_player(self):
        registry = BotRegistry()
        orch = _make_mock_orchestrator()
        msg = make_group_message(user_id=20)
        update = make_update(msg)
        ctx = make_context(registry=registry, orchestrator=orch)
        await cmd_join(update, ctx)
        assert registry.is_known_player(20)
        orch.add_player.assert_called_once()
        msg.reply_text.assert_called_once()
        assert "Welcome" in msg.reply_text.call_args[0][0]

    async def test_join_idempotent_for_existing_player(self):
        registry = BotRegistry()
        registry.register_player(30, "existing-uuid")
        msg = make_group_message(user_id=30)
        update = make_update(msg)
        ctx = make_context(registry=registry)
        await cmd_join(update, ctx)
        # Still the original player_id
        assert registry.player_id_for(30) == "existing-uuid"
        assert "already" in msg.reply_text.call_args[0][0]


class TestCmdHelp:
    async def test_help_shows_commands(self):
        msg = make_private_message()
        update = make_update(msg)
        ctx = make_context()
        await cmd_help(update, ctx)
        text = msg.reply_text.call_args[0][0]
        assert "/join" in text
        assert "/status" in text


class TestCmdStatus:
    async def test_unregistered_user_told_to_join(self):
        registry = BotRegistry()
        msg = make_private_message(user_id=50)
        update = make_update(msg)
        ctx = make_context(registry=registry)
        await cmd_status(update, ctx)
        text = msg.reply_text.call_args[0][0]
        assert "/join" in text

    async def test_registered_user_sees_display_name_not_uuid(self):
        registry = BotRegistry()
        registry.register_player(60, "pid-abc")
        msg = make_private_message(user_id=60)
        update = make_update(msg)
        ctx = make_context(registry=registry)
        await cmd_status(update, ctx)
        text = msg.reply_text.call_args[0][0]
        # UUID should NOT be exposed; display name (first_name) should be shown
        assert "pid-abc" not in text
        assert "Alice" in text
