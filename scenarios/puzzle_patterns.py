"""Reusable puzzle pattern templates for scenario authoring.

Each pattern describes a common puzzle archetype with its required
components, solution template, and auto-generated schema definitions.
Scenario authors instantiate a pattern by supplying the required
component IDs, and the pattern produces PuzzleDefinition(s) and
optionally TriggerDefinition(s) ready for inclusion in a manifest.
"""

from __future__ import annotations

from dataclasses import dataclass

from scenarios.schema import PuzzleDefinition


@dataclass
class PuzzlePattern:
    """Reusable puzzle template that can be instantiated in scenarios."""

    pattern_id: str
    name: str
    description: str
    required_components: list[str]
    solution_template: str

    def instantiate(
        self,
        components: dict[str, str],
        scene_id: str = "",
        **overrides: str,
    ) -> PuzzleDefinition:
        """Create a PuzzleDefinition from this pattern and component bindings.

        ``components`` maps required_component names to actual entity IDs.
        ``overrides`` can set description, success_text, failure_text, etc.
        """
        missing = [c for c in self.required_components if c not in components]
        if missing:
            raise ValueError(
                f"Pattern '{self.pattern_id}' missing components: {missing}"
            )

        solution_text = self.solution_template
        for key, value in components.items():
            solution_text = solution_text.replace(f"{{{key}}}", value)

        puzzle_id = overrides.pop(
            "puzzle_id", f"{self.pattern_id}_{scene_id or 'puzzle'}"
        )
        desc = overrides.pop("description", self.description)
        success = overrides.pop("success_text", f"The {self.name.lower()} is solved!")
        failure = overrides.pop("failure_text", "That doesn't seem to work.")

        return PuzzleDefinition(
            puzzle_id=puzzle_id,
            name=self.name,
            description=desc,
            solution_hint=solution_text,
            solution_actions=[solution_text],
            success_text=success,
            failure_text=failure,
            max_attempts=int(overrides.get("max_attempts", "0")),
            effects_on_solve=list(filter(None, [overrides.get("effect_on_solve", "")])),
            scene_id=scene_id,
            referee_notes=overrides.get("referee_notes", f"Pattern: {self.pattern_id}"),
        )


# ---------------------------------------------------------------------------
# Pre-built patterns
# ---------------------------------------------------------------------------

COMBINATION_LOCK = PuzzlePattern(
    pattern_id="combination_lock",
    name="Combination Lock",
    description="A mechanism that requires the correct combination of items or clues to open.",
    required_components=["lock_object_id", "clue_item_ids"],
    solution_template="Combine clues from {clue_item_ids} and use on {lock_object_id}",
)

LEVER_SEQUENCE = PuzzlePattern(
    pattern_id="lever_sequence",
    name="Lever Sequence",
    description="A series of levers that must be pulled in the correct order.",
    required_components=["lever_object_ids", "correct_sequence"],
    solution_template="Pull levers {lever_object_ids} in order: {correct_sequence}",
)

KEY_AND_LOCK = PuzzlePattern(
    pattern_id="key_and_lock",
    name="Key and Lock",
    description="A locked barrier that requires a specific key to open.",
    required_components=["key_item_id", "locked_exit_id"],
    solution_template="Use {key_item_id} on {locked_exit_id}",
)

RIDDLE_DOOR = PuzzlePattern(
    pattern_id="riddle_door",
    name="Riddle Door",
    description="A sealed door that opens only when the correct answer is spoken.",
    required_components=["riddle_text", "answer_text", "exit_id"],
    solution_template="Answer the riddle: {riddle_text} -- answer: {answer_text}",
)

MULTI_ROOM_ASSEMBLY = PuzzlePattern(
    pattern_id="multi_room_assembly",
    name="Multi-Room Assembly",
    description="Clues scattered across multiple rooms must be gathered and combined.",
    required_components=["room_ids", "clue_fact_ids", "final_puzzle_id"],
    solution_template=(
        "Gather clues {clue_fact_ids} from rooms {room_ids} "
        "and use them to solve {final_puzzle_id}"
    ),
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ALL_PATTERNS: dict[str, PuzzlePattern] = {
    p.pattern_id: p
    for p in [
        COMBINATION_LOCK,
        LEVER_SEQUENCE,
        KEY_AND_LOCK,
        RIDDLE_DOOR,
        MULTI_ROOM_ASSEMBLY,
    ]
}


def get_pattern(pattern_id: str) -> PuzzlePattern:
    """Look up a puzzle pattern by ID.  Raises KeyError if not found."""
    return ALL_PATTERNS[pattern_id]
