"""Integration tests: logging, instrumentation, and transcript reconstruction."""

from __future__ import annotations

import os

from server.domain.enums import ActionType
from server.orchestrator.game_loop import GameOrchestrator


GOBLIN_CAVES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "scenarios", "starters", "goblin_caves.yaml"
)


def _setup_game(num_players: int = 2) -> GameOrchestrator:
    orch = GameOrchestrator()
    orch.load_scenario(GOBLIN_CAVES_PATH)
    for i in range(1, num_players + 1):
        orch.add_player(f"p{i}", f"Player{i}")
    return orch


def _play_turn(orch, scene_id, actions):
    tw = orch.open_turn(scene_id)
    if tw is None:
        return None
    for pid, (atype, text) in actions.items():
        kwargs = {"public_text": text}
        if atype == ActionType.move:
            kwargs["movement_target"] = text
        orch.submit_action(pid, atype, **kwargs)
    return orch.resolve_turn(tw.turn_window_id)


def test_all_turns_logged():
    orch = _setup_game(1)
    starting = orch._find_starting_scene_id()
    for _ in range(3):
        _play_turn(orch, starting, {"p1": (ActionType.hold, "")})
    assert len(orch.turn_log) == 3


def test_turn_log_complete_no_gaps():
    orch = _setup_game(1)
    starting = orch._find_starting_scene_id()
    for _ in range(5):
        _play_turn(orch, starting, {"p1": (ActionType.hold, "")})
    numbers = [e.turn_number for e in orch.turn_log]
    assert numbers == [1, 2, 3, 4, 5]


def test_idempotency_store_tracks_actions():
    orch = _setup_game(1)
    # Mark something in idempotency
    assert orch.idempotency.mark_seen("test_key") is True
    assert orch.idempotency.mark_seen("test_key") is False


def test_transcript_reconstruction():
    orch = _setup_game(1)
    starting = orch._find_starting_scene_id()
    _play_turn(orch, starting, {"p1": (ActionType.inspect, "surroundings")})
    _play_turn(orch, starting, {"p1": (ActionType.search, "")})
    _play_turn(orch, starting, {"p1": (ActionType.hold, "")})

    # Reconstruct transcript
    entries = orch.get_turn_log_for_scene(starting)
    transcript_lines = []
    for entry in entries:
        transcript_lines.append(f"Turn {entry.turn_number}: {entry.narration}")

    assert len(transcript_lines) == 3
    assert "Turn 1" in transcript_lines[0]
    assert "Turn 2" in transcript_lines[1]
    assert "Turn 3" in transcript_lines[2]
