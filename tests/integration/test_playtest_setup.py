"""Integration tests: verify the orchestrator loads and sets up a playtest."""

from __future__ import annotations

import os

from server.orchestrator.game_loop import GameOrchestrator
from server.domain.enums import SceneState, TurnWindowState
from tests.fixtures.db_helpers import create_test_session_factory


GOBLIN_CAVES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "scenarios", "starters", "goblin_caves.yaml"
)


def _make_orchestrator() -> GameOrchestrator:
    return GameOrchestrator(session_factory=create_test_session_factory())


# ------------------------------------------------------------------
# Scenario loading
# ------------------------------------------------------------------


def test_goblin_caves_loads_into_orchestrator():
    orch = _make_orchestrator()
    assert orch.load_scenario(GOBLIN_CAVES_PATH)
    assert len(orch.get_scenes()) == 4
    assert len(orch.get_npcs()) == 2
    assert len(orch.get_monster_groups()) == 2
    assert len(orch.get_items()) == 7
    assert orch.campaign_id is not None


def test_newgame_populates_campaign():
    orch = _make_orchestrator()
    orch.load_scenario(GOBLIN_CAVES_PATH, campaign_name="Test Campaign")
    campaign = orch.get_campaign()
    assert campaign is not None
    assert campaign.name == "Test Campaign"


def test_scenario_starting_scene_is_cave_entrance():
    orch = _make_orchestrator()
    orch.load_scenario(GOBLIN_CAVES_PATH)
    starting_id = orch._find_starting_scene_id()
    assert starting_id is not None
    scene = orch.get_scene(starting_id)
    assert scene is not None
    assert scene.name == "Cave Entrance"


def test_scenario_has_puzzles_and_quests():
    orch = _make_orchestrator()
    orch.load_scenario(GOBLIN_CAVES_PATH)
    assert len(orch.get_puzzles()) == 2
    assert len(orch.get_quests()) == 2


def test_scenario_has_scopes():
    orch = _make_orchestrator()
    orch.load_scenario(GOBLIN_CAVES_PATH)
    assert len(orch.get_scopes()) > 0


def test_scenario_has_triggers():
    orch = _make_orchestrator()
    orch.load_scenario(GOBLIN_CAVES_PATH)
    assert len(orch.triggers) == 2


def test_scenario_has_knowledge_facts():
    orch = _make_orchestrator()
    orch.load_scenario(GOBLIN_CAVES_PATH)
    assert len(orch.get_knowledge_facts()) > 0


# ------------------------------------------------------------------
# Player joining
# ------------------------------------------------------------------


def test_player_join_and_scene_assignment():
    orch = _make_orchestrator()
    orch.load_scenario(GOBLIN_CAVES_PATH)

    p1, c1 = orch.add_player("p1", "Alice", telegram_user_id=1001)
    p2, c2 = orch.add_player("p2", "Bob", telegram_user_id=1002)
    p3, c3 = orch.add_player("p3", "Charlie", telegram_user_id=1003)

    assert len(orch.get_players()) == 3
    assert len(orch.get_characters()) == 3

    # All assigned to starting scene
    starting_id = orch._find_starting_scene_id()
    assert c1.scene_id == starting_id
    assert c2.scene_id == starting_id
    assert c3.scene_id == starting_id


def test_player_has_character_with_stats():
    orch = _make_orchestrator()
    orch.load_scenario(GOBLIN_CAVES_PATH)
    _, char = orch.add_player("p1", "Alice")
    assert char.stats.get("hp") == 20
    assert char.is_alive


def test_player_gets_private_scope():
    orch = _make_orchestrator()
    orch.load_scenario(GOBLIN_CAVES_PATH)
    orch.add_player("p1", "Alice")

    private_scope_id = orch._get_private_scope_id("p1")
    assert private_scope_id is not None


def test_get_player_scene_returns_starting_scene():
    orch = _make_orchestrator()
    orch.load_scenario(GOBLIN_CAVES_PATH)
    orch.add_player("p1", "Alice")
    scene = orch.get_player_scene("p1")
    assert scene is not None
    assert scene.name == "Cave Entrance"


def test_get_scene_players_lists_joined():
    orch = _make_orchestrator()
    orch.load_scenario(GOBLIN_CAVES_PATH)
    orch.add_player("p1", "Alice")
    orch.add_player("p2", "Bob")

    starting_id = orch._find_starting_scene_id()
    players = orch.get_scene_players(starting_id)
    assert len(players) == 2
    names = {p.display_name for p in players}
    assert names == {"Alice", "Bob"}


# ------------------------------------------------------------------
# Turn opening
# ------------------------------------------------------------------


def test_first_turn_opens_correctly():
    orch = _make_orchestrator()
    orch.load_scenario(GOBLIN_CAVES_PATH)
    orch.add_player("p1", "Alice")
    orch.add_player("p2", "Bob")

    starting_id = orch._find_starting_scene_id()
    tw = orch.open_turn(starting_id)
    assert tw is not None
    assert tw.state == TurnWindowState.open
    assert tw.turn_number == 1
    assert tw.scene_id == starting_id

    # Scene state updated
    scene = orch.get_scene(starting_id)
    assert scene.active_turn_window_id == tw.turn_window_id
    assert scene.state == SceneState.awaiting_actions


def test_timer_created_for_turn():
    orch = _make_orchestrator()
    orch.load_scenario(GOBLIN_CAVES_PATH)
    orch.add_player("p1", "Alice")

    starting_id = orch._find_starting_scene_id()
    tw = orch.open_turn(starting_id)
    assert tw is not None
    assert len(orch.timers) == 1


def test_turn_number_increments():
    orch = _make_orchestrator()
    orch.load_scenario(GOBLIN_CAVES_PATH)
    orch.add_player("p1", "Alice")

    starting_id = orch._find_starting_scene_id()
    tw1 = orch.open_turn(starting_id)
    assert tw1.turn_number == 1

    # Resolve turn 1 so we can open turn 2
    from server.domain.enums import ActionType

    orch.submit_action("p1", ActionType.hold)
    orch.resolve_turn(tw1.turn_window_id)

    tw2 = orch.open_turn(starting_id)
    assert tw2.turn_number == 2


def test_cannot_open_turn_without_campaign():
    orch = _make_orchestrator()
    tw = orch.open_turn("nonexistent")
    assert tw is None
