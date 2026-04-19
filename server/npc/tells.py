"""NpcTellEngine — secret NPC tells and referee-only private reactions.

Tells are private KnowledgeFacts (scope: referee_only or private_referee)
that expose the NPC's internal state to the referee without leaking it to
players.  Examples:

  - "Mira's left eye twitches when she denies knowing the merchant." (behavioral tell)
  - "Bram is hiding something — his hands shake as he describes the cellar."
  - "The innkeeper's trust level for this player is now 35 (warm)."

All methods return KnowledgeFact lists.  Callers persist and scope them.

Pure domain logic.  No I/O.  No storage imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid

from server.domain.entities import KnowledgeFact, NPC
from server.domain.enums import KnowledgeFactType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Tell definitions
# ---------------------------------------------------------------------------


@dataclass
class TellDefinition:
    """A registered behavioral tell for an NPC.

    Fires when ``trigger_tag`` is present in npc.memory_tags or
    when ``trigger_stance`` matches npc.stance_to_party.
    """

    tell_id: str
    npc_id: str
    # One or both trigger conditions may be set; either match fires the tell.
    trigger_tag: str = ""  # fires if this tag is in npc.memory_tags
    trigger_stance: str = ""  # fires if npc.stance_to_party == this value
    trigger_action_type: str = ""  # fires on social action of this type
    tell_text: str = ""  # referee-visible behavioral description
    is_active: bool = True


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class TellResult:
    """Returned by NpcTellEngine.evaluate_tells()."""

    npc_id: str
    fired_tells: list[TellDefinition] = field(default_factory=list)
    referee_facts: list[KnowledgeFact] = field(default_factory=list)


# ---------------------------------------------------------------------------
# NpcTellEngine
# ---------------------------------------------------------------------------


class NpcTellEngine:
    """Stateless engine for secret NPC tell generation.

    Callers supply the tell library for each NPC.  The engine evaluates
    which tells fire given current NPC state and action context, then
    packages them as referee-only KnowledgeFacts.
    """

    def evaluate_tells(
        self,
        npc: NPC,
        tells: list[TellDefinition],
        *,
        action_type: str = "",
        campaign_id: str = "",
        scene_id: str = "",
        referee_scope_id: str = "",
    ) -> TellResult:
        """Evaluate all tell definitions against current NPC state.

        A tell fires if any one of its trigger conditions is satisfied:
          - trigger_tag is non-empty and present in npc.memory_tags
          - trigger_stance is non-empty and matches npc.stance_to_party
          - trigger_action_type is non-empty and matches the current action_type

        Args:
            npc:              Current NPC state.
            tells:            Library of TellDefinitions for this NPC.
            action_type:      The social action type being resolved
                              (e.g. "threaten", "question").
            campaign_id:      For stamping new KnowledgeFacts.
            scene_id:         For stamping new KnowledgeFacts.
            referee_scope_id: Scope ID for referee-only facts.

        Returns:
            TellResult with all fired tells and their referee facts.
        """
        fired: list[TellDefinition] = []
        facts: list[KnowledgeFact] = []

        for tell in tells:
            if not tell.is_active:
                continue
            if self._fires(tell, npc, action_type):
                fired.append(tell)
                if tell.tell_text and referee_scope_id:
                    facts.append(
                        KnowledgeFact(
                            fact_id=_new_id(),
                            campaign_id=campaign_id,
                            scene_id=scene_id,
                            owner_scope_id=referee_scope_id,
                            fact_type=KnowledgeFactType.npc_tell,
                            payload=f"[{npc.name} tell] {tell.tell_text}",
                            revealed_at=_now(),
                        )
                    )

        return TellResult(npc_id=npc.npc_id, fired_tells=fired, referee_facts=facts)

    def make_trust_status_fact(
        self,
        npc: NPC,
        player_id: str,
        trust_value: int,
        *,
        campaign_id: str = "",
        scene_id: str = "",
        referee_scope_id: str = "",
    ) -> KnowledgeFact | None:
        """Create a referee-only fact recording the NPC's current trust value.

        Returns None if referee_scope_id is empty (caller skips persistence).
        """
        if not referee_scope_id:
            return None
        payload = (
            f"[NPC state] {npc.name}'s trust for player {player_id} "
            f"is now {trust_value:+d}. Stance: {npc.stance_to_party}."
        )
        return KnowledgeFact(
            fact_id=_new_id(),
            campaign_id=campaign_id,
            scene_id=scene_id,
            owner_scope_id=referee_scope_id,
            fact_type=KnowledgeFactType.npc_tell,
            payload=payload,
            revealed_at=_now(),
        )

    def make_private_reaction_fact(
        self,
        npc: NPC,
        reaction_text: str,
        *,
        campaign_id: str = "",
        scene_id: str = "",
        referee_scope_id: str = "",
    ) -> KnowledgeFact | None:
        """Package an arbitrary private NPC reaction as a referee-only fact.

        Used when the main model generates an NPC reaction that should not
        be visible to players (internal thoughts, true motivations, etc.).

        Returns None if referee_scope_id is empty.
        """
        if not referee_scope_id:
            return None
        return KnowledgeFact(
            fact_id=_new_id(),
            campaign_id=campaign_id,
            scene_id=scene_id,
            owner_scope_id=referee_scope_id,
            fact_type=KnowledgeFactType.npc_tell,
            payload=f"[{npc.name} private reaction] {reaction_text}",
            revealed_at=_now(),
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _fires(tell: TellDefinition, npc: NPC, action_type: str) -> bool:
        """Return True if any trigger condition is satisfied."""
        if tell.trigger_tag and tell.trigger_tag in npc.memory_tags:
            return True
        if tell.trigger_stance and tell.trigger_stance == npc.stance_to_party:
            return True
        if tell.trigger_action_type and tell.trigger_action_type == action_type:
            return True
        return False
