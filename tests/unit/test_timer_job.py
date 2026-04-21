"""Unit tests for timer job integration (Phase 6).

Tests per chat_loop_test_plan §3.8.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.timer_jobs import cancel_turn_timer, turn_timer_callback


def _make_context(
    orchestrator=None,
    config=None,
    registry=None,
    turn_window_id: str = "tw-1",
) -> MagicMock:
    """Build a fake CallbackContext for job callbacks."""
    from bot.config import BotConfig
    from bot.mapping import BotRegistry

    ctx = MagicMock()
    ctx.bot = AsyncMock()
    ctx.application = MagicMock()
    ctx.application.bot_data = {
        "orchestrator": orchestrator,
        "config": config or BotConfig(group_chat_id=-1001234567890),
        "registry": registry or BotRegistry(),
    }

    # Job with data
    ctx.job = MagicMock()
    ctx.job.data = {"turn_window_id": turn_window_id}

    return ctx


def _make_orchestrator(
    tw_state: str = "open",
    turn_window_id: str = "tw-1",
    scene_id: str = "s-1",
    turn_number: int = 1,
    resolve_returns_entry: bool = True,
) -> MagicMock:
    from server.domain.enums import TurnWindowState

    orch = MagicMock()

    tw = MagicMock()
    tw.turn_window_id = turn_window_id
    tw.scene_id = scene_id
    tw.turn_number = turn_number
    tw.state = TurnWindowState(tw_state)
    orch.get_turn_window.return_value = tw

    scene = MagicMock()
    scene.scene_id = scene_id
    scene.name = "Cave"
    scene.description = "A cave."
    orch.get_scene.return_value = scene

    if resolve_returns_entry:
        log_entry = MagicMock()
        log_entry.turn_number = turn_number
        log_entry.turn_window_id = turn_window_id
        log_entry.narration = "Basic narration."
        orch.resolve_turn.return_value = log_entry
    else:
        orch.resolve_turn.return_value = None

    orch.get_committed_actions_for_window.return_value = []
    orch.main_adapter = None
    orch.turn_control_message_ids = {}
    orch.turn_timer_jobs = {}

    return orch


class TestTurnTimerScheduled:
    def test_turn_open_schedules_timer_job(self):
        """schedule_turn_timer calls job_queue.run_once with correct data."""
        from bot.timer_jobs import schedule_turn_timer

        ctx = _make_context()
        ctx.job_queue = MagicMock()
        mock_job = MagicMock()
        ctx.job_queue.run_once.return_value = mock_job

        job = schedule_turn_timer(ctx, "tw-1", 90)

        ctx.job_queue.run_once.assert_called_once()
        call_kwargs = ctx.job_queue.run_once.call_args
        assert call_kwargs.kwargs["when"] == 90
        assert call_kwargs.kwargs["data"]["turn_window_id"] == "tw-1"
        assert job is mock_job


class TestTimerResolvesExpiredTurn:
    @pytest.mark.asyncio
    async def test_timer_job_resolves_expired_turn(self):
        """Job fires -> turn resolved, narration generated, results delivered."""
        orch = _make_orchestrator()
        ctx = _make_context(orchestrator=orch)

        with (
            patch(
                "bot.delivery.generate_narration", new_callable=AsyncMock
            ) as mock_narrate,
            patch(
                "bot.delivery.deliver_turn_results", new_callable=AsyncMock
            ) as mock_deliver,
        ):
            mock_narrate.return_value = "Rich narration."
            await turn_timer_callback(ctx)

        orch.resolve_turn.assert_called_once_with("tw-1")
        mock_narrate.assert_called_once()
        mock_deliver.assert_called_once()


class TestTimerSkipsAlreadyResolved:
    @pytest.mark.asyncio
    async def test_timer_job_skips_already_resolved_turn(self):
        """Turn resolved before timer -> job fires -> no-op."""
        orch = _make_orchestrator(tw_state="committed")
        ctx = _make_context(orchestrator=orch)

        await turn_timer_callback(ctx)

        orch.resolve_turn.assert_not_called()


class TestTimerGeneratesFallbackActions:
    @pytest.mark.asyncio
    async def test_timer_job_passes_resolved_entry_to_delivery(self):
        """Timer fires -> resolved log entry passed to deliver_turn_results."""
        orch = _make_orchestrator()
        ctx = _make_context(orchestrator=orch)

        with (
            patch(
                "bot.delivery.generate_narration", new_callable=AsyncMock
            ) as mock_narrate,
            patch(
                "bot.delivery.deliver_turn_results", new_callable=AsyncMock
            ) as mock_deliver,
        ):
            mock_narrate.return_value = "Narration."
            await turn_timer_callback(ctx)

        # Verify the resolved log entry was forwarded to delivery
        mock_deliver.assert_called_once()
        delivered_entry = mock_deliver.call_args.kwargs["turn_log_entry"]
        assert delivered_entry.turn_window_id == "tw-1"


class TestTimerHasBotContext:
    @pytest.mark.asyncio
    async def test_timer_job_has_bot_context(self):
        """Job callback receives context.bot and context.application.bot_data."""
        orch = _make_orchestrator()
        ctx = _make_context(orchestrator=orch)

        with (
            patch(
                "bot.delivery.generate_narration", new_callable=AsyncMock
            ) as mock_narrate,
            patch(
                "bot.delivery.deliver_turn_results", new_callable=AsyncMock
            ) as mock_deliver,
        ):
            mock_narrate.return_value = "Narration."
            await turn_timer_callback(ctx)

        # Verify bot was passed to deliver_turn_results
        call_kwargs = mock_deliver.call_args
        assert call_kwargs.kwargs.get("bot") is ctx.bot


class TestCancelTurnTimer:
    def test_cancel_turn_timer_removes_job(self):
        """cancel_turn_timer calls schedule_removal on the stored job."""
        orch = MagicMock()
        job = MagicMock()
        orch.turn_timer_jobs = {"tw-1": job}

        cancel_turn_timer(orch, "tw-1")

        job.schedule_removal.assert_called_once()
        assert "tw-1" not in orch.turn_timer_jobs

    def test_cancel_turn_timer_no_op_if_missing(self):
        """cancel_turn_timer does nothing if no job for that turn."""
        orch = MagicMock()
        orch.turn_timer_jobs = {}

        # Should not raise
        cancel_turn_timer(orch, "tw-1")
