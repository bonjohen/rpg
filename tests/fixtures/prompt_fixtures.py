"""Prompt-assembly regression fixtures for Phase 14 contract tests.

Each builder function returns inputs or expected outputs for a specific
contract type, making tests deterministic and self-documenting.
"""

from __future__ import annotations

from models.contracts.context_assembly import ScopedFact


# ---------------------------------------------------------------------------
# Narration inputs
# ---------------------------------------------------------------------------


def make_narration_inputs() -> dict:
    """Inputs for a main.scene_narration contract assembly.

    Scene: a tavern. Two players present. One committed action.
    Expected: prompt contains scene description, action summaries,
    no referee facts.
    """
    return {
        "scene_context": (
            "The Silver Stag Tavern -- a warm, crowded room with a roaring "
            "fireplace. Wooden beams overhead. Ale-stained tables."
        ),
        "active_players": "Kira the Ranger, Dorn the Fighter",
        "committed_actions": (
            "- Kira the Ranger: inspect -> notice board\n"
            "- Dorn the Fighter: interact -> bartender"
        ),
        "public_facts": [
            ScopedFact(
                fact_id="f1",
                text="The notice board has three postings.",
                scope="public",
            ),
            ScopedFact(
                fact_id="f2",
                text="The bartender is a half-orc named Gruk.",
                scope="public",
            ),
        ],
        "referee_facts": [
            ScopedFact(
                fact_id="f3",
                text="Gruk is secretly a spy for the thieves guild.",
                scope="referee_only",
                is_critical=False,
            ),
        ],
    }


# ---------------------------------------------------------------------------
# NPC dialogue inputs
# ---------------------------------------------------------------------------


def make_npc_dialogue_inputs() -> dict:
    """Inputs for a main.npc_dialogue contract assembly.

    NPC: Mira the Innkeeper. Player action: question about local rumours.
    Expected: prompt contains NPC personality + goals, not other NPC facts.
    """
    return {
        "npc_context": (
            "Mira the Innkeeper -- friendly, gossipy, knows local rumours. "
            "Goals: keep the inn profitable, stay out of trouble."
        ),
        "action_context": "Kira the Ranger asks about local rumours.",
        "scene_context": "The Silver Stag Tavern common room.",
        "dialogue_hints": "Speaks with a warm drawl. Lowers voice for secrets.",
        "target_npc_id": "npc_mira",
        "npc_facts": [
            ScopedFact(
                fact_id="f4",
                text="Mira heard about goblin raids on the trade road.",
                scope="public",
                npc_id="npc_mira",
            ),
            ScopedFact(
                fact_id="f5",
                text="Mira knows the innkeeper in the next town is a fence.",
                scope="referee_only",
                npc_id="npc_mira",
            ),
        ],
        "other_npc_facts": [
            ScopedFact(
                fact_id="f6",
                text="Gruk has a hidden dagger under the bar.",
                scope="public",
                npc_id="npc_gruk",
            ),
        ],
    }


# ---------------------------------------------------------------------------
# Combat summary inputs
# ---------------------------------------------------------------------------


def make_combat_summary_inputs() -> dict:
    """Inputs for a main.combat_summary contract assembly.

    Battlefield: three goblins vs two players in a cave.
    Expected: prompt contains combatant lines, no hidden monster awareness.
    """
    return {
        "battlefield_summary": (
            "Cave Entrance -- 3 goblin scouts (alert) vs "
            "Kira the Ranger and Dorn the Fighter. Round 2."
        ),
        "action_results": (
            "- Kira: attack -> goblin_1: hit, 5 damage\n"
            "- Dorn: defend: blocked incoming attack\n"
            "- Goblin_2: attack -> Dorn: miss"
        ),
        "scene_context": "A narrow cave entrance flanked by dead bushes.",
        "hidden_facts": [
            ScopedFact(
                fact_id="f7",
                text="Goblin scouts are planning an ambush from the shadows.",
                scope="referee_only",
            ),
        ],
    }


# ---------------------------------------------------------------------------
# Ruling inputs
# ---------------------------------------------------------------------------


def make_ruling_inputs() -> dict:
    """Inputs for a main.ruling_proposal contract assembly.

    Unusual action: player tries to intimidate a locked door.
    Expected: prompt contains action + character state, minimal private facts.
    """
    return {
        "action_text": "I kick the locked door while shouting threats at it.",
        "character_context": (
            "Dorn the Fighter, Level 3, HP: 25/30, "
            "Status: none, Inventory: greataxe, rope"
        ),
        "scene_context": "A narrow corridor with iron-banded doors.",
        "relevant_rules": "Strength check DC 15 to force open a locked door.",
        "private_facts": [
            ScopedFact(
                fact_id="f8",
                text="The door is trapped with a poison needle.",
                scope="referee_only",
                is_critical=True,
            ),
            ScopedFact(
                fact_id="f9",
                text="Old graffiti behind the door reads 'beware'.",
                scope="referee_only",
                is_critical=False,
            ),
        ],
    }


# ---------------------------------------------------------------------------
# Oversized history for truncation tests
# ---------------------------------------------------------------------------


def make_oversized_history() -> list[str]:
    """200 history entries to test truncation at both fast and main limits."""
    return [
        f"Turn {i}: Player {i % 4 + 1} performs action {i} in the dungeon."
        for i in range(200)
    ]


# ---------------------------------------------------------------------------
# Broken / valid JSON outputs for repair pipeline tests
# ---------------------------------------------------------------------------


def make_broken_json_outputs() -> dict[str, str]:
    """One broken JSON string per contract type, for repair pipeline testing."""
    return {
        "fast.intent_classification": '{"intent": "action", "confidence": }',
        "fast.command_normalization": '{"normalized": attack goblin}',
        "fast.action_extraction": '{"action_type": "attack" "target": "goblin"}',
        "fast.scope_suggestion": '{"suggested_scope": public}',
        "fast.context_summarization": '{"summary": "things happened"',
        "fast.clarification_generation": '{question: "Which door?"}',
        "fast.schema_repair": "{malformed}",
        "main.scene_narration": '{"narration": "The cave echoes." "tone": "tense"}',
        "main.npc_dialogue": '{"dialogue": "Hello there" internal_thought: "hmm"}',
        "main.combat_summary": '{"narration": "Swords clash!", "tone": tense}',
        "main.ruling_proposal": '{"ruling": "allow", success: true, "confidence": "high"}',
        "main.social_arbitration": '{"outcome": "success", "narration": }',
        "main.puzzle_flavor": '{"flavor": "You ponder the riddle."',
        "main.unusual_action": '{"interpretation": "climb wall" suggested_resolution: "check"}',
    }


def make_valid_json_outputs() -> dict[str, str]:
    """One valid JSON string per contract type."""
    return {
        "fast.intent_classification": '{"intent": "action", "confidence": "high"}',
        "fast.command_normalization": '{"normalized": "attack goblin"}',
        "fast.action_extraction": '{"action_type": "attack", "target": "goblin", "item_ids": [], "notes": ""}',
        "fast.scope_suggestion": '{"suggested_scope": "public", "reasoning": "General action."}',
        "fast.context_summarization": '{"summary": "The party explored the cave."}',
        "fast.clarification_generation": '{"question": "Which door did you mean?"}',
        "fast.schema_repair": "{}",
        "main.scene_narration": '{"narration": "The cave echoes with your footsteps.", "private_notes": "", "tone": "tense"}',
        "main.npc_dialogue": '{"dialogue": "Welcome, travelers.", "internal_thought": "They look tired.", "trust_shift_suggestion": 1}',
        "main.combat_summary": '{"narration": "Steel clashes in the dark.", "tone": "tense"}',
        "main.ruling_proposal": '{"ruling": "allow", "success": true, "confidence": "high", "reasoning": "Action is valid."}',
        "main.social_arbitration": '{"outcome": "success", "narration": "The negotiation succeeds.", "trust_delta": {}, "private_notes": ""}',
        "main.puzzle_flavor": '{"flavor": "You study the mechanism.", "hint": "", "progress": "none"}',
        "main.unusual_action": '{"interpretation": "Player climbs the wall.", "suggested_resolution": "Dexterity check", "difficulty_class": 12, "requires_roll": true}',
    }
