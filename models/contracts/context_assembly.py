"""Scope-safe context assembly for prompt contracts.

Builds an AssembledPrompt from a PromptContract and domain state, applying
scope rules to prevent leakage of referee-only, side-channel, or NPC-private
facts into prompts that should not see them.

This module formalises the assembly logic from models/main/context.py into a
contract-driven pipeline.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from models.contracts.fast_contracts import PromptContract, FAST_CONTRACTS
from models.contracts.main_contracts import MAIN_CONTRACTS
from models.contracts.truncation import TruncationPolicy

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Assembled prompt result
# ---------------------------------------------------------------------------


@dataclass
class AssembledPrompt:
    """Fully rendered prompt ready for model submission."""

    system_prompt: str
    user_prompt: str
    contract_id: str
    token_estimate: int
    was_truncated: bool = False
    scope_violations: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Fact wrapper (thin abstraction over KnowledgeFact-like objects)
# ---------------------------------------------------------------------------


@dataclass
class ScopedFact:
    """Lightweight fact container for context assembly.

    Mirrors the essential fields of KnowledgeFact without importing
    the server domain layer, keeping the contracts package dependency-free.
    """

    fact_id: str = ""
    text: str = ""
    scope: str = (
        "public"  # "public" | "referee_only" | "side_channel" | "private_referee"
    )
    fact_type: str = ""
    npc_id: str = ""  # set when fact is NPC-private
    is_critical: bool = False  # quest objectives, critical clues


# ---------------------------------------------------------------------------
# Scope filtering
# ---------------------------------------------------------------------------

# Mapping from scope rule names to the set of scope values they exclude.
_SCOPE_EXCLUSIONS: dict[str, set[str]] = {
    "public_only": {"referee_only", "private_referee", "side_channel"},
    "no_referee_facts": {"referee_only"},
    "no_side_channel_facts": {"side_channel"},
    "public_facts_only": {"referee_only", "private_referee", "side_channel"},
}


def filter_facts_by_scope(
    facts: list[ScopedFact],
    scope_rules: list[str],
    *,
    target_npc_id: str = "",
) -> list[ScopedFact]:
    """Return only facts permitted by the given scope rules.

    Args:
        facts: All available facts.
        scope_rules: Scope rule names from the PromptContract.
        target_npc_id: When scope_rules include "npc_scoped", only
            include facts belonging to this NPC (or public facts).

    Returns:
        Filtered list of ScopedFact.
    """
    excluded_scopes: set[str] = set()
    for rule in scope_rules:
        excluded_scopes |= _SCOPE_EXCLUSIONS.get(rule, set())

    filtered = [f for f in facts if f.scope not in excluded_scopes]

    # NPC scoping: keep only facts belonging to the target NPC or public
    if "npc_scoped" in scope_rules and target_npc_id:
        filtered = [f for f in filtered if not f.npc_id or f.npc_id == target_npc_id]

    # no_other_npc_facts: exclude facts belonging to other NPCs
    if "no_other_npc_facts" in scope_rules and target_npc_id:
        filtered = [f for f in filtered if not f.npc_id or f.npc_id == target_npc_id]

    # minimal_private_facts: only keep private facts that are critical
    if "minimal_private_facts" in scope_rules:
        filtered = [f for f in filtered if f.scope == "public" or f.is_critical]

    return filtered


def detect_scope_violations(
    rendered_prompt: str,
    excluded_facts: list[ScopedFact],
    *,
    min_match_length: int = 15,
) -> list[str]:
    """Check whether any excluded fact text leaked into the rendered prompt.

    Returns a list of violation descriptions (empty if clean).
    """
    violations: list[str] = []
    prompt_lower = rendered_prompt.lower()
    for fact in excluded_facts:
        if len(fact.text) >= min_match_length and fact.text.lower() in prompt_lower:
            violations.append(
                f"Scope violation: {fact.scope} fact '{fact.fact_id}' "
                f"text found in rendered prompt"
            )
    return violations


# ---------------------------------------------------------------------------
# Context assembler
# ---------------------------------------------------------------------------


class ContextAssembler:
    """Assembles scope-safe prompts from contracts and domain state."""

    def __init__(
        self,
        contracts: dict[str, PromptContract] | None = None,
    ) -> None:
        self._contracts: dict[str, PromptContract] = {}
        if contracts:
            self._contracts.update(contracts)
        else:
            self._contracts.update(FAST_CONTRACTS)
            self._contracts.update(MAIN_CONTRACTS)

        self._truncation = TruncationPolicy()

    def get_contract(self, contract_id: str) -> PromptContract:
        """Look up a contract by ID. Raises KeyError if not found."""
        if contract_id not in self._contracts:
            raise KeyError(f"No contract found: {contract_id!r}")
        return self._contracts[contract_id]

    def assemble(
        self,
        contract_id: str,
        *,
        scene_context: str = "",
        active_players: str = "",
        committed_actions: str = "",
        public_facts: list[ScopedFact] | None = None,
        all_facts: list[ScopedFact] | None = None,
        npc_context: str = "",
        action_context: str = "",
        dialogue_hints: str = "",
        target_npc_id: str = "",
        action_text: str = "",
        character_context: str = "",
        relevant_rules: str = "",
        battlefield_summary: str = "",
        action_results: str = "",
        tone_hint: str = "",
        recent_history: list[str] | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> AssembledPrompt:
        """Assemble a scope-safe prompt for the given contract.

        Args:
            contract_id: The contract to assemble for.
            scene_context: Scene description text.
            active_players: Comma-separated active player names.
            committed_actions: Formatted action summaries.
            public_facts: Pre-filtered public facts (deprecated; prefer all_facts).
            all_facts: All available facts; will be filtered by contract scope_rules.
            npc_context: NPC description for dialogue contracts.
            action_context: Action context for dialogue/ruling contracts.
            dialogue_hints: Style hints for NPC dialogue.
            target_npc_id: NPC ID for npc_scoped filtering.
            action_text: Player action text for rulings.
            character_context: Character state text.
            relevant_rules: Rules text for rulings.
            battlefield_summary: Combat summary context.
            action_results: Combat action results text.
            tone_hint: Tone guidance.
            recent_history: Recent message history (oldest first).
            extra_fields: Additional template fields.

        Returns:
            AssembledPrompt with rendered prompts and scope violation checks.
        """
        contract = self.get_contract(contract_id)

        # --- Scope-filter facts ---
        all_available = list(all_facts or [])
        if public_facts and not all_facts:
            all_available = list(public_facts)

        permitted_facts = filter_facts_by_scope(
            all_available,
            contract.scope_rules,
            target_npc_id=target_npc_id,
        )
        permitted_ids = {f.fact_id for f in permitted_facts}
        excluded_facts = [f for f in all_available if f.fact_id not in permitted_ids]

        facts_text = (
            "\n".join(f"- {f.text}" for f in permitted_facts) if permitted_facts else ""
        )

        # --- Build history block with truncation ---
        history_block = ""
        was_truncated = False
        if recent_history:
            # Estimate current size without history
            base_size = (
                len(scene_context) + len(committed_actions) + len(facts_text) + 500
            )
            base_tokens = self._truncation.estimate_tokens("x" * base_size)
            remaining, was_truncated = self._truncation.truncate_history(
                recent_history,
                base_tokens,
                contract.max_input_tokens,
            )
            if remaining:
                history_block = (
                    "Recent events:\n"
                    + "\n".join(f"  - {m}" for m in remaining)
                    + "\n\n"
                )

        # --- Build template fields ---
        fields: dict[str, str] = {
            "scene_context": scene_context,
            "active_players": active_players,
            "committed_actions": committed_actions,
            "public_facts": facts_text,
            "npc_context": npc_context,
            "action_context": action_context,
            "dialogue_hints": dialogue_hints,
            "action_text": action_text,
            "character_context": character_context,
            "relevant_rules": relevant_rules,
            "battlefield_summary": battlefield_summary,
            "action_results": action_results,
            "tone_hint": tone_hint,
            "history_block": history_block,
            "output_schema_inline": json.dumps(contract.output_schema),
        }
        if extra_fields:
            fields.update(extra_fields)

        # --- Render templates ---
        try:
            system_prompt = contract.system_prompt_template.format_map(
                _SafeFormatDict(fields)
            )
        except (KeyError, ValueError) as exc:
            logger.warning(
                "System prompt template rendering failed for contract %r: %s",
                contract_id,
                exc,
            )
            system_prompt = contract.system_prompt_template

        try:
            user_prompt = contract.user_prompt_template.format_map(
                _SafeFormatDict(fields)
            )
        except (KeyError, ValueError) as exc:
            logger.warning(
                "User prompt template rendering failed for contract %r: %s",
                contract_id,
                exc,
            )
            user_prompt = contract.user_prompt_template

        # --- Append facts block if not already in template ---
        if facts_text and "{public_facts}" not in contract.user_prompt_template:
            user_prompt += f"\n\nRelevant facts:\n{facts_text}"

        # --- Token estimation ---
        total_text = system_prompt + user_prompt
        token_estimate = self._truncation.estimate_tokens(total_text)

        # --- Scope violation scan ---
        scope_violations = detect_scope_violations(total_text, excluded_facts)

        return AssembledPrompt(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            contract_id=contract_id,
            token_estimate=token_estimate,
            was_truncated=was_truncated,
            scope_violations=scope_violations,
        )


class _SafeFormatDict(dict):
    """Dict that returns '{key}' for missing keys instead of raising."""

    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"
