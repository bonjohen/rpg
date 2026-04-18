"""Unit tests for the fast local model routing layer.

Covers:
  - OllamaFastAdapter: success path, timeout, HTTP error, generic error
  - Router: is_fast_tier, is_main_tier_only, assert_fast_tier
  - Task functions: extraction, repair, and fallback behavior
  - ModelCallLog instrumentation fields

All tests mock adapter.generate() directly so no Ollama process is required.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.fast.adapter import GenerateResult, OllamaFastAdapter
from models.fast.instrumentation import ModelCallLog
from models.fast.router import (
    TaskType,
    assert_fast_tier,
    is_fast_tier,
    is_main_tier_only,
)
from models.fast.tasks import (
    classify_intent,
    extract_action_packet,
    generate_clarification,
    normalize_command,
    repair_schema,
    suggest_scope,
    summarize_context,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok(text: str, prompt_tokens: int = 10, output_tokens: int = 5) -> GenerateResult:
    return GenerateResult(
        text=text,
        prompt_token_count=prompt_tokens,
        output_token_count=output_tokens,
        latency_ms=42.0,
        success=True,
    )


def _fail(reason: str = "timeout") -> GenerateResult:
    return GenerateResult(
        latency_ms=10001.0,
        success=False,
        failure_reason=reason,
    )


def _adapter(result: GenerateResult) -> OllamaFastAdapter:
    adapter = OllamaFastAdapter()
    adapter.generate = AsyncMock(return_value=result)
    return adapter


# ---------------------------------------------------------------------------
# OllamaFastAdapter unit tests (HTTP-level mocking)
# ---------------------------------------------------------------------------


class TestOllamaFastAdapter:
    @pytest.mark.asyncio
    async def test_success_path(self):
        payload = {
            "response": '{"intent": "action"}',
            "prompt_eval_count": 12,
            "eval_count": 6,
        }
        # httpx response methods are synchronous — use MagicMock, not AsyncMock
        mock_response = MagicMock()
        mock_response.json.return_value = payload
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.post = AsyncMock(return_value=mock_response)
            adapter = OllamaFastAdapter()
            result = await adapter.generate("hello")

        assert result.success is True
        assert result.text == '{"intent": "action"}'
        assert result.prompt_token_count == 12
        assert result.output_token_count == 6
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_timeout_returns_failed_result(self):
        import httpx

        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
            adapter = OllamaFastAdapter()
            result = await adapter.generate("hello")

        assert result.success is False
        assert "timeout" in result.failure_reason

    @pytest.mark.asyncio
    async def test_http_error_returns_failed_result(self):
        import httpx

        mock_response = AsyncMock()
        mock_response.status_code = 503

        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "error", request=AsyncMock(), response=mock_response
                )
            )
            adapter = OllamaFastAdapter()
            result = await adapter.generate("hello")

        assert result.success is False
        assert "http_error" in result.failure_reason

    @pytest.mark.asyncio
    async def test_generic_exception_returns_failed_result(self):
        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.post = AsyncMock(side_effect=RuntimeError("boom"))
            adapter = OllamaFastAdapter()
            result = await adapter.generate("hello")

        assert result.success is False
        assert "error" in result.failure_reason


# ---------------------------------------------------------------------------
# Router unit tests
# ---------------------------------------------------------------------------


class TestRouter:
    def test_fast_tier_tasks_are_fast(self):
        for task in TaskType:
            assert is_fast_tier(task.value) is True

    def test_main_tier_only_tasks_are_not_fast(self):
        for task_type in ("scene_narration", "npc_dialogue", "ruling_proposal"):
            assert is_fast_tier(task_type) is False
            assert is_main_tier_only(task_type) is True

    def test_unknown_task_defaults_to_fast(self):
        assert is_fast_tier("some_new_task") is True

    def test_assert_fast_tier_raises_for_main_tier_task(self):
        with pytest.raises(ValueError, match="not eligible"):
            assert_fast_tier("scene_narration")

    def test_assert_fast_tier_passes_for_fast_task(self):
        assert_fast_tier(TaskType.intent_classification.value)  # must not raise


# ---------------------------------------------------------------------------
# classify_intent
# ---------------------------------------------------------------------------


class TestClassifyIntent:
    @pytest.mark.asyncio
    async def test_success_action(self):
        adapter = _adapter(_ok('{"intent": "action", "confidence": "high"}'))
        result, log = await classify_intent(adapter, "I attack the goblin")
        assert result.intent == "action"
        assert result.confidence == "high"
        assert result.fallback_used is False
        assert log.success is True
        assert log.tier == "fast"
        assert log.task_type == "intent_classification"

    @pytest.mark.asyncio
    async def test_success_question(self):
        adapter = _adapter(_ok('{"intent": "question", "confidence": "high"}'))
        result, log = await classify_intent(adapter, "What is behind the door?")
        assert result.intent == "question"

    @pytest.mark.asyncio
    async def test_invalid_json_fallback(self):
        adapter = _adapter(_ok("not json at all"))
        result, log = await classify_intent(adapter, "something")
        assert result.intent == "unknown"
        assert result.fallback_used is True
        assert log.fallback_triggered is True

    @pytest.mark.asyncio
    async def test_model_failure_fallback(self):
        adapter = _adapter(_fail("timeout"))
        result, log = await classify_intent(adapter, "something")
        assert result.intent == "unknown"
        assert result.fallback_used is True
        assert log.success is False

    @pytest.mark.asyncio
    async def test_unknown_intent_value_normalized(self):
        adapter = _adapter(_ok('{"intent": "gibberish", "confidence": "high"}'))
        result, _ = await classify_intent(adapter, "hmm")
        assert result.intent == "unknown"

    @pytest.mark.asyncio
    async def test_log_has_latency(self):
        adapter = _adapter(_ok('{"intent": "chat", "confidence": "low"}'))
        _, log = await classify_intent(adapter, "hello", trace_id="t1")
        assert log.trace_id == "t1"
        assert log.latency_ms == 42.0


# ---------------------------------------------------------------------------
# normalize_command
# ---------------------------------------------------------------------------


class TestNormalizeCommand:
    @pytest.mark.asyncio
    async def test_success(self):
        adapter = _adapter(_ok('{"normalized": "attack goblin"}'))
        result, log = await normalize_command(adapter, "/Attack the Goblin!")
        assert result.normalized == "attack goblin"
        assert result.fallback_used is False

    @pytest.mark.asyncio
    async def test_fallback_strips_slash(self):
        adapter = _adapter(_fail())
        result, log = await normalize_command(adapter, "/attack goblin")
        assert result.normalized == "attack goblin"
        assert result.fallback_used is True


# ---------------------------------------------------------------------------
# extract_action_packet
# ---------------------------------------------------------------------------


class TestExtractActionPacket:
    @pytest.mark.asyncio
    async def test_success_full_packet(self):
        payload = json.dumps(
            {
                "action_type": "attack",
                "target": "goblin",
                "item_ids": ["sword"],
                "notes": "",
            }
        )
        adapter = _adapter(_ok(payload))
        result, log = await extract_action_packet(
            adapter, "I slash the goblin with my sword"
        )
        assert result.action_type == "attack"
        assert result.target == "goblin"
        assert result.item_ids == ["sword"]
        assert result.fallback_used is False

    @pytest.mark.asyncio
    async def test_fallback_on_failure(self):
        adapter = _adapter(_fail())
        result, log = await extract_action_packet(adapter, "do something")
        assert result.action_type == "unknown"
        assert result.item_ids == []
        assert result.fallback_used is True

    @pytest.mark.asyncio
    async def test_available_action_types_accepted(self):
        payload = json.dumps(
            {
                "action_type": "defend",
                "target": "",
                "item_ids": [],
                "notes": "",
            }
        )
        adapter = _adapter(_ok(payload))
        result, _ = await extract_action_packet(
            adapter, "I defend", available_action_types=["attack", "defend"]
        )
        assert result.action_type == "defend"


# ---------------------------------------------------------------------------
# suggest_scope
# ---------------------------------------------------------------------------


class TestSuggestScope:
    @pytest.mark.asyncio
    async def test_public_scope(self):
        adapter = _adapter(
            _ok('{"suggested_scope": "public", "reasoning": "everyone sees this"}')
        )
        result, log = await suggest_scope(adapter, "I charge forward!")
        assert result.suggested_scope == "public"
        assert result.fallback_used is False

    @pytest.mark.asyncio
    async def test_private_referee_scope(self):
        adapter = _adapter(
            _ok('{"suggested_scope": "private_referee", "reasoning": "secret plan"}')
        )
        result, _ = await suggest_scope(
            adapter, "I secretly tell the referee I'm bluffing"
        )
        assert result.suggested_scope == "private_referee"

    @pytest.mark.asyncio
    async def test_invalid_scope_falls_back_to_public(self):
        adapter = _adapter(
            _ok('{"suggested_scope": "unknown_scope", "reasoning": "?"}')
        )
        result, log = await suggest_scope(adapter, "hmm")
        assert result.suggested_scope == "public"

    @pytest.mark.asyncio
    async def test_fallback_on_failure(self):
        adapter = _adapter(_fail())
        result, log = await suggest_scope(adapter, "whatever")
        assert result.suggested_scope == "public"
        assert result.fallback_used is True


# ---------------------------------------------------------------------------
# summarize_context
# ---------------------------------------------------------------------------


class TestSummarizeContext:
    @pytest.mark.asyncio
    async def test_success(self):
        adapter = _adapter(_ok('{"summary": "The party entered the dungeon."}'))
        result, log = await summarize_context(
            adapter, ["Party entered dungeon", "Found a chest"]
        )
        assert "dungeon" in result.summary
        assert result.fallback_used is False

    @pytest.mark.asyncio
    async def test_fallback_joins_last_three(self):
        adapter = _adapter(_fail())
        msgs = ["a", "b", "c", "d", "e"]
        result, log = await summarize_context(adapter, msgs)
        assert "c" in result.summary
        assert result.fallback_used is True

    @pytest.mark.asyncio
    async def test_fallback_empty_messages(self):
        adapter = _adapter(_fail())
        result, log = await summarize_context(adapter, [])
        assert result.summary == ""
        assert result.fallback_used is True


# ---------------------------------------------------------------------------
# generate_clarification
# ---------------------------------------------------------------------------


class TestGenerateClarification:
    @pytest.mark.asyncio
    async def test_success(self):
        adapter = _adapter(
            _ok('{"question": "Do you mean the north door or the south door?"}')
        )
        result, log = await generate_clarification(
            adapter, "I go through the door", "multiple doors"
        )
        assert "door" in result.question
        assert result.fallback_used is False

    @pytest.mark.asyncio
    async def test_fallback_generic_question(self):
        adapter = _adapter(_fail())
        result, log = await generate_clarification(
            adapter, "something vague", "unclear"
        )
        assert result.question == "Could you clarify what you meant?"
        assert result.fallback_used is True


# ---------------------------------------------------------------------------
# repair_schema
# ---------------------------------------------------------------------------


class TestRepairSchema:
    @pytest.mark.asyncio
    async def test_success_valid_json(self):
        repaired = '{"action_type": "attack", "target": "goblin"}'
        adapter = _adapter(_ok(repaired))
        result, log = await repair_schema(
            adapter,
            malformed_json='{"action_type": "attack", target: goblin}',
            schema_description='{"action_type": "string", "target": "string"}',
        )
        assert result.success is True
        assert result.repaired_json == repaired
        assert result.fallback_used is False

    @pytest.mark.asyncio
    async def test_repair_returns_invalid_json_still_fails(self):
        adapter = _adapter(_ok("still not valid json {{{"))
        result, log = await repair_schema(
            adapter,
            malformed_json="bad",
            schema_description="{}",
        )
        assert result.success is False
        assert result.repaired_json == ""
        assert result.fallback_used is True

    @pytest.mark.asyncio
    async def test_fallback_on_model_failure(self):
        adapter = _adapter(_fail())
        result, log = await repair_schema(
            adapter,
            malformed_json="broken",
            schema_description="{}",
        )
        assert result.success is False
        assert result.fallback_used is True

    @pytest.mark.asyncio
    async def test_log_instrumentation(self):
        repaired = '{"x": 1}'
        adapter = _adapter(_ok(repaired, prompt_tokens=20, output_tokens=8))
        _, log = await repair_schema(
            adapter,
            malformed_json="{x: 1}",
            schema_description='{"x": "int"}',
            trace_id="repair-trace",
        )
        assert log.trace_id == "repair-trace"
        assert log.tier == "fast"
        assert log.task_type == "schema_repair"
        assert log.prompt_token_count == 20
        assert log.output_token_count == 8
        assert log.success is True
        assert log.fallback_triggered is False


# ---------------------------------------------------------------------------
# ModelCallLog structure
# ---------------------------------------------------------------------------


class TestModelCallLog:
    def test_fields_present(self):
        log = ModelCallLog(
            trace_id="t1",
            tier="fast",
            task_type="intent_classification",
            prompt_token_count=10,
            output_token_count=5,
            latency_ms=42.0,
            success=True,
        )
        assert log.failure_reason == ""
        assert log.fallback_triggered is False

    def test_failure_fields(self):
        log = ModelCallLog(
            trace_id="t2",
            tier="fast",
            task_type="schema_repair",
            prompt_token_count=0,
            output_token_count=0,
            latency_ms=10001.0,
            success=False,
            failure_reason="timeout",
            fallback_triggered=True,
        )
        assert log.failure_reason == "timeout"
        assert log.fallback_triggered is True
