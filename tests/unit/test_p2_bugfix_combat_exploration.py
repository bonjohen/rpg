"""Tests for P2 Phase 3: Combat scaling, exploration state, puzzle safety."""

from __future__ import annotations

from server.combat.actions import CombatActionEngine
from server.combat.resolution import CombatResolutionEngine
from server.domain.entities import Character, InventoryItem, MonsterGroup, Scene
from server.domain.enums import ActionType, KnowledgeFactType
from server.domain.helpers import utc_now
from server.exploration.clues import (
    ClueEngine,
    ClueDefinition,
    ClueDiscoveryMethod,
    ClueScopePolicy,
)
from server.exploration.triggers import ExplorationContext, TriggerEffect


# -------------------------------------------------------------------
# BUG-029: search() sets item.is_hidden = False
# -------------------------------------------------------------------


class TestBUG029SearchHiddenFlag:
    def test_search_sets_is_hidden_false(self):
        from server.exploration.actions import ExplorationEngine

        resolver = ExplorationEngine()
        scene = Scene(
            scene_id="s1",
            campaign_id="c1",
            name="Cave",
            description="Dark cave",
            created_at=utc_now(),
        )
        char = Character(
            character_id="ch1",
            campaign_id="c1",
            player_id="p1",
            name="Hero",
            scene_id="s1",
            created_at=utc_now(),
        )
        item = InventoryItem(
            item_id="hidden-gem",
            campaign_id="c1",
            item_type="gem",
            name="Hidden Gem",
            created_at=utc_now(),
            owner_scene_id="s1",
            is_hidden=True,
        )
        result = resolver.search(
            character=char,
            scene=scene,
            scene_items=[item],
            campaign_id="c1",
            private_scope_id="scope-1",
        )
        assert item.is_hidden is False
        assert len(result.new_facts) >= 1


# -------------------------------------------------------------------
# BUG-032: Clue discover() idempotency guard
# -------------------------------------------------------------------


class TestBUG032ClueIdempotency:
    def test_discover_rejects_already_discovered(self):
        engine = ClueEngine()
        scene = Scene(
            scene_id="s1",
            campaign_id="c1",
            name="Hall",
            description="A hall",
            created_at=utc_now(),
        )
        char = Character(
            character_id="ch1",
            campaign_id="c1",
            player_id="p1",
            name="Hero",
            scene_id="s1",
            created_at=utc_now(),
        )
        clue = ClueDefinition(
            clue_id="clue-1",
            campaign_id="c1",
            scene_id="s1",
            payload="A secret passage!",
            fact_type=KnowledgeFactType.clue,
            discovery_method=ClueDiscoveryMethod.search,
            scope_policy=ClueScopePolicy.private,
        )
        # First discovery succeeds
        result1 = engine.discover(
            char, scene, clue, ActionType.search, private_scope_id="scope-1"
        )
        assert result1.discovered is True

        # Second discovery is rejected
        result2 = engine.discover(
            char, scene, clue, ActionType.search, private_scope_id="scope-1"
        )
        assert result2.discovered is False
        assert "already discovered" in result2.rejection_reason.lower()


# -------------------------------------------------------------------
# BUG-030: ExplorationContext has direction field
# -------------------------------------------------------------------


class TestBUG030DirectionField:
    def test_exploration_context_has_direction(self):
        char = Character(
            character_id="ch1",
            campaign_id="c1",
            player_id="p1",
            name="Hero",
            scene_id="s1",
            created_at=utc_now(),
        )
        scene = Scene(
            scene_id="s1",
            campaign_id="c1",
            name="Hall",
            description="A hall",
            created_at=utc_now(),
        )
        ctx = ExplorationContext(
            character=char,
            scene=scene,
            action_type=ActionType.move,
            direction="north",
        )
        assert ctx.direction == "north"


# -------------------------------------------------------------------
# BUG-031: Per-fact scope_override in trigger _apply()
# -------------------------------------------------------------------


class TestBUG031PerFactScopeOverride:
    def test_scope_override_public_uses_public_scope(self):
        from server.exploration.triggers import (
            TriggerDefinition,
            TriggerEngine,
            TriggerKind,
            TriggerCondition,
        )

        engine = TriggerEngine()
        effect = TriggerEffect(
            public_narrative="Something happens.",
            new_fact_payloads=[
                (KnowledgeFactType.lore, "Public lore", "public"),
            ],
        )
        trigger = TriggerDefinition(
            trigger_id="t1",
            campaign_id="c1",
            scene_id="s1",
            kind=TriggerKind.on_enter,
            condition=TriggerCondition.always,
            label="Test trigger",
            effect=effect,
            public_scope_id="pub-scope",
            private_scope_id="priv-scope",
        )
        firing = engine._apply(trigger, None)
        # With scope_override="public", fact should use public scope
        assert len(firing.new_facts) == 1
        assert firing.new_facts[0].owner_scope_id == "pub-scope"

    def test_no_scope_override_uses_private_default(self):
        from server.exploration.triggers import (
            TriggerDefinition,
            TriggerEngine,
            TriggerKind,
            TriggerCondition,
        )

        engine = TriggerEngine()
        effect = TriggerEffect(
            new_fact_payloads=[
                (KnowledgeFactType.lore, "Private lore"),
            ],
        )
        trigger = TriggerDefinition(
            trigger_id="t1",
            campaign_id="c1",
            scene_id="s1",
            kind=TriggerKind.on_enter,
            condition=TriggerCondition.always,
            label="Test",
            effect=effect,
            public_scope_id="pub-scope",
            private_scope_id="priv-scope",
        )
        firing = engine._apply(trigger, None)
        assert len(firing.new_facts) == 1
        # Default: private_scope_id takes precedence
        assert firing.new_facts[0].owner_scope_id == "priv-scope"


# -------------------------------------------------------------------
# BUG-033: Monster damage scales kills by magnitude
# -------------------------------------------------------------------


class TestBUG033DamageScaling:
    def test_high_damage_kills_multiple_units(self):
        engine = CombatResolutionEngine()
        group = MonsterGroup(
            monster_group_id="g1",
            campaign_id="c1",
            scene_id="s1",
            unit_type="goblin",
            count=10,
            created_at=utc_now(),
        )
        _, result = engine.apply_damage_to_group(group, damage=9, original_count=10)
        # 9 // 3 = 3 kills
        assert group.count == 7

    def test_damage_below_threshold_kills_zero(self):
        engine = CombatResolutionEngine()
        group = MonsterGroup(
            monster_group_id="g2",
            campaign_id="c1",
            scene_id="s1",
            unit_type="goblin",
            count=5,
            created_at=utc_now(),
        )
        _, result = engine.apply_damage_to_group(group, damage=2, original_count=5)
        assert group.count == 5

    def test_large_damage_kills_many(self):
        engine = CombatResolutionEngine()
        group = MonsterGroup(
            monster_group_id="g3",
            campaign_id="c1",
            scene_id="s1",
            unit_type="rat",
            count=20,
            created_at=utc_now(),
        )
        _, result = engine.apply_damage_to_group(group, damage=50, original_count=20)
        # 50 // 3 = 16 kills
        assert group.count == 4


# -------------------------------------------------------------------
# BUG-034: Combat move validates direction
# -------------------------------------------------------------------


class TestBUG034DirectionValidation:
    def test_combat_move_rejects_wrong_direction(self):
        resolver = CombatActionEngine()
        char = Character(
            character_id="ch1",
            campaign_id="c1",
            player_id="p1",
            name="Hero",
            scene_id="s1",
            created_at=utc_now(),
        )
        scene = Scene(
            scene_id="s1",
            campaign_id="c1",
            name="Hall",
            description="A hall",
            created_at=utc_now(),
            exits={"north": "s2"},
        )
        dest = Scene(
            scene_id="s2",
            campaign_id="c1",
            name="Garden",
            description="A garden",
            created_at=utc_now(),
        )
        result = resolver.resolve_combat_move(char, scene, dest, direction="south")
        assert result.success is False
        assert "south" in result.rejection_reason

    def test_combat_move_succeeds_with_correct_direction(self):
        resolver = CombatActionEngine()
        char = Character(
            character_id="ch1",
            campaign_id="c1",
            player_id="p1",
            name="Hero",
            scene_id="s1",
            created_at=utc_now(),
        )
        scene = Scene(
            scene_id="s1",
            campaign_id="c1",
            name="Hall",
            description="A hall",
            created_at=utc_now(),
            exits={"north": "s2"},
        )
        dest = Scene(
            scene_id="s2",
            campaign_id="c1",
            name="Garden",
            description="A garden",
            created_at=utc_now(),
        )
        result = resolver.resolve_combat_move(char, scene, dest, direction="north")
        assert result.success is True


# -------------------------------------------------------------------
# BUG-035: Heal amount cast to int
# -------------------------------------------------------------------


class TestBUG035HealAmountCast:
    def test_heal_amount_string_cast_to_int(self):
        resolver = CombatActionEngine()
        char = Character(
            character_id="ch1",
            campaign_id="c1",
            player_id="p1",
            name="Hero",
            scene_id="s1",
            created_at=utc_now(),
            stats={"hp": 5, "max_hp": 20},
        )
        item = InventoryItem(
            item_id="potion",
            campaign_id="c1",
            item_type="consumable",
            name="Healing Potion",
            created_at=utc_now(),
            owner_character_id="ch1",
            properties={"effect": "heal", "amount": "10"},  # string, not int
            quantity=1,
        )
        result = resolver.resolve_use_item(char, item)
        assert result.success is True
        assert char.stats["hp"] == 15  # 5 + 10


# -------------------------------------------------------------------
# BUG-053: puzzle_patterns copy overrides before pop
# -------------------------------------------------------------------


class TestBUG053PuzzleOverridesCopy:
    def test_create_puzzle_does_not_mutate_caller_dict(self):
        from scenarios.puzzle_patterns import PuzzlePattern

        pattern = PuzzlePattern(
            pattern_id="test_lock",
            name="Lock Puzzle",
            description="A locked door.",
            required_components=["key"],
            solution_template="Use {key} to open the door.",
        )
        overrides = {"puzzle_id": "my-puzzle", "description": "Custom desc"}
        original = dict(overrides)  # snapshot

        pattern.instantiate(
            components={"key": "iron_key"},
            scene_id="s1",
            **overrides,
        )
        # Caller's dict should be unchanged
        assert overrides == original
