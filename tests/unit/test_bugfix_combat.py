"""Tests for P1 combat pipeline fixes (BUG-004, 005, 006, 007, 024)."""

from __future__ import annotations

from server.combat.actions import CombatActionEngine
from server.combat.conditions import CombatConditionEngine
from server.combat.resolution import CombatResolutionEngine
from server.domain.enums import MoraleState
from tests.fixtures.builders import make_character, make_monster_group, make_scene


class TestBUG004HPClamp:
    def test_hp_does_not_go_negative(self):
        engine = CombatResolutionEngine()
        char = make_character(stats={"hp": 5, "defense": 0})
        _, result = engine.apply_damage_to_character(char, 100)
        assert result.new_hp == 0
        assert char.stats["hp"] == 0
        assert result.is_defeated

    def test_hp_clamp_zero_prevents_negative_display(self):
        engine = CombatResolutionEngine()
        char = make_character(stats={"hp": 1, "defense": 0})
        _, result = engine.apply_damage_to_character(char, 10)
        assert result.new_hp >= 0


class TestBUG005006DamageDelegation:
    def test_resolve_attack_applies_damage_to_character(self):
        action_engine = CombatActionEngine()
        attacker = make_character(stats={"attack": 10, "hp": 20})
        target = make_character(stats={"hp": 20, "defense": 2})
        result = action_engine.resolve_attack(
            attacker, target.character_id, [], [target]
        )
        assert result.hit is True
        # Damage should be applied: 10 attack - 2 defense = 8 damage
        # HP: 20 - 8 = 12
        assert target.stats["hp"] == 12
        assert result.damage_dealt == 8

    def test_resolve_attack_applies_damage_to_group(self):
        action_engine = CombatActionEngine()
        attacker = make_character(stats={"attack": 8, "hp": 20})
        group = make_monster_group(count=3, is_visible=True)
        result = action_engine.resolve_attack(
            attacker, group.monster_group_id, [group], []
        )
        assert result.hit is True
        # Attack 8 - monster defense 2 = 6 damage, 6 // 3 = 2 kills
        assert group.count == 1

    def test_defense_calculated_once_not_twice(self):
        """Verify defense is only applied once through the resolution engine."""
        action_engine = CombatActionEngine()
        attacker = make_character(stats={"attack": 5, "hp": 20})
        target = make_character(stats={"hp": 20, "defense": 3})
        result = action_engine.resolve_attack(
            attacker, target.character_id, [], [target]
        )
        # 5 attack - 3 defense = 2 damage (not double-subtracted)
        assert result.damage_dealt == 2
        assert target.stats["hp"] == 18


class TestBUG007ClearTurnEffects:
    def test_clear_turn_effects_removes_defended(self):
        engine = CombatResolutionEngine()
        char = make_character()
        char.status_effects = ["defended", "poisoned"]
        engine.clear_turn_effects(char)
        assert "defended" not in char.status_effects
        assert "poisoned" in char.status_effects

    def test_clear_turn_effects_removes_assisted(self):
        engine = CombatResolutionEngine()
        char = make_character()
        char.status_effects = ["assisted", "stunned"]
        engine.clear_turn_effects(char)
        assert "assisted" not in char.status_effects
        assert "stunned" in char.status_effects

    def test_clear_turn_effects_noop_when_empty(self):
        engine = CombatResolutionEngine()
        char = make_character()
        char.status_effects = []
        engine.clear_turn_effects(char)
        assert char.status_effects == []


class TestBUG024MoraleEnum:
    def test_morale_enum_values(self):
        assert MoraleState.steady == "steady"
        assert MoraleState.shaken == "shaken"
        assert MoraleState.routed == "routed"
        assert MoraleState.broken == "broken"

    def test_condition_engine_uses_enum_for_routed(self):
        engine = CombatConditionEngine()
        scene = make_scene()
        group = make_monster_group(count=1, scene_id=scene.scene_id)
        group.morale_state = MoraleState.routed
        char = make_character(scene_id=scene.scene_id)
        result = engine.check_exit(scene, [group], [char])
        assert result.exited is True
        assert result.exit_type == "flee"

    def test_string_morale_still_works_with_enum(self):
        """MoraleState inherits from str, so string comparison still works."""
        assert MoraleState.routed == "routed"
        assert "routed" == MoraleState.routed
