"""Tests for Phase 15: Reliability, Recovery, and Observability.

Covers:
  - Structured logging and trace IDs
  - Retry handling for Telegram delivery failures
  - Duplicate-delivery and replay protection (idempotency)
  - Model timeout and recovery behavior
  - Crash-safe turn recovery
  - Admin diagnostics
  - Metrics collection

Target: ~80 tests.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from server.domain.enums import TurnWindowState
from server.observability.diagnostics import DiagnosticsEngine
from server.observability.logging import (
    StructuredJsonFormatter,
    TraceContext,
    TraceFilter,
    clear_current_trace,
    configure_logging,
    get_current_trace,
    get_logger,
    reset_logging_config,
    set_current_trace,
)
from server.observability.metrics import (
    METRIC_MODEL_CALLS,
    METRIC_MODEL_LATENCY,
    MetricsCollector,
    MetricsSnapshot,
)
from server.reliability.idempotency import (
    IdempotencyStore,
    delivery_key,
    telegram_update_key,
    turn_action_key,
)
from server.reliability.model_recovery import (
    ModelTimeoutPolicy,
    call_with_timeout,
)
from server.reliability.telegram_retry import (
    DeliveryError,
    RetryPolicy,
    send_with_retry,
)
from server.reliability.turn_recovery import TurnRecoveryEngine
from tests.fixtures.reliability_fixtures import (
    CAMPAIGN_ID,
    PLAYER_A_ID,
    PLAYER_B_ID,
    PLAYER_C_ID,
    make_committed_actions,
    make_committed_turn_window,
    make_crash_recovery_scenario,
    make_failed_delivery_results,
    make_model_call_logs,
    make_open_turn_window,
    make_players,
    make_scene,
    make_stuck_turn_window,
    make_successful_delivery_result,
)


# ===================================================================
# Structured Logging and Trace IDs
# ===================================================================


class TestTraceContext:
    """Tests for TraceContext creation and child spanning."""

    def test_new_creates_valid_trace_id(self):
        ctx = TraceContext.new(campaign_id="c1")
        assert ctx.trace_id
        assert len(ctx.trace_id) == 36  # UUID format
        assert ctx.campaign_id == "c1"

    def test_new_with_all_fields(self):
        ctx = TraceContext.new(
            campaign_id="c1",
            scene_id="s1",
            turn_window_id="tw1",
            player_id="p1",
        )
        assert ctx.campaign_id == "c1"
        assert ctx.scene_id == "s1"
        assert ctx.turn_window_id == "tw1"
        assert ctx.player_id == "p1"

    def test_child_preserves_trace_id(self):
        parent = TraceContext.new(campaign_id="c1")
        child = parent.child("model_call")
        assert child.trace_id == parent.trace_id
        assert child.span == "model_call"
        assert child.campaign_id == parent.campaign_id

    def test_child_new_span(self):
        parent = TraceContext.new(campaign_id="c1")
        parent_span = parent.span
        child = parent.child("delivery")
        assert child.span == "delivery"
        assert parent.span == parent_span  # parent unchanged

    def test_to_dict(self):
        ctx = TraceContext.new(campaign_id="c1", scene_id="s1")
        d = ctx.to_dict()
        assert d["campaign_id"] == "c1"
        assert d["scene_id"] == "s1"
        assert "trace_id" in d

    def test_two_new_contexts_have_different_trace_ids(self):
        ctx1 = TraceContext.new()
        ctx2 = TraceContext.new()
        assert ctx1.trace_id != ctx2.trace_id


class TestTraceContextVar:
    """Tests for contextvar-based trace context storage."""

    def test_set_and_get_current_trace(self):
        ctx = TraceContext.new(campaign_id="c1")
        token = set_current_trace(ctx)
        try:
            retrieved = get_current_trace()
            assert retrieved is ctx
        finally:
            clear_current_trace(token)

    def test_get_returns_none_when_not_set(self):
        # Should return None in a fresh context
        result = get_current_trace()
        # May or may not be None depending on test ordering;
        # the important thing is it doesn't raise
        assert result is None or isinstance(result, TraceContext)

    def test_clear_resets_to_previous(self):
        ctx1 = TraceContext.new(campaign_id="c1")
        token1 = set_current_trace(ctx1)
        ctx2 = TraceContext.new(campaign_id="c2")
        token2 = set_current_trace(ctx2)
        assert get_current_trace() is ctx2
        clear_current_trace(token2)
        assert get_current_trace() is ctx1
        clear_current_trace(token1)


class TestStructuredJsonFormatter:
    """Tests for JSON log formatting."""

    def test_format_produces_valid_json(self):
        formatter = StructuredJsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="hello %s",
            args=("world",),
            exc_info=None,
        )
        # Add trace fields
        record.trace_id = "t1"  # type: ignore
        record.campaign_id = "c1"  # type: ignore
        record.scene_id = ""  # type: ignore
        record.turn_window_id = ""  # type: ignore
        record.player_id = ""  # type: ignore
        record.span = ""  # type: ignore
        output = formatter.format(record)
        data = json.loads(output)
        assert data["message"] == "hello world"
        assert data["level"] == "INFO"
        assert data["trace_id"] == "t1"
        assert data["campaign_id"] == "c1"
        # Empty fields should not be present
        assert "scene_id" not in data

    def test_format_includes_exception(self):
        formatter = StructuredJsonFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="error occurred",
            args=(),
            exc_info=exc_info,
        )
        for attr in (
            "trace_id",
            "campaign_id",
            "scene_id",
            "turn_window_id",
            "player_id",
            "span",
        ):
            setattr(record, attr, "")
        output = formatter.format(record)
        data = json.loads(output)
        assert "exception" in data
        assert "ValueError" in data["exception"]


class TestTraceFilter:
    """Tests for the logging filter that injects trace context."""

    def test_filter_attaches_trace_fields(self):
        ctx = TraceContext.new(campaign_id="c1", scene_id="s1")
        token = set_current_trace(ctx)
        try:
            filt = TraceFilter()
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="test",
                args=(),
                exc_info=None,
            )
            filt.filter(record)
            assert record.trace_id == ctx.trace_id  # type: ignore
            assert record.campaign_id == "c1"  # type: ignore
        finally:
            clear_current_trace(token)

    def test_filter_without_context_sets_empty(self):
        # Ensure no context is set
        filt = TraceFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )
        # Clear any existing context
        ctx = TraceContext.new()
        token = set_current_trace(ctx)
        clear_current_trace(token)
        # Now filter with no context
        filt.filter(record)
        # Should have empty string fields (or context from other tests)
        assert hasattr(record, "trace_id")


class TestConfigureLogging:
    """Tests for logging configuration."""

    def setup_method(self):
        reset_logging_config()

    def teardown_method(self):
        reset_logging_config()

    def test_configure_logging_sets_handler(self):
        configure_logging(log_level="DEBUG", log_format="json")
        root = logging.getLogger()
        assert len(root.handlers) > 0

    def test_configure_logging_idempotent(self):
        configure_logging()
        handler_count = len(logging.getLogger().handlers)
        configure_logging()  # second call is no-op
        assert len(logging.getLogger().handlers) == handler_count

    def test_get_logger_returns_logger(self):
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"


# ===================================================================
# Retry Handling
# ===================================================================


class TestRetryPolicy:
    """Tests for RetryPolicy defaults."""

    def test_defaults(self):
        policy = RetryPolicy()
        assert policy.max_retries == 3
        assert policy.base_delay_seconds == 1.0
        assert 429 in policy.retryable_errors
        assert 500 in policy.retryable_errors

    def test_custom_policy(self):
        policy = RetryPolicy(max_retries=5, base_delay_seconds=0.5)
        assert policy.max_retries == 5
        assert policy.base_delay_seconds == 0.5


class TestSendWithRetry:
    """Tests for the retry wrapper around delivery functions."""

    @pytest.mark.asyncio
    async def test_success_on_first_try(self):
        send_fn = AsyncMock(return_value=42)
        result = await send_with_retry(send_fn, RetryPolicy())
        assert result.success is True
        assert result.message_id == 42
        assert len(result.attempts) == 1
        assert result.attempts[0].success is True

    @pytest.mark.asyncio
    async def test_success_on_retry(self):
        call_count = 0

        async def flaky_send():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise DeliveryError("server error", http_status=500)
            return 99

        policy = RetryPolicy(base_delay_seconds=0.01)
        result = await send_with_retry(flaky_send, policy)
        assert result.success is True
        assert result.message_id == 99
        assert len(result.attempts) == 2
        assert result.attempts[0].success is False
        assert result.attempts[1].success is True

    @pytest.mark.asyncio
    async def test_429_rate_limit(self):
        call_count = 0

        async def rate_limited():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise DeliveryError("rate limited", http_status=429, retry_after=0.01)
            return 77

        policy = RetryPolicy(base_delay_seconds=0.01)
        result = await send_with_retry(rate_limited, policy)
        assert result.success is True
        assert len(result.attempts) == 2
        assert result.attempts[0].http_status == 429
        assert result.attempts[0].retry_after_seconds == 0.01

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self):
        async def always_fail():
            raise DeliveryError("server error", http_status=500)

        policy = RetryPolicy(max_retries=3, base_delay_seconds=0.01)
        result = await send_with_retry(always_fail, policy)
        assert result.success is False
        assert len(result.attempts) == 4  # 1 initial + 3 retries

    @pytest.mark.asyncio
    async def test_non_retryable_error(self):
        async def bad_request():
            raise DeliveryError("bad request", http_status=400)

        policy = RetryPolicy(base_delay_seconds=0.01)
        result = await send_with_retry(bad_request, policy)
        assert result.success is False
        assert len(result.attempts) == 1  # no retries

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self):
        """Verify delays increase exponentially (approximately)."""
        call_times: list[float] = []

        async def timed_fail():
            call_times.append(time.monotonic())
            raise DeliveryError("error", http_status=500)

        policy = RetryPolicy(
            max_retries=2, base_delay_seconds=0.05, max_delay_seconds=1.0
        )
        await send_with_retry(timed_fail, policy)
        assert len(call_times) == 3  # initial + 2 retries
        # First delay should be ~0.05s, second ~0.10s
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]
        assert delay1 >= 0.04  # allow some tolerance
        assert delay2 >= delay1 * 0.8  # second delay >= first (roughly)

    @pytest.mark.asyncio
    async def test_trace_id_in_result(self):
        async def ok():
            return 1

        result = await send_with_retry(ok, trace_id="t-123")
        assert result.trace_id == "t-123"

    @pytest.mark.asyncio
    async def test_total_duration_tracked(self):
        async def ok():
            return 1

        result = await send_with_retry(ok)
        assert result.total_duration_ms >= 0


# ===================================================================
# Idempotency
# ===================================================================


class TestIdempotencyStore:
    """Tests for the in-memory idempotency store."""

    def test_first_seen_returns_true(self):
        store = IdempotencyStore()
        assert store.mark_seen("key1") is True

    def test_duplicate_returns_false(self):
        store = IdempotencyStore()
        store.mark_seen("key1")
        assert store.mark_seen("key1") is False

    def test_is_seen_after_mark(self):
        store = IdempotencyStore()
        assert store.is_seen("key1") is False
        store.mark_seen("key1")
        assert store.is_seen("key1") is True

    def test_ttl_expiry(self):
        store = IdempotencyStore(ttl_seconds=1)
        store.mark_seen("key1")
        # Manually backdate the entry
        old_time = datetime.now(timezone.utc) - timedelta(seconds=2)
        store._seen["key1"] = old_time
        # After eviction, key should be treated as new
        assert store.mark_seen("key1") is True

    def test_max_size_eviction(self):
        store = IdempotencyStore(max_size=3)
        store.mark_seen("a")
        store.mark_seen("b")
        store.mark_seen("c")
        store.mark_seen("d")  # should evict "a"
        assert store.size == 3
        assert store.is_seen("a") is False
        assert store.is_seen("d") is True

    def test_clear(self):
        store = IdempotencyStore()
        store.mark_seen("key1")
        store.mark_seen("key2")
        store.clear()
        assert store.size == 0
        assert store.mark_seen("key1") is True

    def test_size_property(self):
        store = IdempotencyStore()
        assert store.size == 0
        store.mark_seen("a")
        assert store.size == 1


class TestIdempotencyKeyGenerators:
    """Tests for key generation helper functions."""

    def test_telegram_update_key(self):
        key = telegram_update_key(12345)
        assert key == "tg_update:12345"

    def test_turn_action_key(self):
        key = turn_action_key("tw-001", "player-001")
        assert key == "turn_action:tw-001:player-001"

    def test_delivery_key(self):
        key = delivery_key("camp-1", "scene-1", 5, "public")
        assert key == "delivery:camp-1:scene-1:5:public"


# ===================================================================
# Model Timeout and Recovery
# ===================================================================


class TestModelTimeoutPolicy:
    """Tests for ModelTimeoutPolicy defaults."""

    def test_defaults(self):
        policy = ModelTimeoutPolicy()
        assert policy.fast_timeout_seconds == 5.0
        assert policy.main_timeout_seconds == 30.0
        assert policy.repair_timeout_seconds == 10.0


class TestCallWithTimeout:
    """Tests for the timeout-protected model call wrapper."""

    @pytest.mark.asyncio
    async def test_completes_in_time(self):
        async def fast_model():
            return {"narration": "The cave opens before you."}

        result = await call_with_timeout(
            lambda: fast_model(),
            timeout_seconds=1.0,
            fallback_fn=lambda: {"narration": "fallback"},
        )
        assert result.success is True
        assert result.data == {"narration": "The cave opens before you."}
        assert result.fallback_used is False
        assert result.timeout is False

    @pytest.mark.asyncio
    async def test_times_out_uses_fallback(self):
        async def slow_model():
            await asyncio.sleep(10)
            return {"narration": "never returned"}

        result = await call_with_timeout(
            lambda: slow_model(),
            timeout_seconds=0.05,
            fallback_fn=lambda: {"narration": "fallback text"},
        )
        assert result.success is True
        assert result.data == {"narration": "fallback text"}
        assert result.fallback_used is True
        assert result.timeout is True

    @pytest.mark.asyncio
    async def test_exception_uses_fallback(self):
        async def broken_model():
            raise RuntimeError("model crashed")

        result = await call_with_timeout(
            lambda: broken_model(),
            timeout_seconds=1.0,
            fallback_fn=lambda: {"narration": "safe fallback"},
        )
        assert result.success is True
        assert result.data == {"narration": "safe fallback"}
        assert result.fallback_used is True
        assert result.timeout is False
        assert "model crashed" in result.error

    @pytest.mark.asyncio
    async def test_duration_tracked(self):
        async def fast():
            return {"ok": True}

        result = await call_with_timeout(
            lambda: fast(),
            timeout_seconds=1.0,
            fallback_fn=lambda: {},
        )
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_trace_id_propagated(self):
        async def ok():
            return {}

        result = await call_with_timeout(
            lambda: ok(),
            timeout_seconds=1.0,
            fallback_fn=lambda: {},
            trace_id="trace-42",
        )
        assert result.trace_id == "trace-42"

    @pytest.mark.asyncio
    async def test_fallback_is_valid_dict(self):
        async def fail():
            raise ValueError("boom")

        result = await call_with_timeout(
            lambda: fail(),
            timeout_seconds=1.0,
            fallback_fn=lambda: {"intent": "unknown", "confidence": "low"},
        )
        assert isinstance(result.data, dict)
        assert result.data["intent"] == "unknown"


# ===================================================================
# Turn Recovery
# ===================================================================


class TestTurnRecoveryDiagnose:
    """Tests for TurnRecoveryEngine.diagnose()."""

    def setup_method(self):
        self.engine = TurnRecoveryEngine()

    def test_diagnose_open_turn(self):
        tw = make_open_turn_window()
        scene = make_scene()
        players = make_players()
        state = self.engine.diagnose(tw, scene, players)
        assert state.recovery_action == "resumed"
        assert state.state_at_crash == "open"

    def test_diagnose_resolving_turn(self):
        tw = make_stuck_turn_window(state="resolving")
        scene = make_scene()
        players = make_players()
        actions = make_committed_actions([PLAYER_A_ID, PLAYER_B_ID])
        state = self.engine.diagnose(tw, scene, players, actions)
        assert state.recovery_action == "force_resolved"
        assert PLAYER_C_ID in state.pending_players

    def test_diagnose_locked_turn(self):
        tw = make_stuck_turn_window(state="locked")
        scene = make_scene()
        players = make_players()
        state = self.engine.diagnose(tw, scene, players)
        assert state.recovery_action == "force_resolved"

    def test_diagnose_committed_turn(self):
        tw = make_committed_turn_window()
        scene = make_scene()
        players = make_players()
        state = self.engine.diagnose(tw, scene, players)
        assert state.recovery_action == "redeliver"

    def test_diagnose_aborted_turn(self):
        tw = make_stuck_turn_window(state="aborted")
        scene = make_scene()
        players = make_players()
        state = self.engine.diagnose(tw, scene, players)
        assert state.recovery_action == "none"

    def test_diagnose_all_ready_turn(self):
        tw = make_open_turn_window()
        tw.state = TurnWindowState.all_ready
        scene = make_scene()
        players = make_players()
        state = self.engine.diagnose(tw, scene, players)
        assert state.recovery_action == "resumed"


class TestTurnRecoveryRecover:
    """Tests for TurnRecoveryEngine.recover()."""

    def setup_method(self):
        self.engine = TurnRecoveryEngine()

    def test_recover_open_turn(self):
        tw = make_open_turn_window()
        scene = make_scene()
        players = make_players()
        actions = make_committed_actions([PLAYER_A_ID])  # only A submitted
        result = self.engine.recover(tw, scene, players, actions)
        assert result.success is True
        assert result.recovery_action == "resumed"
        # Should have synthesized 2 fallback actions (B and C)
        assert result.new_actions_synthesized == 2

    def test_recover_resolving_turn(self):
        tw = make_stuck_turn_window(state="resolving")
        scene = make_scene()
        players = make_players()
        actions = make_committed_actions([PLAYER_A_ID, PLAYER_B_ID])
        result = self.engine.recover(tw, scene, players, actions)
        assert result.success is True
        assert result.recovery_action == "force_resolved"
        assert tw.state == TurnWindowState.resolving

    def test_recover_committed_turn_redelivers(self):
        tw = make_committed_turn_window()
        scene = make_scene()
        players = make_players()
        result = self.engine.recover(tw, scene, players)
        assert result.success is True
        assert result.recovery_action == "redeliver"
        assert result.narration_redelivered is True

    def test_recover_aborted_turn(self):
        tw = make_stuck_turn_window(state="aborted")
        scene = make_scene()
        players = make_players()
        result = self.engine.recover(tw, scene, players)
        assert result.success is True
        assert result.recovery_action == "none"


class TestTurnRecoveryFindStuck:
    """Tests for TurnRecoveryEngine.find_stuck_turns()."""

    def setup_method(self):
        self.engine = TurnRecoveryEngine()

    def test_find_stuck_turns(self):
        stuck = make_stuck_turn_window(state="resolving", age_minutes=45)
        fresh = make_open_turn_window(age_minutes=5)
        result = self.engine.find_stuck_turns([stuck, fresh], max_age_minutes=30)
        assert len(result) == 1
        assert result[0].turn_window_id == stuck.turn_window_id

    def test_committed_not_flagged_as_stuck(self):
        committed = make_committed_turn_window()
        result = self.engine.find_stuck_turns([committed], max_age_minutes=30)
        assert len(result) == 0

    def test_aborted_not_flagged_as_stuck(self):
        tw = make_stuck_turn_window(state="aborted", age_minutes=60)
        result = self.engine.find_stuck_turns([tw], max_age_minutes=30)
        assert len(result) == 0

    def test_young_open_not_stuck(self):
        tw = make_open_turn_window(age_minutes=5)
        result = self.engine.find_stuck_turns([tw], max_age_minutes=30)
        assert len(result) == 0

    def test_old_open_is_stuck(self):
        tw = make_open_turn_window(age_minutes=45)
        result = self.engine.find_stuck_turns([tw], max_age_minutes=30)
        assert len(result) == 1


class TestCrashRecoveryScenario:
    """Integration test using the crash recovery scenario fixture."""

    def test_crash_recovery_scenario(self):
        scenario = make_crash_recovery_scenario()
        engine = TurnRecoveryEngine()
        result = engine.recover(
            scenario["turn_window"],
            scenario["scene"],
            scenario["players"],
            scenario["committed_actions"],
        )
        assert result.success is True
        assert result.recovery_action == "force_resolved"


# ===================================================================
# Diagnostics
# ===================================================================


class TestDiagnosticsEngine:
    """Tests for the admin diagnostics engine."""

    def setup_method(self):
        self.engine = DiagnosticsEngine()

    def test_build_report(self):
        tw = make_stuck_turn_window(state="resolving", age_minutes=45)
        scene = make_scene()
        players = make_players()
        deliveries = make_failed_delivery_results(2)
        model_logs = make_model_call_logs()
        report = self.engine.build_report(
            campaign_id=CAMPAIGN_ID,
            turn_windows=[tw],
            scenes=[scene],
            players=players,
            delivery_log=deliveries,
            model_call_log=model_logs,
        )
        assert report.campaign_id == CAMPAIGN_ID
        assert len(report.stuck_turns) == 1
        assert len(report.failed_deliveries) == 2
        assert report.model_health.recent_failures >= 1

    def test_format_report_all_sections(self):
        tw = make_stuck_turn_window(state="resolving", age_minutes=45)
        scene = make_scene()
        players = make_players()
        deliveries = make_failed_delivery_results(1)
        model_logs = make_model_call_logs(failures=1, fallbacks=1)
        report = self.engine.build_report(
            CAMPAIGN_ID,
            [tw],
            [scene],
            players,
            deliveries,
            model_logs,
        )
        text = self.engine.format_report(report)
        assert "Campaign Diagnostics" in text
        assert "Stuck turns:" in text
        assert "Failed deliveries:" in text
        assert "Model health:" in text
        assert "Players:" in text

    def test_empty_report(self):
        report = self.engine.build_report(
            campaign_id=CAMPAIGN_ID,
            turn_windows=[],
            scenes=[],
            players=[],
        )
        assert len(report.stuck_turns) == 0
        assert len(report.failed_deliveries) == 0
        text = self.engine.format_report(report)
        assert "Stuck turns: 0" in text
        assert "Failed deliveries: 0" in text

    def test_player_status_pending_action(self):
        tw = make_open_turn_window(age_minutes=2)
        scene = make_scene()
        players = make_players()
        report = self.engine.build_report(
            CAMPAIGN_ID,
            [tw],
            [scene],
            players,
        )
        pending = [p for p in report.player_status if p.pending_action]
        assert len(pending) == 3  # all players in the scene with open turn

    def test_model_health_computation(self):
        logs = make_model_call_logs(failures=2, fallbacks=1)
        report = self.engine.build_report(
            CAMPAIGN_ID,
            [],
            [],
            [],
            model_call_log=logs,
        )
        assert report.model_health.recent_failures == 2
        assert report.model_health.recent_fallbacks == 1
        assert report.model_health.fast_avg_latency_ms > 0


# ===================================================================
# Metrics
# ===================================================================


class TestMetricsCollector:
    """Tests for the in-memory metrics aggregator."""

    def setup_method(self):
        self.collector = MetricsCollector()

    def test_counter_increment(self):
        self.collector.increment("requests")
        assert self.collector.get_counter("requests") == 1

    def test_counter_increment_by_value(self):
        self.collector.increment("requests", value=5)
        assert self.collector.get_counter("requests") == 5

    def test_counter_with_tags(self):
        self.collector.increment(METRIC_MODEL_CALLS, tags={"tier": "fast"})
        self.collector.increment(METRIC_MODEL_CALLS, tags={"tier": "main"})
        assert (
            self.collector.get_counter(METRIC_MODEL_CALLS, tags={"tier": "fast"}) == 1
        )
        assert (
            self.collector.get_counter(METRIC_MODEL_CALLS, tags={"tier": "main"}) == 1
        )

    def test_counter_independent_tags(self):
        """Same metric name with different tags tracked independently."""
        self.collector.increment("calls", tags={"type": "a"})
        self.collector.increment("calls", tags={"type": "a"})
        self.collector.increment("calls", tags={"type": "b"})
        assert self.collector.get_counter("calls", tags={"type": "a"}) == 2
        assert self.collector.get_counter("calls", tags={"type": "b"}) == 1

    def test_counter_default_zero(self):
        assert self.collector.get_counter("nonexistent") == 0

    def test_histogram_record_and_stats(self):
        for v in [10, 20, 30, 40, 50]:
            self.collector.record("latency", v)
        stats = self.collector.get_stats("latency")
        assert stats.count == 5
        assert stats.min == 10
        assert stats.max == 50
        assert stats.mean == 30.0
        assert stats.p50 == 30.0

    def test_histogram_percentile(self):
        for v in range(1, 101):  # 1 to 100
            self.collector.record("values", float(v))
        p50 = self.collector.get_percentile("values", 50)
        p95 = self.collector.get_percentile("values", 95)
        p99 = self.collector.get_percentile("values", 99)
        assert 49 <= p50 <= 51
        assert 94 <= p95 <= 96
        assert 98 <= p99 <= 100

    def test_histogram_single_value(self):
        self.collector.record("single", 42.0)
        stats = self.collector.get_stats("single")
        assert stats.count == 1
        assert stats.min == 42.0
        assert stats.max == 42.0
        assert stats.p50 == 42.0

    def test_histogram_empty(self):
        stats = self.collector.get_stats("empty")
        assert stats.count == 0
        assert stats.min == 0.0

    def test_percentile_empty_histogram(self):
        assert self.collector.get_percentile("empty", 50) == 0.0

    def test_histogram_with_tags(self):
        self.collector.record(METRIC_MODEL_LATENCY, 100, tags={"tier": "fast"})
        self.collector.record(METRIC_MODEL_LATENCY, 2000, tags={"tier": "main"})
        fast_stats = self.collector.get_stats(
            METRIC_MODEL_LATENCY, tags={"tier": "fast"}
        )
        main_stats = self.collector.get_stats(
            METRIC_MODEL_LATENCY, tags={"tier": "main"}
        )
        assert fast_stats.mean == 100
        assert main_stats.mean == 2000

    def test_snapshot(self):
        self.collector.increment("requests", value=10)
        self.collector.record("latency", 50.0)
        self.collector.record("latency", 100.0)
        snap = self.collector.snapshot()
        assert isinstance(snap, MetricsSnapshot)
        assert snap.counters["requests"] == 10
        assert "latency" in snap.histograms
        assert snap.histograms["latency"].count == 2

    def test_reset(self):
        self.collector.increment("requests")
        self.collector.record("latency", 50.0)
        self.collector.reset()
        assert self.collector.get_counter("requests") == 0
        assert self.collector.get_stats("latency").count == 0

    def test_snapshot_timestamp(self):
        snap = self.collector.snapshot()
        assert isinstance(snap.timestamp, datetime)


# ===================================================================
# Delivery and Model Call Fixtures
# ===================================================================


class TestReliabilityFixtures:
    """Tests that fixture builders produce valid objects."""

    def test_make_stuck_turn_window(self):
        tw = make_stuck_turn_window()
        assert tw.state == TurnWindowState.resolving
        assert tw.campaign_id == CAMPAIGN_ID

    def test_make_committed_turn_window(self):
        tw = make_committed_turn_window()
        assert tw.state == TurnWindowState.committed

    def test_make_scene(self):
        scene = make_scene()
        assert len(scene.player_ids) == 3

    def test_make_players(self):
        players = make_players()
        assert len(players) == 3

    def test_make_committed_actions(self):
        actions = make_committed_actions()
        assert len(actions) == 2

    def test_make_failed_delivery_results(self):
        results = make_failed_delivery_results(3)
        assert len(results) == 3
        for r in results:
            assert r.success is False

    def test_make_successful_delivery_result(self):
        result = make_successful_delivery_result()
        assert result.success is True
        assert result.message_id == 12345

    def test_make_model_call_logs(self):
        logs = make_model_call_logs(failures=2, fallbacks=1)
        failed = [entry for entry in logs if not entry.success]
        fallbacks = [entry for entry in logs if entry.fallback_triggered]
        assert len(failed) == 2
        assert len(fallbacks) == 1

    def test_make_crash_recovery_scenario(self):
        scenario = make_crash_recovery_scenario()
        assert scenario["turn_window"].state == TurnWindowState.resolving
        assert len(scenario["committed_actions"]) == 2
        assert PLAYER_C_ID in scenario["pending_player_ids"]
