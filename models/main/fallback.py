"""Deterministic fallback behavior for main-tier model failures.

Per model_routing.md failure handling:
  1. Validate output against expected schema.
  2. If schema invalid: send to fast tier for repair (one retry).
  3. If repair fails or model times out: server falls back to a minimal
     deterministic narration. Turn is NOT blocked.

Each fallback function produces a valid output dataclass with minimal but
safe content. The server can post these without breaking the game flow.
"""

from __future__ import annotations

from models.main.schemas import (
    NarrationOutput,
    NpcDialogueOutput,
    CombatSummaryOutput,
    RulingProposalOutput,
    SocialArbitrationOutput,
    PuzzleFlavorOutput,
)


def fallback_narration(location_name: str = "the area") -> NarrationOutput:
    """Minimal safe narration when the model fails."""
    return NarrationOutput(
        narration=(
            f"The party pauses in {location_name}. "
            "The results of their actions settle around them."
        ),
        private_notes="[Fallback narration — model unavailable]",
        tone="neutral",
    )


def fallback_npc_dialogue(npc_name: str = "the NPC") -> NpcDialogueOutput:
    """Minimal safe NPC line when the model fails."""
    return NpcDialogueOutput(
        dialogue=f"{npc_name} remains silent for a moment.",
        action_beat=f"{npc_name} studies the party carefully.",
        mood="neutral",
    )


def fallback_combat_summary(
    outcomes: list[dict] | None = None,
) -> CombatSummaryOutput:
    """Minimal safe combat narrative when the model fails."""
    return CombatSummaryOutput(
        summary="The exchange of blows concludes. The dust settles.",
        outcomes=outcomes or [],
        tension="medium",
    )


def fallback_ruling_proposal(
    reason: str = "Unable to evaluate at this time.",
) -> RulingProposalOutput:
    """Safe fallback ruling: request clarification when model fails.

    Choosing 'request_clarification' rather than 'deny' is safer — it
    doesn't block the player outright and allows the human referee or a
    retry to resolve the ambiguity.
    """
    return RulingProposalOutput(
        ruling="request_clarification",
        reason=reason,
        condition="",
        suggested_action_type="",
        difficulty_class=None,
    )


def fallback_social_arbitration(
    situation_description: str = "the situation",
) -> SocialArbitrationOutput:
    """Minimal safe social outcome when the model fails."""
    return SocialArbitrationOutput(
        outcome="failure",
        narration=f"The attempt at resolving {situation_description} remains inconclusive.",
        trust_delta={},
        private_notes="[Fallback social arbitration — model unavailable]",
    )


def fallback_puzzle_flavor(
    puzzle_description: str = "the puzzle",
) -> PuzzleFlavorOutput:
    """Minimal safe puzzle narration when the model fails."""
    return PuzzleFlavorOutput(
        flavor=f"You study {puzzle_description} carefully, but the answer eludes you for now.",
        hint="",
        progress="none",
    )


# ---------------------------------------------------------------------------
# Registry: fallback factory by task type
# ---------------------------------------------------------------------------


def get_fallback(task_type: str, **kwargs) -> object:
    """Return a safe fallback output for the given task type.

    kwargs are passed through to the specific fallback function where
    relevant (e.g. location_name for narration).
    """
    dispatch = {
        "scene_narration": lambda: fallback_narration(
            kwargs.get("location_name", "the area")
        ),
        "npc_dialogue": lambda: fallback_npc_dialogue(
            kwargs.get("npc_name", "the NPC")
        ),
        "combat_summary": lambda: fallback_combat_summary(kwargs.get("outcomes")),
        "ruling_proposal": lambda: fallback_ruling_proposal(
            kwargs.get("reason", "Unable to evaluate at this time.")
        ),
        "social_arbitration": lambda: fallback_social_arbitration(
            kwargs.get("situation_description", "the situation")
        ),
        "puzzle_flavor": lambda: fallback_puzzle_flavor(
            kwargs.get("puzzle_description", "the puzzle")
        ),
    }
    factory = dispatch.get(task_type)
    if factory is None:
        raise ValueError(f"No fallback defined for task type: {task_type!r}")
    return factory()
