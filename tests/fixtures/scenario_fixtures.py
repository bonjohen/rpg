"""Scenario test fixtures — helper functions for building manifests."""

from __future__ import annotations

import os

from scenarios.loader import ScenarioLoader
from scenarios.schema import (
    ExitDefinition,
    ItemDefinition,
    MonsterDefinition,
    NpcDefinition,
    NpcTellDefinition,
    PuzzleDefinition,
    QuestDefinition,
    ScenarioManifest,
    SceneDefinition,
    TriggerDefinition,
)


def make_minimal_manifest() -> ScenarioManifest:
    """Two scenes, one exit, one NPC, one item. Minimal valid scenario."""
    return ScenarioManifest(
        scenario_id="minimal_test",
        title="Minimal Test Scenario",
        description="A minimal scenario for testing.",
        version="1.0.0",
        author="test",
        starting_scene_id="room_a",
        scenes=[
            SceneDefinition(
                scene_id="room_a",
                name="Room A",
                description="A plain room.",
                exits=[
                    ExitDefinition(
                        exit_id="a_to_b",
                        direction="north",
                        target_scene_id="room_b",
                        description="A door to Room B.",
                    ),
                ],
                npc_ids=["test_npc"],
                item_ids=["test_item"],
            ),
            SceneDefinition(
                scene_id="room_b",
                name="Room B",
                description="Another plain room.",
                exits=[
                    ExitDefinition(
                        exit_id="b_to_a",
                        direction="south",
                        target_scene_id="room_a",
                        description="A door to Room A.",
                    ),
                ],
            ),
        ],
        npcs=[
            NpcDefinition(
                npc_id="test_npc",
                name="Test NPC",
                description="A generic NPC.",
                scene_id="room_a",
            ),
        ],
        items=[
            ItemDefinition(
                item_id="test_item",
                name="Test Item",
                description="A generic item.",
                scene_id="room_a",
            ),
        ],
    )


def make_goblin_caves_manifest() -> ScenarioManifest:
    """Load and parse scenarios/starters/goblin_caves.yaml."""
    yaml_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "scenarios",
        "starters",
        "goblin_caves.yaml",
    )
    loader = ScenarioLoader()
    data, err = loader._parse_yaml(os.path.abspath(yaml_path))
    assert data is not None, f"Failed to parse {yaml_path}: {err}"
    return loader._deserialize(data)


def make_invalid_manifest_broken_ref() -> ScenarioManifest:
    """Scene with exit pointing to nonexistent target_scene_id."""
    return ScenarioManifest(
        scenario_id="broken_ref",
        title="Broken Ref",
        starting_scene_id="room_a",
        scenes=[
            SceneDefinition(
                scene_id="room_a",
                name="Room A",
                description="A room.",
                exits=[
                    ExitDefinition(
                        exit_id="a_to_nowhere",
                        direction="north",
                        target_scene_id="nonexistent_room",
                    ),
                ],
            ),
        ],
    )


def make_invalid_manifest_duplicate_ids() -> ScenarioManifest:
    """Two items with the same item_id."""
    return ScenarioManifest(
        scenario_id="dup_ids",
        title="Duplicate IDs",
        starting_scene_id="room_a",
        scenes=[
            SceneDefinition(
                scene_id="room_a",
                name="Room A",
                description="A room.",
                item_ids=["dupe_item"],
            ),
        ],
        items=[
            ItemDefinition(
                item_id="dupe_item",
                name="Item One",
                scene_id="room_a",
            ),
            ItemDefinition(
                item_id="dupe_item",
                name="Item Two",
                scene_id="room_a",
            ),
        ],
    )


def make_manifest_with_leakage() -> ScenarioManifest:
    """referee_notes text duplicated in a public description field."""
    leaked_text = "The secret passage is behind the bookshelf on the north wall"
    return ScenarioManifest(
        scenario_id="leakage_test",
        title="Leakage Test",
        starting_scene_id="room_a",
        scenes=[
            SceneDefinition(
                scene_id="room_a",
                name="Room A",
                description=f"A library. {leaked_text}.",
                referee_notes=leaked_text,
                exits=[
                    ExitDefinition(
                        exit_id="a_to_b",
                        direction="north",
                        target_scene_id="room_b",
                    ),
                ],
            ),
            SceneDefinition(
                scene_id="room_b",
                name="Room B",
                description="Hidden room.",
                exits=[
                    ExitDefinition(
                        exit_id="b_to_a",
                        direction="south",
                        target_scene_id="room_a",
                    ),
                ],
            ),
        ],
    )


def make_manifest_with_hidden_exit() -> ScenarioManifest:
    """Scene with a hidden exit for testing hidden fact generation."""
    return ScenarioManifest(
        scenario_id="hidden_exit_test",
        title="Hidden Exit Test",
        starting_scene_id="room_a",
        scenes=[
            SceneDefinition(
                scene_id="room_a",
                name="Room A",
                description="A room with a secret.",
                exits=[
                    ExitDefinition(
                        exit_id="visible_exit",
                        direction="north",
                        target_scene_id="room_b",
                    ),
                    ExitDefinition(
                        exit_id="secret_exit",
                        direction="behind the tapestry",
                        target_scene_id="room_b",
                        is_hidden=True,
                    ),
                ],
            ),
            SceneDefinition(
                scene_id="room_b",
                name="Room B",
                description="Another room.",
                exits=[
                    ExitDefinition(
                        exit_id="b_to_a",
                        direction="south",
                        target_scene_id="room_a",
                    ),
                ],
            ),
        ],
    )


def make_manifest_with_hidden_item() -> ScenarioManifest:
    """Scenario with a hidden item for testing hidden fact generation."""
    return ScenarioManifest(
        scenario_id="hidden_item_test",
        title="Hidden Item Test",
        starting_scene_id="room_a",
        scenes=[
            SceneDefinition(
                scene_id="room_a",
                name="Room A",
                description="A dusty room.",
                item_ids=["visible_gem", "hidden_gem"],
            ),
        ],
        items=[
            ItemDefinition(
                item_id="visible_gem",
                name="Visible Gem",
                scene_id="room_a",
            ),
            ItemDefinition(
                item_id="hidden_gem",
                name="Hidden Gem",
                scene_id="room_a",
                is_hidden=True,
            ),
        ],
    )


def make_manifest_with_dead_end() -> ScenarioManifest:
    """Scene with no outbound exits."""
    return ScenarioManifest(
        scenario_id="dead_end",
        title="Dead End",
        starting_scene_id="room_a",
        scenes=[
            SceneDefinition(
                scene_id="room_a",
                name="Room A",
                description="Entry room.",
                exits=[
                    ExitDefinition(
                        exit_id="a_to_b",
                        direction="north",
                        target_scene_id="room_b",
                    ),
                ],
            ),
            SceneDefinition(
                scene_id="room_b",
                name="Dead End Room",
                description="No way out.",
            ),
        ],
    )


def make_manifest_with_orphan() -> ScenarioManifest:
    """Scene with no inbound exits (not the starting scene)."""
    return ScenarioManifest(
        scenario_id="orphan",
        title="Orphan",
        starting_scene_id="room_a",
        scenes=[
            SceneDefinition(
                scene_id="room_a",
                name="Room A",
                description="Start room.",
            ),
            SceneDefinition(
                scene_id="room_b",
                name="Orphan Room",
                description="Nobody leads here.",
                exits=[
                    ExitDefinition(
                        exit_id="b_to_a",
                        direction="south",
                        target_scene_id="room_a",
                    ),
                ],
            ),
        ],
    )


def make_manifest_with_invalid_enums() -> ScenarioManifest:
    """Monster with invalid behavior_mode."""
    return ScenarioManifest(
        scenario_id="bad_enums",
        title="Bad Enums",
        starting_scene_id="room_a",
        scenes=[
            SceneDefinition(
                scene_id="room_a",
                name="Room A",
                description="A room.",
                monster_ids=["bad_monster"],
            ),
        ],
        monsters=[
            MonsterDefinition(
                monster_id="bad_monster",
                unit_type="goblin",
                behavior_mode="nonexistent_mode",
                awareness_state="unaware",
                scene_id="room_a",
                territory_id="room_a",
            ),
        ],
    )


def make_manifest_with_triggers() -> ScenarioManifest:
    """Scenario with triggers for testing conversion."""
    return ScenarioManifest(
        scenario_id="trigger_test",
        title="Trigger Test",
        starting_scene_id="room_a",
        scenes=[
            SceneDefinition(
                scene_id="room_a",
                name="Room A",
                description="A room with triggers.",
                trigger_ids=["test_trigger"],
            ),
        ],
        triggers=[
            TriggerDefinition(
                trigger_id="test_trigger",
                kind="on_enter",
                scene_id="room_a",
                condition_type="first_visit",
                effect_type="narrate",
                effect_value="Welcome to Room A!",
                scope="public",
            ),
        ],
    )


def make_manifest_with_all_entity_types() -> ScenarioManifest:
    """Scenario exercising every entity type for round-trip testing."""
    return ScenarioManifest(
        scenario_id="full_test",
        title="Full Test",
        description="Tests every entity type.",
        version="2.0.0",
        author="test",
        starting_scene_id="room_a",
        scenes=[
            SceneDefinition(
                scene_id="room_a",
                name="Room A",
                description="Main room.",
                referee_notes="GM-only notes for Room A.",
                exits=[
                    ExitDefinition(
                        exit_id="a_to_b",
                        direction="north",
                        target_scene_id="room_b",
                    ),
                ],
                npc_ids=["npc_1"],
                monster_ids=["monster_1"],
                item_ids=["item_1"],
                puzzle_ids=["puzzle_1"],
                trigger_ids=["trigger_1"],
            ),
            SceneDefinition(
                scene_id="room_b",
                name="Room B",
                description="Secondary room.",
                exits=[
                    ExitDefinition(
                        exit_id="b_to_a",
                        direction="south",
                        target_scene_id="room_a",
                    ),
                ],
            ),
        ],
        npcs=[
            NpcDefinition(
                npc_id="npc_1",
                name="Test NPC",
                description="An NPC.",
                personality_tags=["friendly"],
                goals=["help adventurers"],
                faction="neutral",
                scene_id="room_a",
                inventory_item_ids=["item_1"],
                referee_notes="Secretly evil.",
                tells=[
                    NpcTellDefinition(
                        tell_id="tell_1",
                        trigger_type="trust_above",
                        trigger_value="30",
                        behavior="Smiles warmly.",
                        scope="public",
                    ),
                ],
            ),
        ],
        monsters=[
            MonsterDefinition(
                monster_id="monster_1",
                unit_type="goblin",
                count=3,
                behavior_mode="guard",
                awareness_state="unaware",
                stats={"attack": 5, "defense": 2, "hp_per_unit": 6},
                territory_id="room_a",
                scene_id="room_a",
                referee_notes="Patrol the room.",
            ),
        ],
        items=[
            ItemDefinition(
                item_id="item_1",
                name="Magic Sword",
                description="A glowing blade.",
                properties={"damage": "10"},
                scene_id="room_a",
            ),
        ],
        puzzles=[
            PuzzleDefinition(
                puzzle_id="puzzle_1",
                name="Riddle Door",
                description="A door with a riddle.",
                solution_hint="The answer is 'shadow'.",
                solution_actions=["say shadow"],
                success_text="The door swings open!",
                failure_text="Nothing happens.",
                scene_id="room_a",
                referee_notes="Classic puzzle.",
            ),
        ],
        quests=[
            QuestDefinition(
                quest_id="quest_1",
                title="Test Quest",
                description="Complete the test.",
                objectives=["Enter Room A", "Solve the puzzle"],
                completion_condition="puzzle_1 solved",
                referee_notes="Tutorial quest.",
            ),
        ],
        triggers=[
            TriggerDefinition(
                trigger_id="trigger_1",
                kind="on_enter",
                scene_id="room_a",
                condition_type="first_visit",
                effect_type="narrate",
                effect_value="You enter a mysterious room.",
                scope="public",
                referee_notes="Introductory narration.",
            ),
        ],
    )
