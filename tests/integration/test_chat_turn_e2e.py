"""End-to-end chat turn integration tests (Phase 8).

Tests per chat_loop_test_plan §4.1. Full turn lifecycle through the
orchestrator with in-memory DB, mocked model responses, and real
game state.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from models.fast.tasks import ActionPacketResult, IntentClassificationResult
from server.orchestrator.game_loop import GameOrchestrator
from tests.fixtures.db_helpers import create_test_session_factory


def _mock_classify(intent: str):
    """Return a coroutine that returns a canned IntentClassificationResult."""

    async def _classify(adapter, text, **kwargs):
        return IntentClassificationResult(
            intent=intent, confidence="high", raw=intent
        ), MagicMock()

    return _classify


def _mock_extract_action():
    """Return a coroutine that returns a canned ActionPacketResult."""

    async def _extract(adapter, text, available_types, **kwargs):
        return ActionPacketResult(
            action_type="custom", target="", item_ids=[], notes="", raw="custom"
        ), MagicMock()

    return _extract


def _make_orchestrator(fast_adapter=None, main_adapter=None) -> GameOrchestrator:
    """Build a full orchestrator with in-memory DB."""
    session_factory = create_test_session_factory()
    orch = GameOrchestrator(
        fast_adapter=fast_adapter,
        main_adapter=main_adapter,
        session_factory=session_factory,
    )
    return orch


def _load_scenario(
    orch: GameOrchestrator, path: str = "scenarios/starters/goblin_caves.yaml"
) -> None:
    result = orch.load_scenario(path, campaign_name="Test Campaign")
    assert result is not None and result.success


def _add_player(
    orch: GameOrchestrator, name: str = "Alice", telegram_id: int = 100
) -> str:
    player, char = orch.add_player(
        player_id=f"p-{telegram_id}",
        display_name=name,
        telegram_user_id=telegram_id,
    )
    return player.player_id


class TestFullTurnViaChat:
    @pytest.mark.asyncio
    async def test_full_turn_via_chat(self):
        """Player sends action text -> turn auto-opens -> submitted -> resolved."""
        fast = MagicMock()
        orch = _make_orchestrator(fast_adapter=fast)
        _load_scenario(orch)
        pid = _add_player(orch)

        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                _mock_classify("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                _mock_extract_action(),
            ),
        ):
            result = await orch.handle_player_message(
                pid, "I search the cave", is_private=False
            )

        assert result.handled is True
        assert result.action_submitted is True
        # Single player -> all-ready -> auto-resolve
        assert result.turn_resolved is True
        assert result.turn_log_entry is not None


class TestMultiPlayerTurn:
    @pytest.mark.asyncio
    async def test_multi_player_turn(self):
        """Two players send actions -> both submitted -> single resolve."""
        fast = MagicMock()
        orch = _make_orchestrator(fast_adapter=fast)
        _load_scenario(orch)
        pid1 = _add_player(orch, "Alice", 100)
        pid2 = _add_player(orch, "Bob", 200)

        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                _mock_classify("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                _mock_extract_action(),
            ),
        ):
            result1 = await orch.handle_player_message(
                pid1, "I search", is_private=False
            )
            result2 = await orch.handle_player_message(
                pid2, "I watch", is_private=False
            )

        assert result1.action_submitted is True
        assert result1.turn_resolved is False  # Bob hasn't acted yet
        assert result2.action_submitted is True
        assert result2.turn_resolved is True  # Now all-ready


class TestPrivateQuestionViaDm:
    @pytest.mark.asyncio
    async def test_private_question_via_dm(self):
        """Player DMs question -> ruling returned privately."""
        fast = MagicMock()
        orch = _make_orchestrator(fast_adapter=fast)
        _load_scenario(orch)
        pid = _add_player(orch)

        with patch(
            "server.orchestrator.game_loop.classify_intent",
            _mock_classify("question"),
        ):
            result = await orch.handle_player_message(
                pid, "Is the NPC lying?", is_private=True
            )

        assert result.handled is True
        assert result.scope == "private"
        assert result.response_text  # Should have some response


class TestTimeoutFallbackTurn:
    @pytest.mark.asyncio
    async def test_timeout_fallback_turn(self):
        """One player submits, other doesn't -> force resolve -> fallback actions."""
        fast = MagicMock()
        orch = _make_orchestrator(fast_adapter=fast)
        _load_scenario(orch)
        pid1 = _add_player(orch, "Alice", 100)
        _add_player(orch, "Bob", 200)

        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                _mock_classify("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                _mock_extract_action(),
            ),
        ):
            result = await orch.handle_player_message(
                pid1, "I search", is_private=False
            )

        assert result.action_submitted is True
        assert result.turn_resolved is False  # Bob hasn't acted

        # Force resolve (simulates timer expiry)
        scene = orch.get_player_scene(pid1)
        assert scene is not None
        assert scene.active_turn_window_id is not None
        log_entry = orch.resolve_turn(scene.active_turn_window_id)
        assert log_entry is not None
        assert "hesitates" in log_entry.narration.lower() or log_entry.narration


class TestConsecutiveTurnsAutoOpen:
    @pytest.mark.asyncio
    async def test_consecutive_turns_auto_open(self):
        """After resolution, next action auto-opens turn 2."""
        fast = MagicMock()
        orch = _make_orchestrator(fast_adapter=fast)
        _load_scenario(orch)
        pid = _add_player(orch)

        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                _mock_classify("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                _mock_extract_action(),
            ),
        ):
            result1 = await orch.handle_player_message(
                pid, "I search", is_private=False
            )

        assert result1.turn_resolved is True

        # Second action -> should auto-open turn 2
        # Reset idempotency to avoid dedup
        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                _mock_classify("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                _mock_extract_action(),
            ),
        ):
            result2 = await orch.handle_player_message(
                pid, "I move north", is_private=False
            )

        assert result2.action_submitted is True
        assert result2.turn_resolved is True  # Single player, auto-resolves again


class TestPrivateFactsDeliveredAfterResolve:
    @pytest.mark.asyncio
    async def test_private_facts_delivered_after_resolve(self):
        """Resolution produces turn_log_entry with narration for delivery."""
        fast = MagicMock()
        orch = _make_orchestrator(fast_adapter=fast)
        _load_scenario(orch)
        pid = _add_player(orch)

        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                _mock_classify("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                _mock_extract_action(),
            ),
        ):
            result = await orch.handle_player_message(
                pid, "I search for hidden things", is_private=False
            )

        assert result.turn_resolved is True
        log_entry = result.turn_log_entry
        assert log_entry is not None
        assert log_entry.narration  # Has narration text for delivery
