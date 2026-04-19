"""Scenario validation — structural and referential integrity checks."""

from __future__ import annotations

from dataclasses import dataclass, field

from server.domain.enums import AwarenessState, BehaviorMode, ScopeType
from server.exploration.triggers import TriggerKind

from scenarios.schema import ScenarioManifest
from scenarios.visibility_rules import validate_no_leakage


@dataclass
class ValidationResult:
    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ScenarioValidator:
    """Validate a ScenarioManifest for structural and referential integrity."""

    def validate(self, manifest: ScenarioManifest) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        errors.extend(self._check_ids_unique(manifest))
        errors.extend(self._check_references_valid(manifest))
        errors.extend(self._check_starting_scene_exists(manifest))
        errors.extend(self._check_enum_values(manifest))
        warnings.extend(self._check_no_orphan_scenes(manifest))
        warnings.extend(self._check_no_dead_end_scenes(manifest))
        warnings.extend(self._check_puzzle_solvability(manifest))
        warnings.extend(self._check_visibility_rules(manifest))

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def _check_ids_unique(self, manifest: ScenarioManifest) -> list[str]:
        errors: list[str] = []
        all_ids: dict[str, str] = {}  # id -> entity type

        for scene in manifest.scenes:
            if scene.scene_id in all_ids:
                errors.append(
                    f"Duplicate ID '{scene.scene_id}' "
                    f"(scene vs {all_ids[scene.scene_id]})"
                )
            all_ids[scene.scene_id] = "scene"
            for exit_def in scene.exits:
                if exit_def.exit_id in all_ids:
                    errors.append(
                        f"Duplicate ID '{exit_def.exit_id}' "
                        f"(exit vs {all_ids[exit_def.exit_id]})"
                    )
                all_ids[exit_def.exit_id] = "exit"

        id_lists: list[tuple[str, str, list]] = [
            ("npc", "npc_id", manifest.npcs),
            ("monster", "monster_id", manifest.monsters),
            ("item", "item_id", manifest.items),
            ("puzzle", "puzzle_id", manifest.puzzles),
            ("quest", "quest_id", manifest.quests),
            ("trigger", "trigger_id", manifest.triggers),
        ]

        for entity_type, id_field, entities in id_lists:
            for entity in entities:
                eid = getattr(entity, id_field)
                if eid in all_ids:
                    errors.append(
                        f"Duplicate ID '{eid}' ({entity_type} vs {all_ids[eid]})"
                    )
                all_ids[eid] = entity_type

        return errors

    def _check_references_valid(self, manifest: ScenarioManifest) -> list[str]:
        errors: list[str] = []
        scene_ids = {s.scene_id for s in manifest.scenes}
        item_ids = {i.item_id for i in manifest.items}
        exit_ids = {e.exit_id for s in manifest.scenes for e in s.exits}

        # Exit target_scene_id
        for scene in manifest.scenes:
            for exit_def in scene.exits:
                if exit_def.target_scene_id not in scene_ids:
                    errors.append(
                        f"Exit '{exit_def.exit_id}' references "
                        f"nonexistent scene '{exit_def.target_scene_id}'"
                    )

        # NPC scene_id
        for npc in manifest.npcs:
            if npc.scene_id and npc.scene_id not in scene_ids:
                errors.append(
                    f"NPC '{npc.npc_id}' references nonexistent scene '{npc.scene_id}'"
                )
            # NPC inventory items
            for iid in npc.inventory_item_ids:
                if iid not in item_ids:
                    errors.append(
                        f"NPC '{npc.npc_id}' inventory references "
                        f"nonexistent item '{iid}'"
                    )

        # Monster scene_id and territory_id
        for monster in manifest.monsters:
            if monster.scene_id and monster.scene_id not in scene_ids:
                errors.append(
                    f"Monster '{monster.monster_id}' references "
                    f"nonexistent scene '{monster.scene_id}'"
                )
            if monster.territory_id and monster.territory_id not in scene_ids:
                errors.append(
                    f"Monster '{monster.monster_id}' territory references "
                    f"nonexistent scene '{monster.territory_id}'"
                )

        # Puzzle scene_id
        for puzzle in manifest.puzzles:
            if puzzle.scene_id and puzzle.scene_id not in scene_ids:
                errors.append(
                    f"Puzzle '{puzzle.puzzle_id}' references "
                    f"nonexistent scene '{puzzle.scene_id}'"
                )

        # Trigger scene_id
        for trigger in manifest.triggers:
            if trigger.scene_id and trigger.scene_id not in scene_ids:
                errors.append(
                    f"Trigger '{trigger.trigger_id}' references "
                    f"nonexistent scene '{trigger.scene_id}'"
                )

        # Item unlocks_exit_ids
        for item in manifest.items:
            for eid in item.unlocks_exit_ids:
                if eid not in exit_ids:
                    errors.append(
                        f"Item '{item.item_id}' unlocks nonexistent exit '{eid}'"
                    )

        # Scene npc_ids, monster_ids, item_ids, puzzle_ids, trigger_ids
        npc_ids = {n.npc_id for n in manifest.npcs}
        monster_ids = {m.monster_id for m in manifest.monsters}
        puzzle_ids = {p.puzzle_id for p in manifest.puzzles}
        trigger_ids = {t.trigger_id for t in manifest.triggers}

        for scene in manifest.scenes:
            for nid in scene.npc_ids:
                if nid not in npc_ids:
                    errors.append(
                        f"Scene '{scene.scene_id}' references nonexistent NPC '{nid}'"
                    )
            for mid in scene.monster_ids:
                if mid not in monster_ids:
                    errors.append(
                        f"Scene '{scene.scene_id}' references "
                        f"nonexistent monster '{mid}'"
                    )
            for iid in scene.item_ids:
                if iid not in item_ids:
                    errors.append(
                        f"Scene '{scene.scene_id}' references nonexistent item '{iid}'"
                    )
            for pid in scene.puzzle_ids:
                if pid not in puzzle_ids:
                    errors.append(
                        f"Scene '{scene.scene_id}' references "
                        f"nonexistent puzzle '{pid}'"
                    )
            for tid in scene.trigger_ids:
                if tid not in trigger_ids:
                    errors.append(
                        f"Scene '{scene.scene_id}' references "
                        f"nonexistent trigger '{tid}'"
                    )

        return errors

    def _check_starting_scene_exists(self, manifest: ScenarioManifest) -> list[str]:
        if not manifest.starting_scene_id:
            return ["No starting_scene_id defined"]
        scene_ids = {s.scene_id for s in manifest.scenes}
        if manifest.starting_scene_id not in scene_ids:
            return [
                f"starting_scene_id '{manifest.starting_scene_id}' not found in scenes"
            ]
        return []

    def _check_no_orphan_scenes(self, manifest: ScenarioManifest) -> list[str]:
        warnings: list[str] = []
        # Find scenes that no exit leads to (except starting scene)
        target_scene_ids: set[str] = set()
        for scene in manifest.scenes:
            for exit_def in scene.exits:
                target_scene_ids.add(exit_def.target_scene_id)

        for scene in manifest.scenes:
            if scene.scene_id == manifest.starting_scene_id:
                continue
            if scene.scene_id not in target_scene_ids:
                warnings.append(f"Orphan scene '{scene.scene_id}' has no inbound exits")
        return warnings

    def _check_no_dead_end_scenes(self, manifest: ScenarioManifest) -> list[str]:
        warnings: list[str] = []
        for scene in manifest.scenes:
            if not scene.exits:
                warnings.append(
                    f"Dead-end scene '{scene.scene_id}' has no outbound exits"
                )
        return warnings

    def _check_enum_values(self, manifest: ScenarioManifest) -> list[str]:
        errors: list[str] = []
        behavior_values = {e.value for e in BehaviorMode}
        awareness_values = {e.value for e in AwarenessState}
        trigger_kind_values = {e.value for e in TriggerKind}
        scope_values = {e.value for e in ScopeType} | {"public", "referee_only"}
        for monster in manifest.monsters:
            if monster.behavior_mode not in behavior_values:
                errors.append(
                    f"Monster '{monster.monster_id}' has invalid "
                    f"behavior_mode '{monster.behavior_mode}'"
                )
            if monster.awareness_state not in awareness_values:
                errors.append(
                    f"Monster '{monster.monster_id}' has invalid "
                    f"awareness_state '{monster.awareness_state}'"
                )

        for trigger in manifest.triggers:
            if trigger.kind not in trigger_kind_values:
                errors.append(
                    f"Trigger '{trigger.trigger_id}' has invalid kind '{trigger.kind}'"
                )
            if trigger.scope not in scope_values:
                errors.append(
                    f"Trigger '{trigger.trigger_id}' has invalid "
                    f"scope '{trigger.scope}'"
                )

        for npc in manifest.npcs:
            for tell in npc.tells:
                if tell.scope not in scope_values:
                    errors.append(
                        f"NPC tell '{tell.tell_id}' has invalid scope '{tell.scope}'"
                    )

        return errors

    def _check_puzzle_solvability(self, manifest: ScenarioManifest) -> list[str]:
        warnings: list[str] = []
        exit_ids = {e.exit_id for s in manifest.scenes for e in s.exits}
        item_ids = {i.item_id for i in manifest.items}

        for puzzle in manifest.puzzles:
            for effect in puzzle.effects_on_solve:
                if effect.startswith("unlock:"):
                    ref_id = effect[len("unlock:") :]
                    if ref_id not in exit_ids:
                        warnings.append(
                            f"Puzzle '{puzzle.puzzle_id}' effect references "
                            f"nonexistent exit '{ref_id}'"
                        )
                elif effect.startswith("reveal:"):
                    ref_id = effect[len("reveal:") :]
                    if ref_id not in item_ids and ref_id not in exit_ids:
                        warnings.append(
                            f"Puzzle '{puzzle.puzzle_id}' effect references "
                            f"nonexistent entity '{ref_id}'"
                        )
        return warnings

    def _check_visibility_rules(self, manifest: ScenarioManifest) -> list[str]:
        return validate_no_leakage(manifest)
