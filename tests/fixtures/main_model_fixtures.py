"""Regression fixtures for main-tier model tests.

Provides representative game state snapshots used to test:
  - Prompt assembly correctness and scope safety
  - Schema validation (valid, invalid, partial-valid responses)
  - Fallback behavior on model failure or invalid output
  - Fast-tier repair integration

All fixtures are self-contained; no database or live model is needed.
"""

from __future__ import annotations

from models.main.context import (
    ActionContext,
    NpcContext,
    PlayerContext,
    RecentHistory,
    SceneContext,
)


# ---------------------------------------------------------------------------
# Representative game states
# ---------------------------------------------------------------------------


def make_tavern_scene() -> SceneContext:
    """Cozy tavern with two players present and a known spy."""
    return SceneContext(
        scene_id="scene-tavern-001",
        location_name="The Rusty Flagon Tavern",
        description=(
            "A low-ceilinged common room reeking of tallow candles and spilled ale. "
            "Rough-hewn tables are packed with off-duty guards and traders. "
            "A roaring hearth dominates the far wall."
        ),
        active_player_names=["Aldric", "Mirela"],
        public_facts=[
            "The innkeeper, Bram, is nervous and avoids eye contact.",
            "A hooded stranger in the corner has been watching the party.",
        ],
    )


def make_dungeon_scene() -> SceneContext:
    """Dark corridor with combat in progress."""
    return SceneContext(
        scene_id="scene-dungeon-001",
        location_name="The Sunken Corridor",
        description=(
            "A narrow stone passage barely wide enough for two abreast. "
            "Torchlight reveals a pack of goblin warriors blocking the way ahead."
        ),
        active_player_names=["Aldric", "Mirela", "Torvek"],
        public_facts=[
            "Three goblin warriors stand between the party and the exit.",
            "Torvek is poisoned (–2 to attack rolls).",
        ],
    )


def make_puzzle_room_scene() -> SceneContext:
    """Puzzle room with rune-lock mechanism."""
    return SceneContext(
        scene_id="scene-puzzle-001",
        location_name="The Rune Chamber",
        description=(
            "A circular room whose walls are covered in carved runes. "
            "Four stone pillars, each bearing a different symbol, surround a central dais."
        ),
        active_player_names=["Aldric"],
        public_facts=[
            "The runes glow faintly when touched.",
            "The exit door has a recessed slot matching the shape of the central dais.",
        ],
    )


def make_bram_npc() -> NpcContext:
    """Innkeeper Bram — nervous, hiding information about a local gang."""
    return NpcContext(
        npc_id="npc-bram-001",
        name="Bram",
        archetype="innkeeper",
        disposition="nervous",
        known_facts=[
            "The Redcloak gang has been extorting local businesses.",
            "His daughter was taken as leverage three days ago.",
        ],
        memory_tags=[
            "Seen Aldric defend a traveler from pickpockets last winter.",
            "Doesn't know Mirela.",
        ],
        durable_mind=(
            "Bram is a stocky, middle-aged man with a kind face hardened by worry. "
            "He's normally chatty and generous but is currently terrified. "
            "He won't volunteer information about the gang unless he trusts the party completely."
        ),
    )


def make_aldric_player() -> PlayerContext:
    """Aldric — fighter, healthy."""
    return PlayerContext(
        player_id="player-aldric-001",
        character_name="Aldric",
        character_class="Fighter",
        hp_current=18,
        hp_max=20,
        status_effects=[],
        inventory_summary="Longsword, chainmail, torch (x2), 15 gold",
    )


def make_torvek_player() -> PlayerContext:
    """Torvek — rogue, poisoned."""
    return PlayerContext(
        player_id="player-torvek-001",
        character_name="Torvek",
        character_class="Rogue",
        hp_current=9,
        hp_max=14,
        status_effects=["poisoned"],
        inventory_summary="Short sword, leather armor, thieves' tools",
    )


def make_attack_action(
    character_name: str = "Aldric",
    target: str = "goblin leader",
    player_id: str = "player-aldric-001",
) -> ActionContext:
    return ActionContext(
        player_id=player_id,
        character_name=character_name,
        action_type="attack",
        target=target,
        notes="",
    )


def make_persuade_action(
    character_name: str = "Mirela",
    target: str = "Bram",
    player_id: str = "player-mirela-001",
) -> ActionContext:
    return ActionContext(
        player_id=player_id,
        character_name=character_name,
        action_type="persuade",
        target=target,
        notes="Offers to help find his daughter",
    )


def make_inspect_action(
    character_name: str = "Aldric",
    target: str = "northern pillar",
    player_id: str = "player-aldric-001",
) -> ActionContext:
    return ActionContext(
        player_id=player_id,
        character_name=character_name,
        action_type="inspect",
        target=target,
        notes="",
    )


def make_recent_history() -> RecentHistory:
    """Three recent public messages (oldest first)."""
    return RecentHistory(
        messages=[
            "Aldric: I approach the bar and order two ales.",
            "Mirela: I take a seat by the fire and watch the room.",
            "Referee: Bram serves you quickly, his hands trembling slightly.",
        ]
    )


# ---------------------------------------------------------------------------
# Valid raw JSON responses for schema validation tests
# ---------------------------------------------------------------------------

VALID_NARRATION_JSON = (
    '{"narration": "The party enters the tavern, drawing a few suspicious glances. '
    'Bram hurries over, his smile strained.", '
    '"private_notes": "Bram is actively scanning for Redcloak watchers.", '
    '"tone": "tense"}'
)

VALID_NPC_DIALOGUE_JSON = (
    '{"dialogue": "W-welcome, friends. What... what brings you to the Rusty Flagon tonight?", '
    '"action_beat": "Bram wipes the counter repeatedly without looking up.", '
    '"mood": "nervous"}'
)

VALID_COMBAT_SUMMARY_JSON = (
    '{"summary": "Aldric\'s blade sings as he drives the goblin leader back into the shadows. '
    'The remaining goblins scatter momentarily.", '
    '"outcomes": ['
    '{"entity": "goblin leader", "result": "hit", "detail": "12 damage, staggered"}, '
    '{"entity": "Aldric", "result": "miss", "detail": "counter-slash goes wide"}'
    "], "
    '"tension": "high"}'
)

VALID_RULING_PROPOSAL_JSON = (
    '{"ruling": "allow_with_condition", '
    '"condition": "Aldric must succeed on a DC 14 Athletics check", '
    '"reason": "Leaping the chasm is plausible for a trained fighter but not trivial.", '
    '"suggested_action_type": "athletic_leap", '
    '"difficulty_class": 14}'
)

VALID_SOCIAL_ARBITRATION_JSON = (
    '{"outcome": "partial_success", '
    '"narration": "Bram\'s composure cracks slightly. He leans in and whispers something about \'the red cloaks\'.", '
    '"trust_delta": {"npc-bram-001": 1}, '
    '"private_notes": "Bram is one more trust point away from revealing his daughter\'s location."}'
)

VALID_PUZZLE_FLAVOR_JSON = (
    '{"flavor": "As Aldric touches the northern pillar, the rune glows a warm amber. '
    'A low hum fills the chamber.", '
    '"hint": "Three more symbols remain dark.", '
    '"progress": "partial"}'
)

# ---------------------------------------------------------------------------
# Invalid / malformed JSON responses for failure-path tests
# ---------------------------------------------------------------------------

INVALID_JSON_RAW = "This is not JSON at all. Just prose."

MISSING_REQUIRED_FIELD_NARRATION = (
    '{"private_notes": "Some notes", "tone": "tense"}'  # missing 'narration'
)

MISSING_REQUIRED_FIELD_DIALOGUE = (
    '{"action_beat": "NPC fidgets", "mood": "nervous"}'  # missing 'dialogue'
)

MISSING_REQUIRED_FIELD_RULING = (
    '{"ruling": "allow", "condition": ""}'  # missing 'reason'
)

INVALID_RULING_VALUE = '{"ruling": "maybe", "reason": "Not sure"}'

EMPTY_NARRATION_FIELD = (
    '{"narration": "   ", "tone": "neutral"}'  # whitespace-only narration
)

# A response that is valid JSON but has wrong ruling enum
BAD_RULING_ENUM_JSON = (
    '{"ruling": "perhaps", "reason": "The action seems reasonable.", '
    '"condition": "", "suggested_action_type": "", "difficulty_class": null}'
)

# Valid structure but out-of-range difficulty_class (should be silently clamped to None)
OUT_OF_RANGE_DC_JSON = (
    '{"ruling": "allow_with_condition", '
    '"condition": "DC check required", '
    '"reason": "Difficult but possible.", '
    '"suggested_action_type": "jump", '
    '"difficulty_class": 99}'
)

# Repairable JSON: missing closing brace
REPAIRABLE_NARRATION_JSON = (
    '{"narration": "The party moves forward cautiously.", "tone": "neutral"'
    # missing closing }
)

# ---------------------------------------------------------------------------
# Combat outcome fixtures
# ---------------------------------------------------------------------------

SAMPLE_COMBAT_OUTCOMES = [
    {
        "entity": "goblin warrior 1",
        "result": "defeat",
        "detail": "killed by Aldric's strike",
    },
    {"entity": "Torvek", "result": "hit", "detail": "4 damage from goblin crossbow"},
    {"entity": "goblin warrior 2", "result": "miss", "detail": "swing goes wide"},
]
