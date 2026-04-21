"""Unit tests for bot handler dispatch (Phase 2).

Tests per chat_loop_test_plan §3.1:
- Group play_action dispatches to orchestrator
- Non-play topic ignored
- Action response sent public
- Action submitted triggers resolve check
- Unknown user gets onboarding
- Orchestrator error handled gracefully
- Private message dispatches to orchestrator
- Private response sent as DM
- Private unregistered user gets onboarding
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers import _handle_group_message, _handle_private_message
from bot.mapping import BotRegistry
from bot.routing import RouteTarget
from server.orchestrator.game_loop import DispatchResult
from tests.fixtures.telegram_builders import (
    make_context,
    make_group_message,
    make_private_message,
    make_update,
)


def _make_config():
    from bot.config import BotConfig

    return BotConfig(group_chat_id=-1001234567890, play_topic_id=42)


def _make_dispatch_result(
    response_text: str = "",
    action_submitted: bool = False,
    handled: bool = True,
    scope: str = "public",
) -> DispatchResult:
    return DispatchResult(
        handled=handled,
        response_text=response_text,
        scope=scope,
        action_submitted=action_submitted,
    )


class TestGroupMessageDispatch:
    @pytest.mark.asyncio
    async def test_group_play_action_dispatches_to_orchestrator(self):
        """Player sends text in play topic -> handle_player_message called."""
        registry = BotRegistry()
        registry.register_player(100, "p-1")

        orch = MagicMock()
        orch.handle_player_message = AsyncMock(
            return_value=_make_dispatch_result(response_text="Action submitted: custom")
        )

        config = _make_config()
        msg = make_group_message(text="I search the fire pit", user_id=100, thread_id=42)
        update = make_update(msg)
        ctx = make_context(registry=registry, orchestrator=orch, config=config)

        with patch("bot.handlers.route_message") as mock_route:
            mock_route.return_value = MagicMock(target=RouteTarget.play_action)
            with patch("bot.handlers.send_public", new_callable=AsyncMock):
                await _handle_group_message(update, ctx)

        orch.handle_player_message.assert_called_once_with(
            "p-1", "I search the fire pit", is_private=False
        )

    @pytest.mark.asyncio
    async def test_group_non_play_topic_ignored(self):
        """Message in non-play topic -> orchestrator NOT called."""
        registry = BotRegistry()
        registry.register_player(100, "p-1")

        orch = MagicMock()
        orch.handle_player_message = AsyncMock()

        config = _make_config()
        msg = make_group_message(text="hello", user_id=100, thread_id=99)
        update = make_update(msg)
        ctx = make_context(registry=registry, orchestrator=orch, config=config)

        with patch("bot.handlers.route_message") as mock_route:
            mock_route.return_value = MagicMock(target=RouteTarget.group_chat)
            await _handle_group_message(update, ctx)

        orch.handle_player_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_group_action_response_sent_public(self):
        """Orchestrator returns response_text -> send_public called."""
        registry = BotRegistry()
        registry.register_player(100, "p-1")

        orch = MagicMock()
        orch.handle_player_message = AsyncMock(
            return_value=_make_dispatch_result(response_text="Action submitted: search")
        )

        config = _make_config()
        msg = make_group_message(text="I search", user_id=100, thread_id=42)
        update = make_update(msg)
        ctx = make_context(registry=registry, orchestrator=orch, config=config)

        with patch("bot.handlers.route_message") as mock_route:
            mock_route.return_value = MagicMock(target=RouteTarget.play_action)
            with patch("bot.handlers.send_public", new_callable=AsyncMock) as mock_pub:
                await _handle_group_message(update, ctx)
                mock_pub.assert_called_once()
                assert "Action submitted" in mock_pub.call_args[0][2]

    @pytest.mark.asyncio
    async def test_group_action_submitted_triggers_resolve_check(self):
        """DispatchResult.action_submitted=True -> result is returned (resolve check in later phase)."""
        registry = BotRegistry()
        registry.register_player(100, "p-1")

        orch = MagicMock()
        orch.handle_player_message = AsyncMock(
            return_value=_make_dispatch_result(
                response_text="Action submitted: search",
                action_submitted=True,
            )
        )

        config = _make_config()
        msg = make_group_message(text="I attack", user_id=100, thread_id=42)
        update = make_update(msg)
        ctx = make_context(registry=registry, orchestrator=orch, config=config)

        with patch("bot.handlers.route_message") as mock_route:
            mock_route.return_value = MagicMock(target=RouteTarget.play_action)
            with patch("bot.handlers.send_public", new_callable=AsyncMock):
                await _handle_group_message(update, ctx)

        orch.handle_player_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_group_unknown_user_gets_onboarding(self):
        """Unregistered user sends message -> onboarding reply, no crash."""
        registry = BotRegistry()  # no players registered

        orch = MagicMock()
        orch.handle_player_message = AsyncMock()

        config = _make_config()
        msg = make_group_message(text="hello", user_id=999, thread_id=42)
        update = make_update(msg)
        ctx = make_context(registry=registry, orchestrator=orch, config=config)

        with patch("bot.handlers.route_message") as mock_route:
            mock_route.return_value = MagicMock(target=RouteTarget.play_action)
            await _handle_group_message(update, ctx)

        msg.reply_text.assert_called_once()
        assert "/join" in msg.reply_text.call_args[0][0]
        orch.handle_player_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_group_orchestrator_error_handled_gracefully(self):
        """Orchestrator raises -> error logged, generic reply sent."""
        registry = BotRegistry()
        registry.register_player(100, "p-1")

        orch = MagicMock()
        orch.handle_player_message = AsyncMock(side_effect=RuntimeError("boom"))

        config = _make_config()
        msg = make_group_message(text="I attack", user_id=100, thread_id=42)
        update = make_update(msg)
        ctx = make_context(registry=registry, orchestrator=orch, config=config)

        with patch("bot.handlers.route_message") as mock_route:
            mock_route.return_value = MagicMock(target=RouteTarget.play_action)
            await _handle_group_message(update, ctx)

        msg.reply_text.assert_called_once()
        assert "wrong" in msg.reply_text.call_args[0][0].lower()


class TestPrivateMessageDispatch:
    @pytest.mark.asyncio
    async def test_private_message_dispatches_to_orchestrator(self):
        """Player sends DM -> handle_player_message called with is_private=True."""
        registry = BotRegistry()
        registry.register_player(100, "p-1")

        orch = MagicMock()
        orch.handle_player_message = AsyncMock(
            return_value=_make_dispatch_result(response_text="Referee says: yes")
        )

        config = _make_config()
        msg = make_private_message(text="Can I pick the lock?", user_id=100)
        update = make_update(msg)
        ctx = make_context(registry=registry, orchestrator=orch, config=config)

        with patch("bot.handlers.send_private", new_callable=AsyncMock):
            await _handle_private_message(update, ctx)

        orch.handle_player_message.assert_called_once_with(
            "p-1", "Can I pick the lock?", is_private=True
        )

    @pytest.mark.asyncio
    async def test_private_response_sent_as_dm(self):
        """Orchestrator returns response -> send_private called."""
        registry = BotRegistry()
        registry.register_player(100, "p-1")

        orch = MagicMock()
        orch.handle_player_message = AsyncMock(
            return_value=_make_dispatch_result(response_text="The lock clicks open.")
        )

        config = _make_config()
        msg = make_private_message(text="I try the lock", user_id=100)
        update = make_update(msg)
        ctx = make_context(registry=registry, orchestrator=orch, config=config)

        with patch("bot.handlers.send_private", new_callable=AsyncMock) as mock_priv:
            await _handle_private_message(update, ctx)
            mock_priv.assert_called_once()
            assert "lock clicks" in mock_priv.call_args[0][3]

    @pytest.mark.asyncio
    async def test_private_unregistered_user_gets_onboarding(self):
        """Unregistered DM from a known-to-registry but not onboarded user -> onboarding prompt."""
        registry = BotRegistry()
        # User is NOT registered in registry, so requires_onboarding returns True

        msg = make_private_message(text="hello", user_id=999)
        update = make_update(msg)
        ctx = make_context(registry=registry)

        with patch("bot.handlers.send_onboarding_prompt", new_callable=AsyncMock) as mock_onb:
            await _handle_private_message(update, ctx)
            mock_onb.assert_called_once()
