"""Fast-tier prompt contracts.

Each fast-tier task has a PromptContract that codifies the system prompt,
user prompt template, output schema, token limits, scope rules, and
deterministic fallback.  The contracts registry replaces ad-hoc prompt
strings scattered across models/fast/tasks.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PromptContract:
    """Versioned prompt contract for one LLM task."""

    contract_id: str  # e.g. "fast.intent_classification"
    version: str  # semver
    tier: str  # "fast" | "main"
    task_type: str  # matches TaskType or MainTaskType value
    system_prompt_template: str  # may contain {placeholders}
    user_prompt_template: str
    input_fields: list[str]
    output_schema: dict  # JSON Schema dict
    output_example: str  # example valid JSON string
    max_input_tokens: int
    max_output_tokens: int
    scope_rules: list[str] = field(default_factory=list)
    fallback_output: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Fast-tier contracts registry
# ---------------------------------------------------------------------------

FAST_CONTRACTS: dict[str, PromptContract] = {}


def _register(contract: PromptContract) -> PromptContract:
    FAST_CONTRACTS[contract.contract_id] = contract
    return contract


# --- intent_classification ------------------------------------------------

_register(
    PromptContract(
        contract_id="fast.intent_classification",
        version="1.0.0",
        tier="fast",
        task_type="intent_classification",
        system_prompt_template=(
            "You are a message classifier for a text RPG. "
            "Classify the player message and reply with valid JSON only. "
            "Schema: {output_schema_inline}"
        ),
        user_prompt_template=(
            'Classify this player message:\n"""\n{message_text}\n"""'
        ),
        input_fields=["message_text"],
        output_schema={
            "type": "object",
            "required": ["intent", "confidence"],
            "properties": {
                "intent": {
                    "type": "string",
                    "enum": ["action", "question", "chat", "command", "unknown"],
                },
                "confidence": {"type": "string", "enum": ["high", "low"]},
            },
        },
        output_example='{"intent": "action", "confidence": "high"}',
        max_input_tokens=2048,
        max_output_tokens=128,
        scope_rules=["public_only"],
        fallback_output={"intent": "unknown", "confidence": "low"},
    )
)

# --- command_normalization ------------------------------------------------

_register(
    PromptContract(
        contract_id="fast.command_normalization",
        version="1.0.0",
        tier="fast",
        task_type="command_normalization",
        system_prompt_template=(
            "You are a command normalizer for a text RPG. "
            "Clean the player input into a normalized command string. "
            "Reply with valid JSON only. "
            "Schema: {output_schema_inline}"
        ),
        user_prompt_template=('Normalize this player input:\n"""\n{message_text}\n"""'),
        input_fields=["message_text"],
        output_schema={
            "type": "object",
            "required": ["normalized"],
            "properties": {
                "normalized": {"type": "string"},
            },
        },
        output_example='{"normalized": "attack goblin"}',
        max_input_tokens=2048,
        max_output_tokens=128,
        scope_rules=["public_only"],
        fallback_output={"normalized": ""},
    )
)

# --- action_packet_extraction ---------------------------------------------

_register(
    PromptContract(
        contract_id="fast.action_extraction",
        version="1.0.0",
        tier="fast",
        task_type="action_packet_extraction",
        system_prompt_template=(
            "You are an action parser for a text RPG. "
            "Extract the player's intended action from their message. "
            "Reply with valid JSON only. "
            "Schema: {output_schema_inline}"
        ),
        user_prompt_template=(
            'Extract the action from this player message:\n"""\n{message_text}\n"""'
        ),
        input_fields=["message_text"],
        output_schema={
            "type": "object",
            "required": ["action_type", "target", "item_ids", "notes"],
            "properties": {
                "action_type": {"type": "string"},
                "target": {"type": "string"},
                "item_ids": {"type": "array", "items": {"type": "string"}},
                "notes": {"type": "string"},
            },
        },
        output_example='{"action_type": "attack", "target": "goblin", "item_ids": [], "notes": ""}',
        max_input_tokens=2048,
        max_output_tokens=256,
        scope_rules=["public_only"],
        fallback_output={
            "action_type": "unknown",
            "target": "",
            "item_ids": [],
            "notes": "",
        },
    )
)

# --- scope_suggestion -----------------------------------------------------

_register(
    PromptContract(
        contract_id="fast.scope_suggestion",
        version="1.0.0",
        tier="fast",
        task_type="scope_suggestion",
        system_prompt_template=(
            "You are a scope classifier for a text RPG. "
            "Decide whether a player message should be public (visible to all), "
            "private_referee (shared only with the game referee), or side_channel "
            "(shared within a small player sub-group). "
            "Reply with valid JSON only. "
            "Schema: {output_schema_inline}"
        ),
        user_prompt_template=(
            'Classify the scope of this player message:\n"""\n{message_text}\n"""'
        ),
        input_fields=["message_text"],
        output_schema={
            "type": "object",
            "required": ["suggested_scope", "reasoning"],
            "properties": {
                "suggested_scope": {
                    "type": "string",
                    "enum": ["public", "private_referee", "side_channel"],
                },
                "reasoning": {"type": "string"},
            },
        },
        output_example='{"suggested_scope": "public", "reasoning": "General chat message."}',
        max_input_tokens=2048,
        max_output_tokens=128,
        scope_rules=["public_only"],
        fallback_output={"suggested_scope": "public", "reasoning": ""},
    )
)

# --- context_summarization ------------------------------------------------

_register(
    PromptContract(
        contract_id="fast.context_summarization",
        version="1.0.0",
        tier="fast",
        task_type="context_summarization",
        system_prompt_template=(
            "You are a context summarizer for a text RPG. "
            "Summarize the following recent messages in at most {max_words} words. "
            "Reply with valid JSON only. "
            "Schema: {output_schema_inline}"
        ),
        user_prompt_template=(
            "Summarize these recent game messages:\n{combined_messages}"
        ),
        input_fields=["combined_messages", "max_words"],
        output_schema={
            "type": "object",
            "required": ["summary"],
            "properties": {
                "summary": {"type": "string"},
            },
        },
        output_example='{"summary": "The party entered the cave and fought goblins."}',
        max_input_tokens=2048,
        max_output_tokens=256,
        scope_rules=["public_only"],
        fallback_output={"summary": ""},
    )
)

# --- clarification_generation ---------------------------------------------

_register(
    PromptContract(
        contract_id="fast.clarification_generation",
        version="1.0.0",
        tier="fast",
        task_type="clarification_generation",
        system_prompt_template=(
            "You are an assistant referee for a text RPG. "
            "Write a short, clear question to resolve an ambiguous player action. "
            "The question must be one sentence, under 20 words. "
            "Reply with valid JSON only. "
            "Schema: {output_schema_inline}"
        ),
        user_prompt_template=(
            'Player said:\n"""\n{message_text}\n"""\n\n'
            "Ambiguity: {ambiguity_reason}\n\n"
            "What clarification question should the referee ask?"
        ),
        input_fields=["message_text", "ambiguity_reason"],
        output_schema={
            "type": "object",
            "required": ["question"],
            "properties": {
                "question": {"type": "string"},
            },
        },
        output_example='{"question": "Did you mean the wooden door or the iron gate?"}',
        max_input_tokens=2048,
        max_output_tokens=128,
        scope_rules=["public_only"],
        fallback_output={"question": "Could you clarify what you meant?"},
    )
)

# --- schema_repair --------------------------------------------------------

_register(
    PromptContract(
        contract_id="fast.schema_repair",
        version="1.0.0",
        tier="fast",
        task_type="schema_repair",
        system_prompt_template=(
            "You are a JSON repair specialist. "
            "Fix the malformed JSON so it matches the given schema. "
            "Reply with the repaired JSON only -- no explanation, no markdown fences."
        ),
        user_prompt_template=(
            "Schema:\n{schema_description}\n\n"
            "Malformed JSON:\n{malformed_json}\n\n"
            "Output the corrected JSON:"
        ),
        input_fields=["schema_description", "malformed_json"],
        output_schema={
            "type": "object",
            "description": "Any valid JSON matching the target schema",
        },
        output_example="{}",
        max_input_tokens=4096,
        max_output_tokens=512,
        scope_rules=[],
        fallback_output={},
    )
)


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


def get_fast_contract(task_type: str) -> PromptContract:
    """Look up a fast-tier contract by task_type.

    Raises KeyError if the task_type has no registered contract.
    """
    for contract in FAST_CONTRACTS.values():
        if contract.task_type == task_type:
            return contract
    raise KeyError(f"No fast-tier contract for task_type={task_type!r}")
