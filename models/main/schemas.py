"""Output schema definitions and validation for main-tier model responses.

Each main-tier task type has a defined output schema. This module provides:
  1. Dataclasses for each schema.
  2. validate_* functions that parse raw model JSON and return a typed result
     or raise SchemaValidationError on failure.
  3. SCHEMA_DESCRIPTIONS used by the fast-tier repair function.

Validation is strict on required fields and lenient on extra fields.

Per model_routing.md failure handling:
  1. Validate output against expected schema.
  2. If schema invalid: send to fast tier for repair (one retry).
  3. If repair fails or model times out: deterministic fallback.
  Turn is never blocked.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


class SchemaValidationError(Exception):
    """Raised when model output does not match the expected schema."""

    def __init__(self, task_type: str, reason: str, raw: str = "") -> None:
        self.task_type = task_type
        self.reason = reason
        self.raw = raw
        super().__init__(f"[{task_type}] schema validation failed: {reason}")


# ---------------------------------------------------------------------------
# Scene Narration
# ---------------------------------------------------------------------------


@dataclass
class NarrationOutput:
    """Validated output from a scene_narration call.

    Schema::
        {
          "narration": "<public prose for the party>",
          "private_notes": "<optional referee-only observations>",
          "tone": "neutral" | "tense" | "triumphant" | "ominous" | "comic"
        }
    """

    narration: str
    private_notes: str = ""
    tone: str = "neutral"

    _VALID_TONES = frozenset({"neutral", "tense", "triumphant", "ominous", "comic"})

    def __post_init__(self) -> None:
        if self.tone not in self._VALID_TONES:
            self.tone = "neutral"


NARRATION_SCHEMA_DESCRIPTION = (
    '{"narration": "string (required, non-empty)", '
    '"private_notes": "string (optional)", '
    '"tone": "neutral|tense|triumphant|ominous|comic (optional, default neutral)"}'
)


def validate_narration(raw: str) -> NarrationOutput:
    """Parse and validate a scene_narration model response."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(
            "scene_narration", f"invalid JSON: {exc}", raw
        ) from exc

    narration = data.get("narration", "")
    if not isinstance(narration, str) or not narration.strip():
        raise SchemaValidationError(
            "scene_narration", "missing or empty 'narration' field", raw
        )

    return NarrationOutput(
        narration=narration.strip(),
        private_notes=str(data.get("private_notes", "")),
        tone=str(data.get("tone", "neutral")),
    )


# ---------------------------------------------------------------------------
# NPC Dialogue
# ---------------------------------------------------------------------------


@dataclass
class NpcDialogueOutput:
    """Validated output from an npc_dialogue call.

    Schema::
        {
          "dialogue": "<the NPC's spoken words, first-person>",
          "action_beat": "<optional brief stage direction>",
          "mood": "friendly" | "hostile" | "nervous" | "neutral" | "suspicious"
        }
    """

    dialogue: str
    action_beat: str = ""
    mood: str = "neutral"

    _VALID_MOODS = frozenset(
        {"friendly", "hostile", "nervous", "neutral", "suspicious"}
    )

    def __post_init__(self) -> None:
        if self.mood not in self._VALID_MOODS:
            self.mood = "neutral"


NPC_DIALOGUE_SCHEMA_DESCRIPTION = (
    '{"dialogue": "string (required, non-empty, NPC spoken words in first person)", '
    '"action_beat": "string (optional brief stage direction)", '
    '"mood": "friendly|hostile|nervous|neutral|suspicious (optional, default neutral)"}'
)


def validate_npc_dialogue(raw: str) -> NpcDialogueOutput:
    """Parse and validate an npc_dialogue model response."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(
            "npc_dialogue", f"invalid JSON: {exc}", raw
        ) from exc

    dialogue = data.get("dialogue", "")
    if not isinstance(dialogue, str) or not dialogue.strip():
        raise SchemaValidationError(
            "npc_dialogue", "missing or empty 'dialogue' field", raw
        )

    return NpcDialogueOutput(
        dialogue=dialogue.strip(),
        action_beat=str(data.get("action_beat", "")),
        mood=str(data.get("mood", "neutral")),
    )


# ---------------------------------------------------------------------------
# Combat Summary
# ---------------------------------------------------------------------------


@dataclass
class CombatSummaryOutput:
    """Validated output from a combat_summary call.

    Schema::
        {
          "summary": "<public narrative of the combat exchange>",
          "outcomes": [{"entity": "name", "result": "hit|miss|defeat|status_change", "detail": "string"}],
          "tension": "low" | "medium" | "high" | "critical"
        }
    """

    summary: str
    outcomes: list[dict] = field(default_factory=list)
    tension: str = "medium"

    _VALID_TENSIONS = frozenset({"low", "medium", "high", "critical"})

    def __post_init__(self) -> None:
        if self.tension not in self._VALID_TENSIONS:
            self.tension = "medium"


COMBAT_SUMMARY_SCHEMA_DESCRIPTION = (
    '{"summary": "string (required, non-empty narrative)", '
    '"outcomes": [{"entity": "string", "result": "hit|miss|defeat|status_change", "detail": "string"}], '
    '"tension": "low|medium|high|critical (optional, default medium)"}'
)


def validate_combat_summary(raw: str) -> CombatSummaryOutput:
    """Parse and validate a combat_summary model response."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(
            "combat_summary", f"invalid JSON: {exc}", raw
        ) from exc

    summary = data.get("summary", "")
    if not isinstance(summary, str) or not summary.strip():
        raise SchemaValidationError(
            "combat_summary", "missing or empty 'summary' field", raw
        )

    outcomes = data.get("outcomes", [])
    if not isinstance(outcomes, list):
        outcomes = []

    return CombatSummaryOutput(
        summary=summary.strip(),
        outcomes=outcomes,
        tension=str(data.get("tension", "medium")),
    )


# ---------------------------------------------------------------------------
# Ruling Proposal
# ---------------------------------------------------------------------------


@dataclass
class RulingProposalOutput:
    """Validated output from a ruling_proposal call.

    Ruling proposals are the most structurally constrained output because the
    server must validate them before committing any game-state change.

    Schema::
        {
          "ruling": "allow" | "allow_with_condition" | "deny" | "request_clarification",
          "condition": "<string, required when ruling is allow_with_condition>",
          "reason": "<one-sentence justification>",
          "suggested_action_type": "<normalized action type string, may be empty>",
          "difficulty_class": <integer 1-20 or null>
        }
    """

    ruling: str
    reason: str
    condition: str = ""
    suggested_action_type: str = ""
    difficulty_class: int | None = None

    _VALID_RULINGS = frozenset(
        {"allow", "allow_with_condition", "deny", "request_clarification"}
    )

    def __post_init__(self) -> None:
        if self.ruling not in self._VALID_RULINGS:
            raise ValueError(f"Invalid ruling value: {self.ruling!r}")
        if self.difficulty_class is not None:
            dc = int(self.difficulty_class)
            if not (1 <= dc <= 20):
                self.difficulty_class = None
            else:
                self.difficulty_class = dc


RULING_PROPOSAL_SCHEMA_DESCRIPTION = (
    '{"ruling": "allow|allow_with_condition|deny|request_clarification (required)", '
    '"condition": "string (required when ruling is allow_with_condition)", '
    '"reason": "string (required, one-sentence justification)", '
    '"suggested_action_type": "string (optional normalized action type)", '
    '"difficulty_class": "integer 1-20 or null (optional)"}'
)


def validate_ruling_proposal(raw: str) -> RulingProposalOutput:
    """Parse and validate a ruling_proposal model response."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(
            "ruling_proposal", f"invalid JSON: {exc}", raw
        ) from exc

    ruling = data.get("ruling", "")
    if ruling not in RulingProposalOutput._VALID_RULINGS:
        raise SchemaValidationError(
            "ruling_proposal",
            f"'ruling' must be one of {sorted(RulingProposalOutput._VALID_RULINGS)}, got {ruling!r}",
            raw,
        )

    reason = data.get("reason", "")
    if not isinstance(reason, str) or not reason.strip():
        raise SchemaValidationError(
            "ruling_proposal", "missing or empty 'reason' field", raw
        )

    dc_raw = data.get("difficulty_class")
    dc: int | None = None
    if dc_raw is not None:
        try:
            dc = int(dc_raw)
            if not (1 <= dc <= 20):
                dc = None
        except (ValueError, TypeError):
            dc = None

    return RulingProposalOutput(
        ruling=ruling,
        reason=reason.strip(),
        condition=str(data.get("condition", "")),
        suggested_action_type=str(data.get("suggested_action_type", "")),
        difficulty_class=dc,
    )


# ---------------------------------------------------------------------------
# Social Arbitration
# ---------------------------------------------------------------------------


@dataclass
class SocialArbitrationOutput:
    """Validated output from a social_arbitration call.

    Schema::
        {
          "outcome": "success" | "partial_success" | "failure" | "escalation",
          "narration": "<public prose describing the outcome>",
          "trust_delta": {"<entity_id>": <int -3 to 3>},
          "private_notes": "<optional referee-only context>"
        }
    """

    outcome: str
    narration: str
    trust_delta: dict[str, int] = field(default_factory=dict)
    private_notes: str = ""

    _VALID_OUTCOMES = frozenset({"success", "partial_success", "failure", "escalation"})

    def __post_init__(self) -> None:
        if self.outcome not in self._VALID_OUTCOMES:
            self.outcome = "failure"


SOCIAL_ARBITRATION_SCHEMA_DESCRIPTION = (
    '{"outcome": "success|partial_success|failure|escalation (required)", '
    '"narration": "string (required, public prose)", '
    '"trust_delta": {"entity_id": integer_delta} (optional), '
    '"private_notes": "string (optional)"}'
)


def validate_social_arbitration(raw: str) -> SocialArbitrationOutput:
    """Parse and validate a social_arbitration model response."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(
            "social_arbitration", f"invalid JSON: {exc}", raw
        ) from exc

    outcome = data.get("outcome", "")
    if outcome not in SocialArbitrationOutput._VALID_OUTCOMES:
        raise SchemaValidationError(
            "social_arbitration",
            f"'outcome' must be one of {sorted(SocialArbitrationOutput._VALID_OUTCOMES)}, got {outcome!r}",
            raw,
        )

    narration = data.get("narration", "")
    if not isinstance(narration, str) or not narration.strip():
        raise SchemaValidationError(
            "social_arbitration", "missing or empty 'narration' field", raw
        )

    # Coerce trust_delta values to int, drop invalid entries
    raw_delta = data.get("trust_delta", {})
    trust_delta: dict[str, int] = {}
    if isinstance(raw_delta, dict):
        for k, v in raw_delta.items():
            try:
                trust_delta[str(k)] = int(v)
            except (ValueError, TypeError):
                pass

    return SocialArbitrationOutput(
        outcome=outcome,
        narration=narration.strip(),
        trust_delta=trust_delta,
        private_notes=str(data.get("private_notes", "")),
    )


# ---------------------------------------------------------------------------
# Puzzle Flavor
# ---------------------------------------------------------------------------


@dataclass
class PuzzleFlavorOutput:
    """Validated output from a puzzle_flavor call.

    Schema::
        {
          "flavor": "<public narrative of the puzzle interaction>",
          "hint": "<optional subtle hint visible to the player>",
          "progress": "none" | "partial" | "solved" | "failed"
        }
    """

    flavor: str
    hint: str = ""
    progress: str = "none"

    _VALID_PROGRESS = frozenset({"none", "partial", "solved", "failed"})

    def __post_init__(self) -> None:
        if self.progress not in self._VALID_PROGRESS:
            self.progress = "none"


PUZZLE_FLAVOR_SCHEMA_DESCRIPTION = (
    '{"flavor": "string (required, public narrative of puzzle interaction)", '
    '"hint": "string (optional subtle hint for the player)", '
    '"progress": "none|partial|solved|failed (optional, default none)"}'
)


def validate_puzzle_flavor(raw: str) -> PuzzleFlavorOutput:
    """Parse and validate a puzzle_flavor model response."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(
            "puzzle_flavor", f"invalid JSON: {exc}", raw
        ) from exc

    flavor = data.get("flavor", "")
    if not isinstance(flavor, str) or not flavor.strip():
        raise SchemaValidationError(
            "puzzle_flavor", "missing or empty 'flavor' field", raw
        )

    return PuzzleFlavorOutput(
        flavor=flavor.strip(),
        hint=str(data.get("hint", "")),
        progress=str(data.get("progress", "none")),
    )


# ---------------------------------------------------------------------------
# Registry: schema descriptions by task type (for fast-tier repair calls)
# ---------------------------------------------------------------------------

SCHEMA_DESCRIPTIONS: dict[str, str] = {
    "scene_narration": NARRATION_SCHEMA_DESCRIPTION,
    "npc_dialogue": NPC_DIALOGUE_SCHEMA_DESCRIPTION,
    "combat_summary": COMBAT_SUMMARY_SCHEMA_DESCRIPTION,
    "ruling_proposal": RULING_PROPOSAL_SCHEMA_DESCRIPTION,
    "social_arbitration": SOCIAL_ARBITRATION_SCHEMA_DESCRIPTION,
    "puzzle_flavor": PUZZLE_FLAVOR_SCHEMA_DESCRIPTION,
}
