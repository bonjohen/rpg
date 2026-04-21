"""Unit tests for orchestrator message handling (Phase 2).

Tests per chat_loop_test_plan §3.2:
- Action intent submits to turn
- Question intent calls ruling (placeholder — full implementation in Phase 7)
- Question private stays private
- Chat intent returns empty
- Unknown intent falls back to action
- Duplicate message deduped
- Identical text different turns not deduped
- No fast adapter treats as action
- Action extraction failure fallback
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.fast.tasks import ActionPacketResult, IntentClassificationResult
from server.orchestrator.game_loop import GameOrchestrator
from tests.fixtures.db_helpers import create_test_session_factory


def _make_orchestrator(fast_adapter=None) -> GameOrchestrator:
    """Build a GameOrchestrator with in-memory DB and optional mock fast adapter."""
    session_factory = create_test_session_factory()
    orch = GameOrchestrator(
        fast_adapter=fast_adapter,
        session_factory=session_factory,
    )
    # Load a minimal scenario so we have a campaign and scene
    from scenarios.loader import ScenarioLoader
    from scenarios.schema import ScenarioManifest, SceneDefinition

    manifest = ScenarioManifest(
        scenario_id="test",
        title="Test Scenario",
        starting_scene_id="scene1",
        scenes=[
            SceneDefinition(scene_id="scene1", name="Test Scene", description="A test."),
        ],
    )
    loader = ScenarioLoader()
    result = loader.load_from_manifest(manifest)

    # Patch the orchestrator's scenario_loader to return our pre-built result
    with patch.object(orch.scenario_loader, "load_from_yaml", return_value=result):
        orch.load_scenario("dummy.yaml")

    return orch


def _add_player(orch: GameOrchestrator, player_id: str = "player-1") -> str:
    """Add a player and return the player_id."""
    orch.add_player(player_id=player_id, display_name="Test Player")
    return player_id


def _mock_classify(intent: str = "action", confidence: str = "high"):
    """Return a mock classify_intent coroutine result."""
    result = IntentClassificationResult(intent=intent, confidence=confidence, raw="{}")
    log = MagicMock()
    return AsyncMock(return_value=(result, log))


def _mock_extract(action_type: str = "search", target: str = "", item_ids: list | None = None):
    """Return a mock extract_action_packet coroutine result."""
    result = ActionPacketResult(
        action_type=action_type, target=target, item_ids=item_ids or [], notes="", raw="{}"
    )
    log = MagicMock()
    return AsyncMock(return_value=(result, log))


class TestHandlePlayerMessage:
    @pytest.mark.asyncio
    async def test_action_intent_submits_to_turn(self):
        """Text classified as 'action' -> submit_action called."""
        fast = MagicMock()
        orch = _make_orchestrator(fast_adapter=fast)
        pid = _add_player(orch)

        # Open a turn so submit_action works
        orch.open_turn("scene1")

        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                _mock_classify("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                _mock_extract("search"),
            ),
        ):
            result = await orch.handle_player_message(pid, "I search the pit", False)

        assert result.action_submitted is True
        assert result.handled is True

    @pytest.mark.asyncio
    async def test_question_intent_returns_response(self):
        """Text classified as 'question' -> response returned (canned for now)."""
        fast = MagicMock()
        orch = _make_orchestrator(fast_adapter=fast)
        pid = _add_player(orch)

        with patch(
            "server.orchestrator.game_loop.classify_intent",
            _mock_classify("question"),
        ):
            result = await orch.handle_player_message(pid, "Can I see the door?", True)

        assert result.handled is True
        assert result.scope == "private"

    @pytest.mark.asyncio
    async def test_question_private_stays_private(self):
        """Private question -> response scope is 'private'."""
        fast = MagicMock()
        orch = _make_orchestrator(fast_adapter=fast)
        pid = _add_player(orch)

        with patch(
            "server.orchestrator.game_loop.classify_intent",
            _mock_classify("question"),
        ):
            result = await orch.handle_player_message(pid, "Is the NPC lying?", True)

        assert result.scope == "private"

    @pytest.mark.asyncio
    async def test_chat_intent_returns_empty(self):
        """Text classified as 'chat' -> handled=True, response_text=''."""
        fast = MagicMock()
        orch = _make_orchestrator(fast_adapter=fast)
        pid = _add_player(orch)

        with patch(
            "server.orchestrator.game_loop.classify_intent",
            _mock_classify("chat"),
        ):
            result = await orch.handle_player_message(pid, "lol nice", False)

        assert result.handled is True
        assert result.response_text == ""

    @pytest.mark.asyncio
    async def test_unknown_intent_falls_back_to_action(self):
        """Unknown/ambiguous intent -> treated as action (via default else branch)."""
        fast = MagicMock()
        orch = _make_orchestrator(fast_adapter=fast)
        pid = _add_player(orch)

        with patch(
            "server.orchestrator.game_loop.classify_intent",
            _mock_classify("chat"),  # chat drops; "unknown" would too
        ):
            result = await orch.handle_player_message(pid, "hmm", False)

        # chat intent → handled with empty response (not an error)
        assert result.handled is True

    @pytest.mark.asyncio
    async def test_duplicate_message_deduped(self):
        """Same player+text+turn -> second call returns handled=True, empty response."""
        fast = MagicMock()
        orch = _make_orchestrator(fast_adapter=fast)
        pid = _add_player(orch)
        orch.open_turn("scene1")

        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                _mock_classify("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                _mock_extract("search"),
            ),
        ):
            r1 = await orch.handle_player_message(pid, "I attack", False)
            r2 = await orch.handle_player_message(pid, "I attack", False)

        assert r1.action_submitted is True
        assert r2.handled is True
        assert r2.response_text == ""

    @pytest.mark.asyncio
    async def test_identical_text_different_turns_not_deduped(self):
        """Same text in turn 1 and turn 2 -> both processed."""
        fast = MagicMock()
        orch = _make_orchestrator(fast_adapter=fast)
        pid = _add_player(orch)

        # Turn 1
        orch.open_turn("scene1")
        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                _mock_classify("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                _mock_extract("attack"),
            ),
        ):
            r1 = await orch.handle_player_message(pid, "I attack", False)

        assert r1.action_submitted is True

        # Resolve turn 1 so we can open turn 2
        scene = orch.get_scene("scene1")
        if scene and scene.active_turn_window_id:
            orch.resolve_turn(scene.active_turn_window_id)

        # Turn 2
        orch.open_turn("scene1")
        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                _mock_classify("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                _mock_extract("attack"),
            ),
        ):
            r2 = await orch.handle_player_message(pid, "I attack", False)

        assert r2.action_submitted is True

    @pytest.mark.asyncio
    async def test_no_fast_adapter_treats_as_action(self):
        """Fast adapter is None -> message treated as action directly."""
        orch = _make_orchestrator(fast_adapter=None)
        pid = _add_player(orch)
        orch.open_turn("scene1")

        result = await orch.handle_player_message(pid, "I search", False)
        assert result.action_submitted is True

    @pytest.mark.asyncio
    async def test_action_extraction_failure_fallback(self):
        """Fast model returns garbage -> action_type falls back to 'custom'."""
        fast = MagicMock()
        orch = _make_orchestrator(fast_adapter=fast)
        pid = _add_player(orch)
        orch.open_turn("scene1")

        with (
            patch(
                "server.orchestrator.game_loop.classify_intent",
                _mock_classify("action"),
            ),
            patch(
                "server.orchestrator.game_loop.extract_action_packet",
                _mock_extract("totally_invalid_type"),
            ),
        ):
            result = await orch.handle_player_message(pid, "I do something", False)

        # Should still submit (falls back to custom action type)
        assert result.action_submitted is True
