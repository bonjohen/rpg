"""Phase 7 bug-fix tests: model recovery, async fallback, empty choices."""

from __future__ import annotations

import asyncio

import pytest

from server.reliability.model_recovery import (
    _invoke_fallback,
    call_with_timeout,
)


# ---------------------------------------------------------------------------
# BUG-015: _invoke_fallback returns None + logs warning for async fallbacks
# ---------------------------------------------------------------------------


class TestInvokeFallback:
    def test_sync_fallback_returns_dict(self):
        result = _invoke_fallback(lambda: {"key": "value"})
        assert result == {"key": "value"}

    def test_async_fallback_returns_none(self):
        async def async_fallback():
            return {"key": "value"}

        result = _invoke_fallback(async_fallback)
        assert result is None

    def test_async_fallback_logs_warning(self, caplog):
        import logging

        async def async_fallback():
            return {"key": "value"}

        with caplog.at_level(
            logging.WARNING, logger="server.reliability.model_recovery"
        ):
            _invoke_fallback(async_fallback)

        assert any(
            "async" in r.message.lower() or "discarded" in r.message.lower()
            for r in caplog.records
        )


class TestCallWithTimeoutFallback:
    @pytest.mark.asyncio
    async def test_timeout_with_sync_fallback_returns_success(self):
        async def slow_call():
            await asyncio.sleep(10)
            return {}

        result = await call_with_timeout(
            lambda: slow_call(),
            timeout_seconds=0.01,
            fallback_fn=lambda: {"fallback": True},
            trace_id="test",
        )
        assert result.success is True
        assert result.fallback_used is True
        assert result.data == {"fallback": True}

    @pytest.mark.asyncio
    async def test_timeout_with_async_fallback_returns_failure(self):
        async def slow_call():
            await asyncio.sleep(10)
            return {}

        async def async_fallback():
            return {"fallback": True}

        result = await call_with_timeout(
            lambda: slow_call(),
            timeout_seconds=0.01,
            fallback_fn=async_fallback,
            trace_id="test",
        )
        assert result.success is False
        assert result.fallback_used is True
        assert result.data is None

    @pytest.mark.asyncio
    async def test_exception_with_async_fallback_returns_failure(self):
        async def failing_call():
            raise RuntimeError("model error")

        async def async_fallback():
            return {"fallback": True}

        result = await call_with_timeout(
            lambda: failing_call(),
            timeout_seconds=5.0,
            fallback_fn=async_fallback,
            trace_id="test",
        )
        assert result.success is False
        assert result.fallback_used is True


# ---------------------------------------------------------------------------
# BUG-023: Empty choices returns success=False
# ---------------------------------------------------------------------------


class TestEmptyChoices:
    @pytest.mark.asyncio
    async def test_empty_choices_returns_failure(self, respx_mock):
        from models.main.adapter import OpenAIMainAdapter

        respx_mock.post("https://api.openai.com/v1/chat/completions").respond(
            200,
            json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "choices": [],
                "usage": {"prompt_tokens": 10, "completion_tokens": 0},
            },
        )

        adapter = OpenAIMainAdapter(api_key="test-key")
        result = await adapter.generate("test prompt")

        assert result.success is False
        assert "empty choices" in result.failure_reason

    @pytest.mark.asyncio
    async def test_valid_choices_returns_success(self, respx_mock):
        from models.main.adapter import OpenAIMainAdapter

        respx_mock.post("https://api.openai.com/v1/chat/completions").respond(
            200,
            json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "choices": [{"message": {"content": "Hello"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

        adapter = OpenAIMainAdapter(api_key="test-key")
        result = await adapter.generate("test prompt")

        assert result.success is True
        assert result.text == "Hello"


# ---------------------------------------------------------------------------
# BUG-014: turn_recovery already uses passed-in data (verify)
# ---------------------------------------------------------------------------


class TestTurnRecoveryPure:
    def test_recovery_engine_has_no_db_imports(self):
        """Verify turn_recovery doesn't import from server.storage."""
        import inspect

        import server.reliability.turn_recovery as mod

        source = inspect.getsource(mod)
        assert "from server.storage" not in source
        assert "import server.storage" not in source
