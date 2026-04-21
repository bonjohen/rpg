"""Shared orchestrator builder for tests.

Consolidates the _make_orchestrator pattern duplicated across 12+ test files
into a single reusable builder with all commonly needed optional parameters.
"""

from __future__ import annotations

from unittest.mock import patch

from server.orchestrator.game_loop import GameOrchestrator
from tests.fixtures.db_helpers import create_test_session_factory

from scenarios.loader import ScenarioLoader
from scenarios.schema import ScenarioManifest, SceneDefinition


def make_test_orchestrator(
    fast_adapter=None,
    main_adapter=None,
    session_factory=None,
    scenario_path: str | None = None,
    campaign_name: str = "Test Campaign",
    load_minimal: bool = True,
) -> GameOrchestrator:
    """Build a GameOrchestrator with in-memory DB and optional mock adapters.

    Args:
        fast_adapter: Mock or real fast model adapter (default: None).
        main_adapter: Mock or real main model adapter (default: None).
        session_factory: SQLAlchemy session factory (default: in-memory SQLite).
        scenario_path: If set, load a real scenario file (e.g. goblin_caves).
            Mutually exclusive with load_minimal.
        campaign_name: Campaign name for scenario loading.
        load_minimal: If True (default) and scenario_path is None, load a
            one-scene test scenario so the orchestrator has a campaign and scene.
    """
    if session_factory is None:
        session_factory = create_test_session_factory()

    orch = GameOrchestrator(
        fast_adapter=fast_adapter,
        main_adapter=main_adapter,
        session_factory=session_factory,
    )

    if scenario_path:
        result = orch.load_scenario(scenario_path, campaign_name=campaign_name)
        assert result is not None and result.success, (
            f"Failed to load scenario: {scenario_path}"
        )
    elif load_minimal:
        manifest = ScenarioManifest(
            scenario_id="test",
            title="Test Scenario",
            starting_scene_id="scene1",
            scenes=[
                SceneDefinition(
                    scene_id="scene1",
                    name="Test Scene",
                    description="A test scene.",
                ),
            ],
        )
        loader = ScenarioLoader()
        result = loader.load_from_manifest(manifest)
        with patch.object(orch.scenario_loader, "load_from_yaml", return_value=result):
            orch.load_scenario("dummy.yaml")

    return orch


def add_test_player(
    orch: GameOrchestrator,
    player_id: str = "player-1",
    display_name: str = "Test Player",
    telegram_user_id: int | None = None,
) -> str:
    """Add a player to the orchestrator and return the player_id.

    Args:
        orch: The orchestrator to add the player to.
        player_id: Player ID string.
        display_name: Display name.
        telegram_user_id: Optional Telegram user ID for registry integration.
    """
    kwargs: dict = {
        "player_id": player_id,
        "display_name": display_name,
    }
    if telegram_user_id is not None:
        kwargs["telegram_user_id"] = telegram_user_id

    result = orch.add_player(**kwargs)
    # add_player returns (Player, Character) or just adds — handle both
    if isinstance(result, tuple):
        return result[0].player_id
    return player_id


def add_test_players(
    orch: GameOrchestrator,
    count: int = 2,
    base_telegram_user_id: int = 1000,
) -> list[str]:
    """Add multiple test players and return their player_ids."""
    ids = []
    for i in range(count):
        pid = add_test_player(
            orch,
            player_id=f"player_{i}",
            display_name=f"Player {i}",
            telegram_user_id=base_telegram_user_id + i,
        )
        ids.append(pid)
    return ids
