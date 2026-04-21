"""Shared mock helpers for model adapters (fast + main tier).

Consolidates the _mock_classify / _mock_extract pattern duplicated across
multiple test files into reusable builders.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from models.fast.tasks import ActionPacketResult, IntentClassificationResult


def mock_classify_intent(
    intent: str = "action",
    confidence: str = "high",
):
    """Return a mock classify_intent coroutine that returns a canned result.

    Can be used with ``patch("server.orchestrator.game_loop.classify_intent", ...)``.
    """
    result = IntentClassificationResult(
        intent=intent, confidence=confidence, raw=intent
    )
    log = MagicMock()

    async def _classify(adapter, text, **kwargs):
        return result, log

    return _classify


def mock_extract_action(
    action_type: str = "custom",
    target: str = "",
    item_ids: list[str] | None = None,
):
    """Return a mock extract_action_packet coroutine that returns a canned result.

    Can be used with ``patch("server.orchestrator.game_loop.extract_action_packet", ...)``.
    """
    result = ActionPacketResult(
        action_type=action_type,
        target=target,
        item_ids=item_ids or [],
        notes="",
        raw=action_type,
    )
    log = MagicMock()

    async def _extract(adapter, text, available_types, **kwargs):
        return result, log

    return _extract
