"""Unit tests for bot.commands (/start, /join, /help, /status)."""

from __future__ import annotations


from bot.commands import cmd_help, cmd_join, cmd_start, cmd_status
from bot.mapping import BotRegistry
from tests.fixtures.telegram_builders import (
    make_context,
    make_group_message,
    make_private_message,
    make_update,
)


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
        msg = make_group_message(user_id=20)
        update = make_update(msg)
        ctx = make_context(registry=registry)
        await cmd_join(update, ctx)
        assert registry.is_known_player(20)
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

    async def test_registered_user_sees_player_id(self):
        registry = BotRegistry()
        registry.register_player(60, "pid-abc")
        msg = make_private_message(user_id=60)
        update = make_update(msg)
        ctx = make_context(registry=registry)
        await cmd_status(update, ctx)
        text = msg.reply_text.call_args[0][0]
        assert "pid-abc" in text
