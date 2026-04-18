"""Scoped context assembly for main-tier model calls.

Builds the prompt context packet for each task type using only the facts
allowed for that call, per model_routing.md Scoped Knowledge Packets rules.

Scoping rules:
  - Public narration call: public scene state, all public facts, committed
    action summaries. No referee-only facts.
  - NPC dialogue call: NPC hard state + durable mind for that NPC, NPC's
    known facts, scene context. No other NPC private facts.
  - Ruling proposal call: the specific action, relevant rules, player
    character state, scene context. Minimal private facts relevant only to
    the ruling.

Prompt size limits (per model_routing.md):
  - Target: < 16K tokens.
  - Hard limit: 32K tokens (standard); 256K (deep-context).
  - Truncation policy: drop oldest public chat history first, before
    dropping scene state or player facts.

Token estimation: rough heuristic of 4 characters per token. Accurate
token counting requires a tokenizer; this estimate is conservative and
sufficient for the truncation guard.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Input dataclasses (lightweight containers — no ORM/DB dependency)
# ---------------------------------------------------------------------------


@dataclass
class SceneContext:
    """Minimal scene state needed for any main-tier prompt."""

    scene_id: str
    location_name: str
    description: str
    active_player_names: list[str] = field(default_factory=list)
    public_facts: list[str] = field(default_factory=list)


@dataclass
class PlayerContext:
    """Minimal player/character state for prompt assembly."""

    player_id: str
    character_name: str
    character_class: str = ""
    hp_current: int = 0
    hp_max: int = 0
    status_effects: list[str] = field(default_factory=list)
    inventory_summary: str = ""


@dataclass
class NpcContext:
    """Minimal NPC state for dialogue and social calls."""

    npc_id: str
    name: str
    archetype: str = ""
    disposition: str = "neutral"
    known_facts: list[str] = field(default_factory=list)
    memory_tags: list[str] = field(default_factory=list)
    durable_mind: str = ""  # personality / backstory excerpt


@dataclass
class ActionContext:
    """A player's committed action summary for context assembly."""

    player_id: str
    character_name: str
    action_type: str
    target: str = ""
    notes: str = ""


@dataclass
class RecentHistory:
    """Recent public turn messages (oldest first)."""

    messages: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Token budget helpers
# ---------------------------------------------------------------------------

CHARS_PER_TOKEN_ESTIMATE = 4
TARGET_TOKENS = 16_000
HARD_LIMIT_TOKENS = 32_000


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: 4 chars ≈ 1 token."""
    return max(1, len(text) // CHARS_PER_TOKEN_ESTIMATE)


def _truncate_history(messages: list[str], budget_chars: int) -> list[str]:
    """Return as many recent messages as fit within budget_chars (newest kept)."""
    kept: list[str] = []
    used = 0
    for msg in reversed(messages):
        cost = len(msg) + 1  # +1 for newline separator
        if used + cost > budget_chars:
            break
        kept.append(msg)
        used += cost
    return list(reversed(kept))


# ---------------------------------------------------------------------------
# Prompt assembly functions (one per main-tier task type)
# ---------------------------------------------------------------------------


def assemble_narration_prompt(
    scene: SceneContext,
    committed_actions: list[ActionContext],
    recent_history: RecentHistory | None = None,
    *,
    token_limit: int = TARGET_TOKENS,
) -> tuple[str, str]:
    """Build (system_prompt, user_prompt) for a scene_narration call.

    Only public-safe content is included — no referee-only facts.

    Returns:
        (system_prompt, user_prompt) both as plain strings.
    """
    system = (
        "You are the narrative voice for an AI-refereed multiplayer text RPG. "
        "Write vivid, immersive scene narration in second-person plural perspective. "
        "Base the narration solely on the facts provided. "
        "Do not invent facts, NPCs, or items not listed. "
        "Do not reveal hidden referee information. "
        "Reply with valid JSON only. "
        "Schema: {'narration': 'string', 'private_notes': 'string', 'tone': 'neutral|tense|triumphant|ominous|comic'}"
    )

    # Budget: reserve ~20% of char limit for system prompt overhead
    char_limit = token_limit * CHARS_PER_TOKEN_ESTIMATE

    scene_block = _format_scene_block(scene)
    actions_block = _format_actions_block(committed_actions)

    history_block = ""
    if recent_history and recent_history.messages:
        used = len(system) + len(scene_block) + len(actions_block)
        history_budget = max(0, char_limit - used - 200)
        kept = _truncate_history(recent_history.messages, history_budget)
        if kept:
            history_block = "Recent events:\n" + "\n".join(f"  - {m}" for m in kept)

    parts = [scene_block, actions_block]
    if history_block:
        parts.append(history_block)
    parts.append(
        "Write the official public narration for this turn. "
        "Include any relevant private notes for the referee."
    )

    user_prompt = "\n\n".join(p for p in parts if p)
    return system, user_prompt


def assemble_npc_dialogue_prompt(
    npc: NpcContext,
    scene: SceneContext,
    trigger_action: ActionContext | None = None,
    *,
    token_limit: int = TARGET_TOKENS,
) -> tuple[str, str]:
    """Build (system_prompt, user_prompt) for an npc_dialogue call.

    Only the target NPC's facts are included — no other NPC private data.
    """
    system = (
        f"You are voicing {npc.name}, an NPC in an AI-refereed text RPG. "
        f"Archetype: {npc.archetype or 'unknown'}. "
        f"Current disposition toward the party: {npc.disposition}. "
        f"Personality: {npc.durable_mind or 'not specified'}. "
        "Write natural, in-character dialogue. "
        "Do not break character or reference game mechanics directly. "
        "Reply with valid JSON only. "
        'Schema: {"dialogue": "string", "action_beat": "string", "mood": "friendly|hostile|nervous|neutral|suspicious"}'
    )

    parts: list[str] = []
    parts.append(f"Scene: {scene.location_name}\n{scene.description}")

    if npc.known_facts:
        parts.append(
            "What {name} knows:\n{facts}".format(
                name=npc.name,
                facts="\n".join(f"  - {f}" for f in npc.known_facts),
            )
        )

    if npc.memory_tags:
        parts.append(
            "What {name} remembers about the party:\n{tags}".format(
                name=npc.name,
                tags="\n".join(f"  - {t}" for t in npc.memory_tags),
            )
        )

    if trigger_action:
        parts.append(
            f"{trigger_action.character_name} just performed: "
            f"{trigger_action.action_type}"
            + (f" targeting {trigger_action.target}" if trigger_action.target else "")
            + (f" ({trigger_action.notes})" if trigger_action.notes else "")
        )

    parts.append(f"Write {npc.name}'s spoken dialogue and any brief action beat.")

    user_prompt = "\n\n".join(parts)
    return system, user_prompt


def assemble_ruling_proposal_prompt(
    action: ActionContext,
    scene: SceneContext,
    acting_player: PlayerContext,
    relevant_rules: list[str] | None = None,
    *,
    token_limit: int = TARGET_TOKENS,
) -> tuple[str, str]:
    """Build (system_prompt, user_prompt) for a ruling_proposal call.

    Includes only the specific action, relevant rules, player state, and
    scene context. Minimal private facts relevant to the ruling only.
    """
    system = (
        "You are the rules arbiter for an AI-refereed text RPG. "
        "Evaluate the player's action against the game rules and scene context. "
        "Propose a ruling: allow, allow_with_condition, deny, or request_clarification. "
        "Be fair, consistent, and brief. "
        "Reply with valid JSON only. "
        "Schema: {"
        '"ruling": "allow|allow_with_condition|deny|request_clarification", '
        '"condition": "string", '
        '"reason": "string (one sentence)", '
        '"suggested_action_type": "string", '
        '"difficulty_class": "integer 1-20 or null"}'
    )

    parts: list[str] = []

    # Player context
    hp_str = (
        f"{acting_player.hp_current}/{acting_player.hp_max}"
        if acting_player.hp_max
        else "unknown"
    )
    char_desc = (
        f"Character: {acting_player.character_name}"
        + (
            f" ({acting_player.character_class})"
            if acting_player.character_class
            else ""
        )
        + f", HP: {hp_str}"
    )
    if acting_player.status_effects:
        char_desc += f", Status: {', '.join(acting_player.status_effects)}"
    if acting_player.inventory_summary:
        char_desc += f", Inventory: {acting_player.inventory_summary}"
    parts.append(char_desc)

    # Scene
    parts.append(f"Scene: {scene.location_name}\n{scene.description}")
    if scene.public_facts:
        parts.append(
            "Relevant scene facts:\n"
            + "\n".join(f"  - {f}" for f in scene.public_facts)
        )

    # Requested action
    action_str = (
        f"Requested action: {action.action_type}"
        + (f" targeting '{action.target}'" if action.target else "")
        + (f" — {action.notes}" if action.notes else "")
    )
    parts.append(action_str)

    # Optional rules excerpts
    if relevant_rules:
        rules_text = "\n".join(f"  - {r}" for r in relevant_rules)
        parts.append(f"Relevant rules:\n{rules_text}")

    parts.append("Propose a ruling on this action.")

    user_prompt = "\n\n".join(parts)
    return system, user_prompt


def assemble_combat_summary_prompt(
    scene: SceneContext,
    combat_outcomes: list[dict],
    committed_actions: list[ActionContext],
    *,
    token_limit: int = TARGET_TOKENS,
) -> tuple[str, str]:
    """Build (system_prompt, user_prompt) for a combat_summary call."""
    system = (
        "You are the narrative voice for an AI-refereed multiplayer text RPG. "
        "Write vivid combat narration based only on the provided mechanically-resolved outcomes. "
        "Do not invent outcomes; describe the given results dramatically. "
        "Reply with valid JSON only. "
        "Schema: {"
        '"summary": "string (required, public narrative)", '
        '"outcomes": [{"entity": "string", "result": "hit|miss|defeat|status_change", "detail": "string"}], '
        '"tension": "low|medium|high|critical"}'
    )

    parts: list[str] = []
    parts.append(f"Scene: {scene.location_name}\n{scene.description}")

    if committed_actions:
        action_lines = []
        for a in committed_actions:
            line = f"  - {a.character_name}: {a.action_type}"
            if a.target:
                line += f" → {a.target}"
            action_lines.append(line)
        parts.append("Actions this turn:\n" + "\n".join(action_lines))

    if combat_outcomes:
        outcome_lines = [
            f"  - {o.get('entity', '?')}: {o.get('result', '?')} ({o.get('detail', '')})"
            for o in combat_outcomes
        ]
        parts.append("Mechanical outcomes:\n" + "\n".join(outcome_lines))

    parts.append("Write the public combat narration and list the outcomes.")

    user_prompt = "\n\n".join(parts)
    return system, user_prompt


def assemble_social_arbitration_prompt(
    scene: SceneContext,
    players_involved: list[PlayerContext],
    npcs_involved: list[NpcContext],
    situation_description: str,
    *,
    token_limit: int = TARGET_TOKENS,
) -> tuple[str, str]:
    """Build (system_prompt, user_prompt) for a social_arbitration call."""
    system = (
        "You are the social arbiter for an AI-refereed text RPG. "
        "Resolve the described social situation fairly based on the provided context. "
        "Narrate the public outcome and note any trust or attitude shifts. "
        "Reply with valid JSON only. "
        "Schema: {"
        '"outcome": "success|partial_success|failure|escalation", '
        '"narration": "string (required)", '
        '"trust_delta": {"entity_id": integer_delta}, '
        '"private_notes": "string"}'
    )

    parts: list[str] = []
    parts.append(f"Scene: {scene.location_name}\n{scene.description}")
    parts.append(f"Situation:\n{situation_description}")

    if players_involved:
        player_lines = [
            f"  - {p.character_name}"
            + (f" ({p.character_class})" if p.character_class else "")
            for p in players_involved
        ]
        parts.append("Players involved:\n" + "\n".join(player_lines))

    if npcs_involved:
        npc_lines = [
            f"  - {n.name} (disposition: {n.disposition})" for n in npcs_involved
        ]
        parts.append("NPCs involved:\n" + "\n".join(npc_lines))

    parts.append("Resolve the social situation and narrate the outcome.")

    user_prompt = "\n\n".join(parts)
    return system, user_prompt


def assemble_puzzle_flavor_prompt(
    scene: SceneContext,
    puzzle_description: str,
    player_action: ActionContext,
    puzzle_state: str = "unsolved",
    *,
    token_limit: int = TARGET_TOKENS,
) -> tuple[str, str]:
    """Build (system_prompt, user_prompt) for a puzzle_flavor call."""
    system = (
        "You are the narrative voice for an AI-refereed text RPG. "
        "Describe the player's interaction with the puzzle in immersive prose. "
        "Do not reveal the puzzle solution or give direct hints unless instructed. "
        "Reply with valid JSON only. "
        "Schema: {"
        '"flavor": "string (required, public narrative)", '
        '"hint": "string (optional subtle hint)", '
        '"progress": "none|partial|solved|failed"}'
    )

    parts: list[str] = []
    parts.append(f"Scene: {scene.location_name}")
    parts.append(f"Puzzle:\n{puzzle_description}\nCurrent state: {puzzle_state}")
    action_str = (
        f"{player_action.character_name} performs: {player_action.action_type}"
        + (f" on {player_action.target}" if player_action.target else "")
        + (f" ({player_action.notes})" if player_action.notes else "")
    )
    parts.append(action_str)
    parts.append("Narrate the player's puzzle interaction.")

    user_prompt = "\n\n".join(parts)
    return system, user_prompt


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_scene_block(scene: SceneContext) -> str:
    lines = [f"Location: {scene.location_name}", scene.description]
    if scene.active_player_names:
        lines.append("Players present: " + ", ".join(scene.active_player_names))
    if scene.public_facts:
        lines.append("Known facts:")
        for f in scene.public_facts:
            lines.append(f"  - {f}")
    return "\n".join(lines)


def _format_actions_block(actions: list[ActionContext]) -> str:
    if not actions:
        return ""
    lines = ["Actions committed this turn:"]
    for a in actions:
        line = f"  - {a.character_name}: {a.action_type}"
        if a.target:
            line += f" → {a.target}"
        if a.notes:
            line += f" ({a.notes})"
        lines.append(line)
    return "\n".join(lines)
