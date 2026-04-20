"""Integration tests: scripted multi-turn playtest through the orchestrator."""

from __future__ import annotations

import os

from server.domain.enums import ActionType, SceneState
from server.orchestrator.game_loop import GameOrchestrator
from tests.fixtures.db_helpers import create_test_session_factory


GOBLIN_CAVES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "scenarios", "starters", "goblin_caves.yaml"
)


def _setup_game(num_players: int = 3) -> GameOrchestrator:
    """Load goblin_caves, register players, return ready orchestrator."""
    orch = GameOrchestrator(session_factory=create_test_session_factory())
    orch.load_scenario(GOBLIN_CAVES_PATH)
    for i in range(1, num_players + 1):
        orch.add_player(f"p{i}", f"Player{i}")
    return orch


def _play_turn(
    orch: GameOrchestrator,
    scene_id: str,
    actions: dict[str, tuple[ActionType, str]],
) -> str | None:
    """Open a turn, submit actions, resolve. Return turn_window_id."""
    tw = orch.open_turn(scene_id)
    if tw is None:
        return None
    for player_id, (action_type, text) in actions.items():
        kwargs = {"public_text": text}
        if action_type == ActionType.move:
            kwargs["movement_target"] = text
        orch.submit_action(player_id, action_type, **kwargs)
    orch.resolve_turn(tw.turn_window_id)
    return tw.turn_window_id


# ------------------------------------------------------------------
# Exploration sequences
# ------------------------------------------------------------------


class TestExplorationSequence:
    """Multi-turn exploration through the caves."""

    def test_turn_produces_log_entry(self):
        orch = _setup_game(2)
        starting = orch._find_starting_scene_id()
        tw = orch.open_turn(starting)
        orch.submit_action("p1", ActionType.inspect, public_text="surroundings")
        orch.submit_action("p2", ActionType.hold)
        entry = orch.resolve_turn(tw.turn_window_id)
        assert entry is not None
        assert entry.turn_number == 1
        assert entry.narration != ""

    def test_movement_updates_scene(self):
        orch = _setup_game(1)
        starting = orch._find_starting_scene_id()

        # Open turn and move north
        tw = orch.open_turn(starting)
        orch.submit_action(
            "p1",
            ActionType.move,
            movement_target="north (into the cave)",
        )
        orch.resolve_turn(tw.turn_window_id)

        # Player should now be in main_hall
        scene = orch.get_player_scene("p1")
        assert scene is not None
        assert scene.name == "Main Hall"

    def test_multiple_turns_log_entries(self):
        orch = _setup_game(1)
        starting = orch._find_starting_scene_id()

        # Turn 1: inspect
        _play_turn(orch, starting, {"p1": (ActionType.inspect, "surroundings")})
        # Turn 2: hold
        _play_turn(orch, starting, {"p1": (ActionType.hold, "")})

        entries = orch.get_turn_log_for_scene(starting)
        assert len(entries) == 2
        assert entries[0].turn_number == 1
        assert entries[1].turn_number == 2

    def test_scene_state_after_resolution(self):
        orch = _setup_game(1)
        starting = orch._find_starting_scene_id()

        tw = orch.open_turn(starting)
        orch.submit_action("p1", ActionType.hold)
        orch.resolve_turn(tw.turn_window_id)

        scene = orch.get_scene(starting)
        assert scene.state == SceneState.narrated
        assert scene.active_turn_window_id is None

    def test_search_action_text(self):
        orch = _setup_game(1)
        starting = orch._find_starting_scene_id()

        tw = orch.open_turn(starting)
        orch.submit_action("p1", ActionType.search)
        entry = orch.resolve_turn(tw.turn_window_id)
        assert entry is not None
        assert "searches" in entry.narration.lower()


# ------------------------------------------------------------------
# Social sequences
# ------------------------------------------------------------------


class TestSocialSequence:
    """Player social actions against NPCs."""

    def test_social_action_produces_narration(self):
        orch = _setup_game(1)
        # Move to main_hall where Grix is
        starting = orch._find_starting_scene_id()
        tw = orch.open_turn(starting)
        orch.submit_action(
            "p1", ActionType.move, movement_target="north (into the cave)"
        )
        orch.resolve_turn(tw.turn_window_id)

        # Now in main_hall, do social action
        main_hall = orch.get_player_scene("p1")
        assert main_hall is not None
        tw2 = orch.open_turn(main_hall.scene_id)
        # Find Grix's NPC id
        grix_id = None
        for npc in orch.get_npcs():
            if "Grix" in npc.name:
                grix_id = npc.npc_id
                break
        orch.submit_action(
            "p1",
            ActionType.question,
            public_text="What do you want?",
            target_ids=[grix_id] if grix_id else [],
        )
        entry = orch.resolve_turn(tw2.turn_window_id)
        assert entry is not None
        assert "question" in entry.narration.lower()


# ------------------------------------------------------------------
# Combat sequences
# ------------------------------------------------------------------


class TestCombatSequence:
    """Player attack actions."""

    def test_attack_produces_narration(self):
        orch = _setup_game(1)
        starting = orch._find_starting_scene_id()
        tw = orch.open_turn(starting)
        # Attack goblin scouts
        scout_id = None
        for mg in orch.get_monster_groups():
            if mg.unit_type == "goblin_scout":
                scout_id = mg.monster_group_id
                break
        orch.submit_action(
            "p1",
            ActionType.attack,
            public_text="attack the scouts",
            target_ids=[scout_id] if scout_id else [],
        )
        entry = orch.resolve_turn(tw.turn_window_id)
        assert entry is not None
        assert "attack" in entry.narration.lower()


# ------------------------------------------------------------------
# Timer and fallback
# ------------------------------------------------------------------


class TestTimerFallback:
    """Timeout fallback behavior."""

    def test_timeout_fallback_for_missing_player(self):
        orch = _setup_game(2)
        starting = orch._find_starting_scene_id()
        tw = orch.open_turn(starting)
        # Only p1 submits, p2 doesn't
        orch.submit_action("p1", ActionType.hold)
        entry = orch.resolve_turn(tw.turn_window_id)
        assert entry is not None
        # p2 should have a timeout fallback
        all_actions = orch.get_committed_actions_for_window(tw.turn_window_id)
        fallback_actions = [a for a in all_actions if a.is_timeout_fallback]
        assert len(fallback_actions) == 1
        assert fallback_actions[0].player_id == "p2"

    def test_all_players_submit_no_fallback(self):
        orch = _setup_game(2)
        starting = orch._find_starting_scene_id()
        tw = orch.open_turn(starting)
        orch.submit_action("p1", ActionType.hold)
        orch.submit_action("p2", ActionType.hold)
        entry = orch.resolve_turn(tw.turn_window_id)
        assert entry is not None
        all_actions = orch.get_committed_actions_for_window(tw.turn_window_id)
        fallback_actions = [a for a in all_actions if a.is_timeout_fallback]
        assert len(fallback_actions) == 0


# ------------------------------------------------------------------
# Action submission validation
# ------------------------------------------------------------------


class TestActionSubmission:
    """Action submission edge cases."""

    def test_submit_action_returns_action(self):
        orch = _setup_game(1)
        starting = orch._find_starting_scene_id()
        orch.open_turn(starting)
        action = orch.submit_action("p1", ActionType.hold)
        assert action is not None
        assert action.declared_action_type == ActionType.hold

    def test_duplicate_submit_rejected(self):
        orch = _setup_game(1)
        starting = orch._find_starting_scene_id()
        orch.open_turn(starting)
        a1 = orch.submit_action("p1", ActionType.hold)
        assert a1 is not None
        a2 = orch.submit_action("p1", ActionType.inspect)
        assert a2 is None  # second submission rejected

    def test_submit_without_turn_fails(self):
        orch = _setup_game(1)
        action = orch.submit_action("p1", ActionType.hold)
        assert action is None

    def test_submit_after_resolve_fails(self):
        orch = _setup_game(1)
        starting = orch._find_starting_scene_id()
        tw = orch.open_turn(starting)
        orch.submit_action("p1", ActionType.hold)
        orch.resolve_turn(tw.turn_window_id)
        # No active turn now
        action = orch.submit_action("p1", ActionType.hold)
        assert action is None


# ------------------------------------------------------------------
# Turn log integrity
# ------------------------------------------------------------------


class TestTurnLog:
    """Turn log append-only, complete, no gaps."""

    def test_turn_log_append_only(self):
        orch = _setup_game(1)
        starting = orch._find_starting_scene_id()
        for _ in range(3):
            _play_turn(orch, starting, {"p1": (ActionType.hold, "")})
        entries = orch.get_turn_log_for_scene(starting)
        assert len(entries) == 3
        for i, entry in enumerate(entries):
            assert entry.turn_number == i + 1

    def test_turn_log_has_narration(self):
        orch = _setup_game(1)
        starting = orch._find_starting_scene_id()
        _play_turn(orch, starting, {"p1": (ActionType.hold, "")})
        entries = orch.get_turn_log_for_scene(starting)
        assert entries[0].narration != ""

    def test_turn_log_has_state_snapshot(self):
        orch = _setup_game(1)
        starting = orch._find_starting_scene_id()
        _play_turn(orch, starting, {"p1": (ActionType.hold, "")})
        entries = orch.get_turn_log_for_scene(starting)
        assert entries[0].state_snapshot is not None
        assert "scene_id" in entries[0].state_snapshot

    def test_turn_log_committed_actions(self):
        orch = _setup_game(1)
        starting = orch._find_starting_scene_id()
        _play_turn(orch, starting, {"p1": (ActionType.hold, "")})
        entries = orch.get_turn_log_for_scene(starting)
        assert len(entries[0].action_ids) >= 1
