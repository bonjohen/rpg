"""Unit tests for result delivery (Phase 4).

Tests per chat_loop_test_plan §3.5.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from bot.delivery import deliver_turn_results
from bot.mapping import BotRegistry, UnknownUserError
from tests.fixtures.builders import make_scene, make_turn_log_entry
from tests.fixtures.telegram_builders import make_bot_config

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class TestDeliverTurnResults:
    @pytest.mark.asyncio
    async def test_public_narration_sent_to_group(self):
        """After resolution, send_public called with narration text."""
        bot = AsyncMock()
        registry = BotRegistry()
        config = make_bot_config()

        with patch("bot.delivery.send_public", new_callable=AsyncMock) as mock_pub:
            await deliver_turn_results(
                make_turn_log_entry(narration="Basic narration."),
                make_scene(name="Cave", description="A cave."),
                "Rich narration text.",
                bot,
                config,
                registry,
            )
            mock_pub.assert_called_once()
            text = mock_pub.call_args[0][2]
            assert "Rich narration text." in text
            assert "Turn 1" in text

    @pytest.mark.asyncio
    async def test_private_facts_sent_to_owning_player(self):
        """Private fact -> send_private_by_player_id called for that player."""
        bot = AsyncMock()
        registry = BotRegistry()
        registry.register_player(100, "p-1")
        config = make_bot_config()

        facts = [("p-1", "You notice a hidden door.")]

        with (
            patch("bot.delivery.send_public", new_callable=AsyncMock),
            patch(
                "bot.delivery.send_private_by_player_id", new_callable=AsyncMock
            ) as mock_priv,
        ):
            await deliver_turn_results(
                make_turn_log_entry(narration="Basic narration."),
                make_scene(name="Cave", description="A cave."),
                "Narration.",
                bot,
                config,
                registry,
                private_facts=facts,
            )
            mock_priv.assert_called_once()
            assert mock_priv.call_args[0][2] == "p-1"
            assert "hidden door" in mock_priv.call_args[0][3]

    @pytest.mark.asyncio
    async def test_other_players_do_not_receive_private_facts(self):
        """Private fact for player A -> player B's DM NOT called."""
        bot = AsyncMock()
        registry = BotRegistry()
        registry.register_player(100, "p-1")
        registry.register_player(200, "p-2")
        config = make_bot_config()

        facts = [("p-1", "Secret for player 1 only.")]

        with (
            patch("bot.delivery.send_public", new_callable=AsyncMock),
            patch(
                "bot.delivery.send_private_by_player_id", new_callable=AsyncMock
            ) as mock_priv,
        ):
            await deliver_turn_results(
                make_turn_log_entry(narration="Basic narration."),
                make_scene(name="Cave", description="A cave."),
                "Narration.",
                bot,
                config,
                registry,
                private_facts=facts,
            )
            # Only one call — for p-1
            assert mock_priv.call_count == 1
            assert mock_priv.call_args[0][2] == "p-1"

    @pytest.mark.asyncio
    async def test_partial_delivery_failure_continues(self):
        """DM to player B fails -> player A's DM still sent."""
        bot = AsyncMock()
        registry = BotRegistry()
        registry.register_player(100, "p-1")
        registry.register_player(200, "p-2")
        config = make_bot_config()

        facts = [
            ("p-1", "Fact for p-1."),
            ("p-2", "Fact for p-2."),
        ]

        call_count = 0

        async def _side_effect(b, reg, pid, text, **kwargs):
            nonlocal call_count
            call_count += 1
            if pid == "p-1":
                raise Exception("DM failed for p-1")

        with (
            patch("bot.delivery.send_public", new_callable=AsyncMock),
            patch(
                "bot.delivery.send_private_by_player_id",
                side_effect=_side_effect,
            ),
        ):
            # Should not raise — logs error and continues
            await deliver_turn_results(
                make_turn_log_entry(narration="Basic narration."),
                make_scene(name="Cave", description="A cave."),
                "Narration.",
                bot,
                config,
                registry,
                private_facts=facts,
            )

        # Both were attempted
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_partial_delivery_failure_logged(self, caplog):
        """Failed DM -> error logged with player_id."""
        bot = AsyncMock()
        registry = BotRegistry()
        registry.register_player(100, "p-1")
        config = make_bot_config()

        facts = [("p-1", "Secret.")]

        with (
            patch("bot.delivery.send_public", new_callable=AsyncMock),
            patch(
                "bot.delivery.send_private_by_player_id",
                new_callable=AsyncMock,
                side_effect=UnknownUserError("not found"),
            ),
        ):
            import logging

            with caplog.at_level(logging.ERROR, logger="bot.delivery"):
                await deliver_turn_results(
                    make_turn_log_entry(narration="Basic narration."),
                    make_scene(name="Cave", description="A cave."),
                    "Narration.",
                    bot,
                    config,
                    registry,
                    private_facts=facts,
                )

        assert "p-1" in caplog.text

    @pytest.mark.asyncio
    async def test_empty_turn_no_private_facts(self):
        """Turn with no private revelations -> no DMs sent."""
        bot = AsyncMock()
        registry = BotRegistry()
        config = make_bot_config()

        with (
            patch("bot.delivery.send_public", new_callable=AsyncMock),
            patch(
                "bot.delivery.send_private_by_player_id", new_callable=AsyncMock
            ) as mock_priv,
        ):
            await deliver_turn_results(
                make_turn_log_entry(narration="Basic narration."),
                make_scene(name="Cave", description="A cave."),
                "Narration.",
                bot,
                config,
                registry,
            )
            mock_priv.assert_not_called()
