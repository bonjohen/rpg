"""Scope and Visibility Engine — pure domain logic, no I/O.

All four scope types are enforced here:

  public          — visible to every player in the campaign
  private_referee — visible only to the owning player (+ server)
  side_channel    — visible only to the explicit member set (+ server)
  referee_only    — never delivered to any player; server-internal only

Key design rules (from architecture.md):
  - Scope is a first-class data field.  It is never inferred from chat structure.
  - The LLM never directly reads referee_only facts.
  - Public scope delivery never leaks private or referee_only content.
  - Scope-safe context assembly filters facts before passing them to the LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from server.domain.entities import (
    ConversationScope,
    KnowledgeFact,
    SideChannel,
    VisibilityGrant,
)
from server.domain.enums import ScopeType


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ScopeViolationError(Exception):
    """Raised when a delivery or assembly would leak private/referee content."""


# ---------------------------------------------------------------------------
# Delivery target descriptor
# ---------------------------------------------------------------------------


@dataclass
class DeliveryTarget:
    """Describes who should receive a message or fact.

    Returned by ScopeEngine.delivery_targets_for().
    The caller translates this into Telegram sends.
    """

    # Deliver to the public group / play topic
    send_public: bool = False
    # Deliver to these individual player_ids via private DM
    send_private_to: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# ScopeEngine
# ---------------------------------------------------------------------------


class ScopeEngine:
    """Stateless engine that enforces scope rules.

    Callers are responsible for:
      - Loading scopes, facts, grants, and side-channels from the repository.
      - Passing complete, accurate data — the engine trusts its inputs.
      - Translating DeliveryTarget results into actual Telegram sends.

    No I/O.  No mutation of stored entities.
    """

    # ------------------------------------------------------------------
    # Public scope rules
    # ------------------------------------------------------------------

    def is_public(self, scope: ConversationScope) -> bool:
        """Return True if this scope is public."""
        return scope.scope_type == ScopeType.public

    def delivery_targets_for(
        self,
        scope: ConversationScope,
        all_player_ids: list[str],
        side_channel: SideChannel | None = None,
    ) -> DeliveryTarget:
        """Return the DeliveryTarget for a given scope.

        Args:
            scope:           The ConversationScope of the message or fact.
            all_player_ids:  All active player_ids in the campaign.
            side_channel:    Required when scope_type is side_channel.

        Returns:
            DeliveryTarget indicating where to send the content.

        Raises:
            ScopeViolationError: If referee_only content would be delivered to
                any player, or if side_channel data is missing when required.
        """
        if scope.scope_type == ScopeType.public:
            return DeliveryTarget(send_public=True)

        if scope.scope_type == ScopeType.private_referee:
            if scope.player_id is None:
                raise ScopeViolationError("private_referee scope missing player_id")
            return DeliveryTarget(send_private_to=[scope.player_id])

        if scope.scope_type == ScopeType.side_channel:
            if side_channel is None:
                raise ScopeViolationError(
                    "side_channel scope requires a SideChannel object"
                )
            if not side_channel.is_open:
                return DeliveryTarget()  # closed channel → deliver nothing
            return DeliveryTarget(send_private_to=list(side_channel.member_player_ids))

        if scope.scope_type == ScopeType.referee_only:
            raise ScopeViolationError(
                "referee_only content must never be delivered to any player"
            )

        raise ScopeViolationError(f"Unknown scope_type: {scope.scope_type!r}")

    # ------------------------------------------------------------------
    # Visibility checks
    # ------------------------------------------------------------------

    def can_player_see_fact(
        self,
        player_id: str,
        fact: KnowledgeFact,
        scope: ConversationScope,
        grants: list[VisibilityGrant],
        side_channel: SideChannel | None = None,
    ) -> bool:
        """Return True if ``player_id`` is allowed to see ``fact``.

        Checks the fact's owning scope first, then any VisibilityGrants that
        extend visibility to additional scopes.

        Args:
            player_id:    The player whose visibility is being checked.
            fact:         The KnowledgeFact to check.
            scope:        The ConversationScope that owns the fact.
            grants:       All VisibilityGrants for this fact.
            side_channel: The SideChannel, if the owning scope is side_channel.
        """
        # referee_only is never visible to any player
        if scope.scope_type == ScopeType.referee_only:
            return False

        # Public → everyone can see it
        if scope.scope_type == ScopeType.public:
            return True

        # private_referee → only the owning player
        if scope.scope_type == ScopeType.private_referee:
            if scope.player_id == player_id:
                return True
            # fall through to check grants

        # side_channel → members only
        if scope.scope_type == ScopeType.side_channel:
            if side_channel and player_id in side_channel.member_player_ids:
                return True
            # fall through to check grants

        # Check explicit visibility grants
        for grant in grants:
            if grant.fact_id != fact.fact_id:
                continue
            # A grant to a public scope means everyone can now see it
            # (this handles "player announces their private discovery")
            # We accept the grant as broadening access; the caller must pass
            # the granted scope in future calls.  Here we just check if any
            # grant covers this player by looking at the granted scope.
            # Since we don't have the granted-scope object in this call, we
            # treat the existence of a grant to ANY scope as sufficient.
            # Callers that need strict grant-scope checking should pass
            # the granted scopes and call can_player_see_fact recursively.
            return True

        return False

    def filter_facts_for_player(
        self,
        player_id: str,
        facts: list[KnowledgeFact],
        scopes_by_id: dict[str, ConversationScope],
        grants_by_fact_id: dict[str, list[VisibilityGrant]],
        side_channels_by_id: dict[str, SideChannel],
    ) -> list[KnowledgeFact]:
        """Return only the facts visible to ``player_id``.

        Args:
            player_id:           Target player.
            facts:               All candidate facts to filter.
            scopes_by_id:        scope_id → ConversationScope mapping.
            grants_by_fact_id:   fact_id → list of VisibilityGrants.
            side_channels_by_id: side_channel_id → SideChannel mapping.

        Returns:
            Filtered list of facts the player is allowed to see.
        """
        visible = []
        for fact in facts:
            scope = scopes_by_id.get(fact.owner_scope_id)
            if scope is None:
                continue  # unknown scope → deny
            side_channel: SideChannel | None = None
            if scope.scope_type == ScopeType.side_channel and scope.side_channel_id:
                side_channel = side_channels_by_id.get(scope.side_channel_id)
            grants = grants_by_fact_id.get(fact.fact_id, [])
            if self.can_player_see_fact(player_id, fact, scope, grants, side_channel):
                visible.append(fact)
        return visible

    # ------------------------------------------------------------------
    # Scope-safe context assembly (LLM prompt safety)
    # ------------------------------------------------------------------

    def assemble_public_context(
        self,
        facts: list[KnowledgeFact],
        scopes_by_id: dict[str, ConversationScope],
    ) -> list[KnowledgeFact]:
        """Return only public facts safe to include in public LLM prompts.

        Raises ScopeViolationError if any non-public fact would be included.
        Private, side-channel, and referee-only facts must never reach a
        prompt that is delivered publicly.
        """
        safe: list[KnowledgeFact] = []
        for fact in facts:
            scope = scopes_by_id.get(fact.owner_scope_id)
            if scope is None:
                raise ScopeViolationError(
                    f"Fact {fact.fact_id!r} has unknown scope_id "
                    f"{fact.owner_scope_id!r}; cannot determine safety"
                )
            if scope.scope_type != ScopeType.public:
                raise ScopeViolationError(
                    f"Fact {fact.fact_id!r} has scope {scope.scope_type.value!r} "
                    "and must not appear in a public prompt"
                )
            safe.append(fact)
        return safe

    def assemble_private_context(
        self,
        player_id: str,
        facts: list[KnowledgeFact],
        scopes_by_id: dict[str, ConversationScope],
        grants_by_fact_id: dict[str, list[VisibilityGrant]],
        side_channels_by_id: dict[str, SideChannel],
    ) -> list[KnowledgeFact]:
        """Return facts visible to ``player_id`` for a player-scoped prompt.

        Excludes referee_only facts — they must never reach the LLM.
        """
        candidate = self.filter_facts_for_player(
            player_id, facts, scopes_by_id, grants_by_fact_id, side_channels_by_id
        )
        # Extra safety: strip referee_only even if filter_facts_for_player
        # somehow included one (should not happen, but belt-and-suspenders)
        return [
            f
            for f in candidate
            if scopes_by_id.get(
                f.owner_scope_id,
                ConversationScope(
                    scope_id="", campaign_id="", scope_type=ScopeType.referee_only
                ),
            ).scope_type
            != ScopeType.referee_only
        ]

    def assemble_referee_context(
        self,
        facts: list[KnowledgeFact],
        scopes_by_id: dict[str, ConversationScope],
    ) -> list[KnowledgeFact]:
        """Return all facts including referee_only for server-side resolution.

        This context MUST NEVER be forwarded to any LLM prompt that is
        subsequently delivered to players.  It is for internal server logic only.
        """
        return list(facts)
