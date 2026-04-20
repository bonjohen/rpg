"""TrustEngine — trust-by-player delta computation and party-stance transitions.

Pure domain logic.  No I/O.  Callers persist returned NPC entities.

Trust scores are integers in the range -100..100.
  > 60   → friendly threshold
  20..60 → warm / cooperative
 -20..20 → neutral
-20..-60 → suspicious
  < -60  → hostile threshold

Party stance labels:
  "friendly" | "neutral" | "hostile" | "fearful"

Stance is re-derived from the mean of all per-player trust values each time
a trust delta is applied.  The caller may override stance independently for
hard scenario events (e.g. a scripted betrayal).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from server.domain.entities import NPC

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TRUST_MIN: int = -100
TRUST_MAX: int = 100

# Per-action base deltas (before NPC personality modifiers).
# Positive means trust increases; negative decreases.
_BASE_DELTAS: dict[str, int] = {
    "question": 2,  # mild engagement — slight positive
    "persuade": 6,  # success case; engine applies this on success
    "persuade_fail": -3,  # persuasion attempt that failed
    "threaten": -15,  # always damages trust
    "lie": -8,  # discovered-lie; engine applies on detection
    "lie_undetected": 1,  # successful lie — tiny positive (NPC thinks you're agreeable)
    "bargain": 4,  # fair offer accepted
    "bargain_fail": -2,  # offer refused
    "help_npc": 20,  # player materially helped the NPC
    "betray_npc": -30,  # player betrayed the NPC
}

_FRIENDLY_THRESHOLD: int = 60
_HOSTILE_THRESHOLD: int = -60
_FEARFUL_THRESHOLD: int = -45  # fearful kicks in when hostile+threatening

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class TrustDeltaResult:
    """Returned by TrustEngine.apply_delta()."""

    npc_id: str
    player_id: str
    old_trust: int
    new_trust: int
    old_stance: str
    new_stance: str
    # Human-readable summary for referee log
    summary: str


# ---------------------------------------------------------------------------
# TrustEngine
# ---------------------------------------------------------------------------


class TrustEngine:
    """Stateless engine for trust and stance management.

    All methods accept and return domain entities.
    Callers must persist the modified NPC.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply_delta(
        self,
        npc: NPC,
        player_id: str,
        delta: int,
        *,
        reason: str = "",
    ) -> TrustDeltaResult:
        """Apply a raw trust delta for a single player.

        Clamps to [-100, 100].  Re-derives party stance from mean trust.
        Mutates ``npc`` in place; caller persists.

        Args:
            npc:       The NPC being updated.
            player_id: The player whose interaction drove the change.
            delta:     Signed integer change to apply.
            reason:    Human-readable reason (for referee log).

        Returns:
            TrustDeltaResult with before/after values.
        """
        old_trust = npc.trust_by_player.get(player_id, 0)
        new_trust = max(TRUST_MIN, min(TRUST_MAX, old_trust + delta))
        npc.trust_by_player[player_id] = new_trust

        old_stance = npc.stance_to_party
        new_stance = self._derive_stance(npc)
        npc.stance_to_party = new_stance

        summary = (
            f"Trust({npc.name}, {player_id}): {old_trust:+d} → {new_trust:+d} "
            f"[delta={delta:+d}] stance: {old_stance}→{new_stance}"
        )
        if reason:
            summary += f" ({reason})"

        return TrustDeltaResult(
            npc_id=npc.npc_id,
            player_id=player_id,
            old_trust=old_trust,
            new_trust=new_trust,
            old_stance=old_stance,
            new_stance=new_stance,
            summary=summary,
        )

    def apply_action_delta(
        self,
        npc: NPC,
        player_id: str,
        action_key: str,
        *,
        personality_modifier: float = 1.0,
        reason: str = "",
    ) -> TrustDeltaResult:
        """Apply a named action's base delta, optionally scaled by personality.

        ``action_key`` must be one of the keys in ``_BASE_DELTAS``.
        ``personality_modifier`` scales the delta (e.g. 1.5 for a sensitive NPC,
        0.5 for a stoic one).  The result is rounded to nearest integer.

        Args:
            npc:                  The NPC being updated.
            player_id:            The acting player.
            action_key:           Key from ``_BASE_DELTAS``.
            personality_modifier: Scale factor (default 1.0).
            reason:               Human-readable reason.

        Returns:
            TrustDeltaResult.
        """
        base = _BASE_DELTAS.get(action_key, 0)
        if action_key not in _BASE_DELTAS:
            logger.warning(
                "Unknown trust action_key %r — defaulting to delta 0", action_key
            )
        delta = int(round(base * personality_modifier))
        return self.apply_delta(npc, player_id, delta, reason=reason or action_key)

    def get_trust(self, npc: NPC, player_id: str) -> int:
        """Return the current trust score for a player (default 0)."""
        return npc.trust_by_player.get(player_id, 0)

    def set_stance(self, npc: NPC, stance: str) -> str:
        """Force-set the party stance (for scripted scenario events).

        Returns the previous stance.
        """
        old = npc.stance_to_party
        npc.stance_to_party = stance
        return old

    # ------------------------------------------------------------------
    # Stance derivation
    # ------------------------------------------------------------------

    def _derive_stance(self, npc: NPC) -> str:
        """Derive party-level stance from the mean of all trust scores.

        If trust_by_player is empty, stance stays as-is (neutral default).
        """
        if not npc.trust_by_player:
            return npc.stance_to_party

        mean_trust = sum(npc.trust_by_player.values()) / len(npc.trust_by_player)
        min_trust = min(npc.trust_by_player.values())

        # Any single player with extreme hostility can override to hostile/fearful
        if min_trust <= _HOSTILE_THRESHOLD:
            # If threatening NPC is also fearful by personality
            if "fearful" in npc.personality_tags or "timid" in npc.personality_tags:
                return "fearful"
            return "hostile"

        if mean_trust >= _FRIENDLY_THRESHOLD:
            return "friendly"
        if mean_trust >= -20:
            return "neutral"
        if mean_trust >= _HOSTILE_THRESHOLD:
            return "suspicious"
        # Should not reach here given min_trust check above, but guard it
        return "hostile"

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def is_cooperative(self, npc: NPC, player_id: Optional[str] = None) -> bool:
        """Return True if the NPC is disposed to cooperate.

        If player_id given, checks that player's personal trust; otherwise
        uses party stance.
        """
        if player_id is not None:
            trust = self.get_trust(npc, player_id)
            return trust >= 0 and npc.stance_to_party != "hostile"
        return npc.stance_to_party in ("friendly", "neutral")

    def is_hostile(self, npc: NPC) -> bool:
        """Return True if the NPC stance is hostile."""
        return npc.stance_to_party == "hostile"

    def is_fearful(self, npc: NPC) -> bool:
        """Return True if the NPC stance is fearful."""
        return npc.stance_to_party == "fearful"
