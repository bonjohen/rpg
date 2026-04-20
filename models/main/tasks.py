"""Main-tier task implementations.

Each public function wraps one main-tier LLM call with the full failure-
handling pipeline:
  1. Call the main model (OpenAIMainAdapter).
  2. Validate output schema (schemas.validate_*).
  3. On validation failure: attempt fast-tier repair (one retry via
     fast.tasks.repair_schema).
  4. If repair fails or model times out: use deterministic fallback
     (fallback.*).

All functions:
  - Accept an OpenAIMainAdapter and task-specific inputs.
  - Accept an optional fast-tier adapter for the repair step.
  - Return (typed_result, ModelCallLog).
  - Never raise on model failure.
  - Set fallback_triggered=True on the log if fallback was used.

Per model_routing.md instrumentation requirements, every call logs:
  trace_id, tier, task_type, prompt_token_count, output_token_count,
  latency_ms, success, failure_reason, fallback_triggered.
"""

from __future__ import annotations

import logging
import uuid

from models.fast.adapter import OllamaFastAdapter
from models.fast.tasks import repair_schema
from models.main.adapter import GenerateResult
from models.protocol import MainAdapter
from models.main.context import (
    ActionContext,
    NpcContext,
    PlayerContext,
    RecentHistory,
    SceneContext,
    assemble_combat_summary_prompt,
    assemble_narration_prompt,
    assemble_npc_dialogue_prompt,
    assemble_puzzle_flavor_prompt,
    assemble_ruling_proposal_prompt,
    assemble_social_arbitration_prompt,
)
from models.main.fallback import (
    fallback_combat_summary,
    fallback_narration,
    fallback_npc_dialogue,
    fallback_puzzle_flavor,
    fallback_ruling_proposal,
    fallback_social_arbitration,
)
from models.main.schemas import (
    SCHEMA_DESCRIPTIONS,
    CombatSummaryOutput,
    NarrationOutput,
    NpcDialogueOutput,
    PuzzleFlavorOutput,
    RulingProposalOutput,
    SchemaValidationError,
    SocialArbitrationOutput,
    validate_combat_summary,
    validate_narration,
    validate_npc_dialogue,
    validate_puzzle_flavor,
    validate_ruling_proposal,
    validate_social_arbitration,
)
from models.fast.instrumentation import ModelCallLog

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scene Narration
# ---------------------------------------------------------------------------


async def narrate_scene(
    adapter: MainAdapter,
    scene: SceneContext,
    committed_actions: list[ActionContext],
    recent_history: RecentHistory | None = None,
    *,
    fast_adapter: OllamaFastAdapter | None = None,
    trace_id: str = "",
) -> tuple[NarrationOutput, ModelCallLog]:
    """Generate official public scene narration after turn resolution.

    Args:
        adapter: Main gameplay model adapter.
        scene: Scene context (public facts only).
        committed_actions: This turn's resolved player actions.
        recent_history: Optional recent public message history.
        fast_adapter: Optional fast-tier adapter for schema repair.
        trace_id: Caller-supplied trace identifier.

    Returns:
        (NarrationOutput, ModelCallLog)
    """
    trace_id = trace_id or str(uuid.uuid4())
    task_type = "scene_narration"
    system, prompt = assemble_narration_prompt(scene, committed_actions, recent_history)

    result = await adapter.generate(
        prompt, system=system, expect_json=True, temperature=0.7
    )
    log = _make_log(trace_id, task_type, result, tier=_adapter_tier(adapter))

    if result.success:
        try:
            output = validate_narration(result.text)
            return output, log
        except SchemaValidationError as exc:
            logger.warning("Schema validation failed: %s [trace=%s]", exc, trace_id)

    # --- Repair attempt ---
    if result.success and fast_adapter is not None:
        repaired, repair_log = await repair_schema(
            fast_adapter,
            result.text,
            SCHEMA_DESCRIPTIONS[task_type],
            trace_id=trace_id,
        )
        if repaired.success:
            try:
                output = validate_narration(repaired.repaired_json)
                log.failure_reason = "schema_invalid_repaired"
                log.fallback_triggered = False
                return output, log
            except SchemaValidationError:
                pass

    # --- Deterministic fallback ---
    log.fallback_triggered = True
    if not log.failure_reason:
        log.failure_reason = result.failure_reason or "schema_invalid"
    return fallback_narration(scene.location_name), log


# ---------------------------------------------------------------------------
# NPC Dialogue
# ---------------------------------------------------------------------------


async def generate_npc_dialogue(
    adapter: MainAdapter,
    npc: NpcContext,
    scene: SceneContext,
    trigger_action: ActionContext | None = None,
    *,
    fast_adapter: OllamaFastAdapter | None = None,
    trace_id: str = "",
) -> tuple[NpcDialogueOutput, ModelCallLog]:
    """Generate NPC dialogue in response to a player action or scene event.

    Args:
        adapter: Main gameplay model adapter.
        npc: NPC context (only this NPC's facts — no other NPC private data).
        scene: Scene context.
        trigger_action: The player action that triggered the dialogue, if any.
        fast_adapter: Optional fast-tier adapter for schema repair.
        trace_id: Caller-supplied trace identifier.

    Returns:
        (NpcDialogueOutput, ModelCallLog)
    """
    trace_id = trace_id or str(uuid.uuid4())
    task_type = "npc_dialogue"
    system, prompt = assemble_npc_dialogue_prompt(npc, scene, trigger_action)

    result = await adapter.generate(
        prompt, system=system, expect_json=True, temperature=0.8
    )
    log = _make_log(trace_id, task_type, result, tier=_adapter_tier(adapter))

    if result.success:
        try:
            output = validate_npc_dialogue(result.text)
            return output, log
        except SchemaValidationError as exc:
            logger.warning("Schema validation failed: %s [trace=%s]", exc, trace_id)

    if result.success and fast_adapter is not None:
        repaired, _ = await repair_schema(
            fast_adapter, result.text, SCHEMA_DESCRIPTIONS[task_type], trace_id=trace_id
        )
        if repaired.success:
            try:
                output = validate_npc_dialogue(repaired.repaired_json)
                log.failure_reason = "schema_invalid_repaired"
                return output, log
            except SchemaValidationError:
                pass

    log.fallback_triggered = True
    if not log.failure_reason:
        log.failure_reason = result.failure_reason or "schema_invalid"
    return fallback_npc_dialogue(npc.name), log


# ---------------------------------------------------------------------------
# Combat Summary
# ---------------------------------------------------------------------------


async def summarize_combat(
    adapter: MainAdapter,
    scene: SceneContext,
    combat_outcomes: list[dict],
    committed_actions: list[ActionContext],
    *,
    fast_adapter: OllamaFastAdapter | None = None,
    trace_id: str = "",
) -> tuple[CombatSummaryOutput, ModelCallLog]:
    """Generate public combat narrative from mechanically-resolved outcomes.

    Args:
        adapter: Main gameplay model adapter.
        scene: Scene context.
        combat_outcomes: Server-resolved mechanical outcomes (already
            committed — LLM only narrates, never decides).
        committed_actions: Player action context for this turn.
        fast_adapter: Optional fast-tier adapter for schema repair.
        trace_id: Caller-supplied trace identifier.

    Returns:
        (CombatSummaryOutput, ModelCallLog)
    """
    trace_id = trace_id or str(uuid.uuid4())
    task_type = "combat_summary"
    system, prompt = assemble_combat_summary_prompt(
        scene, combat_outcomes, committed_actions
    )

    result = await adapter.generate(
        prompt, system=system, expect_json=True, temperature=0.7
    )
    log = _make_log(trace_id, task_type, result, tier=_adapter_tier(adapter))

    if result.success:
        try:
            output = validate_combat_summary(result.text)
            return output, log
        except SchemaValidationError as exc:
            logger.warning("Schema validation failed: %s [trace=%s]", exc, trace_id)

    if result.success and fast_adapter is not None:
        repaired, _ = await repair_schema(
            fast_adapter, result.text, SCHEMA_DESCRIPTIONS[task_type], trace_id=trace_id
        )
        if repaired.success:
            try:
                output = validate_combat_summary(repaired.repaired_json)
                log.failure_reason = "schema_invalid_repaired"
                return output, log
            except SchemaValidationError:
                pass

    log.fallback_triggered = True
    if not log.failure_reason:
        log.failure_reason = result.failure_reason or "schema_invalid"
    return fallback_combat_summary(combat_outcomes), log


# ---------------------------------------------------------------------------
# Ruling Proposal
# ---------------------------------------------------------------------------


async def propose_ruling(
    adapter: MainAdapter,
    action: ActionContext,
    scene: SceneContext,
    acting_player: PlayerContext,
    relevant_rules: list[str] | None = None,
    *,
    fast_adapter: OllamaFastAdapter | None = None,
    trace_id: str = "",
) -> tuple[RulingProposalOutput, ModelCallLog]:
    """Propose a ruling on an ambiguous player action.

    The proposal is advisory — the server validates and commits the final
    ruling. The LLM never directly commits game state.

    Args:
        adapter: Main gameplay model adapter.
        action: The player's action to rule on.
        scene: Scene context.
        acting_player: The acting player's character state.
        relevant_rules: Optional list of rule excerpts relevant to the ruling.
        fast_adapter: Optional fast-tier adapter for schema repair.
        trace_id: Caller-supplied trace identifier.

    Returns:
        (RulingProposalOutput, ModelCallLog)
    """
    trace_id = trace_id or str(uuid.uuid4())
    task_type = "ruling_proposal"
    system, prompt = assemble_ruling_proposal_prompt(
        action, scene, acting_player, relevant_rules
    )

    # Lower temperature for structured, consistent rulings
    result = await adapter.generate(
        prompt, system=system, expect_json=True, temperature=0.3
    )
    log = _make_log(trace_id, task_type, result, tier=_adapter_tier(adapter))

    if result.success:
        try:
            output = validate_ruling_proposal(result.text)
            return output, log
        except SchemaValidationError as exc:
            logger.warning("Schema validation failed: %s [trace=%s]", exc, trace_id)

    if result.success and fast_adapter is not None:
        repaired, _ = await repair_schema(
            fast_adapter, result.text, SCHEMA_DESCRIPTIONS[task_type], trace_id=trace_id
        )
        if repaired.success:
            try:
                output = validate_ruling_proposal(repaired.repaired_json)
                log.failure_reason = "schema_invalid_repaired"
                return output, log
            except SchemaValidationError:
                pass

    log.fallback_triggered = True
    if not log.failure_reason:
        log.failure_reason = result.failure_reason or "schema_invalid"
    return fallback_ruling_proposal(), log


# ---------------------------------------------------------------------------
# Social Arbitration
# ---------------------------------------------------------------------------


async def arbitrate_social(
    adapter: MainAdapter,
    scene: SceneContext,
    players_involved: list[PlayerContext],
    npcs_involved: list[NpcContext],
    situation_description: str,
    *,
    fast_adapter: OllamaFastAdapter | None = None,
    trace_id: str = "",
) -> tuple[SocialArbitrationOutput, ModelCallLog]:
    """Resolve a multi-party social situation.

    Args:
        adapter: Main gameplay model adapter.
        scene: Scene context.
        players_involved: Players in the social interaction.
        npcs_involved: NPCs in the social interaction.
        situation_description: Plain-text description of the conflict/situation.
        fast_adapter: Optional fast-tier adapter for schema repair.
        trace_id: Caller-supplied trace identifier.

    Returns:
        (SocialArbitrationOutput, ModelCallLog)
    """
    trace_id = trace_id or str(uuid.uuid4())
    task_type = "social_arbitration"
    system, prompt = assemble_social_arbitration_prompt(
        scene, players_involved, npcs_involved, situation_description
    )

    result = await adapter.generate(
        prompt, system=system, expect_json=True, temperature=0.6
    )
    log = _make_log(trace_id, task_type, result, tier=_adapter_tier(adapter))

    if result.success:
        try:
            output = validate_social_arbitration(result.text)
            return output, log
        except SchemaValidationError as exc:
            logger.warning("Schema validation failed: %s [trace=%s]", exc, trace_id)

    if result.success and fast_adapter is not None:
        repaired, _ = await repair_schema(
            fast_adapter, result.text, SCHEMA_DESCRIPTIONS[task_type], trace_id=trace_id
        )
        if repaired.success:
            try:
                output = validate_social_arbitration(repaired.repaired_json)
                log.failure_reason = "schema_invalid_repaired"
                return output, log
            except SchemaValidationError:
                pass

    log.fallback_triggered = True
    if not log.failure_reason:
        log.failure_reason = result.failure_reason or "schema_invalid"
    return fallback_social_arbitration(situation_description), log


# ---------------------------------------------------------------------------
# Puzzle Flavor
# ---------------------------------------------------------------------------


async def generate_puzzle_flavor(
    adapter: MainAdapter,
    scene: SceneContext,
    puzzle_description: str,
    player_action: ActionContext,
    puzzle_state: str = "unsolved",
    *,
    fast_adapter: OllamaFastAdapter | None = None,
    trace_id: str = "",
) -> tuple[PuzzleFlavorOutput, ModelCallLog]:
    """Generate narrative flavor for a puzzle interaction.

    Args:
        adapter: Main gameplay model adapter.
        scene: Scene context.
        puzzle_description: Description of the puzzle.
        player_action: The player's action on the puzzle.
        puzzle_state: Current puzzle state (e.g. "unsolved", "partial", "solved").
        fast_adapter: Optional fast-tier adapter for schema repair.
        trace_id: Caller-supplied trace identifier.

    Returns:
        (PuzzleFlavorOutput, ModelCallLog)
    """
    trace_id = trace_id or str(uuid.uuid4())
    task_type = "puzzle_flavor"
    system, prompt = assemble_puzzle_flavor_prompt(
        scene, puzzle_description, player_action, puzzle_state
    )

    result = await adapter.generate(
        prompt, system=system, expect_json=True, temperature=0.7
    )
    log = _make_log(trace_id, task_type, result, tier=_adapter_tier(adapter))

    if result.success:
        try:
            output = validate_puzzle_flavor(result.text)
            return output, log
        except SchemaValidationError as exc:
            logger.warning("Schema validation failed: %s [trace=%s]", exc, trace_id)

    if result.success and fast_adapter is not None:
        repaired, _ = await repair_schema(
            fast_adapter, result.text, SCHEMA_DESCRIPTIONS[task_type], trace_id=trace_id
        )
        if repaired.success:
            try:
                output = validate_puzzle_flavor(repaired.repaired_json)
                log.failure_reason = "schema_invalid_repaired"
                return output, log
            except SchemaValidationError:
                pass

    log.fallback_triggered = True
    if not log.failure_reason:
        log.failure_reason = result.failure_reason or "schema_invalid"
    return fallback_puzzle_flavor(puzzle_description), log


def _adapter_tier(adapter: MainAdapter) -> str:
    """Derive a tier label from the adapter's model name."""
    model = adapter.model
    if "gemma" in model:
        return "gemma"
    if "gpt" in model:
        return "openai"
    return "main"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _make_log(
    trace_id: str,
    task_type: str,
    result: GenerateResult,
    *,
    tier: str = "main",
) -> ModelCallLog:
    return ModelCallLog(
        trace_id=trace_id,
        tier=tier,
        task_type=task_type,
        prompt_token_count=result.prompt_token_count,
        output_token_count=result.output_token_count,
        latency_ms=result.latency_ms,
        success=result.success,
        failure_reason=result.failure_reason,
    )
