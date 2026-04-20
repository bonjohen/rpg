"""Guardrails against accidental public leakage of private/referee content.

This module provides a single pre-flight check surface:

    guard = LeakageGuard()
    guard.check_public_prompt(facts, scopes_by_id)   # before any public LLM call
    guard.check_player_prompt(player_id, facts, ...)  # before any player-DM LLM call

If any check fails it raises ScopeViolationError with a descriptive message,
giving callers a clear traceback to the offending fact.

These guards are belt-and-suspenders; ScopeEngine already enforces scope rules
during assembly.  LeakageGuard is the last line of defence before facts are
serialised into a prompt string.
"""

from __future__ import annotations

from server.domain.entities import (
    ConversationScope,
    KnowledgeFact,
    SideChannel,
    VisibilityGrant,
)
from server.domain.enums import ScopeType
from server.scope.engine import ScopeEngine, ScopeViolationError
from server.scope.referee import RefereeGuard


class LeakageGuard:
    """Consolidated leakage-prevention checks."""

    def __init__(
        self,
        engine: ScopeEngine | None = None,
        referee_guard: RefereeGuard | None = None,
    ) -> None:
        self._engine = engine or ScopeEngine()
        self._referee = referee_guard or RefereeGuard()

    def check_public_prompt(
        self,
        facts: list[KnowledgeFact],
        scopes_by_id: dict[str, ConversationScope],
        context: str = "public prompt",
    ) -> None:
        """Assert that every fact in the list is safe for a public prompt.

        Raises ScopeViolationError if any fact is non-public (private_referee,
        side_channel, or referee_only).
        """
        for fact in facts:
            scope = scopes_by_id.get(fact.owner_scope_id)
            if scope is None:
                raise ScopeViolationError(
                    f"Fact {fact.fact_id!r} has unknown scope — blocked from {context}"
                )
            if scope.scope_type != ScopeType.public:
                raise ScopeViolationError(
                    f"Fact {fact.fact_id!r} has scope {scope.scope_type.value!r} "
                    f"and must not appear in {context}"
                )

    def check_player_prompt(
        self,
        player_id: str,
        facts: list[KnowledgeFact],
        scopes_by_id: dict[str, ConversationScope],
        grants_by_fact_id: dict[str, list[VisibilityGrant]],
        side_channels_by_id: dict[str, SideChannel],
        context: str = "player prompt",
    ) -> None:
        """Assert that every fact is visible to ``player_id`` and not referee_only.

        Raises ScopeViolationError if any fact would leak private info from
        another player or any referee_only content.
        """
        # Strip referee_only first (hard block — no exceptions)
        self._referee.assert_no_referee_facts(facts, scopes_by_id, context=context)

        # Verify each fact is actually visible to this player
        for fact in facts:
            scope = scopes_by_id.get(fact.owner_scope_id)
            if scope is None:
                raise ScopeViolationError(
                    f"Fact {fact.fact_id!r} has unknown scope — blocked from {context}"
                )
            side_channel: SideChannel | None = None
            if scope.scope_type == ScopeType.side_channel and scope.side_channel_id:
                side_channel = side_channels_by_id.get(scope.side_channel_id)
            grants = grants_by_fact_id.get(fact.fact_id, [])
            if not self._engine.can_player_see_fact(
                player_id, fact, scope, grants, side_channel
            ):
                raise ScopeViolationError(
                    f"Fact {fact.fact_id!r} (scope={scope.scope_type.value!r}) "
                    f"is not visible to player {player_id!r} — blocked from {context}"
                )
