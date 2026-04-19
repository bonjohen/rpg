"""Authoring visibility policy for scenario content.

Maps scenario definition fields to scope types at load time and checks
for accidental leakage of referee-only text into public fields.
"""

from __future__ import annotations

from typing import Any

from server.domain.enums import ScopeType

from scenarios.schema import ScenarioManifest


# Fields whose content is always referee-only
REFEREE_ONLY_FIELDS: set[str] = {
    "referee_notes",
    "solution_hint",
    "solution_actions",
}

# Fields that mark content as hidden (discoverable, not initially shown)
HIDDEN_FIELDS: set[str] = {
    "is_hidden",
}

# Everything else — player-visible from the start
PUBLIC_FIELDS: set[str] = {
    "name",
    "description",
    "direction",
    "success_text",
    "failure_text",
    "title",
    "objectives",
    "reward_description",
    "effect_value",
}


def classify_field(
    definition_type: str,
    field_name: str,
    field_value: Any,
) -> ScopeType:
    """Return the scope type for a given definition field.

    Used during scenario import to assign correct scope to generated
    KnowledgeFacts.
    """
    if field_name in REFEREE_ONLY_FIELDS:
        return ScopeType.referee_only

    # NPC tells with scope == "referee_only"
    if field_name == "tells" and isinstance(field_value, list):
        # Individual tells are classified per-tell in the loader
        return ScopeType.public

    # Hidden items/exits
    if field_name == "is_hidden" and field_value is True:
        return ScopeType.private_referee

    # Trigger scope follows the trigger's own scope field
    if definition_type == "trigger" and field_name == "effect_value":
        # The trigger's scope field determines this; caller handles it
        return ScopeType.public

    return ScopeType.public


def validate_no_leakage(manifest: ScenarioManifest) -> list[str]:
    """Return warnings if referee-only text appears in public fields.

    Heuristic: checks if any referee_notes substring (>10 chars) appears
    in description, success_text, or other public fields.
    """
    warnings: list[str] = []

    # Collect all referee-only text fragments
    referee_texts: list[tuple[str, str]] = []  # (source_label, text)

    for scene in manifest.scenes:
        if scene.referee_notes and len(scene.referee_notes) > 10:
            referee_texts.append((f"scene:{scene.scene_id}", scene.referee_notes))

    for npc in manifest.npcs:
        if npc.referee_notes and len(npc.referee_notes) > 10:
            referee_texts.append((f"npc:{npc.npc_id}", npc.referee_notes))

    for monster in manifest.monsters:
        if monster.referee_notes and len(monster.referee_notes) > 10:
            referee_texts.append(
                (f"monster:{monster.monster_id}", monster.referee_notes)
            )

    for puzzle in manifest.puzzles:
        if puzzle.referee_notes and len(puzzle.referee_notes) > 10:
            referee_texts.append((f"puzzle:{puzzle.puzzle_id}", puzzle.referee_notes))
        if puzzle.solution_hint and len(puzzle.solution_hint) > 10:
            referee_texts.append(
                (f"puzzle:{puzzle.puzzle_id}:solution_hint", puzzle.solution_hint)
            )

    for quest in manifest.quests:
        if quest.referee_notes and len(quest.referee_notes) > 10:
            referee_texts.append((f"quest:{quest.quest_id}", quest.referee_notes))

    for trigger in manifest.triggers:
        if trigger.referee_notes and len(trigger.referee_notes) > 10:
            referee_texts.append(
                (f"trigger:{trigger.trigger_id}", trigger.referee_notes)
            )

    # Collect all public-facing text
    public_texts: list[tuple[str, str]] = []  # (source_label, text)

    for scene in manifest.scenes:
        if scene.description:
            public_texts.append(
                (f"scene:{scene.scene_id}:description", scene.description)
            )
        for exit_def in scene.exits:
            if exit_def.description:
                public_texts.append(
                    (f"exit:{exit_def.exit_id}:description", exit_def.description)
                )

    for npc in manifest.npcs:
        if npc.description:
            public_texts.append((f"npc:{npc.npc_id}:description", npc.description))

    for puzzle in manifest.puzzles:
        if puzzle.description:
            public_texts.append(
                (f"puzzle:{puzzle.puzzle_id}:description", puzzle.description)
            )
        if puzzle.success_text:
            public_texts.append(
                (f"puzzle:{puzzle.puzzle_id}:success_text", puzzle.success_text)
            )

    for quest in manifest.quests:
        if quest.description:
            public_texts.append(
                (f"quest:{quest.quest_id}:description", quest.description)
            )

    # Cross-check: does any referee text appear in any public text?
    for ref_label, ref_text in referee_texts:
        ref_lower = ref_text.lower()
        for pub_label, pub_text in public_texts:
            pub_lower = pub_text.lower()
            if ref_lower in pub_lower:
                warnings.append(
                    f"Leakage: referee text from {ref_label} "
                    f"found in public field {pub_label}"
                )

    return warnings
