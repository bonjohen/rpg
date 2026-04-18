"""Unit tests for bot.outbound."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.config import BotConfig
from bot.mapping import BotRegistry, UnknownUserError
from bot.outbound import send_private, send_private_by_player_id, send_public


def _config(**kwargs) -> BotConfig:
    defaults = {"group_chat_id": -9999, "play_topic_id": 42}
    defaults.update(kwargs)
    return BotConfig(**defaults)


def _bot() -> MagicMock:
    bot = MagicMock()
    bot.send_message = AsyncMock()
    return bot


class TestSendPublic:
    async def test_sends_to_group_with_topic(self):
        bot = _bot()
        config = _config(play_topic_id=42)
        await send_public(bot, config, "Narration text")
        bot.send_message.assert_called_once()
        call_kwargs = bot.send_message.call_args[1]
        assert call_kwargs["chat_id"] == -9999
        assert call_kwargs["message_thread_id"] == 42
        assert call_kwargs["text"] == "Narration text"

    async def test_sends_to_group_without_topic(self):
        bot = _bot()
        config = _config(play_topic_id=None)
        await send_public(bot, config, "hello")
        call_kwargs = bot.send_message.call_args[1]
        assert call_kwargs["message_thread_id"] is None

    async def test_skips_send_when_no_group_chat_id(self):
        bot = _bot()
        config = BotConfig(group_chat_id=0)
        await send_public(bot, config, "hello")
        bot.send_message.assert_not_called()


class TestSendPrivate:
    async def test_sends_to_registered_user(self):
        bot = _bot()
        registry = BotRegistry()
        registry.register_player(100, "p-1")
        await send_private(bot, registry, 100, "Your HP is 10")
        bot.send_message.assert_called_once()
        assert bot.send_message.call_args[1]["chat_id"] == 100
        assert "HP" in bot.send_message.call_args[1]["text"]

    async def test_raises_for_unregistered_user(self):
        bot = _bot()
        registry = BotRegistry()
        with pytest.raises(UnknownUserError):
            await send_private(bot, registry, 999, "hello")
        bot.send_message.assert_not_called()


class TestSendPrivateByPlayerId:
    async def test_sends_to_correct_user(self):
        bot = _bot()
        registry = BotRegistry()
        registry.register_player(200, "player-abc")
        await send_private_by_player_id(bot, registry, "player-abc", "Secret clue")
        bot.send_message.assert_called_once()
        assert bot.send_message.call_args[1]["chat_id"] == 200

    async def test_raises_for_unknown_player_id(self):
        bot = _bot()
        registry = BotRegistry()
        with pytest.raises(UnknownUserError):
            await send_private_by_player_id(bot, registry, "no-such-player", "hello")
