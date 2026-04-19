"""DialogueContextBuilder — assemble structured NPC dialogue context.

Builds the context dict passed to the main model (models/main/tasks.py
generate_npc_dialogue) from structured NPC hard state plus social action
details.  Pure Python, no I/O, no model calls.

The resulting DialogueContext contains:
  - NPC identity and personality snapshot
  - Trust and stance values for the interacting player
  - Action type and declared player text
  - Memory tag summary (recent interaction history)
  - Flags for lie-detection, threat escalation, and refusal
  - Private reaction hint (referee-only, not in public output)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from server.domain.entities import NPC


# ---------------------------------------------------------------------------
# Social action types (mirrors ActionType enum values used in social context)
# ---------------------------------------------------------------------------

SOCIAL_ACTION_TYPES: frozenset[str] = frozenset(
    {"question", "persuade", "threaten", "lie", "bargain"}
)

# ---------------------------------------------------------------------------
# Dialogue context
# ---------------------------------------------------------------------------


@dataclass
class DialogueContext:
    """Structured input for NPC dialogue generation.

    Passed to the main model's generate_npc_dialogue task.  All fields
    are plain Python types (strings, ints, dicts, lists) for easy
    JSON serialization.
    """

    # NPC identity
    npc_id: str
    npc_name: str
    npc_stance: str  # "friendly" | "neutral" | "hostile" | "fearful"
    npc_health_state: str  # "healthy" | "injured" | "incapacitated" | "dead"
    # Personality and goals
    personality_tags: list[str] = field(default_factory=list)
    goal_tags: list[str] = field(default_factory=list)
    fear_tags: list[str] = field(default_factory=list)
    # Trust snapshot for the interacting player
    player_id: str = ""
    trust_value: int = 0  # -100..100
    # Interaction details
    action_type: str = ""  # "question" | "persuade" | "threaten" | "lie" | "bargain"
    player_text: str = ""  # raw player declaration
    target_info: str = ""  # what the player is asking/pressing about
    # History context
    memory_tags: list[str] = field(default_factory=list)
    # Behavioural flags derived from state (set by builder logic)
    will_resist: bool = False  # NPC is likely to refuse / push back
    is_evasive: bool = False  # NPC will be vague or deflect
    can_be_threatened: bool = True  # False for fearless/powerful NPCs
    # Private hint for referee (not included in public model context)
    private_reaction_hint: str = ""  # e.g. "Bram knows the cellar is trapped"


# ---------------------------------------------------------------------------
# DialogueContextBuilder
# ---------------------------------------------------------------------------


class DialogueContextBuilder:
    """Build a DialogueContext from structured NPC state and action details.

    Pure stateless builder — no I/O, no side effects.
    """

    def build(
        self,
        npc: NPC,
        player_id: str,
        action_type: str,
        player_text: str,
        *,
        target_info: str = "",
        private_reaction_hint: str = "",
    ) -> DialogueContext:
        """Assemble a DialogueContext from NPC entity and interaction details.

        Derives behavioural flags from NPC personality and trust/stance state.

        Args:
            npc:                    Current NPC entity.
            player_id:              The interacting player.
            action_type:            Social action type string.
            player_text:            Player's declared action text.
            target_info:            What the player is asking about (optional).
            private_reaction_hint:  Referee-only internal hint (optional).

        Returns:
            Populated DialogueContext.
        """
        trust = npc.trust_by_player.get(player_id, 0)
        stance = npc.stance_to_party

        will_resist = self._compute_will_resist(npc, stance, trust, action_type)
        is_evasive = self._compute_is_evasive(npc, stance, trust, action_type)
        can_be_threatened = self._compute_can_be_threatened(npc)

        return DialogueContext(
            npc_id=npc.npc_id,
            npc_name=npc.name,
            npc_stance=stance,
            npc_health_state=npc.health_state,
            personality_tags=list(npc.personality_tags),
            goal_tags=list(npc.goal_tags),
            fear_tags=list(npc.fear_tags),
            player_id=player_id,
            trust_value=trust,
            action_type=action_type,
            player_text=player_text,
            target_info=target_info,
            memory_tags=list(npc.memory_tags),
            will_resist=will_resist,
            is_evasive=is_evasive,
            can_be_threatened=can_be_threatened,
            private_reaction_hint=private_reaction_hint,
        )

    # ------------------------------------------------------------------
    # Flag derivation
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_will_resist(
        npc: NPC, stance: str, trust: int, action_type: str
    ) -> bool:
        """NPC resists when hostile, very low personal trust, or action is threatening."""
        if stance == "hostile":
            return True
        if trust < -20:
            return True
        if action_type == "threaten" and trust < 30:
            return True
        if action_type == "persuade" and trust < -10:
            return True
        return False

    @staticmethod
    def _compute_is_evasive(
        npc: NPC, stance: str, trust: int, action_type: str
    ) -> bool:
        """NPC is evasive when neutral-negative or action is a question/lie target."""
        if "secretive" in npc.personality_tags or "deceptive" in npc.personality_tags:
            return True
        if action_type == "question" and trust < 10:
            return True
        if stance in ("neutral",) and trust < 0:
            return True
        return False

    @staticmethod
    def _compute_can_be_threatened(npc: NPC) -> bool:
        """True unless NPC has fearless/powerful personality tags."""
        immune_tags = {"fearless", "powerful", "guard_captain", "boss", "immune_fear"}
        return not bool(immune_tags & set(npc.personality_tags))

    # ------------------------------------------------------------------
    # Public context (strips private hint for player-visible output)
    # ------------------------------------------------------------------

    def to_public_dict(self, ctx: DialogueContext) -> dict:
        """Return a copy of the context dict safe to include in player-visible prompts.

        Strips private_reaction_hint.
        """
        return {
            "npc_id": ctx.npc_id,
            "npc_name": ctx.npc_name,
            "npc_stance": ctx.npc_stance,
            "npc_health_state": ctx.npc_health_state,
            "personality_tags": ctx.personality_tags,
            "goal_tags": ctx.goal_tags,
            "fear_tags": ctx.fear_tags,
            "player_id": ctx.player_id,
            "trust_value": ctx.trust_value,
            "action_type": ctx.action_type,
            "player_text": ctx.player_text,
            "target_info": ctx.target_info,
            "memory_tags": ctx.memory_tags,
            "will_resist": ctx.will_resist,
            "is_evasive": ctx.is_evasive,
            "can_be_threatened": ctx.can_be_threatened,
        }

    def to_referee_dict(self, ctx: DialogueContext) -> dict:
        """Return the full context dict including the private reaction hint."""
        d = self.to_public_dict(ctx)
        d["private_reaction_hint"] = ctx.private_reaction_hint
        return d
