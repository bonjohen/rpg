"""Main-tier (GPT-5.4 mini via OpenAI) prompt contracts.

One contract per main-tier task type.  Each contract codifies the system
prompt, user prompt template, expected JSON output schema, scope rules, and
deterministic fallback so that prompt assembly, validation, and failure
handling are testable and auditable.
"""

from __future__ import annotations

from models.contracts.fast_contracts import PromptContract

# ---------------------------------------------------------------------------
# Main-tier contracts registry
# ---------------------------------------------------------------------------

MAIN_CONTRACTS: dict[str, PromptContract] = {}


def _register(contract: PromptContract) -> PromptContract:
    MAIN_CONTRACTS[contract.contract_id] = contract
    return contract


# ---------------------------------------------------------------------------
# Style guides — injected into system prompts for consistent narration
# ---------------------------------------------------------------------------

NARRATION_STYLE_GUIDE = (
    "Style rules:\n"
    "- Use second-person plural ('you') for the party.\n"
    "- Keep paragraphs to 2-3 sentences maximum.\n"
    "- Lead with sensory details (sight, sound, smell) before exposition.\n"
    "- End narration with an implicit prompt for player action.\n"
    "- Never address players by real name -- use character names only.\n"
    "- Vary sentence structure. Avoid starting consecutive sentences the same way.\n"
    "- For combat: lead with the most dramatic action, then resolve others concisely.\n"
    "- For exploration: prioritize spatial orientation, then notable features.\n"
    "- For social: lead with the NPC's most visible reaction, then dialogue.\n\n"
    "Pacing rules:\n"
    "- Exploration turns: 2-4 sentences of narration.\n"
    "- Social turns: 1-2 sentences of NPC reaction + 1-3 sentences of dialogue.\n"
    "- Combat turns: 3-5 sentences covering all combatant actions.\n"
    "- Discovery moments: Allow 1 extra sentence for atmosphere.\n"
)

DIALOGUE_STYLE_GUIDE = (
    "- Stay in character at all times.\n"
    "- Reference specific personality tags in your tone and word choice.\n"
    "- If trust is low, be evasive or hostile as appropriate.\n"
    "- If trust is high, be more forthcoming but stay in character.\n"
    "- Never break the fourth wall or reference game mechanics.\n"
    "- Use dialogue tags sparingly ('says', 'replies') -- prefer action beats.\n"
    "- Maximum 3 sentences of dialogue per response.\n"
)


# --- scene_narration ------------------------------------------------------

_register(
    PromptContract(
        contract_id="main.scene_narration",
        version="1.1.0",
        tier="main",
        task_type="scene_narration",
        system_prompt_template=(
            "You are the narrator for a multiplayer text RPG. "
            "Write vivid, concise scene narration. Use second-person plural ('you'). "
            "Do not reveal hidden information. Stay within the facts provided. "
            "Reply with valid JSON only. Schema: {output_schema_inline}\n\n"
            + NARRATION_STYLE_GUIDE
        ),
        user_prompt_template=(
            "Scene: {scene_context}\n\n"
            "Players: {active_players}\n\n"
            "Committed actions:\n{committed_actions}\n\n"
            "Known facts:\n{public_facts}\n\n"
            "{history_block}"
            "Write the official public narration for this turn."
        ),
        input_fields=[
            "scene_context",
            "committed_actions",
            "public_facts",
            "active_players",
            "tone_hint",
        ],
        output_schema={
            "type": "object",
            "required": ["narration"],
            "properties": {
                "narration": {"type": "string"},
                "private_notes": {"type": "string"},
                "tone": {
                    "type": "string",
                    "enum": ["neutral", "tense", "triumphant", "ominous", "comic"],
                },
            },
        },
        output_example=(
            '{"narration": "You press deeper into the cave.", '
            '"private_notes": "", "tone": "tense"}'
        ),
        max_input_tokens=16384,
        max_output_tokens=2048,
        scope_rules=["no_referee_facts", "no_side_channel_facts", "public_facts_only"],
        fallback_output={
            "narration": "The party pauses. The results of their actions settle around them.",
            "private_notes": "[Fallback narration]",
            "tone": "neutral",
        },
    )
)

# --- npc_dialogue ---------------------------------------------------------

_register(
    PromptContract(
        contract_id="main.npc_dialogue",
        version="1.1.0",
        tier="main",
        task_type="npc_dialogue",
        system_prompt_template=(
            "You are voicing an NPC in a text RPG. Stay in character based on "
            "the personality, goals, and trust level provided. Do not reveal "
            "information the NPC would not share at this trust level. "
            "Reply with valid JSON only. Schema: {output_schema_inline}\n\n"
            + DIALOGUE_STYLE_GUIDE
        ),
        user_prompt_template=(
            "NPC: {npc_context}\n\n"
            "Scene: {scene_context}\n\n"
            "Action: {action_context}\n\n"
            "Dialogue hints: {dialogue_hints}\n\n"
            "Write the NPC's spoken dialogue and any brief action beat."
        ),
        input_fields=[
            "npc_context",
            "action_context",
            "scene_context",
            "dialogue_hints",
        ],
        output_schema={
            "type": "object",
            "required": ["dialogue"],
            "properties": {
                "dialogue": {"type": "string"},
                "action_beat": {"type": "string"},
                "mood": {
                    "type": "string",
                    "enum": [
                        "friendly",
                        "hostile",
                        "nervous",
                        "neutral",
                        "suspicious",
                    ],
                },
            },
        },
        output_example=(
            '{"dialogue": "Welcome, travelers.", '
            '"action_beat": "The innkeeper sets down a mug.", '
            '"mood": "friendly"}'
        ),
        max_input_tokens=8192,
        max_output_tokens=1024,
        scope_rules=["npc_scoped", "no_other_npc_facts"],
        fallback_output={
            "dialogue": "The NPC remains silent for a moment.",
            "action_beat": "",
            "mood": "neutral",
        },
    )
)

# --- combat_summary -------------------------------------------------------

_register(
    PromptContract(
        contract_id="main.combat_summary",
        version="1.1.0",
        tier="main",
        task_type="combat_summary",
        system_prompt_template=(
            "You are the narrator for a multiplayer text RPG. "
            "Write vivid combat narration based only on the provided "
            "mechanically-resolved outcomes. Do not invent outcomes. "
            "Reply with valid JSON only. Schema: {output_schema_inline}\n\n"
            + NARRATION_STYLE_GUIDE
        ),
        user_prompt_template=(
            "Battlefield: {battlefield_summary}\n\n"
            "Action results:\n{action_results}\n\n"
            "Scene: {scene_context}\n\n"
            "Write the public combat narration."
        ),
        input_fields=["battlefield_summary", "action_results", "scene_context"],
        output_schema={
            "type": "object",
            "required": ["summary"],
            "properties": {
                "summary": {"type": "string"},
                "outcomes": {
                    "type": "array",
                    "items": {"type": "object"},
                },
                "tension": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                },
            },
        },
        output_example='{"summary": "Steel clashes in the darkness.", "outcomes": [], "tension": "high"}',
        max_input_tokens=8192,
        max_output_tokens=1024,
        scope_rules=["public_only", "no_hidden_monster_stats"],
        fallback_output={
            "summary": "The exchange of blows concludes. The dust settles.",
            "outcomes": [],
            "tension": "medium",
        },
    )
)

# --- ruling_proposal ------------------------------------------------------

_register(
    PromptContract(
        contract_id="main.ruling_proposal",
        version="1.0.0",
        tier="main",
        task_type="ruling_proposal",
        system_prompt_template=(
            "You are the rules arbiter for an AI-refereed text RPG. "
            "Evaluate the player's action against the game rules and scene context. "
            "Propose a ruling. Be fair, consistent, and brief. "
            "Reply with valid JSON only. Schema: {output_schema_inline}"
        ),
        user_prompt_template=(
            "Action: {action_text}\n\n"
            "Character: {character_context}\n\n"
            "Scene: {scene_context}\n\n"
            "Rules:\n{relevant_rules}\n\n"
            "Propose a ruling on this action."
        ),
        input_fields=[
            "action_text",
            "character_context",
            "scene_context",
            "relevant_rules",
        ],
        output_schema={
            "type": "object",
            "required": ["ruling", "reason"],
            "properties": {
                "ruling": {
                    "type": "string",
                    "enum": [
                        "allow",
                        "allow_with_condition",
                        "deny",
                        "request_clarification",
                    ],
                },
                "reason": {"type": "string"},
                "condition": {"type": "string"},
                "suggested_action_type": {"type": "string"},
                "difficulty_class": {"type": "integer"},
            },
        },
        output_example=(
            '{"ruling": "allow", "reason": "Action is valid within the scene context."}'
        ),
        max_input_tokens=8192,
        max_output_tokens=512,
        scope_rules=["minimal_private_facts"],
        fallback_output={
            "ruling": "request_clarification",
            "reason": "Unable to evaluate at this time.",
            "condition": "",
            "suggested_action_type": "",
            "difficulty_class": None,
        },
    )
)

# --- social_arbitration ---------------------------------------------------

_register(
    PromptContract(
        contract_id="main.social_arbitration",
        version="1.0.0",
        tier="main",
        task_type="social_arbitration",
        system_prompt_template=(
            "You are the social arbiter for an AI-refereed text RPG. "
            "Resolve the described social situation fairly. "
            "Narrate the public outcome and note any trust or attitude shifts. "
            "Reply with valid JSON only. Schema: {output_schema_inline}"
        ),
        user_prompt_template=(
            "Situation: {situation}\n\n"
            "Scene: {scene_context}\n\n"
            "Players involved: {players}\n\n"
            "NPCs involved: {npcs}\n\n"
            "Resolve the social situation and narrate the outcome."
        ),
        input_fields=["situation", "scene_context", "players", "npcs"],
        output_schema={
            "type": "object",
            "required": ["outcome", "narration"],
            "properties": {
                "outcome": {
                    "type": "string",
                    "enum": [
                        "success",
                        "partial_success",
                        "failure",
                        "escalation",
                    ],
                },
                "narration": {"type": "string"},
                "trust_delta": {"type": "object"},
                "private_notes": {"type": "string"},
            },
        },
        output_example=(
            '{"outcome": "success", "narration": "Diplomacy prevails.", '
            '"trust_delta": {}, "private_notes": ""}'
        ),
        max_input_tokens=8192,
        max_output_tokens=1024,
        scope_rules=["public_only"],
        fallback_output={
            "outcome": "failure",
            "narration": "The attempt at resolution remains inconclusive.",
            "trust_delta": {},
            "private_notes": "[Fallback]",
        },
    )
)

# --- puzzle_flavor --------------------------------------------------------

_register(
    PromptContract(
        contract_id="main.puzzle_flavor",
        version="1.0.0",
        tier="main",
        task_type="puzzle_flavor",
        system_prompt_template=(
            "You are the narrative voice for an AI-refereed text RPG. "
            "Describe the player's interaction with the puzzle in immersive prose. "
            "Do not reveal the puzzle solution. "
            "Reply with valid JSON only. Schema: {output_schema_inline}"
        ),
        user_prompt_template=(
            "Puzzle: {puzzle_description}\n\n"
            "Scene: {scene_context}\n\n"
            "Action: {action_text}\n\n"
            "State: {puzzle_state}\n\n"
            "Narrate the puzzle interaction."
        ),
        input_fields=[
            "puzzle_description",
            "scene_context",
            "action_text",
            "puzzle_state",
        ],
        output_schema={
            "type": "object",
            "required": ["flavor"],
            "properties": {
                "flavor": {"type": "string"},
                "hint": {"type": "string"},
                "progress": {
                    "type": "string",
                    "enum": ["none", "partial", "solved", "failed"],
                },
            },
        },
        output_example='{"flavor": "You study the mechanism.", "hint": "", "progress": "none"}',
        max_input_tokens=8192,
        max_output_tokens=1024,
        scope_rules=["public_only", "no_solution_hints"],
        fallback_output={
            "flavor": "You study the puzzle carefully, but the answer eludes you for now.",
            "hint": "",
            "progress": "none",
        },
    )
)

# --- unusual_action -------------------------------------------------------

_register(
    PromptContract(
        contract_id="main.unusual_action",
        version="1.0.0",
        tier="main",
        task_type="unusual_action_interpretation",
        system_prompt_template=(
            "You are the rules interpreter for an AI-refereed text RPG. "
            "Interpret an unusual player action that standard rules cannot classify. "
            "Reply with valid JSON only. Schema: {output_schema_inline}"
        ),
        user_prompt_template=(
            "Action: {action_text}\n\n"
            "Character: {character_context}\n\n"
            "Scene: {scene_context}\n\n"
            "Interpret this unusual action and suggest how to resolve it."
        ),
        input_fields=["action_text", "character_context", "scene_context"],
        output_schema={
            "type": "object",
            "required": ["interpretation", "suggested_resolution"],
            "properties": {
                "interpretation": {"type": "string"},
                "suggested_resolution": {"type": "string"},
                "difficulty_class": {"type": "integer"},
                "requires_roll": {"type": "boolean"},
            },
        },
        output_example=(
            '{"interpretation": "Player attempts to climb the wall.", '
            '"suggested_resolution": "Dexterity check", '
            '"difficulty_class": 12, "requires_roll": true}'
        ),
        max_input_tokens=8192,
        max_output_tokens=512,
        scope_rules=["minimal_private_facts"],
        fallback_output={
            "interpretation": "Unable to interpret the action.",
            "suggested_resolution": "request_clarification",
            "difficulty_class": 10,
            "requires_roll": False,
        },
    )
)


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


def get_main_contract(task_type: str) -> PromptContract:
    """Look up a main-tier contract by task_type.

    Raises KeyError if the task_type has no registered contract.
    """
    for contract in MAIN_CONTRACTS.values():
        if contract.task_type == task_type:
            return contract
    raise KeyError(f"No main-tier contract for task_type={task_type!r}")
