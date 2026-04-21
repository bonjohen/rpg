"""Unit tests for narration pipeline (Phase 4).

Tests per chat_loop_test_plan §3.4.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.delivery import generate_narration
from models.main.context import ActionContext
from models.main.schemas import NarrationOutput
from server.domain.entities import Scene, TurnLogEntry
from server.domain.enums import SceneState

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _make_scene(state: SceneState = SceneState.idle) -> Scene:
    return Scene(
        scene_id="s1",
        campaign_id="c1",
        name="Cave Entrance",
        description="A dark mouth.",
        created_at=_NOW,
        state=state,
    )


def _make_log_entry(narration: str = "Basic fallback narration.") -> TurnLogEntry:
    return TurnLogEntry(
        log_entry_id="log1",
        campaign_id="c1",
        scene_id="s1",
        turn_window_id="tw1",
        turn_number=1,
        committed_at=_NOW,
        narration=narration,
    )


def _make_action_ctx() -> ActionContext:
    return ActionContext(
        player_id="p1",
        character_name="Alice",
        action_type="search",
        notes="I search the pit",
    )


class TestGenerateNarration:
    @pytest.mark.asyncio
    async def test_narration_calls_main_model(self):
        """After resolution, narrate_scene called."""
        adapter = MagicMock()
        output = NarrationOutput(narration="The torchlight reveals old bones.")
        log = MagicMock()

        with patch(
            "bot.delivery.narrate_scene", new_callable=AsyncMock
        ) as mock_narrate:
            mock_narrate.return_value = (output, log)
            result = await generate_narration(
                adapter, _make_log_entry(), _make_scene(), [_make_action_ctx()]
            )

        assert result == "The torchlight reveals old bones."
        mock_narrate.assert_called_once()

    @pytest.mark.asyncio
    async def test_narration_fallback_on_model_failure(self):
        """Main model raises -> fallback narration used."""
        adapter = MagicMock()

        with patch(
            "bot.delivery.narrate_scene",
            new_callable=AsyncMock,
            side_effect=RuntimeError("model timeout"),
        ):
            result = await generate_narration(
                adapter, _make_log_entry(), _make_scene(), [_make_action_ctx()]
            )

        assert result == "Basic fallback narration."

    @pytest.mark.asyncio
    async def test_narration_fallback_on_model_timeout(self):
        """Main model times out -> fallback narration used."""
        adapter = MagicMock()

        with patch(
            "bot.delivery.narrate_scene",
            new_callable=AsyncMock,
            side_effect=TimeoutError("slow"),
        ):
            result = await generate_narration(
                adapter, _make_log_entry(), _make_scene(), [_make_action_ctx()]
            )

        assert result == "Basic fallback narration."

    @pytest.mark.asyncio
    async def test_narration_uses_narrate_scene_for_all_states(self):
        """All scene states -> narrate_scene called (combat refinement deferred)."""
        adapter = MagicMock()
        output = NarrationOutput(narration="The scene unfolds.")
        log = MagicMock()

        with patch(
            "bot.delivery.narrate_scene", new_callable=AsyncMock
        ) as mock_narrate:
            mock_narrate.return_value = (output, log)
            result = await generate_narration(
                adapter,
                _make_log_entry(),
                _make_scene(state=SceneState.resolving),
                [_make_action_ctx()],
            )

        assert result == "The scene unfolds."
        mock_narrate.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_main_adapter_uses_fallback(self):
        """No main adapter -> fallback narration."""
        result = await generate_narration(
            None, _make_log_entry(), _make_scene(), [_make_action_ctx()]
        )
        assert result == "Basic fallback narration."

    @pytest.mark.asyncio
    async def test_empty_narration_uses_fallback(self):
        """Model returns empty narration -> fallback used."""
        adapter = MagicMock()
        output = NarrationOutput(narration="")
        log = MagicMock()

        with patch(
            "bot.delivery.narrate_scene", new_callable=AsyncMock
        ) as mock_narrate:
            mock_narrate.return_value = (output, log)
            result = await generate_narration(
                adapter, _make_log_entry(), _make_scene(), [_make_action_ctx()]
            )

        assert result == "Basic fallback narration."

    @pytest.mark.asyncio
    async def test_narration_scene_context_built_correctly(self):
        """SceneContext passed to narrate_scene has correct fields."""
        adapter = MagicMock()
        output = NarrationOutput(narration="narration text")
        log = MagicMock()

        with patch(
            "bot.delivery.narrate_scene", new_callable=AsyncMock
        ) as mock_narrate:
            mock_narrate.return_value = (output, log)
            await generate_narration(
                adapter, _make_log_entry(), _make_scene(), [_make_action_ctx()]
            )

        call_args = mock_narrate.call_args
        scene_ctx = call_args[0][1]
        assert scene_ctx.scene_id == "s1"
        assert scene_ctx.location_name == "Cave Entrance"
