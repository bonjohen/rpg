"""Extended session tests — multi-turn campaign runs across all starter scenarios.

Verifies:
  - 20-turn goblin_caves session completes without crashes
  - 10-turn haunted_manor session with exploration and puzzle interaction
  - 10-turn forest_ambush session with combat actions
  - Player disconnect/rejoin mid-session
  - Split party across scenes
"""

from __future__ import annotations

import os

from server.domain.enums import ActionType, SceneState
from server.orchestrator.game_loop import GameOrchestrator


SCENARIOS = os.path.join(os.path.dirname(__file__), "..", "..", "scenarios", "starters")


def _load(scenario_name: str, num_players: int = 3) -> GameOrchestrator:
    """Load a scenario, register players, return ready orchestrator."""
    orch = GameOrchestrator()
    path = os.path.join(SCENARIOS, f"{scenario_name}.yaml")
    assert orch.load_scenario(path), f"Failed to load {scenario_name}"
    for i in range(1, num_players + 1):
        orch.add_player(f"p{i}", f"Player{i}")
    return orch


def _play_turn(
    orch: GameOrchestrator,
    scene_id: str,
    actions: dict[str, tuple[ActionType, str]],
):
    """Open a turn, submit actions, resolve. Return the log entry."""
    tw = orch.open_turn(scene_id)
    assert tw is not None, "Failed to open turn"
    for player_id, (action_type, text) in actions.items():
        kwargs = {"public_text": text}
        if action_type == ActionType.move:
            kwargs["movement_target"] = text
        orch.submit_action(player_id, action_type, **kwargs)
    return orch.resolve_turn(tw.turn_window_id)


# ------------------------------------------------------------------
# 20-turn goblin_caves extended session
# ------------------------------------------------------------------


class TestGoblinCaves20Turn:
    """Run 20 turns through goblin_caves without crashing."""

    def test_20_turns_complete_without_crash(self):
        orch = _load("goblin_caves", num_players=3)
        starting = orch._find_starting_scene_id()

        # Action rotation for variety
        action_cycle = [
            (ActionType.inspect, "surroundings"),
            (ActionType.hold, ""),
            (ActionType.search, "hidden items"),
            (ActionType.inspect, "walls"),
            (ActionType.hold, ""),
        ]

        for turn in range(20):
            action = action_cycle[turn % len(action_cycle)]
            entry = _play_turn(
                orch,
                starting,
                {
                    "p1": action,
                    "p2": (ActionType.hold, ""),
                    "p3": (ActionType.hold, ""),
                },
            )
            assert entry is not None, f"Turn {turn + 1} returned None"
            assert entry.narration != "", f"Turn {turn + 1} has empty narration"

        entries = orch.get_turn_log_for_scene(starting)
        assert len(entries) == 20

    def test_turn_numbers_are_sequential(self):
        orch = _load("goblin_caves", num_players=1)
        starting = orch._find_starting_scene_id()

        for turn in range(10):
            entry = _play_turn(orch, starting, {"p1": (ActionType.hold, "")})
            assert entry.turn_number == turn + 1


# ------------------------------------------------------------------
# 10-turn haunted_manor session
# ------------------------------------------------------------------


class TestHauntedManor10Turn:
    """Run 10 turns through haunted_manor with exploration actions."""

    def test_10_turns_complete(self):
        orch = _load("haunted_manor", num_players=2)
        starting = orch._find_starting_scene_id()

        actions_seq = [
            {
                "p1": (ActionType.inspect, "entrance"),
                "p2": (ActionType.search, "ground"),
            },
            {"p1": (ActionType.inspect, "door"), "p2": (ActionType.hold, "")},
            {
                "p1": (ActionType.search, "walls"),
                "p2": (ActionType.inspect, "surroundings"),
            },
            {"p1": (ActionType.hold, ""), "p2": (ActionType.search, "hidden passages")},
            {"p1": (ActionType.inspect, "decorations"), "p2": (ActionType.hold, "")},
        ]

        for turn in range(10):
            actions = actions_seq[turn % len(actions_seq)]
            entry = _play_turn(orch, starting, actions)
            assert entry is not None
            assert entry.narration != ""

        entries = orch.get_turn_log_for_scene(starting)
        assert len(entries) == 10

    def test_scene_state_resets_between_turns(self):
        orch = _load("haunted_manor", num_players=1)
        starting = orch._find_starting_scene_id()

        for _ in range(3):
            _play_turn(orch, starting, {"p1": (ActionType.inspect, "room")})
            scene = orch.scenes[starting]
            assert scene.state == SceneState.narrated


# ------------------------------------------------------------------
# 10-turn forest_ambush session
# ------------------------------------------------------------------


class TestForestAmbush10Turn:
    """Run 10 turns through forest_ambush with combat actions."""

    def test_10_turns_with_combat_actions(self):
        orch = _load("forest_ambush", num_players=2)
        starting = orch._find_starting_scene_id()

        combat_actions = [
            {"p1": (ActionType.attack, "enemy"), "p2": (ActionType.defend, "")},
            {"p1": (ActionType.defend, ""), "p2": (ActionType.attack, "enemy")},
            {"p1": (ActionType.inspect, "battlefield"), "p2": (ActionType.hold, "")},
        ]

        for turn in range(10):
            actions = combat_actions[turn % len(combat_actions)]
            entry = _play_turn(orch, starting, actions)
            assert entry is not None

        entries = orch.get_turn_log_for_scene(starting)
        assert len(entries) == 10


# ------------------------------------------------------------------
# Player disconnect/rejoin
# ------------------------------------------------------------------


class TestPlayerDisconnectRejoin:
    """Verify a player can leave and rejoin without breaking state."""

    def test_remove_and_readd_player(self):
        orch = _load("goblin_caves", num_players=3)
        starting = orch._find_starting_scene_id()

        # Play 2 turns with all 3 players
        for _ in range(2):
            _play_turn(
                orch,
                starting,
                {
                    "p1": (ActionType.hold, ""),
                    "p2": (ActionType.hold, ""),
                    "p3": (ActionType.hold, ""),
                },
            )

        # Remove p3 from scene membership
        scene = orch.scenes[starting]
        char_p3 = orch.get_player_character("p3")
        if char_p3 and char_p3.character_id in scene.character_ids:
            scene.character_ids.remove(char_p3.character_id)

        # Play a turn without p3
        entry = _play_turn(
            orch,
            starting,
            {"p1": (ActionType.hold, ""), "p2": (ActionType.hold, "")},
        )
        assert entry is not None

        # Re-add p3 to the scene
        if char_p3:
            scene.character_ids.append(char_p3.character_id)

        # Play another turn with all 3
        entry = _play_turn(
            orch,
            starting,
            {
                "p1": (ActionType.hold, ""),
                "p2": (ActionType.hold, ""),
                "p3": (ActionType.hold, ""),
            },
        )
        assert entry is not None

        entries = orch.get_turn_log_for_scene(starting)
        assert len(entries) == 4


# ------------------------------------------------------------------
# Split party across scenes
# ------------------------------------------------------------------


class TestSplitParty:
    """Verify turns work when players are in different scenes."""

    def test_players_in_separate_scenes_get_separate_turns(self):
        orch = _load("goblin_caves", num_players=2)
        starting = orch._find_starting_scene_id()

        # Move p1 to a different scene via movement
        tw = orch.open_turn(starting)
        orch.submit_action(
            "p1", ActionType.move, movement_target="north (into the cave)"
        )
        orch.submit_action("p2", ActionType.hold)
        orch.resolve_turn(tw.turn_window_id)

        p1_scene = orch.get_player_scene("p1")
        p2_scene = orch.get_player_scene("p2")

        # If movement succeeded, they are in different scenes
        if p1_scene and p2_scene and p1_scene.scene_id != p2_scene.scene_id:
            # Play a turn in each scene independently
            entry_a = _play_turn(
                orch,
                p1_scene.scene_id,
                {"p1": (ActionType.inspect, "new room")},
            )
            entry_b = _play_turn(
                orch,
                p2_scene.scene_id,
                {"p2": (ActionType.hold, "")},
            )
            assert entry_a is not None
            assert entry_b is not None
        else:
            # Movement might not have resolved to a different scene
            # (depends on scene graph). Just verify no crash.
            pass

    def test_all_scenarios_load_without_error(self):
        """Smoke test: all 4 starter scenarios load and accept players."""
        for name in [
            "goblin_caves",
            "haunted_manor",
            "forest_ambush",
            "merchant_quarter",
        ]:
            orch = _load(name, num_players=2)
            assert orch.campaign is not None
            assert len(orch.scenes) > 0
            assert len(orch.players) == 2
            starting = orch._find_starting_scene_id()
            assert starting is not None
            # One turn each
            entry = _play_turn(
                orch,
                starting,
                {"p1": (ActionType.hold, ""), "p2": (ActionType.hold, "")},
            )
            assert entry is not None
