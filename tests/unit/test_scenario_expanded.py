"""Expanded scenario tests — new scenarios, puzzle patterns, archetypes,
monster templates, extended validation, and long-session regression.
"""

from __future__ import annotations

import os

import pytest

from scenarios.archetypes import (
    ALL_ARCHETYPES,
    ALL_TEMPLATES,
    BANDIT_GROUP,
    COWARDLY_MINION,
    GOBLIN_PATROL,
    LOYAL_GUARD,
    MYSTERIOUS_SAGE,
    SKELETON_GUARD,
    SPIDER_SWARM,
    SUSPICIOUS_MERCHANT,
    WOLF_PACK,
    get_archetype,
    get_template,
)
from scenarios.loader import ScenarioLoader
from scenarios.puzzle_patterns import (
    ALL_PATTERNS,
    COMBINATION_LOCK,
    KEY_AND_LOCK,
    LEVER_SEQUENCE,
    MULTI_ROOM_ASSEMBLY,
    RIDDLE_DOOR,
    get_pattern,
)
from scenarios.schema import (
    ExitDefinition,
    ItemDefinition,
    QuestDefinition,
    ScenarioManifest,
    SceneDefinition,
    TriggerDefinition,
)
from scenarios.validator import ScenarioValidator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STARTERS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "scenarios", "starters"
)


def _load_yaml_scenario(filename: str):
    """Load a scenario from the starters directory."""
    loader = ScenarioLoader()
    path = os.path.normpath(os.path.join(STARTERS_DIR, filename))
    return loader.load_from_yaml(path)


# ---------------------------------------------------------------------------
# New scenario load tests
# ---------------------------------------------------------------------------


class TestHauntedManorLoads:
    def test_haunted_manor_loads_successfully(self):
        result = _load_yaml_scenario("haunted_manor.yaml")
        assert result.success, f"Load errors: {result.errors}"

    def test_haunted_manor_has_correct_scene_count(self):
        result = _load_yaml_scenario("haunted_manor.yaml")
        assert len(result.scenes) == 5

    def test_haunted_manor_has_correct_npc_count(self):
        result = _load_yaml_scenario("haunted_manor.yaml")
        assert len(result.npcs) == 2

    def test_haunted_manor_puzzle_chain_valid(self):
        """The bookshelf cipher requires both cipher fragments."""
        result = _load_yaml_scenario("haunted_manor.yaml")
        assert result.success
        item_ids = {i.item_id for i in result.items}
        assert "cipher_fragment_a" in item_ids
        assert "cipher_fragment_b" in item_ids
        puzzle_ids = {p.puzzle_id for p in result.puzzles}
        assert "bookshelf_cipher" in puzzle_ids
        assert "clock_puzzle" in puzzle_ids


class TestForestAmbushLoads:
    def test_forest_ambush_loads_successfully(self):
        result = _load_yaml_scenario("forest_ambush.yaml")
        assert result.success, f"Load errors: {result.errors}"

    def test_forest_ambush_has_correct_scene_count(self):
        result = _load_yaml_scenario("forest_ambush.yaml")
        assert len(result.scenes) == 3

    def test_forest_ambush_combat_groups_valid(self):
        """Scenario has multiple monster groups with varied behavior."""
        result = _load_yaml_scenario("forest_ambush.yaml")
        assert result.success
        assert len(result.monster_groups) == 3
        unit_types = {mg.unit_type for mg in result.monster_groups}
        assert "bandit_scout" in unit_types
        assert "bandit" in unit_types
        assert "wolf" in unit_types


class TestMerchantQuarterLoads:
    def test_merchant_quarter_loads_successfully(self):
        result = _load_yaml_scenario("merchant_quarter.yaml")
        assert result.success, f"Load errors: {result.errors}"

    def test_merchant_quarter_has_correct_scene_count(self):
        result = _load_yaml_scenario("merchant_quarter.yaml")
        assert len(result.scenes) == 4

    def test_merchant_quarter_multiple_quest_paths(self):
        """The necklace quest can be solved multiple ways."""
        result = _load_yaml_scenario("merchant_quarter.yaml")
        assert result.success
        assert len(result.npcs) == 3  # Elara, Kel, Holt
        quest_ids = {q.quest_id for q in result.quests}
        assert "find_necklace" in quest_ids


# ---------------------------------------------------------------------------
# Puzzle pattern tests
# ---------------------------------------------------------------------------


class TestPuzzlePatterns:
    def test_combination_lock_pattern(self):
        puzzle = COMBINATION_LOCK.instantiate(
            components={"lock_object_id": "chest_01", "clue_item_ids": "clue_a,clue_b"},
            scene_id="room_1",
        )
        assert puzzle.puzzle_id == "combination_lock_room_1"
        assert "chest_01" in puzzle.solution_hint
        assert puzzle.scene_id == "room_1"

    def test_lever_sequence_pattern(self):
        puzzle = LEVER_SEQUENCE.instantiate(
            components={"lever_object_ids": "lev_1,lev_2", "correct_sequence": "2,1"},
            scene_id="hall",
        )
        assert "lev_1,lev_2" in puzzle.solution_hint
        assert "2,1" in puzzle.solution_hint

    def test_key_and_lock_pattern(self):
        puzzle = KEY_AND_LOCK.instantiate(
            components={"key_item_id": "gold_key", "locked_exit_id": "gate_01"},
            scene_id="entrance",
        )
        assert "gold_key" in puzzle.solution_hint
        assert "gate_01" in puzzle.solution_hint

    def test_riddle_door_pattern(self):
        puzzle = RIDDLE_DOOR.instantiate(
            components={
                "riddle_text": "What has keys but no locks?",
                "answer_text": "a piano",
                "exit_id": "riddle_gate",
            },
            scene_id="passage",
        )
        assert "piano" in puzzle.solution_hint

    def test_multi_room_assembly_pattern(self):
        puzzle = MULTI_ROOM_ASSEMBLY.instantiate(
            components={
                "room_ids": "room_a,room_b",
                "clue_fact_ids": "fact_1,fact_2",
                "final_puzzle_id": "master_lock",
            },
            scene_id="finale",
        )
        assert "master_lock" in puzzle.solution_hint

    def test_pattern_missing_component_raises(self):
        with pytest.raises(ValueError, match="missing components"):
            KEY_AND_LOCK.instantiate(
                components={"key_item_id": "key_1"},  # missing locked_exit_id
                scene_id="room",
            )

    def test_pattern_registry_complete(self):
        assert len(ALL_PATTERNS) == 5
        assert get_pattern("combination_lock") is COMBINATION_LOCK
        assert get_pattern("key_and_lock") is KEY_AND_LOCK

    def test_pattern_registry_missing_raises(self):
        with pytest.raises(KeyError):
            get_pattern("nonexistent_pattern")


# ---------------------------------------------------------------------------
# Archetype tests
# ---------------------------------------------------------------------------


class TestNpcArchetypes:
    def test_suspicious_merchant_archetype_valid(self):
        npc = SUSPICIOUS_MERCHANT.instantiate(
            npc_id="merchant_1", name="Shady Pete", scene_id="market"
        )
        assert npc.npc_id == "merchant_1"
        assert "cautious" in npc.personality_tags
        assert len(npc.tells) == 2

    def test_loyal_guard_archetype_valid(self):
        npc = LOYAL_GUARD.instantiate(
            npc_id="guard_1", name="Sir Reginald", scene_id="gate"
        )
        assert "dutiful" in npc.personality_tags
        assert len(npc.tells) == 2

    def test_mysterious_sage_archetype_valid(self):
        npc = MYSTERIOUS_SAGE.instantiate(
            npc_id="sage_1", name="Elder Moss", scene_id="tower"
        )
        assert "cryptic" in npc.personality_tags
        assert len(npc.tells) == 1

    def test_cowardly_minion_archetype_valid(self):
        npc = COWARDLY_MINION.instantiate(
            npc_id="minion_1", name="Snitch", scene_id="dungeon"
        )
        assert "fearful" in npc.personality_tags

    def test_all_archetypes_produce_valid_npcs(self):
        for arch_id, archetype in ALL_ARCHETYPES.items():
            npc = archetype.instantiate(
                npc_id=f"test_{arch_id}",
                name=f"Test {arch_id}",
                scene_id="test_scene",
            )
            assert npc.npc_id == f"test_{arch_id}"
            assert len(npc.personality_tags) > 0
            assert len(npc.goals) > 0

    def test_archetype_with_overrides(self):
        npc = SUSPICIOUS_MERCHANT.instantiate(
            npc_id="custom_1",
            name="Custom Merchant",
            scene_id="shop",
            description="A custom description",
            faction="guild",
        )
        assert npc.description == "A custom description"
        assert npc.faction == "guild"

    def test_archetype_registry_complete(self):
        assert len(ALL_ARCHETYPES) == 4
        assert get_archetype("loyal_guard") is LOYAL_GUARD

    def test_archetype_registry_missing_raises(self):
        with pytest.raises(KeyError):
            get_archetype("nonexistent_archetype")


# ---------------------------------------------------------------------------
# Monster template tests
# ---------------------------------------------------------------------------


class TestMonsterTemplates:
    def test_goblin_patrol_template(self):
        monster = GOBLIN_PATROL.instantiate(
            monster_id="gob_01", scene_id="cave", count=3
        )
        assert monster.unit_type == "goblin"
        assert monster.behavior_mode == "patrol"
        assert monster.count == 3

    def test_skeleton_guard_template(self):
        monster = SKELETON_GUARD.instantiate(
            monster_id="skel_01", scene_id="crypt", count=2
        )
        assert monster.unit_type == "skeleton"
        assert "immune_to_morale" in monster.special_rules

    def test_wolf_pack_template(self):
        monster = WOLF_PACK.instantiate(
            monster_id="wolves_01", scene_id="forest", count=4
        )
        assert monster.unit_type == "wolf"
        assert monster.behavior_mode == "pursue"

    def test_bandit_group_template(self):
        monster = BANDIT_GROUP.instantiate(
            monster_id="bandits_01", scene_id="road", count=5
        )
        assert "leader_dead_routs" in monster.special_rules

    def test_spider_swarm_template(self):
        monster = SPIDER_SWARM.instantiate(
            monster_id="spiders_01", scene_id="web_nest", count=6
        )
        assert "poison_bite" in monster.special_rules

    def test_all_templates_produce_valid_groups(self):
        for tmpl_id, template in ALL_TEMPLATES.items():
            monster = template.instantiate(
                monster_id=f"test_{tmpl_id}",
                scene_id="test_scene",
                count=2,
            )
            assert monster.monster_id == f"test_{tmpl_id}"
            assert monster.count == 2
            assert len(monster.stats) > 0

    def test_template_with_overrides(self):
        monster = GOBLIN_PATROL.instantiate(
            monster_id="custom_gob",
            scene_id="custom_cave",
            count=1,
            behavior_mode="guard",
            awareness_state="alert",
        )
        assert monster.behavior_mode == "guard"
        assert monster.awareness_state == "alert"

    def test_template_registry_complete(self):
        assert len(ALL_TEMPLATES) == 5
        assert get_template("wolf_pack") is WOLF_PACK

    def test_template_registry_missing_raises(self):
        with pytest.raises(KeyError):
            get_template("nonexistent_template")


# ---------------------------------------------------------------------------
# Extended validation tests
# ---------------------------------------------------------------------------


class TestExtendedValidation:
    def test_quest_completability_check_warns_on_empty(self):
        """A quest with no completion_condition should produce a warning."""
        manifest = ScenarioManifest(
            scenario_id="test_quest",
            title="Test",
            starting_scene_id="room_a",
            scenes=[
                SceneDefinition(
                    scene_id="room_a",
                    name="Room A",
                    exits=[
                        ExitDefinition(
                            exit_id="a_b", direction="n", target_scene_id="room_b"
                        )
                    ],
                ),
                SceneDefinition(
                    scene_id="room_b",
                    name="Room B",
                    exits=[
                        ExitDefinition(
                            exit_id="b_a", direction="s", target_scene_id="room_a"
                        )
                    ],
                ),
            ],
            quests=[
                QuestDefinition(
                    quest_id="no_condition",
                    title="Missing Condition",
                    completion_condition="",
                ),
            ],
        )
        validator = ScenarioValidator()
        result = validator.validate(manifest)
        assert any("no completion_condition" in w for w in result.warnings)

    def test_item_accessibility_check_warns(self):
        """Key behind the exit it unlocks should produce a warning."""
        manifest = ScenarioManifest(
            scenario_id="test_access",
            title="Test",
            starting_scene_id="room_a",
            scenes=[
                SceneDefinition(
                    scene_id="room_a",
                    name="Room A",
                    exits=[
                        ExitDefinition(
                            exit_id="locked_door",
                            direction="n",
                            target_scene_id="room_b",
                            is_locked=True,
                        ),
                    ],
                ),
                SceneDefinition(
                    scene_id="room_b",
                    name="Room B",
                    exits=[
                        ExitDefinition(
                            exit_id="b_a", direction="s", target_scene_id="room_a"
                        )
                    ],
                    item_ids=["the_key"],
                ),
            ],
            items=[
                ItemDefinition(
                    item_id="the_key",
                    name="The Key",
                    is_key=True,
                    unlocks_exit_ids=["locked_door"],
                    scene_id="room_b",
                ),
            ],
        )
        validator = ScenarioValidator()
        result = validator.validate(manifest)
        assert any("behind the locked exit" in w for w in result.warnings)

    def test_scene_connectivity_check_catches_unreachable(self):
        """A scene only reachable through a hidden exit produces a warning."""
        manifest = ScenarioManifest(
            scenario_id="test_conn",
            title="Test",
            starting_scene_id="room_a",
            scenes=[
                SceneDefinition(
                    scene_id="room_a",
                    name="Room A",
                    exits=[
                        ExitDefinition(
                            exit_id="hidden_door",
                            direction="n",
                            target_scene_id="room_b",
                            is_hidden=True,
                        ),
                    ],
                ),
                SceneDefinition(
                    scene_id="room_b",
                    name="Room B",
                    exits=[
                        ExitDefinition(
                            exit_id="b_a", direction="s", target_scene_id="room_a"
                        )
                    ],
                ),
            ],
        )
        validator = ScenarioValidator()
        result = validator.validate(manifest)
        # room_b unreachable via non-hidden exits -> warning (not error)
        assert result.is_valid
        assert any("unreachable" in w for w in result.warnings)

    def test_trigger_chain_validity_warns_on_missing(self):
        """A chain_trigger referencing a nonexistent trigger should warn."""
        manifest = ScenarioManifest(
            scenario_id="test_chain",
            title="Test",
            starting_scene_id="room_a",
            scenes=[
                SceneDefinition(
                    scene_id="room_a",
                    name="Room A",
                    exits=[
                        ExitDefinition(
                            exit_id="a_b", direction="n", target_scene_id="room_b"
                        )
                    ],
                    trigger_ids=["chain_trig"],
                ),
                SceneDefinition(
                    scene_id="room_b",
                    name="Room B",
                    exits=[
                        ExitDefinition(
                            exit_id="b_a", direction="s", target_scene_id="room_a"
                        )
                    ],
                ),
            ],
            triggers=[
                TriggerDefinition(
                    trigger_id="chain_trig",
                    kind="on_enter",
                    scene_id="room_a",
                    effect_type="chain_trigger",
                    effect_value="nonexistent_trigger",
                ),
            ],
        )
        validator = ScenarioValidator()
        result = validator.validate(manifest)
        assert any("nonexistent_trigger" in w for w in result.warnings)

    def test_scene_connectivity_valid_when_connected(self):
        """All scenes reachable = no connectivity errors."""
        manifest = ScenarioManifest(
            scenario_id="test_ok",
            title="Test",
            starting_scene_id="room_a",
            scenes=[
                SceneDefinition(
                    scene_id="room_a",
                    name="Room A",
                    exits=[
                        ExitDefinition(
                            exit_id="a_b", direction="n", target_scene_id="room_b"
                        )
                    ],
                ),
                SceneDefinition(
                    scene_id="room_b",
                    name="Room B",
                    exits=[
                        ExitDefinition(
                            exit_id="b_a", direction="s", target_scene_id="room_a"
                        )
                    ],
                ),
            ],
        )
        validator = ScenarioValidator()
        result = validator.validate(manifest)
        assert result.is_valid
        assert not any("unreachable" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Narration style guide tests
# ---------------------------------------------------------------------------


class TestNarrationStyleGuides:
    def test_narration_guide_in_scene_contract(self):
        from models.contracts.main_contracts import (
            MAIN_CONTRACTS,
            NARRATION_STYLE_GUIDE,
        )

        contract = MAIN_CONTRACTS["main.scene_narration"]
        assert NARRATION_STYLE_GUIDE in contract.system_prompt_template

    def test_dialogue_guide_in_npc_contract(self):
        from models.contracts.main_contracts import MAIN_CONTRACTS, DIALOGUE_STYLE_GUIDE

        contract = MAIN_CONTRACTS["main.npc_dialogue"]
        assert DIALOGUE_STYLE_GUIDE in contract.system_prompt_template

    def test_narration_guide_in_combat_contract(self):
        from models.contracts.main_contracts import (
            MAIN_CONTRACTS,
            NARRATION_STYLE_GUIDE,
        )

        contract = MAIN_CONTRACTS["main.combat_summary"]
        assert NARRATION_STYLE_GUIDE in contract.system_prompt_template


# ---------------------------------------------------------------------------
# New trigger effect types in loader
# ---------------------------------------------------------------------------


class TestNewTriggerEffects:
    def test_spawn_monster_effect_converted(self):
        loader = ScenarioLoader()
        manifest = ScenarioManifest(
            scenario_id="effect_test",
            title="Test",
            starting_scene_id="room_a",
            scenes=[
                SceneDefinition(
                    scene_id="room_a",
                    name="Room A",
                    exits=[
                        ExitDefinition(
                            exit_id="a_b", direction="n", target_scene_id="room_b"
                        )
                    ],
                    trigger_ids=["spawn_trig"],
                ),
                SceneDefinition(
                    scene_id="room_b",
                    name="Room B",
                    exits=[
                        ExitDefinition(
                            exit_id="b_a", direction="s", target_scene_id="room_a"
                        )
                    ],
                ),
            ],
            triggers=[
                TriggerDefinition(
                    trigger_id="spawn_trig",
                    kind="on_enter",
                    scene_id="room_a",
                    effect_type="spawn_monster",
                    effect_value="goblin_squad",
                ),
            ],
        )
        result = loader.load_from_manifest(manifest)
        assert result.success
        # The trigger should have a fact payload about spawning
        trig = result.triggers[0]
        assert any("spawn_monster" in p for _, p in trig.effect.new_fact_payloads)

    def test_chain_trigger_effect_converted(self):
        loader = ScenarioLoader()
        manifest = ScenarioManifest(
            scenario_id="chain_test",
            title="Test",
            starting_scene_id="room_a",
            scenes=[
                SceneDefinition(
                    scene_id="room_a",
                    name="Room A",
                    exits=[
                        ExitDefinition(
                            exit_id="a_b", direction="n", target_scene_id="room_b"
                        )
                    ],
                    trigger_ids=["trig_a", "trig_b"],
                ),
                SceneDefinition(
                    scene_id="room_b",
                    name="Room B",
                    exits=[
                        ExitDefinition(
                            exit_id="b_a", direction="s", target_scene_id="room_a"
                        )
                    ],
                ),
            ],
            triggers=[
                TriggerDefinition(
                    trigger_id="trig_a",
                    kind="on_enter",
                    scene_id="room_a",
                    effect_type="chain_trigger",
                    effect_value="trig_b",
                ),
                TriggerDefinition(
                    trigger_id="trig_b",
                    kind="on_enter",
                    scene_id="room_a",
                    effect_type="narrate",
                    effect_value="Chained event fires!",
                ),
            ],
        )
        result = loader.load_from_manifest(manifest)
        assert result.success
        chain_trig = [t for t in result.triggers if t.trigger_id == "trig_a"][0]
        assert any("chain_trigger" in p for _, p in chain_trig.effect.new_fact_payloads)
