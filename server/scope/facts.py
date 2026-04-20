"""KnowledgeFact ownership and scope enforcement.

Every KnowledgeFact is owned by exactly one ConversationScope.
Ownership determines:
  - Who can see the fact (see ScopeEngine.can_player_see_fact)
  - Whether the fact can appear in LLM prompts (referee_only cannot)
  - Whether a VisibilityGrant is needed to extend visibility

This module provides:
  - FactOwnershipPolicy: validates fact creation and grant operations
  - fact_scope_type(): convenience getter for a fact's scope type
"""

from __future__ import annotations

import uuid
from datetime import datetime

from server.domain.entities import (
    ConversationScope,
    KnowledgeFact,
    VisibilityGrant,
)
from server.domain.enums import KnowledgeFactType, ScopeType
from server.domain.helpers import utc_now
from server.scope.engine import ScopeViolationError


class FactOwnershipError(Exception):
    """Raised when a fact creation or grant operation violates ownership rules."""


def fact_scope_type(
    fact: KnowledgeFact, scopes_by_id: dict[str, ConversationScope]
) -> ScopeType:
    """Return the ScopeType of a fact's owning scope.

    Raises FactOwnershipError if the scope is unknown.
    """
    scope = scopes_by_id.get(fact.owner_scope_id)
    if scope is None:
        raise FactOwnershipError(
            f"Fact {fact.fact_id!r} has unknown owner_scope_id {fact.owner_scope_id!r}"
        )
    return scope.scope_type


class FactOwnershipPolicy:
    """Stateless enforcer for KnowledgeFact ownership rules.

    No I/O.  All methods raise FactOwnershipError or ScopeViolationError on
    violations.
    """

    def validate_fact_creation(
        self,
        scope: ConversationScope,
        fact_type: KnowledgeFactType,
    ) -> None:
        """Validate that a fact of ``fact_type`` may be created in ``scope``.

        Rules:
          - Any scope type may own any fact type.
          - referee_only scopes may own any fact type (including hidden traps,
            NPC secrets, etc.).
          - No fact may be created without a valid scope.
        """
        # Currently no per-fact-type restrictions; all combos are valid.
        # This hook exists so future rules (e.g. "quest facts must be
        # campaign-level, not scene-level") can be added without API churn.
        if scope is None:
            raise FactOwnershipError("Cannot create fact without a scope.")

    def create_fact(
        self,
        campaign_id: str,
        scene_id: str,
        owner_scope: ConversationScope,
        fact_type: KnowledgeFactType,
        payload: str,
        source_event_id: str | None = None,
        now: datetime | None = None,
    ) -> KnowledgeFact:
        """Create and return a new KnowledgeFact.

        Does not persist — caller is responsible for saving.
        """
        self.validate_fact_creation(owner_scope, fact_type)
        return KnowledgeFact(
            fact_id=str(uuid.uuid4()),
            campaign_id=campaign_id,
            scene_id=scene_id,
            owner_scope_id=owner_scope.scope_id,
            fact_type=fact_type,
            payload=payload,
            revealed_at=now or utc_now(),
            source_event_id=source_event_id,
        )

    def create_visibility_grant(
        self,
        fact: KnowledgeFact,
        fact_scope: ConversationScope,
        grant_to_scope: ConversationScope,
        granting_player_id: str | None = None,
        now: datetime | None = None,
    ) -> VisibilityGrant:
        """Create a VisibilityGrant that broadens a fact's visibility.

        Raises ScopeViolationError if:
          - The fact is referee_only (those can never be granted to players).
          - The grant_to_scope is referee_only (nonsensical).
        """
        if fact_scope.scope_type == ScopeType.referee_only:
            raise ScopeViolationError(
                f"referee_only fact {fact.fact_id!r} cannot be granted to any player scope."
            )
        if grant_to_scope.scope_type == ScopeType.referee_only:
            raise ScopeViolationError(
                "Cannot grant visibility to a referee_only scope."
            )
        return VisibilityGrant(
            grant_id=str(uuid.uuid4()),
            fact_id=fact.fact_id,
            campaign_id=fact.campaign_id,
            granted_to_scope_id=grant_to_scope.scope_id,
            granted_at=now or utc_now(),
            granted_by_player_id=granting_player_id,
        )
