"""Combat action resolution — attack, defend, assist, use item, use ability, move.

All outcomes are deterministic. No randomness. Server is referee authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from server.combat.resolution import CombatResolutionEngine
from server.domain.entities import Character, InventoryItem, MonsterGroup, Scene


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class AttackResult:
    hit: bool
    damage_dealt: int
    target_id: str
    target_new_health: str
    status_effects_applied: list[str] = field(default_factory=list)


@dataclass
class DefendResult:
    character: Character
    armor_bonus: int


@dataclass
class AssistResult:
    success: bool
    target_id: str
    effect: str


@dataclass
class UseItemResult:
    success: bool
    item_id: str
    effect: str
    rejection_reason: str = ""


@dataclass
class UseAbilityResult:
    success: bool
    ability_id: str
    effect: str
    rejection_reason: str = ""


@dataclass
class CombatMoveResult:
    success: bool
    character: Character
    from_scene_id: str
    to_scene_id: str
    rejection_reason: str = ""


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class CombatActionEngine:
    """Resolves individual combat actions. Stateless."""

    def __init__(self, resolution_engine: CombatResolutionEngine | None = None):
        self._resolution = resolution_engine or CombatResolutionEngine()

    def resolve_attack(
        self,
        attacker: Character,
        target_id: str,
        target_groups: list[MonsterGroup],
        target_characters: list[Character],
    ) -> AttackResult:
        # Check blinded
        if "blinded" in attacker.status_effects:
            return AttackResult(
                hit=False,
                damage_dealt=0,
                target_id=target_id,
                target_new_health="unchanged",
            )

        # Check stunned
        if "stunned" in attacker.status_effects:
            return AttackResult(
                hit=False,
                damage_dealt=0,
                target_id=target_id,
                target_new_health="unchanged",
            )

        attack_power = attacker.stats.get("attack", 5)

        # Try monster groups first
        for group in target_groups:
            if group.monster_group_id == target_id:
                if not group.is_visible:
                    return AttackResult(
                        hit=False,
                        damage_dealt=0,
                        target_id=target_id,
                        target_new_health="hidden",
                    )
                defense = 2  # base monster defense
                damage = max(0, attack_power - defense)
                original_count = group.count
                _, result = self._resolution.apply_damage_to_group(
                    group, damage, original_count
                )
                return AttackResult(
                    hit=result.final_damage > 0,
                    damage_dealt=result.final_damage,
                    target_id=target_id,
                    target_new_health=f"{group.count} remaining",
                )

        # Try characters (PvP or friendly fire)
        for char in target_characters:
            if char.character_id == target_id:
                _, result = self._resolution.apply_damage_to_character(
                    char, attack_power
                )
                return AttackResult(
                    hit=result.final_damage > 0,
                    damage_dealt=result.final_damage,
                    target_id=target_id,
                    target_new_health=f"{result.new_hp} HP",
                )

        return AttackResult(
            hit=False,
            damage_dealt=0,
            target_id=target_id,
            target_new_health="target not found",
        )

    def resolve_defend(self, character: Character) -> DefendResult:
        if "defended" not in character.status_effects:
            character.status_effects.append("defended")
        return DefendResult(character=character, armor_bonus=3)

    def resolve_assist(
        self,
        character: Character,
        target_id: str,
        allies: list[Character],
    ) -> AssistResult:
        for ally in allies:
            if ally.character_id == target_id:
                hp = ally.stats.get("hp", 0)
                max_hp = ally.stats.get("max_hp", hp)
                if hp < max_hp:
                    heal = min(5, max_hp - hp)
                    ally.stats["hp"] = hp + heal
                    return AssistResult(
                        success=True,
                        target_id=target_id,
                        effect=f"heal {heal}",
                    )
                else:
                    if "assisted" not in ally.status_effects:
                        ally.status_effects.append("assisted")
                    return AssistResult(
                        success=True,
                        target_id=target_id,
                        effect="buff",
                    )
        return AssistResult(
            success=False, target_id=target_id, effect="target not found"
        )

    def resolve_use_item(
        self,
        character: Character,
        item: InventoryItem | None,
    ) -> UseItemResult:
        if item is None:
            return UseItemResult(
                success=False,
                item_id="",
                effect="",
                rejection_reason="Item not found",
            )

        effect_type = item.properties.get("effect", "")
        if effect_type == "heal":
            amount = item.properties.get("amount", 0)
            hp = character.stats.get("hp", 0)
            max_hp = character.stats.get("max_hp", hp)
            heal = min(amount, max_hp - hp)
            character.stats["hp"] = hp + heal
            if item.quantity > 0:
                item.quantity -= 1
            return UseItemResult(
                success=True,
                item_id=item.item_id,
                effect=f"heal {heal}",
            )

        if effect_type:
            if item.quantity > 0:
                item.quantity -= 1
            return UseItemResult(
                success=True,
                item_id=item.item_id,
                effect=effect_type,
            )

        return UseItemResult(
            success=False,
            item_id=item.item_id,
            effect="",
            rejection_reason="Item has no usable effect",
        )

    def resolve_use_ability(
        self,
        character: Character,
        ability_id: str,
    ) -> UseAbilityResult:
        return UseAbilityResult(
            success=True,
            ability_id=ability_id,
            effect=f"ability {ability_id} activated",
        )

    def resolve_combat_move(
        self,
        character: Character,
        scene: Scene,
        destination: Scene,
    ) -> CombatMoveResult:
        # Check the exit exists
        valid_exits = scene.exits or {}
        if destination.scene_id not in valid_exits.values():
            return CombatMoveResult(
                success=False,
                character=character,
                from_scene_id=scene.scene_id,
                to_scene_id=destination.scene_id,
                rejection_reason="No exit to destination",
            )

        character.scene_id = destination.scene_id
        return CombatMoveResult(
            success=True,
            character=character,
            from_scene_id=scene.scene_id,
            to_scene_id=destination.scene_id,
        )
