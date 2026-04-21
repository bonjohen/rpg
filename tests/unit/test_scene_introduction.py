"""Unit tests for scene introduction on /newgame and /join (Phase 1).

Tests per chat_loop_test_plan §3.6:
- newgame shows scenario title and description
- newgame shows starting scene description
- join shows scene description and exits
- join announces arrival to group
- ScenarioLoadResult carries metadata from manifest
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.commands import cmd_join, cmd_newgame
from bot.mapping import BotRegistry
from scenarios.loader import ScenarioLoadResult
from server.domain.entities import Scene
from server.domain.enums import SceneState
from tests.fixtures.telegram_builders import (
    make_context,
    make_group_message,
    make_update,
)

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _make_scene(
    scene_id: str = "cave_entrance",
    name: str = "Cave Entrance",
    description: str = "A dark mouth in the hillside.",
    exits: dict | None = None,
) -> Scene:
    return Scene(
        scene_id=scene_id,
        campaign_id="test-campaign",
        name=name,
        description=description,
        created_at=_NOW,
        state=SceneState.idle,
        exits=exits or {"north": "main_hall"},
    )


def _make_load_result(
    title: str = "The Goblin Caves",
    description: str = "A party of adventurers investigates goblin raids.",
    scenes: list[Scene] | None = None,
) -> ScenarioLoadResult:
    return ScenarioLoadResult(
        success=True,
        campaign_id="test-campaign",
        title=title,
        description=description,
        scenes=scenes or [_make_scene()],
    )


def _make_orchestrator_for_newgame(load_result=None):
    orch = MagicMock()
    orch.campaign_id = "test-campaign"
    orch.load_scenario = MagicMock(return_value=load_result or _make_load_result())
    orch.get_scenes = MagicMock(return_value=[_make_scene()])

    main_hall = _make_scene(
        scene_id="main_hall", name="Main Hall", description="A large cavern."
    )
    orch.get_scene = MagicMock(return_value=main_hall)
    return orch


def _make_orchestrator_for_join():
    orch = MagicMock()
    orch.campaign_id = "test-campaign"

    scene = _make_scene()
    player = MagicMock()
    char = MagicMock()
    char.name = "Alice"

    orch.add_player = MagicMock(return_value=(player, char))
    orch.get_player_scene = MagicMock(return_value=scene)

    main_hall = _make_scene(
        scene_id="main_hall", name="Main Hall", description="A large cavern."
    )
    orch.get_scene = MagicMock(return_value=main_hall)
    return orch


class TestNewgameSceneIntroduction:
    @pytest.mark.asyncio
    async def test_newgame_shows_scenario_title_and_description(self):
        """PDR §5 Gap 5: /newgame posts scenario title and description."""
        orch = _make_orchestrator_for_newgame()
        registry = BotRegistry()
        msg = make_group_message(text="/newgame scenarios/starters/goblin_caves.yaml")
        update = make_update(msg)
        ctx = make_context(registry=registry, orchestrator=orch)
        ctx.args = ["scenarios/starters/goblin_caves.yaml"]

        with patch("bot.commands._SCENARIOS_ROOT", new=MagicMock()) as mock_root:
            mock_root.__truediv__ = MagicMock()
            with patch("bot.commands.Path") as mock_path_cls:
                mock_resolved = MagicMock()
                mock_resolved.resolve.return_value = mock_resolved
                mock_resolved.is_relative_to.return_value = True
                mock_path_cls.return_value = mock_resolved

                await cmd_newgame(update, ctx)

        text = msg.reply_text.call_args[0][0]
        assert "The Goblin Caves" in text
        assert "goblin raids" in text

    @pytest.mark.asyncio
    async def test_newgame_shows_starting_scene_description(self):
        """PDR §5 Gap 5: /newgame posts starting scene description."""
        orch = _make_orchestrator_for_newgame()
        registry = BotRegistry()
        msg = make_group_message(text="/newgame scenarios/starters/goblin_caves.yaml")
        update = make_update(msg)
        ctx = make_context(registry=registry, orchestrator=orch)
        ctx.args = ["scenarios/starters/goblin_caves.yaml"]

        with patch("bot.commands.Path") as mock_path_cls:
            mock_resolved = MagicMock()
            mock_resolved.resolve.return_value = mock_resolved
            mock_resolved.is_relative_to.return_value = True
            mock_path_cls.return_value = mock_resolved

            await cmd_newgame(update, ctx)

        text = msg.reply_text.call_args[0][0]
        assert "Cave Entrance" in text
        assert "dark mouth" in text
        assert "/join" in text


class TestJoinSceneIntroduction:
    @pytest.mark.asyncio
    async def test_join_shows_scene_description(self):
        """PDR §5 Gap 5: /join posts full scene description and exits."""
        orch = _make_orchestrator_for_join()
        registry = BotRegistry()
        msg = make_group_message(user_id=20)
        update = make_update(msg)
        from bot.config import BotConfig

        config = BotConfig(group_chat_id=-1001234567890)
        ctx = make_context(registry=registry, orchestrator=orch, config=config)

        with patch("bot.commands.send_public", new_callable=AsyncMock):
            await cmd_join(update, ctx)

        text = msg.reply_text.call_args[0][0]
        assert "Cave Entrance" in text
        assert "dark mouth" in text
        assert "north" in text

    @pytest.mark.asyncio
    async def test_join_announces_arrival_to_group(self):
        """PDR §5 Gap 5: /join announces '{name} has entered {scene}'."""
        orch = _make_orchestrator_for_join()
        registry = BotRegistry()
        msg = make_group_message(user_id=20)
        update = make_update(msg)
        from bot.config import BotConfig

        config = BotConfig(group_chat_id=-1001234567890)
        ctx = make_context(registry=registry, orchestrator=orch, config=config)

        with patch("bot.commands.send_public", new_callable=AsyncMock) as mock_pub:
            await cmd_join(update, ctx)
            mock_pub.assert_called_once()
            announce_text = mock_pub.call_args[0][2]
            assert "has entered" in announce_text
            assert "Cave Entrance" in announce_text


class TestScenarioLoadResultMetadata:
    def test_scenario_load_result_carries_metadata(self):
        """ScenarioLoadResult has title and description from manifest."""
        result = _make_load_result()
        assert result.title == "The Goblin Caves"
        assert result.description == "A party of adventurers investigates goblin raids."
        assert result.success is True

    def test_scenario_load_result_defaults_empty(self):
        """ScenarioLoadResult defaults to empty strings for title/description."""
        result = ScenarioLoadResult()
        assert result.title == ""
        assert result.description == ""
