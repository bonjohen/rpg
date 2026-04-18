"""Fast-tier task implementations.

Each public function wraps one structured LLM call. All functions:
  - Accept an OllamaFastAdapter and task-specific inputs.
  - Return a typed result dataclass + a ModelCallLog.
  - Never raise on model failure — the result includes a fallback value so
    the turn is never blocked.

Fallback policy (per model_routing.md):
  If the fast model returns garbage or times out, the server handles the
  task deterministically. Do not block a turn.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from models.fast.adapter import OllamaFastAdapter, GenerateResult
from models.fast.instrumentation import ModelCallLog
from models.fast.router import TaskType


# ---------------------------------------------------------------------------
# Intent Classification
# ---------------------------------------------------------------------------


@dataclass
class IntentClassificationResult:
    """Result of intent classification for a player message."""

    intent: str  # "action" | "question" | "chat" | "command" | "unknown"
    confidence: str  # "high" | "low"
    raw: str  # raw model output
    fallback_used: bool = False


async def classify_intent(
    adapter: OllamaFastAdapter,
    message_text: str,
    *,
    trace_id: str = "",
) -> tuple[IntentClassificationResult, ModelCallLog]:
    """Classify a player message as action, question, chat, or command."""
    trace_id = trace_id or str(uuid.uuid4())
    system = (
        "You are a message classifier for a text RPG. "
        "Classify the player message and reply with valid JSON only. "
        'Schema: {"intent": "action"|"question"|"chat"|"command", "confidence": "high"|"low"}'
    )
    prompt = f'Classify this player message:\n"""\n{message_text}\n"""'

    result = await adapter.generate(prompt, system=system, expect_json=True)
    log = _make_log(trace_id, TaskType.intent_classification, result)

    if result.success:
        try:
            data = json.loads(result.text)
            intent = data.get("intent", "unknown")
            if intent not in ("action", "question", "chat", "command"):
                intent = "unknown"
            confidence = data.get("confidence", "low")
            if confidence not in ("high", "low"):
                confidence = "low"
            return IntentClassificationResult(
                intent=intent,
                confidence=confidence,
                raw=result.text,
            ), log
        except (json.JSONDecodeError, AttributeError):
            pass

    log.fallback_triggered = True
    return IntentClassificationResult(
        intent="unknown",
        confidence="low",
        raw=result.text,
        fallback_used=True,
    ), log


# ---------------------------------------------------------------------------
# Command Normalization
# ---------------------------------------------------------------------------


@dataclass
class CommandNormResult:
    """Result of normalizing a player command string."""

    normalized: str  # e.g. "/attack goblin" → "attack goblin"
    raw: str
    fallback_used: bool = False


async def normalize_command(
    adapter: OllamaFastAdapter,
    message_text: str,
    *,
    trace_id: str = "",
) -> tuple[CommandNormResult, ModelCallLog]:
    """Strip noise and normalize a command-like message to a clean form."""
    trace_id = trace_id or str(uuid.uuid4())
    system = (
        "You are a command normalizer for a text RPG. "
        "Clean the player input into a normalized command string. "
        "Reply with valid JSON only. "
        'Schema: {"normalized": "<clean command string>"}'
    )
    prompt = f'Normalize this player input:\n"""\n{message_text}\n"""'

    result = await adapter.generate(prompt, system=system, expect_json=True)
    log = _make_log(trace_id, TaskType.command_normalization, result)

    if result.success:
        try:
            data = json.loads(result.text)
            normalized = str(data.get("normalized", "")).strip()
            if normalized:
                return CommandNormResult(normalized=normalized, raw=result.text), log
        except (json.JSONDecodeError, AttributeError):
            pass

    log.fallback_triggered = True
    # Fallback: strip leading slash and extra whitespace
    normalized = message_text.lstrip("/").strip()
    return CommandNormResult(
        normalized=normalized,
        raw=result.text,
        fallback_used=True,
    ), log


# ---------------------------------------------------------------------------
# Action Packet Extraction
# ---------------------------------------------------------------------------


@dataclass
class ActionPacketResult:
    """Structured action fields extracted from free-form player text."""

    action_type: str  # e.g. "attack", "move", "use_item", "unknown"
    target: str  # e.g. "goblin", ""
    item_ids: list[str]  # item references mentioned, may be empty
    notes: str  # anything the model flagged but couldn't classify
    raw: str
    fallback_used: bool = False


async def extract_action_packet(
    adapter: OllamaFastAdapter,
    message_text: str,
    *,
    available_action_types: list[str] | None = None,
    trace_id: str = "",
) -> tuple[ActionPacketResult, ModelCallLog]:
    """Extract a structured action packet from free-form player text."""
    trace_id = trace_id or str(uuid.uuid4())
    types_hint = (
        ", ".join(available_action_types)
        if available_action_types
        else "attack, move, defend, use_item, inspect, interact, pass"
    )
    system = (
        "You are an action parser for a text RPG. "
        "Extract the player's intended action from their message. "
        "Reply with valid JSON only. "
        f'Schema: {{"action_type": one of [{types_hint}] or "unknown", '
        '"target": "string or empty string", '
        '"item_ids": ["list", "of", "item", "names"], '
        '"notes": "anything else relevant"}}'
    )
    prompt = f'Extract the action from this player message:\n"""\n{message_text}\n"""'

    result = await adapter.generate(prompt, system=system, expect_json=True)
    log = _make_log(trace_id, TaskType.action_packet_extraction, result)

    if result.success:
        try:
            data = json.loads(result.text)
            return ActionPacketResult(
                action_type=str(data.get("action_type", "unknown")),
                target=str(data.get("target", "")),
                item_ids=list(data.get("item_ids", [])),
                notes=str(data.get("notes", "")),
                raw=result.text,
            ), log
        except (json.JSONDecodeError, AttributeError):
            pass

    log.fallback_triggered = True
    return ActionPacketResult(
        action_type="unknown",
        target="",
        item_ids=[],
        notes="",
        raw=result.text,
        fallback_used=True,
    ), log


# ---------------------------------------------------------------------------
# Scope Suggestion
# ---------------------------------------------------------------------------


@dataclass
class ScopeSuggestionResult:
    """Suggested scope for a player message."""

    suggested_scope: str  # "public" | "private_referee" | "side_channel"
    reasoning: str
    raw: str
    fallback_used: bool = False


async def suggest_scope(
    adapter: OllamaFastAdapter,
    message_text: str,
    *,
    trace_id: str = "",
) -> tuple[ScopeSuggestionResult, ModelCallLog]:
    """Suggest the appropriate scope for a player message."""
    trace_id = trace_id or str(uuid.uuid4())
    system = (
        "You are a scope classifier for a text RPG. "
        "Decide whether a player message should be public (visible to all), "
        "private_referee (shared only with the game referee), or side_channel "
        "(shared within a small player sub-group). "
        "Reply with valid JSON only. "
        'Schema: {"suggested_scope": "public"|"private_referee"|"side_channel", "reasoning": "one sentence"}'
    )
    prompt = f'Classify the scope of this player message:\n"""\n{message_text}\n"""'

    result = await adapter.generate(prompt, system=system, expect_json=True)
    log = _make_log(trace_id, TaskType.scope_suggestion, result)

    if result.success:
        try:
            data = json.loads(result.text)
            scope = data.get("suggested_scope", "public")
            if scope not in ("public", "private_referee", "side_channel"):
                scope = "public"
            return ScopeSuggestionResult(
                suggested_scope=scope,
                reasoning=str(data.get("reasoning", "")),
                raw=result.text,
            ), log
        except (json.JSONDecodeError, AttributeError):
            pass

    log.fallback_triggered = True
    return ScopeSuggestionResult(
        suggested_scope="public",
        reasoning="",
        raw=result.text,
        fallback_used=True,
    ), log


# ---------------------------------------------------------------------------
# Context Summarization
# ---------------------------------------------------------------------------


@dataclass
class ContextSummaryResult:
    """Summary of recent public turn messages."""

    summary: str
    raw: str
    fallback_used: bool = False


async def summarize_context(
    adapter: OllamaFastAdapter,
    messages: list[str],
    *,
    max_words: int = 100,
    trace_id: str = "",
) -> tuple[ContextSummaryResult, ModelCallLog]:
    """Compact a list of recent public messages into a brief turn summary."""
    trace_id = trace_id or str(uuid.uuid4())
    combined = "\n".join(f"- {m}" for m in messages)
    system = (
        "You are a context summarizer for a text RPG. "
        f"Summarize the following recent messages in at most {max_words} words. "
        "Reply with valid JSON only. "
        'Schema: {"summary": "concise summary text"}'
    )
    prompt = f"Summarize these recent game messages:\n{combined}"

    result = await adapter.generate(prompt, system=system, expect_json=True)
    log = _make_log(trace_id, TaskType.context_summarization, result)

    if result.success:
        try:
            data = json.loads(result.text)
            summary = str(data.get("summary", "")).strip()
            if summary:
                return ContextSummaryResult(summary=summary, raw=result.text), log
        except (json.JSONDecodeError, AttributeError):
            pass

    log.fallback_triggered = True
    # Fallback: join up to the last 3 messages
    fallback_summary = " | ".join(messages[-3:]) if messages else ""
    return ContextSummaryResult(
        summary=fallback_summary,
        raw=result.text,
        fallback_used=True,
    ), log


# ---------------------------------------------------------------------------
# Clarification Question Generation
# ---------------------------------------------------------------------------


@dataclass
class ClarificationResult:
    """A short clarification question to resolve an ambiguous player message."""

    question: str
    raw: str
    fallback_used: bool = False


async def generate_clarification(
    adapter: OllamaFastAdapter,
    message_text: str,
    ambiguity_reason: str,
    *,
    trace_id: str = "",
) -> tuple[ClarificationResult, ModelCallLog]:
    """Generate a short clarification question for an ambiguous player action."""
    trace_id = trace_id or str(uuid.uuid4())
    system = (
        "You are an assistant referee for a text RPG. "
        "Write a short, clear question to resolve an ambiguous player action. "
        "The question must be one sentence, under 20 words. "
        "Reply with valid JSON only. "
        'Schema: {"question": "the clarification question"}'
    )
    prompt = (
        f'Player said:\n"""\n{message_text}\n"""\n\n'
        f"Ambiguity: {ambiguity_reason}\n\n"
        "What clarification question should the referee ask?"
    )

    result = await adapter.generate(prompt, system=system, expect_json=True)
    log = _make_log(trace_id, TaskType.clarification_generation, result)

    if result.success:
        try:
            data = json.loads(result.text)
            question = str(data.get("question", "")).strip()
            if question:
                return ClarificationResult(question=question, raw=result.text), log
        except (json.JSONDecodeError, AttributeError):
            pass

    log.fallback_triggered = True
    return ClarificationResult(
        question="Could you clarify what you meant?",
        raw=result.text,
        fallback_used=True,
    ), log


# ---------------------------------------------------------------------------
# Schema Repair
# ---------------------------------------------------------------------------


@dataclass
class SchemaRepairResult:
    """Result of attempting to repair a malformed JSON string."""

    repaired_json: str  # the repaired JSON string; may be empty on failure
    success: bool  # True if the repair produced valid JSON
    raw: str  # raw model output
    fallback_used: bool = False


async def repair_schema(
    adapter: OllamaFastAdapter,
    malformed_json: str,
    schema_description: str,
    *,
    trace_id: str = "",
) -> tuple[SchemaRepairResult, ModelCallLog]:
    """Attempt to fix a malformed JSON string returned by the main model.

    Returns a SchemaRepairResult. If the repair also fails (invalid JSON or
    model error), result.success is False and repaired_json is empty.
    """
    trace_id = trace_id or str(uuid.uuid4())
    system = (
        "You are a JSON repair specialist. "
        "Fix the malformed JSON so it matches the given schema. "
        "Reply with the repaired JSON only — no explanation, no markdown fences."
    )
    prompt = (
        f"Schema:\n{schema_description}\n\n"
        f"Malformed JSON:\n{malformed_json}\n\n"
        "Output the corrected JSON:"
    )

    result = await adapter.generate(prompt, system=system, expect_json=True)
    log = _make_log(trace_id, TaskType.schema_repair, result)

    if result.success:
        try:
            # Validate that the repair is actually valid JSON
            json.loads(result.text)
            return SchemaRepairResult(
                repaired_json=result.text,
                success=True,
                raw=result.text,
            ), log
        except json.JSONDecodeError:
            pass

    log.fallback_triggered = True
    return SchemaRepairResult(
        repaired_json="",
        success=False,
        raw=result.text,
        fallback_used=True,
    ), log


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _make_log(
    trace_id: str,
    task_type: TaskType,
    result: GenerateResult,
) -> ModelCallLog:
    return ModelCallLog(
        trace_id=trace_id,
        tier="fast",
        task_type=task_type.value,
        prompt_token_count=result.prompt_token_count,
        output_token_count=result.output_token_count,
        latency_ms=result.latency_ms,
        success=result.success,
        failure_reason=result.failure_reason,
    )
