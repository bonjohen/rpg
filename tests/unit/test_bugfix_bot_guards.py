"""Tests for P1 bot handler None guards (BUG-016, 017, 018, 019)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.commands import (
    cmd_diagnostics,
    cmd_forceresolve,
    cmd_help,
    cmd_join,
    cmd_newgame,
    cmd_nextturn,
    cmd_scene,
    cmd_start,
    cmd_status,
    cmd_who,
)
from bot.mapping import BotRegistry


def _make_context(registry: BotRegistry | None = None):
    ctx = MagicMock()
    bot_data = {}
    if registry is not None:
        bot_data["registry"] = registry
    ctx.application.bot_data = bot_data
    return ctx


# -------------------------------------------------------------------
# BUG-016/017: None effective_user / message
# -------------------------------------------------------------------


class TestNoneUserGuards:
    """All cmd_* handlers should return silently when effective_user is None."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "handler",
        [
            cmd_start,
            cmd_join,
            cmd_status,
            cmd_newgame,
            cmd_nextturn,
            cmd_forceresolve,
            cmd_scene,
        ],
    )
    async def test_none_effective_user_returns_silently(self, handler):
        update = MagicMock()
        update.effective_user = None
        update.message = AsyncMock()
        ctx = _make_context(BotRegistry())
        # Should not raise or call reply_text
        await handler(update, ctx)
        update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "handler",
        [
            cmd_start,
            cmd_join,
            cmd_help,
            cmd_status,
            cmd_newgame,
            cmd_nextturn,
            cmd_forceresolve,
            cmd_diagnostics,
            cmd_scene,
            cmd_who,
        ],
    )
    async def test_none_message_returns_silently(self, handler):
        update = MagicMock()
        update.effective_user = MagicMock()
        update.message = None
        ctx = _make_context(BotRegistry())
        # Should not raise
        await handler(update, ctx)


# -------------------------------------------------------------------
# BUG-018: _registry() fallback creates empty BotRegistry
# -------------------------------------------------------------------


class TestRegistryFallback:
    def test_missing_registry_raises(self):
        from bot.commands import _registry

        ctx = _make_context()  # No registry in bot_data
        with pytest.raises(RuntimeError, match="BotRegistry not configured"):
            _registry(ctx)

    def test_present_registry_returned(self):
        from bot.commands import _registry

        reg = BotRegistry()
        ctx = _make_context(reg)
        assert _registry(ctx) is reg


# -------------------------------------------------------------------
# BUG-019: from_user None guard in handlers.py
# -------------------------------------------------------------------


class TestFromUserGuard:
    @pytest.mark.asyncio
    async def test_none_from_user_returns_silently(self):
        from bot.handlers import _handle_private_message

        update = MagicMock()
        message = MagicMock()
        message.from_user = None
        update.effective_message = message
        ctx = MagicMock()
        ctx.application.bot_data = {"registry": BotRegistry()}
        # Should return without error
        await _handle_private_message(update, ctx)
