"""SocialEngine — NPC social interaction resolution.

Resolves five social action types:
  question  — ask the NPC about something
  persuade  — attempt to convince the NPC to cooperate
  threaten  — attempt to coerce the NPC through intimidation
  lie       — present false information to the NPC
  bargain   — offer something in exchange for cooperation

Architecture
------------
The engine is stateless and pure.  It:

1. Reads NPC hard state (health, stance, trust, memory_tags) to determine
   the interaction outcome.
2. Delegates trust delta computation to TrustEngine.
3. Delegates tell evaluation to NpcTellEngine.
4. Returns a SocialActionResult that the caller uses to:
     - Persist the mutated NPC entity (trust, stance, memory_tags).
     - Persist referee-only KnowledgeFacts.
     - Pass the DialogueContext to the main model for narration.

Outcome determination is intentionally rule-based and deterministic so the
server—not the LLM—controls outcome truth.  The LLM only narrates.

No imports from server.storage.  No I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from server.domain.entities import KnowledgeFact, NPC
from server.domain.enums import HealthState, KnowledgeFactType
from server.domain.helpers import new_id, utc_now
from server.npc.dialogue import DialogueContext, DialogueContextBuilder
from server.npc.tells import NpcTellEngine, TellDefinition, TellResult
from server.npc.trust import TrustDeltaResult, TrustEngine


# ---------------------------------------------------------------------------
# Outcome enum
# ---------------------------------------------------------------------------


class SocialOutcome(str, Enum):
    """Possible outcomes of a social action.

    Inherits from ``str`` so existing ``== "success"`` comparisons still work.
    """

    SUCCESS = "success"  # NPC cooperates / accepts / reveals info
    PARTIAL = "partial"  # NPC partially complies
    FAILURE = "failure"  # NPC refuses / deflects
    ESCALATION = "escalation"  # Situation worsened (e.g. threatened NPC calls guard)
    DETECTED_LIE = "detected_lie"  # NPC caught the lie


# ---------------------------------------------------------------------------
# Interaction context (input to engine methods)
# ---------------------------------------------------------------------------


@dataclass
class SocialActionInput:
    """All inputs needed to resolve a single social action."""

    player_id: str
    character_id: str
    npc_id: str
    action_type: str  # "question" | "persuade" | "threaten" | "lie" | "bargain"
    player_text: str  # raw declaration from player
    target_info: str = ""  # what the action is about
    campaign_id: str = ""
    scene_id: str = ""
    public_scope_id: str = ""
    private_scope_id: str = ""
    referee_scope_id: str = ""


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class SocialActionResult:
    """Returned by SocialEngine.resolve()."""

    success: bool
    outcome: str  # SocialOutcome constant

    # Updated NPC entity (trust/stance/memory mutated in place — caller persists)
    npc: NPC | None = None

    # Trust change summary
    trust_result: TrustDeltaResult | None = None

    # KnowledgeFacts to persist (referee-only tells + optional public facts)
    referee_facts: list[KnowledgeFact] = field(default_factory=list)
    public_facts: list[KnowledgeFact] = field(default_factory=list)

    # Dialogue context for main model narration
    dialogue_context: DialogueContext | None = None

    # Tell evaluation result
    tell_result: TellResult | None = None

    # Rejection reason (if outcome is FAILURE or illegal action)
    rejection_reason: str = ""


# ---------------------------------------------------------------------------
# SocialEngine
# ---------------------------------------------------------------------------


class SocialEngine:
    """Stateless engine for NPC social interaction resolution.

    Callers must:
      - Load the NPC entity before calling resolve().
      - Persist npc, referee_facts, and public_facts from the returned result.
      - Pass dialogue_context to the main model for narration.
    """

    def __init__(self) -> None:
        self._trust = TrustEngine()
        self._tells = NpcTellEngine()
        self._dialogue = DialogueContextBuilder()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def resolve(
        self,
        inp: SocialActionInput,
        npc: NPC,
        tells: list[TellDefinition] | None = None,
    ) -> SocialActionResult:
        """Resolve a social action against an NPC.

        Dispatches to the appropriate action handler based on inp.action_type.
        Mutates npc (trust, stance, memory_tags) in place.

        Args:
            inp:   Social action input.
            npc:   The NPC entity (will be mutated).
            tells: Optional list of TellDefinitions for this NPC.

        Returns:
            SocialActionResult.
        """
        # Guard: NPC must be alive and in the same scene
        if npc.health_state in (HealthState.incapacitated, HealthState.dead):
            return SocialActionResult(
                success=False,
                outcome=SocialOutcome.FAILURE,
                npc=npc,
                rejection_reason=f"{npc.name} cannot interact (state: {npc.health_state}).",
            )

        dispatch = {
            "question": self._resolve_question,
            "persuade": self._resolve_persuade,
            "threaten": self._resolve_threaten,
            "lie": self._resolve_lie,
            "bargain": self._resolve_bargain,
        }
        handler = dispatch.get(inp.action_type)
        if handler is None:
            return SocialActionResult(
                success=False,
                outcome=SocialOutcome.FAILURE,
                npc=npc,
                rejection_reason=f"Unknown social action type: {inp.action_type!r}.",
            )

        # Snapshot trust state before resolution for rollback on failure
        trust_snapshot = dict(npc.trust_by_player)
        stance_snapshot = npc.stance_to_party
        memory_snapshot = list(npc.memory_tags)

        result = handler(inp, npc)

        # Restore trust on failure — partial mutations should not persist
        if not result.success:
            npc.trust_by_player = trust_snapshot
            npc.stance_to_party = stance_snapshot
            npc.memory_tags = memory_snapshot

        # Evaluate tells after state mutation
        tell_result = self._tells.evaluate_tells(
            npc,
            tells or [],
            action_type=inp.action_type,
            campaign_id=inp.campaign_id,
            scene_id=inp.scene_id,
            referee_scope_id=inp.referee_scope_id,
        )
        result.tell_result = tell_result
        result.referee_facts.extend(tell_result.referee_facts)

        # Build dialogue context
        result.dialogue_context = self._dialogue.build(
            npc,
            inp.player_id,
            inp.action_type,
            inp.player_text,
            target_info=inp.target_info,
        )

        return result

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _resolve_question(self, inp: SocialActionInput, npc: NPC) -> SocialActionResult:
        """Resolve a question action.

        The NPC answers honestly if trust ≥ -20 and stance is not hostile.
        Hostile or very low trust NPCs deflect or lie.
        """
        trust = self._trust.get_trust(npc, inp.player_id)
        is_hostile = self._trust.is_hostile(npc)

        # Outcome determination
        if is_hostile or trust < -20:
            outcome = SocialOutcome.FAILURE
            success = False
            memory_tag = "player_questioned_npc_refused"
            trust_key = "question"  # tiny positive even on refusal — they engaged
        elif trust < 10 and "secretive" in npc.personality_tags:
            outcome = SocialOutcome.PARTIAL
            success = True
            memory_tag = "player_questioned_npc_evasive"
            trust_key = "question"
        else:
            outcome = SocialOutcome.SUCCESS
            success = True
            memory_tag = "player_questioned_npc_answered"
            trust_key = "question"

        trust_result = self._trust.apply_action_delta(
            npc, inp.player_id, trust_key, reason=f"question → {outcome}"
        )
        _append_memory_tag(npc, memory_tag)

        referee_facts = self._make_trust_fact(
            npc, inp.player_id, trust_result.new_trust, inp
        )

        return SocialActionResult(
            success=success,
            outcome=outcome,
            npc=npc,
            trust_result=trust_result,
            referee_facts=referee_facts,
        )

    def _resolve_persuade(self, inp: SocialActionInput, npc: NPC) -> SocialActionResult:
        """Resolve a persuade action.

        Success requires trust ≥ 0 and non-hostile stance.
        Failure for hostile or very suspicious NPCs.
        """
        trust = self._trust.get_trust(npc, inp.player_id)
        is_hostile = self._trust.is_hostile(npc)

        if is_hostile or trust < -30:
            outcome = SocialOutcome.FAILURE
            success = False
            memory_tag = "player_persuade_rejected"
            trust_key = "persuade_fail"
        elif trust >= 20:
            outcome = SocialOutcome.SUCCESS
            success = True
            memory_tag = "player_persuade_succeeded"
            trust_key = "persuade"
        else:
            # Borderline — partial success (NPC hedges)
            outcome = SocialOutcome.PARTIAL
            success = True
            memory_tag = "player_persuade_partial"
            trust_key = "question"  # neutral delta

        trust_result = self._trust.apply_action_delta(
            npc, inp.player_id, trust_key, reason=f"persuade → {outcome}"
        )
        _append_memory_tag(npc, memory_tag)

        referee_facts = self._make_trust_fact(
            npc, inp.player_id, trust_result.new_trust, inp
        )

        return SocialActionResult(
            success=success,
            outcome=outcome,
            npc=npc,
            trust_result=trust_result,
            referee_facts=referee_facts,
        )

    def _resolve_threaten(self, inp: SocialActionInput, npc: NPC) -> SocialActionResult:
        """Resolve a threaten action.

        Threats always damage trust.  Fearful NPCs may comply; others resist.
        Powerful/guard NPCs may escalate.
        """
        is_fearful = self._trust.is_fearful(npc)
        is_powerful = any(
            t in npc.personality_tags
            for t in ("fearless", "powerful", "guard_captain", "boss")
        )

        if is_powerful:
            outcome = SocialOutcome.ESCALATION
            success = False
            memory_tag = "player_threatened_npc_escalated"
        elif is_fearful or "timid" in npc.personality_tags:
            outcome = SocialOutcome.SUCCESS
            success = True
            memory_tag = "player_threatened_npc_complied"
        else:
            outcome = SocialOutcome.FAILURE
            success = False
            memory_tag = "player_threatened_npc_refused"

        trust_result = self._trust.apply_action_delta(
            npc, inp.player_id, "threaten", reason=f"threaten → {outcome}"
        )
        _append_memory_tag(npc, memory_tag)

        referee_facts = self._make_trust_fact(
            npc, inp.player_id, trust_result.new_trust, inp
        )

        return SocialActionResult(
            success=success,
            outcome=outcome,
            npc=npc,
            trust_result=trust_result,
            referee_facts=referee_facts,
        )

    def _resolve_lie(self, inp: SocialActionInput, npc: NPC) -> SocialActionResult:
        """Resolve a lie action.

        NPCs with 'perceptive' personality or high trust (they expect honesty)
        have a higher chance of detecting the lie.  Lie detection uses
        npc.personality_tags as a simple rule — no randomness (server-controlled).

        If trust >= 40, the NPC suspects something is off (DETECTED_LIE).
        Otherwise the lie is believed (SUCCESS) but trust ticks up only a little.
        """
        trust = self._trust.get_trust(npc, inp.player_id)
        is_perceptive = "perceptive" in npc.personality_tags

        if is_perceptive or trust >= 40:
            outcome = SocialOutcome.DETECTED_LIE
            success = False
            memory_tag = "player_lied_npc_detected"
            trust_key = "lie"  # large negative
        else:
            outcome = SocialOutcome.SUCCESS
            success = True
            memory_tag = "player_lied_npc_believed"
            trust_key = "lie_undetected"  # tiny positive

        trust_result = self._trust.apply_action_delta(
            npc, inp.player_id, trust_key, reason=f"lie → {outcome}"
        )
        _append_memory_tag(npc, memory_tag)

        referee_facts = self._make_trust_fact(
            npc, inp.player_id, trust_result.new_trust, inp
        )

        # Add an extra referee fact noting the lie was detected/believed
        if inp.referee_scope_id:
            lie_note = (
                f"{npc.name} {'detected the lie' if outcome == SocialOutcome.DETECTED_LIE else 'believed the lie'}. "
                f"Player trust: {trust_result.new_trust:+d}."
            )
            referee_facts.append(
                KnowledgeFact(
                    fact_id=new_id(),
                    campaign_id=inp.campaign_id,
                    scene_id=inp.scene_id,
                    owner_scope_id=inp.referee_scope_id,
                    fact_type=KnowledgeFactType.npc_tell,
                    payload=f"[lie detection] {lie_note}",
                    revealed_at=utc_now(),
                )
            )

        return SocialActionResult(
            success=success,
            outcome=outcome,
            npc=npc,
            trust_result=trust_result,
            referee_facts=referee_facts,
        )

    def _resolve_bargain(self, inp: SocialActionInput, npc: NPC) -> SocialActionResult:
        """Resolve a bargain action.

        NPCs accept a fair bargain if trust ≥ 0 and stance is not hostile.
        The server does not evaluate whether the offer is fair in value — that
        is the caller's responsibility (or the main model's flavour job).
        """
        trust = self._trust.get_trust(npc, inp.player_id)
        is_hostile = self._trust.is_hostile(npc)

        if is_hostile or trust < -20:
            outcome = SocialOutcome.FAILURE
            success = False
            memory_tag = "player_bargain_rejected"
            trust_key = "bargain_fail"
        elif trust >= 0:
            outcome = SocialOutcome.SUCCESS
            success = True
            memory_tag = "player_bargain_accepted"
            trust_key = "bargain"
        else:
            # Slightly suspicious — partial
            outcome = SocialOutcome.PARTIAL
            success = True
            memory_tag = "player_bargain_partial"
            trust_key = "question"  # neutral delta

        trust_result = self._trust.apply_action_delta(
            npc, inp.player_id, trust_key, reason=f"bargain → {outcome}"
        )
        _append_memory_tag(npc, memory_tag)

        referee_facts = self._make_trust_fact(
            npc, inp.player_id, trust_result.new_trust, inp
        )

        return SocialActionResult(
            success=success,
            outcome=outcome,
            npc=npc,
            trust_result=trust_result,
            referee_facts=referee_facts,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_trust_fact(
        self,
        npc: NPC,
        player_id: str,
        trust_value: int,
        inp: SocialActionInput,
    ) -> list[KnowledgeFact]:
        """Return a list containing a referee trust-status fact (or empty)."""
        fact = self._tells.make_trust_status_fact(
            npc,
            player_id,
            trust_value,
            campaign_id=inp.campaign_id,
            scene_id=inp.scene_id,
            referee_scope_id=inp.referee_scope_id,
        )
        return [fact] if fact else []


# ---------------------------------------------------------------------------
# Helpers (module-level)
# ---------------------------------------------------------------------------


def _append_memory_tag(npc: NPC, tag: str) -> None:
    """Append a memory tag to the NPC if not already present."""
    if tag not in npc.memory_tags:
        npc.memory_tags.append(tag)
