"""Routes incoming player messages through the fast model pipeline
and into the appropriate game subsystem."""

from __future__ import annotations


from server.orchestrator.game_loop import DispatchResult, GameOrchestrator


class MessageDispatcher:
    """Thin wrapper that delegates to the orchestrator's message handling."""

    def __init__(self, orchestrator: GameOrchestrator) -> None:
        self.orchestrator = orchestrator

    async def dispatch(
        self, player_id: str, text: str, is_private: bool
    ) -> DispatchResult:
        """Route a player message through the orchestrator."""
        return await self.orchestrator.handle_player_message(
            player_id, text, is_private
        )
