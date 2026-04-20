"""Fast-tier routing rules.

The router is deterministic code, not an LLM call. It decides whether a task
is eligible for the fast local model tier.

Per model_routing.md:
  Fast tier: cheap, structured, or classification tasks.
  Main tier: narration, NPC dialogue, ruling proposals, social arbitration.
"""

from __future__ import annotations

from enum import Enum


class TaskType(str, Enum):
    """Task types handled by the fast local model tier."""

    intent_classification = "intent_classification"
    command_normalization = "command_normalization"
    action_packet_extraction = "action_packet_extraction"
    scope_suggestion = "scope_suggestion"
    context_summarization = "context_summarization"
    clarification_generation = "clarification_generation"
    schema_repair = "schema_repair"


# Tasks that must NOT be routed to the fast tier (reserved for main tier).
_MAIN_TIER_ONLY: frozenset[str] = frozenset(
    {
        "scene_narration",
        "npc_dialogue",
        "combat_summary",
        "ruling_proposal",
        "social_arbitration",
        "puzzle_flavor",
        "unusual_action_interpretation",
    }
)

_FAST_TIER_TASKS: frozenset[str] = frozenset(t.value for t in TaskType)


def is_fast_tier(task_type: str) -> bool:
    """Return True if the task should be routed to the fast local model.

    Raises ValueError for unknown task types that are neither in the fast-tier
    set nor the main-tier-only set.
    """
    if task_type in _MAIN_TIER_ONLY:
        return False
    if task_type in _FAST_TIER_TASKS:
        return True
    raise ValueError(
        f"Unknown task type {task_type!r}. "
        f"Must be one of {sorted(_FAST_TIER_TASKS | _MAIN_TIER_ONLY)}."
    )


def is_main_tier_only(task_type: str) -> bool:
    """Return True if the task must NOT be routed to the fast tier."""
    return task_type in _MAIN_TIER_ONLY


def assert_fast_tier(task_type: str) -> None:
    """Raise ValueError if the task is not eligible for the fast tier."""
    if not is_fast_tier(task_type):
        raise ValueError(
            f"Task '{task_type}' is not eligible for the fast model tier. "
            f"Route to the main model instead."
        )
