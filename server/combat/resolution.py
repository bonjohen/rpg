"""Damage calculation, status effects, and defeat state management."""

from __future__ import annotations

from dataclasses import dataclass, field

from server.domain.entities import Character, MonsterGroup


@dataclass
class DamageResult:
    raw_damage: int
    armor_reduction: int
    final_damage: int
    new_hp: int
    is_defeated: bool
    status_effects_applied: list[str] = field(default_factory=list)


class CombatResolutionEngine:
    """Applies damage, status effects, and checks defeat."""

    def apply_damage_to_character(
        self,
        character: Character,
        raw_damage: int,
    ) -> tuple[Character, DamageResult]:
        armor = character.stats.get("defense", 0)
        if "defended" in character.status_effects:
            armor += 3
        final_damage = max(0, raw_damage - armor)
        hp = character.stats.get("hp", 0)
        new_hp = max(0, hp - final_damage)
        character.stats["hp"] = new_hp
        if new_hp <= 0:
            character.is_alive = False
        return character, DamageResult(
            raw_damage=raw_damage,
            armor_reduction=armor,
            final_damage=final_damage,
            new_hp=new_hp,
            is_defeated=new_hp <= 0,
        )

    def apply_damage_to_group(
        self,
        group: MonsterGroup,
        damage: int,
        original_count: int,
    ) -> tuple[MonsterGroup, DamageResult]:
        # Each hit of damage >= 3 kills one unit
        kills = 1 if damage >= 3 else 0
        group.count = max(0, group.count - kills)

        # Update health state
        if original_count > 0:
            ratio = group.count / original_count
            if ratio > 0.5:
                group.health_state = "healthy"
            elif ratio > 0.25:
                group.health_state = "injured"
            elif ratio > 0:
                group.health_state = "critical"
            else:
                group.health_state = "dead"

        return group, DamageResult(
            raw_damage=damage,
            armor_reduction=0,
            final_damage=damage,
            new_hp=group.count,
            is_defeated=group.count <= 0,
        )

    def apply_status_effect(
        self,
        character: Character,
        effect: str,
    ) -> Character:
        if effect not in character.status_effects:
            character.status_effects.append(effect)
        return character

    def remove_status_effect(
        self,
        character: Character,
        effect: str,
    ) -> Character:
        if effect in character.status_effects:
            character.status_effects.remove(effect)
        return character

    def process_status_effects(
        self,
        character: Character,
    ) -> tuple[Character, list[str]]:
        fired: list[str] = []

        if "poisoned" in character.status_effects:
            hp = character.stats.get("hp", 0)
            character.stats["hp"] = hp - 1
            if character.stats["hp"] <= 0:
                character.is_alive = False
            fired.append("poisoned")

        return character, fired

    def clear_turn_effects(self, character: Character) -> Character:
        """Remove temporary status effects that expire at end of turn."""
        turn_effects = ["defended", "assisted"]
        character.status_effects = [
            e for e in character.status_effects if e not in turn_effects
        ]
        return character

    def check_defeat(self, character: Character) -> bool:
        return character.stats.get("hp", 0) <= 0
