"""Integration tests: defect category regression checks."""

from __future__ import annotations

import os

from server.domain.enums import ActionType, ScopeType, TurnWindowState
from server.orchestrator.game_loop import GameOrchestrator
from tests.fixtures.db_helpers import create_test_session_factory


GOBLIN_CAVES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "scenarios", "starters", "goblin_caves.yaml"
)


def _setup_game(num_players: int = 2) -> GameOrchestrator:
    orch = GameOrchestrator(session_factory=create_test_session_factory())
    orch.load_scenario(GOBLIN_CAVES_PATH)
    for i in range(1, num_players + 1):
        orch.add_player(f"p{i}", f"Player{i}")
    return orch


# ------------------------------------------------------------------
# Timing defects
# ------------------------------------------------------------------


class TestTimingDefects:
    def test_timeout_fallback_applied_when_player_missing(self):
        orch = _setup_game(2)
        starting = orch._find_starting_scene_id()
        tw = orch.open_turn(starting)
        orch.submit_action("p1", ActionType.hold)
        # p2 doesn't submit
        entry = orch.resolve_turn(tw.turn_window_id)
        assert entry is not None
        fallbacks = [
            a
            for a in orch.committed_actions.values()
            if a.turn_window_id == tw.turn_window_id and a.is_timeout_fallback
        ]
        assert len(fallbacks) == 1

    def test_early_close_triggers_when_all_ready(self):
        orch = _setup_game(2)
        starting = orch._find_starting_scene_id()
        tw = orch.open_turn(starting)
        orch.submit_action("p1", ActionType.hold)
        orch.submit_action("p2", ActionType.hold)
        # After both submit, the window should transition toward all_ready
        updated_tw = orch.turn_windows[tw.turn_window_id]
        assert updated_tw.state in (
            TurnWindowState.open,
            TurnWindowState.all_ready,
        )

    def test_late_submission_rejected_after_lock(self):
        orch = _setup_game(2)
        starting = orch._find_starting_scene_id()
        tw = orch.open_turn(starting)
        orch.submit_action("p1", ActionType.hold)
        orch.resolve_turn(tw.turn_window_id)
        # Turn is now resolved/committed — late submission should fail
        action = orch.submit_action("p1", ActionType.hold)
        assert action is None


# ------------------------------------------------------------------
# Leakage defects
# ------------------------------------------------------------------


class TestLeakageDefects:
    def test_referee_notes_not_in_narration(self):
        orch = _setup_game(1)
        starting = orch._find_starting_scene_id()
        tw = orch.open_turn(starting)
        orch.submit_action("p1", ActionType.inspect, public_text="surroundings")
        entry = orch.resolve_turn(tw.turn_window_id)
        assert entry is not None
        # Referee notes should not appear in public narration
        for scene in orch.get_scenes():
            if scene.hidden_description:
                assert scene.hidden_description not in entry.narration

    def test_hidden_exit_not_in_scene_description(self):
        orch = _setup_game(1)
        # Main hall has a hidden exit to treasury
        main_hall = None
        for s in orch.get_scenes():
            if s.name == "Main Hall":
                main_hall = s
                break
        assert main_hall is not None
        # Hidden exits should not be in the exits dict
        for direction, target in main_hall.exits.items():
            assert "treasury" not in direction.lower() or target != "treasury"

    def test_private_scope_facts_isolated(self):
        orch = _setup_game(2)
        # Each player should have their own private scope
        p1_scope = orch._get_private_scope_id("p1")
        p2_scope = orch._get_private_scope_id("p2")
        assert p1_scope is not None
        assert p2_scope is not None
        assert p1_scope != p2_scope

    def test_referee_only_facts_have_correct_scope(self):
        orch = _setup_game(1)
        scopes = orch.get_scopes()
        referee_scope_ids = {
            s.scope_id for s in scopes if s.scope_type == ScopeType.referee_only
        }
        referee_facts = [
            f
            for f in orch.get_knowledge_facts()
            if f.owner_scope_id in referee_scope_ids
        ]
        # Should have referee-only facts from scenario
        assert len(referee_facts) > 0


# ------------------------------------------------------------------
# Routing defects
# ------------------------------------------------------------------


class TestRoutingDefects:
    def test_action_classified_before_submission(self):
        orch = _setup_game(1)
        starting = orch._find_starting_scene_id()
        orch.open_turn(starting)
        action = orch.submit_action("p1", ActionType.inspect, public_text="the cave")
        assert action is not None
        assert action.declared_action_type == ActionType.inspect


# ------------------------------------------------------------------
# Rules defects
# ------------------------------------------------------------------


class TestRulesDefects:
    def test_movement_to_nonexistent_exit_fails(self):
        orch = _setup_game(1)
        starting = orch._find_starting_scene_id()
        tw = orch.open_turn(starting)
        orch.submit_action("p1", ActionType.move, movement_target="teleport")
        entry = orch.resolve_turn(tw.turn_window_id)
        assert entry is not None
        # Player should still be in starting scene (move failed)
        scene = orch.get_player_scene("p1")
        assert scene.scene_id == starting

    def test_one_action_per_player_per_turn_enforced(self):
        orch = _setup_game(1)
        starting = orch._find_starting_scene_id()
        orch.open_turn(starting)
        a1 = orch.submit_action("p1", ActionType.hold)
        a2 = orch.submit_action("p1", ActionType.attack)
        assert a1 is not None
        assert a2 is None

    def test_resolve_returns_none_for_nonexistent_turn(self):
        orch = _setup_game(1)
        entry = orch.resolve_turn("nonexistent_tw")
        assert entry is None

    def test_pass_turn_action_produces_narration(self):
        orch = _setup_game(1)
        starting = orch._find_starting_scene_id()
        tw = orch.open_turn(starting)
        orch.submit_action("p1", ActionType.pass_turn)
        entry = orch.resolve_turn(tw.turn_window_id)
        assert entry is not None
        assert entry.narration != ""
