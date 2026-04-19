"""Tests for scenario authoring: schema, validation, visibility, and loader."""

from __future__ import annotations

import os
import tempfile

import pytest
import yaml

from server.domain.enums import (
    AwarenessState,
    BehaviorMode,
    KnowledgeFactType,
    SceneState,
    ScopeType,
)
from server.exploration.triggers import TriggerCondition, TriggerKind

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
from scenarios.validator import ScenarioValidator
from scenarios.visibility_rules import (
    HIDDEN_FIELDS,
    PUBLIC_FIELDS,
    REFEREE_ONLY_FIELDS,
    classify_field,
    validate_no_leakage,
)

from tests.fixtures.scenario_fixtures import (
    make_goblin_caves_manifest,
    make_invalid_manifest_broken_ref,
    make_invalid_manifest_duplicate_ids,
    make_manifest_with_all_entity_types,
    make_manifest_with_dead_end,
    make_manifest_with_hidden_exit,
    make_manifest_with_hidden_item,
    make_manifest_with_invalid_enums,
    make_manifest_with_leakage,
    make_manifest_with_orphan,
    make_manifest_with_triggers,
    make_minimal_manifest,
)


# ===================================================================
# Schema deserialization
# ===================================================================


class TestSchemaDeserialization:
    """YAML round-trips to dataclasses correctly."""

    def test_minimal_manifest_fields(self):
        m = make_minimal_manifest()
        assert m.scenario_id == "minimal_test"
        assert m.title == "Minimal Test Scenario"
        assert m.starting_scene_id == "room_a"
        assert len(m.scenes) == 2
        assert len(m.npcs) == 1
        assert len(m.items) == 1

    def test_scene_definition_fields(self):
        m = make_minimal_manifest()
        scene = m.scenes[0]
        assert scene.scene_id == "room_a"
        assert scene.name == "Room A"
        assert len(scene.exits) == 1
        assert scene.exits[0].exit_id == "a_to_b"

    def test_exit_definition_defaults(self):
        e = ExitDefinition(exit_id="x", direction="north", target_scene_id="s")
        assert e.is_hidden is False
        assert e.is_locked is False
        assert e.unlock_condition == ""

    def test_npc_definition_defaults(self):
        n = NpcDefinition(npc_id="n", name="N")
        assert n.personality_tags == []
        assert n.goals == []
        assert n.trust_initial == {}
        assert n.tells == []

    def test_monster_definition_defaults(self):
        m = MonsterDefinition(monster_id="m", unit_type="goblin")
        assert m.count == 1
        assert m.behavior_mode == "patrol"
        assert m.awareness_state == "unaware"

    def test_item_definition_defaults(self):
        i = ItemDefinition(item_id="i", name="I")
        assert i.is_hidden is False
        assert i.is_key is False
        assert i.quantity == 1

    def test_puzzle_definition_defaults(self):
        p = PuzzleDefinition(puzzle_id="p", name="P")
        assert p.max_attempts == 0
        assert p.solution_actions == []

    def test_quest_definition_defaults(self):
        q = QuestDefinition(quest_id="q", title="Q")
        assert q.objectives == []
        assert q.completion_condition == ""

    def test_trigger_definition_defaults(self):
        t = TriggerDefinition(trigger_id="t", kind="on_enter")
        assert t.condition_type == "always"
        assert t.scope == "public"
        assert t.is_repeatable is False

    def test_npc_tell_definition(self):
        tell = NpcTellDefinition(
            tell_id="t1",
            trigger_type="trust_above",
            trigger_value="30",
            behavior="smiles",
            scope="public",
        )
        assert tell.scope == "public"

    def test_yaml_round_trip(self):
        """Write a manifest to YAML and read it back."""
        m = make_minimal_manifest()
        loader = ScenarioLoader()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            yaml.dump(
                {
                    "scenario_id": m.scenario_id,
                    "title": m.title,
                    "description": m.description,
                    "starting_scene_id": m.starting_scene_id,
                    "scenes": [
                        {
                            "scene_id": s.scene_id,
                            "name": s.name,
                            "description": s.description,
                            "exits": [
                                {
                                    "exit_id": e.exit_id,
                                    "direction": e.direction,
                                    "target_scene_id": e.target_scene_id,
                                }
                                for e in s.exits
                            ],
                            "npc_ids": s.npc_ids,
                            "item_ids": s.item_ids,
                        }
                        for s in m.scenes
                    ],
                    "npcs": [
                        {"npc_id": n.npc_id, "name": n.name, "scene_id": n.scene_id}
                        for n in m.npcs
                    ],
                    "items": [
                        {"item_id": i.item_id, "name": i.name, "scene_id": i.scene_id}
                        for i in m.items
                    ],
                },
                f,
            )
            tmppath = f.name

        try:
            result = loader.load_from_yaml(tmppath)
            assert result.success
            assert len(result.scenes) == 2
        finally:
            os.unlink(tmppath)

    def test_missing_required_field_raises(self):
        loader = ScenarioLoader()
        # scenario_id is required
        with pytest.raises(KeyError):
            loader._deserialize({"title": "no id"})

    def test_extra_fields_ignored(self):
        loader = ScenarioLoader()
        data = {
            "scenario_id": "test",
            "title": "Test",
            "starting_scene_id": "room_a",
            "extra_unknown_field": "ignored",
            "scenes": [
                {
                    "scene_id": "room_a",
                    "name": "A",
                    "unknown": True,
                }
            ],
        }
        m = loader._deserialize(data)
        assert m.scenario_id == "test"


# ===================================================================
# Validation — IDs
# ===================================================================


class TestValidationIds:
    def test_unique_ids_pass(self):
        m = make_minimal_manifest()
        v = ScenarioValidator()
        result = v.validate(m)
        assert result.is_valid

    def test_duplicate_item_ids_error(self):
        m = make_invalid_manifest_duplicate_ids()
        v = ScenarioValidator()
        result = v.validate(m)
        assert not result.is_valid
        assert any("Duplicate ID" in e and "dupe_item" in e for e in result.errors)

    def test_duplicate_across_entity_types(self):
        m = ScenarioManifest(
            scenario_id="dup_cross",
            title="Dup Cross",
            starting_scene_id="shared_id",
            scenes=[
                SceneDefinition(
                    scene_id="shared_id",
                    name="A",
                    description="A",
                    npc_ids=["shared_id"],
                ),
            ],
            npcs=[NpcDefinition(npc_id="shared_id", name="NPC", scene_id="shared_id")],
        )
        v = ScenarioValidator()
        result = v.validate(m)
        assert not result.is_valid
        assert any("Duplicate ID" in e for e in result.errors)


# ===================================================================
# Validation — references
# ===================================================================


class TestValidationReferences:
    def test_valid_references_pass(self):
        m = make_minimal_manifest()
        v = ScenarioValidator()
        result = v.validate(m)
        assert result.is_valid

    def test_invalid_exit_target(self):
        m = make_invalid_manifest_broken_ref()
        v = ScenarioValidator()
        result = v.validate(m)
        assert not result.is_valid
        assert any("nonexistent_room" in e for e in result.errors)

    def test_invalid_npc_scene_id(self):
        m = ScenarioManifest(
            scenario_id="bad_npc",
            title="Bad NPC",
            starting_scene_id="room_a",
            scenes=[
                SceneDefinition(scene_id="room_a", name="A", description="A"),
            ],
            npcs=[
                NpcDefinition(npc_id="n1", name="N", scene_id="nonexistent"),
            ],
        )
        v = ScenarioValidator()
        result = v.validate(m)
        assert not result.is_valid
        assert any("nonexistent" in e for e in result.errors)

    def test_invalid_npc_inventory_item(self):
        m = ScenarioManifest(
            scenario_id="bad_inv",
            title="Bad Inv",
            starting_scene_id="room_a",
            scenes=[
                SceneDefinition(scene_id="room_a", name="A", description="A"),
            ],
            npcs=[
                NpcDefinition(
                    npc_id="n1",
                    name="N",
                    scene_id="room_a",
                    inventory_item_ids=["fake_item"],
                ),
            ],
        )
        v = ScenarioValidator()
        result = v.validate(m)
        assert not result.is_valid
        assert any("fake_item" in e for e in result.errors)

    def test_invalid_monster_scene_id(self):
        m = ScenarioManifest(
            scenario_id="bad_mon",
            title="Bad Mon",
            starting_scene_id="room_a",
            scenes=[
                SceneDefinition(
                    scene_id="room_a",
                    name="A",
                    description="A",
                    monster_ids=["m1"],
                ),
            ],
            monsters=[
                MonsterDefinition(
                    monster_id="m1",
                    unit_type="goblin",
                    scene_id="nonexistent",
                    territory_id="room_a",
                ),
            ],
        )
        v = ScenarioValidator()
        result = v.validate(m)
        assert not result.is_valid

    def test_invalid_monster_territory_id(self):
        m = ScenarioManifest(
            scenario_id="bad_terr",
            title="Bad Terr",
            starting_scene_id="room_a",
            scenes=[
                SceneDefinition(
                    scene_id="room_a",
                    name="A",
                    description="A",
                    monster_ids=["m1"],
                ),
            ],
            monsters=[
                MonsterDefinition(
                    monster_id="m1",
                    unit_type="goblin",
                    scene_id="room_a",
                    territory_id="nonexistent",
                ),
            ],
        )
        v = ScenarioValidator()
        result = v.validate(m)
        assert not result.is_valid

    def test_invalid_trigger_scene_id(self):
        m = ScenarioManifest(
            scenario_id="bad_trig",
            title="Bad Trig",
            starting_scene_id="room_a",
            scenes=[
                SceneDefinition(
                    scene_id="room_a",
                    name="A",
                    description="A",
                    trigger_ids=["t1"],
                ),
            ],
            triggers=[
                TriggerDefinition(
                    trigger_id="t1",
                    kind="on_enter",
                    scene_id="nonexistent",
                ),
            ],
        )
        v = ScenarioValidator()
        result = v.validate(m)
        assert not result.is_valid

    def test_invalid_puzzle_scene_id(self):
        m = ScenarioManifest(
            scenario_id="bad_puz",
            title="Bad Puz",
            starting_scene_id="room_a",
            scenes=[
                SceneDefinition(
                    scene_id="room_a",
                    name="A",
                    description="A",
                    puzzle_ids=["p1"],
                ),
            ],
            puzzles=[
                PuzzleDefinition(
                    puzzle_id="p1",
                    name="P",
                    scene_id="nonexistent",
                ),
            ],
        )
        v = ScenarioValidator()
        result = v.validate(m)
        assert not result.is_valid

    def test_scene_references_nonexistent_npc(self):
        m = ScenarioManifest(
            scenario_id="missing_npc",
            title="Missing NPC",
            starting_scene_id="room_a",
            scenes=[
                SceneDefinition(
                    scene_id="room_a",
                    name="A",
                    description="A",
                    npc_ids=["ghost_npc"],
                ),
            ],
        )
        v = ScenarioValidator()
        result = v.validate(m)
        assert not result.is_valid
        assert any("ghost_npc" in e for e in result.errors)

    def test_scene_references_nonexistent_item(self):
        m = ScenarioManifest(
            scenario_id="missing_item",
            title="Missing Item",
            starting_scene_id="room_a",
            scenes=[
                SceneDefinition(
                    scene_id="room_a",
                    name="A",
                    description="A",
                    item_ids=["ghost_item"],
                ),
            ],
        )
        v = ScenarioValidator()
        result = v.validate(m)
        assert not result.is_valid

    def test_item_unlocks_nonexistent_exit(self):
        m = ScenarioManifest(
            scenario_id="bad_unlock",
            title="Bad Unlock",
            starting_scene_id="room_a",
            scenes=[
                SceneDefinition(scene_id="room_a", name="A", description="A"),
            ],
            items=[
                ItemDefinition(
                    item_id="key1",
                    name="Key",
                    unlocks_exit_ids=["nonexistent_exit"],
                    scene_id="room_a",
                ),
            ],
        )
        v = ScenarioValidator()
        result = v.validate(m)
        assert not result.is_valid


# ===================================================================
# Validation — starting scene
# ===================================================================


class TestValidationStartingScene:
    def test_valid_starting_scene(self):
        m = make_minimal_manifest()
        v = ScenarioValidator()
        result = v.validate(m)
        assert result.is_valid

    def test_missing_starting_scene(self):
        m = ScenarioManifest(
            scenario_id="no_start",
            title="No Start",
            starting_scene_id="nonexistent",
            scenes=[
                SceneDefinition(scene_id="room_a", name="A", description="A"),
            ],
        )
        v = ScenarioValidator()
        result = v.validate(m)
        assert not result.is_valid
        assert any("starting_scene_id" in e for e in result.errors)

    def test_empty_starting_scene_id(self):
        m = ScenarioManifest(
            scenario_id="empty_start",
            title="Empty Start",
            starting_scene_id="",
            scenes=[
                SceneDefinition(scene_id="room_a", name="A", description="A"),
            ],
        )
        v = ScenarioValidator()
        result = v.validate(m)
        assert not result.is_valid


# ===================================================================
# Validation — orphan / dead-end scenes
# ===================================================================


class TestValidationOrphanDeadEnd:
    def test_orphan_scene_warning(self):
        m = make_manifest_with_orphan()
        v = ScenarioValidator()
        result = v.validate(m)
        assert result.is_valid  # warnings don't block
        assert any("Orphan" in w for w in result.warnings)

    def test_dead_end_scene_warning(self):
        m = make_manifest_with_dead_end()
        v = ScenarioValidator()
        result = v.validate(m)
        assert result.is_valid
        assert any("Dead-end" in w for w in result.warnings)

    def test_starting_scene_not_flagged_as_orphan(self):
        """Starting scene should never be flagged as orphan."""
        m = ScenarioManifest(
            scenario_id="start_only",
            title="Start Only",
            starting_scene_id="room_a",
            scenes=[
                SceneDefinition(scene_id="room_a", name="A", description="A"),
            ],
        )
        v = ScenarioValidator()
        result = v.validate(m)
        assert not any("Orphan" in w and "room_a" in w for w in result.warnings)


# ===================================================================
# Validation — enums
# ===================================================================


class TestValidationEnums:
    def test_valid_enums_pass(self):
        m = make_manifest_with_all_entity_types()
        v = ScenarioValidator()
        result = v.validate(m)
        assert result.is_valid

    def test_invalid_behavior_mode(self):
        m = make_manifest_with_invalid_enums()
        v = ScenarioValidator()
        result = v.validate(m)
        assert not result.is_valid
        assert any("behavior_mode" in e for e in result.errors)

    def test_invalid_trigger_kind(self):
        m = ScenarioManifest(
            scenario_id="bad_kind",
            title="Bad Kind",
            starting_scene_id="room_a",
            scenes=[
                SceneDefinition(
                    scene_id="room_a",
                    name="A",
                    description="A",
                    trigger_ids=["t1"],
                ),
            ],
            triggers=[
                TriggerDefinition(
                    trigger_id="t1",
                    kind="nonexistent_kind",
                    scene_id="room_a",
                ),
            ],
        )
        v = ScenarioValidator()
        result = v.validate(m)
        assert not result.is_valid

    def test_invalid_tell_scope(self):
        m = ScenarioManifest(
            scenario_id="bad_tell",
            title="Bad Tell",
            starting_scene_id="room_a",
            scenes=[
                SceneDefinition(
                    scene_id="room_a",
                    name="A",
                    description="A",
                    npc_ids=["n1"],
                ),
            ],
            npcs=[
                NpcDefinition(
                    npc_id="n1",
                    name="N",
                    scene_id="room_a",
                    tells=[
                        NpcTellDefinition(
                            tell_id="t1",
                            trigger_type="trust_above",
                            scope="invalid_scope",
                        ),
                    ],
                ),
            ],
        )
        v = ScenarioValidator()
        result = v.validate(m)
        assert not result.is_valid


# ===================================================================
# Validation — visibility / leakage
# ===================================================================


class TestValidationVisibility:
    def test_no_leakage_clean(self):
        m = make_minimal_manifest()
        warnings = validate_no_leakage(m)
        assert warnings == []

    def test_leakage_detected(self):
        m = make_manifest_with_leakage()
        warnings = validate_no_leakage(m)
        assert len(warnings) > 0
        assert any("Leakage" in w for w in warnings)

    def test_leakage_in_validation_result(self):
        m = make_manifest_with_leakage()
        v = ScenarioValidator()
        result = v.validate(m)
        assert result.is_valid  # leakage is a warning, not an error
        assert any("Leakage" in w for w in result.warnings)


# ===================================================================
# Visibility policy — classify_field
# ===================================================================


class TestClassifyField:
    def test_referee_notes_is_referee_only(self):
        assert (
            classify_field("scene", "referee_notes", "text") == ScopeType.referee_only
        )

    def test_solution_hint_is_referee_only(self):
        assert (
            classify_field("puzzle", "solution_hint", "hint") == ScopeType.referee_only
        )

    def test_solution_actions_is_referee_only(self):
        assert (
            classify_field("puzzle", "solution_actions", []) == ScopeType.referee_only
        )

    def test_description_is_public(self):
        assert classify_field("scene", "description", "text") == ScopeType.public

    def test_name_is_public(self):
        assert classify_field("item", "name", "Sword") == ScopeType.public

    def test_is_hidden_true_is_private(self):
        assert classify_field("item", "is_hidden", True) == ScopeType.private_referee

    def test_is_hidden_false_is_public(self):
        assert classify_field("item", "is_hidden", False) == ScopeType.public

    def test_referee_only_fields_set(self):
        assert "referee_notes" in REFEREE_ONLY_FIELDS
        assert "solution_hint" in REFEREE_ONLY_FIELDS

    def test_public_fields_set(self):
        assert "description" in PUBLIC_FIELDS
        assert "name" in PUBLIC_FIELDS

    def test_hidden_fields_set(self):
        assert "is_hidden" in HIDDEN_FIELDS


# ===================================================================
# Validation — puzzle solvability
# ===================================================================


class TestPuzzleSolvability:
    def test_puzzle_with_valid_effects(self):
        m = make_manifest_with_all_entity_types()
        v = ScenarioValidator()
        result = v.validate(m)
        assert result.is_valid

    def test_puzzle_with_invalid_unlock_ref(self):
        m = ScenarioManifest(
            scenario_id="bad_puzzle_effect",
            title="Bad Puzzle Effect",
            starting_scene_id="room_a",
            scenes=[
                SceneDefinition(
                    scene_id="room_a",
                    name="A",
                    description="A",
                    puzzle_ids=["p1"],
                ),
            ],
            puzzles=[
                PuzzleDefinition(
                    puzzle_id="p1",
                    name="P",
                    scene_id="room_a",
                    effects_on_solve=["unlock:nonexistent_exit"],
                ),
            ],
        )
        v = ScenarioValidator()
        result = v.validate(m)
        assert any("nonexistent_exit" in w for w in result.warnings)


# ===================================================================
# Loader — basic loading
# ===================================================================


class TestLoader:
    def test_load_minimal_manifest(self):
        m = make_minimal_manifest()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        assert result.success
        assert len(result.scenes) == 2
        assert len(result.npcs) == 1
        assert len(result.items) == 1

    def test_load_goblin_caves(self):
        m = make_goblin_caves_manifest()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        assert result.success
        assert len(result.scenes) == 4
        assert len(result.npcs) == 2
        assert len(result.monster_groups) == 2
        assert len(result.items) == 7
        assert len(result.puzzles) == 2
        assert len(result.quests) == 2
        assert len(result.triggers) == 2

    def test_starting_scene_is_cave_entrance(self):
        m = make_goblin_caves_manifest()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        scene_ids = [s.scene_id for s in result.scenes]
        assert "cave_entrance" in scene_ids

    def test_campaign_id_generated(self):
        m = make_minimal_manifest()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        assert result.campaign_id
        assert len(result.campaign_id) > 0

    def test_scene_state_is_idle(self):
        m = make_minimal_manifest()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        for scene in result.scenes:
            assert scene.state == SceneState.idle

    def test_scene_exits_populated(self):
        m = make_minimal_manifest()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        room_a = [s for s in result.scenes if s.scene_id == "room_a"][0]
        assert "north" in room_a.exits
        assert room_a.exits["north"] == "room_b"


# ===================================================================
# Loader — facts
# ===================================================================


class TestLoaderFacts:
    def test_referee_notes_produce_facts(self):
        m = make_manifest_with_all_entity_types()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        referee_facts = [
            f for f in result.knowledge_facts if f.fact_type == KnowledgeFactType.lore
        ]
        assert len(referee_facts) > 0

    def test_hidden_exit_produces_fact(self):
        m = make_manifest_with_hidden_exit()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        hidden_facts = [
            f
            for f in result.knowledge_facts
            if f.fact_type == KnowledgeFactType.hidden_object
        ]
        assert len(hidden_facts) >= 1
        assert any(
            "secret_exit" in f.payload or "Hidden exit" in f.payload
            for f in hidden_facts
        )

    def test_hidden_item_produces_fact(self):
        m = make_manifest_with_hidden_item()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        hidden_facts = [
            f
            for f in result.knowledge_facts
            if f.fact_type == KnowledgeFactType.hidden_object
        ]
        assert len(hidden_facts) >= 1
        assert any("hidden_gem" in f.payload for f in hidden_facts)

    def test_puzzle_solution_hint_produces_fact(self):
        m = make_manifest_with_all_entity_types()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        hint_facts = [f for f in result.knowledge_facts if "hint" in f.payload.lower()]
        assert len(hint_facts) >= 1

    def test_all_facts_have_referee_scope(self):
        m = make_manifest_with_all_entity_types()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        referee_scope = [
            s for s in result.scopes if s.scope_type == ScopeType.referee_only
        ]
        assert len(referee_scope) == 1
        referee_scope_id = referee_scope[0].scope_id
        for fact in result.knowledge_facts:
            assert fact.owner_scope_id == referee_scope_id

    def test_goblin_caves_fact_count(self):
        """Goblin caves should produce facts for referee notes + hidden exit."""
        m = make_goblin_caves_manifest()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        # At minimum: 4 scene referee_notes + 2 NPC referee_notes +
        # 2 monster referee_notes + 4 puzzle referee_notes/hints +
        # 2 quest referee_notes + 2 trigger referee_notes + 1 hidden exit
        assert len(result.knowledge_facts) >= 15


# ===================================================================
# Loader — scopes
# ===================================================================


class TestLoaderScopes:
    def test_each_scene_gets_public_scope(self):
        m = make_minimal_manifest()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        public_scopes = [s for s in result.scopes if s.scope_type == ScopeType.public]
        assert len(public_scopes) == 2  # one per scene

    def test_referee_scope_created(self):
        m = make_minimal_manifest()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        referee_scopes = [
            s for s in result.scopes if s.scope_type == ScopeType.referee_only
        ]
        assert len(referee_scopes) == 1

    def test_all_scopes_have_campaign_id(self):
        m = make_minimal_manifest()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        for scope in result.scopes:
            assert scope.campaign_id == result.campaign_id


# ===================================================================
# Loader — error handling
# ===================================================================


class TestLoaderErrors:
    def test_malformed_yaml(self):
        loader = ScenarioLoader()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write("{{invalid yaml: [")
            tmppath = f.name

        try:
            result = loader.load_from_yaml(tmppath)
            assert not result.success
            assert len(result.errors) > 0
        finally:
            os.unlink(tmppath)

    def test_nonexistent_file(self):
        loader = ScenarioLoader()
        result = loader.load_from_yaml("/nonexistent/path.yaml")
        assert not result.success

    def test_broken_ref_returns_errors(self):
        m = make_invalid_manifest_broken_ref()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        assert not result.success
        assert len(result.errors) > 0

    def test_duplicate_ids_returns_errors(self):
        m = make_invalid_manifest_duplicate_ids()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        assert not result.success


# ===================================================================
# Loader — entity conversion details
# ===================================================================


class TestLoaderConversion:
    def test_npc_conversion_fields(self):
        m = make_manifest_with_all_entity_types()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        npc = result.npcs[0]
        assert npc.npc_id == "npc_1"
        assert npc.name == "Test NPC"
        assert npc.scene_id == "room_a"
        assert "friendly" in npc.personality_tags
        assert "help adventurers" in npc.goal_tags

    def test_monster_conversion_fields(self):
        m = make_manifest_with_all_entity_types()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        mg = result.monster_groups[0]
        assert mg.monster_group_id == "monster_1"
        assert mg.unit_type == "goblin"
        assert mg.count == 3
        assert mg.behavior_mode == BehaviorMode.guard
        assert mg.awareness_state == AwarenessState.unaware

    def test_item_conversion_fields(self):
        m = make_manifest_with_all_entity_types()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        item = result.items[0]
        assert item.item_id == "item_1"
        assert item.name == "Magic Sword"
        assert item.properties == {"damage": "10"}

    def test_puzzle_conversion(self):
        m = make_manifest_with_all_entity_types()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        puzzle = result.puzzles[0]
        assert puzzle.puzzle_id == "puzzle_1"
        assert puzzle.scene_id == "room_a"

    def test_quest_conversion(self):
        m = make_manifest_with_all_entity_types()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        quest = result.quests[0]
        assert quest.quest_id == "quest_1"

    def test_trigger_conversion(self):
        m = make_manifest_with_triggers()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        assert len(result.triggers) == 1
        trigger = result.triggers[0]
        assert trigger.trigger_id == "test_trigger"
        assert trigger.kind == TriggerKind.on_enter
        assert trigger.condition == TriggerCondition.once

    def test_hidden_exit_not_in_scene_exits(self):
        """Hidden exits should not appear in the scene's visible exits dict."""
        m = make_manifest_with_hidden_exit()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        room_a = [s for s in result.scenes if s.scene_id == "room_a"][0]
        assert "north" in room_a.exits
        assert "behind the tapestry" not in room_a.exits

    def test_scene_hidden_description_from_referee_notes(self):
        m = make_manifest_with_all_entity_types()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        room_a = [s for s in result.scenes if s.scene_id == "room_a"][0]
        assert room_a.hidden_description == "GM-only notes for Room A."

    def test_npc_faction_mapped(self):
        m = make_manifest_with_all_entity_types()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        npc = result.npcs[0]
        assert npc.faction_id == "neutral"


# ===================================================================
# Full round-trip: goblin caves YAML
# ===================================================================


class TestFullRoundTrip:
    def test_goblin_caves_yaml_loads(self):
        yaml_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "scenarios",
            "starters",
            "goblin_caves.yaml",
        )
        yaml_path = os.path.abspath(yaml_path)
        loader = ScenarioLoader()
        result = loader.load_from_yaml(yaml_path)
        assert result.success, f"Errors: {result.errors}"

    def test_goblin_caves_scene_count(self):
        m = make_goblin_caves_manifest()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        assert len(result.scenes) == 4

    def test_goblin_caves_npc_count(self):
        m = make_goblin_caves_manifest()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        assert len(result.npcs) == 2

    def test_goblin_caves_item_count(self):
        m = make_goblin_caves_manifest()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        assert len(result.items) == 7

    def test_goblin_caves_quest_count(self):
        m = make_goblin_caves_manifest()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        assert len(result.quests) == 2

    def test_goblin_caves_trigger_count(self):
        m = make_goblin_caves_manifest()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        assert len(result.triggers) == 2

    def test_goblin_caves_monster_count(self):
        m = make_goblin_caves_manifest()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        assert len(result.monster_groups) == 2

    def test_goblin_caves_puzzle_count(self):
        m = make_goblin_caves_manifest()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        assert len(result.puzzles) == 2

    def test_goblin_caves_scope_count(self):
        """4 scenes = 4 public scopes + 1 referee = 5 total."""
        m = make_goblin_caves_manifest()
        loader = ScenarioLoader()
        result = loader.load_from_manifest(m)
        assert len(result.scopes) == 5
