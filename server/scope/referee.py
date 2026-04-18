"""Referee-only storage rules.

referee_only scoped content is stored in the database like any other fact,
but it is subject to hard access rules:

  - NEVER delivered to any player via Telegram.
  - NEVER included in any LLM prompt (narration, NPC dialogue, or arbitration)
    whose output is subsequently sent to players.
  - MAY be read by server-side game logic for resolution (e.g. trap triggers,
    hidden map links, NPC true intent, unrevealed facts).

This module provides the RefereeGuard — a stateless checker that can be
inserted as a safety layer before any delivery or prompt assembly operation.
"""

from __future__ import annotations

from server.domain.entities import ConversationScope, KnowledgeFact
from server.domain.enums import ScopeType
from server.scope.engine import ScopeViolationError


class RefereeGuard:
    """Stateless guard for referee_only content.

    Use assert_not_referee_only() before any delivery or LLM prompt assembly
    to ensure referee content never leaks to players.
    """

    def is_referee_only(self, scope: ConversationScope) -> bool:
        """Return True if this scope is referee_only."""
        return scope.scope_type == ScopeType.referee_only

    def assert_not_referee_only(
        self, scope: ConversationScope, context: str = ""
    ) -> None:
        """Raise ScopeViolationError if scope is referee_only.

        Args:
            scope:   The scope to check.
            context: Short description of the operation (for error messages).
        """
        if scope.scope_type == ScopeType.referee_only:
            label = f" ({context})" if context else ""
            raise ScopeViolationError(
                f"referee_only content must not be delivered to players{label}"
            )

    def strip_referee_facts(
        self,
        facts: list[KnowledgeFact],
        scopes_by_id: dict[str, ConversationScope],
    ) -> list[KnowledgeFact]:
        """Remove all referee_only facts from the list.

        Safe to call before any player-visible or LLM operation.
        Unknown scope_ids are also stripped (fail-closed).
        """
        result = []
        for fact in facts:
            scope = scopes_by_id.get(fact.owner_scope_id)
            if scope is None:
                continue  # unknown scope → strip (fail-closed)
            if scope.scope_type == ScopeType.referee_only:
                continue
            result.append(fact)
        return result

    def assert_no_referee_facts(
        self,
        facts: list[KnowledgeFact],
        scopes_by_id: dict[str, ConversationScope],
        context: str = "",
    ) -> None:
        """Raise ScopeViolationError if any fact in the list is referee_only.

        Use this as a final pre-flight check before passing facts to the LLM.
        """
        for fact in facts:
            scope = scopes_by_id.get(fact.owner_scope_id)
            if scope is None:
                raise ScopeViolationError(
                    f"Fact {fact.fact_id!r} has unknown scope; cannot verify safety"
                )
            self.assert_not_referee_only(scope, context=context)
