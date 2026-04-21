"""PTB job_queue integration for turn timer expiry.

When a turn opens, schedule a job via job_queue.run_once().
When the job fires, resolve the turn, generate narration, and deliver results.
"""

from __future__ import annotations

import logging

from telegram.ext import CallbackContext

logger = logging.getLogger(__name__)


async def turn_timer_callback(context: CallbackContext) -> None:
    """Job callback: resolve an expired turn and deliver results.

    The job's ``data`` dict must contain ``turn_window_id``.
    Skips silently if the turn was already resolved (e.g. via all-ready).
    """
    job = context.job
    if job is None or job.data is None:
        return

    turn_window_id = job.data.get("turn_window_id")
    if not turn_window_id:
        logger.warning("turn_timer_callback fired with no turn_window_id")
        return

    orchestrator = context.application.bot_data.get("orchestrator")
    if orchestrator is None:
        logger.warning("turn_timer_callback: no orchestrator in bot_data")
        return

    # Check if turn is still open
    tw = orchestrator.get_turn_window(turn_window_id)
    if tw is None:
        logger.debug("turn_timer_callback: turn %s not found", turn_window_id)
        return

    from server.domain.enums import TurnWindowState

    if tw.state not in (TurnWindowState.open, TurnWindowState.all_ready):
        logger.debug(
            "turn_timer_callback: turn %s already %s, skipping",
            turn_window_id,
            tw.state.value,
        )
        return

    # Resolve the turn
    log_entry = orchestrator.resolve_turn(turn_window_id)
    if log_entry is None:
        logger.warning(
            "turn_timer_callback: resolve_turn returned None for %s", turn_window_id
        )
        return

    logger.info(
        "Timer expired — resolved turn %s (turn %d)",
        turn_window_id,
        log_entry.turn_number,
    )

    # Generate narration and deliver results
    config = context.application.bot_data.get("config")
    if config is None:
        return

    from bot.delivery import deliver_turn_results, generate_narration
    from models.main.context import ActionContext

    scene = orchestrator.get_scene(tw.scene_id)
    if scene is None:
        return

    # Build action contexts for narration
    actions = orchestrator.get_committed_actions_for_window(turn_window_id)
    action_contexts = []
    for a in actions:
        char = orchestrator.get_player_character(a.player_id)
        action_contexts.append(
            ActionContext(
                player_id=a.player_id,
                character_name=char.name if char else "Unknown",
                action_type=a.declared_action_type.value,
                notes=a.public_text,
            )
        )

    narration_text = await generate_narration(
        orchestrator.main_adapter, log_entry, scene, action_contexts
    )

    registry = context.application.bot_data.get("registry")
    control_msg_id = orchestrator.turn_control_message_ids.get(turn_window_id)

    await deliver_turn_results(
        turn_log_entry=log_entry,
        scene=scene,
        narration_text=narration_text,
        bot=context.bot,
        config=config,
        registry=registry,
        control_message_id=control_msg_id,
    )

    # Clean up references
    orchestrator.turn_timer_jobs.pop(turn_window_id, None)
    orchestrator.turn_control_message_ids.pop(turn_window_id, None)


def schedule_turn_timer(
    context: CallbackContext, turn_window_id: str, duration_seconds: int
):
    """Schedule a timer job for a turn window. Returns the Job."""
    job = context.job_queue.run_once(
        turn_timer_callback,
        when=duration_seconds,
        data={"turn_window_id": turn_window_id},
        name=f"turn_timer:{turn_window_id}",
    )
    return job


def cancel_turn_timer(orchestrator, turn_window_id: str) -> None:
    """Cancel a scheduled timer job for a turn window."""
    job = orchestrator.turn_timer_jobs.pop(turn_window_id, None)
    if job is not None:
        job.schedule_removal()
        logger.debug("Cancelled timer job for turn %s", turn_window_id)
