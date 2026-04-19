"""Main-tier routing definitions.

Defines the task types handled exclusively by the main gameplay model tier
(GPT-5.4 mini via OpenAI). These tasks require narrative quality that the fast tier
cannot reliably provide.

Per model_routing.md — main tier handles:
  - scene_narration
  - npc_dialogue
  - combat_summary
  - ruling_proposal
  - social_arbitration
  - puzzle_flavor
  - unusual_action_interpretation
"""

from __future__ import annotations

from enum import Enum


class MainTaskType(str, Enum):
    """Task types handled by the main gameplay model tier."""

    scene_narration = "scene_narration"
    npc_dialogue = "npc_dialogue"
    combat_summary = "combat_summary"
    ruling_proposal = "ruling_proposal"
    social_arbitration = "social_arbitration"
    puzzle_flavor = "puzzle_flavor"
    unusual_action_interpretation = "unusual_action_interpretation"


_MAIN_TIER_TASKS: frozenset[str] = frozenset(t.value for t in MainTaskType)


def is_main_tier(task_type: str) -> bool:
    """Return True if the task must be routed to the main gameplay model."""
    return task_type in _MAIN_TIER_TASKS


def assert_main_tier(task_type: str) -> None:
    """Raise ValueError if the task is not a main-tier task."""
    if not is_main_tier(task_type):
        raise ValueError(
            f"Task '{task_type}' is not a main-tier task. "
            f"Route to the fast model instead."
        )
