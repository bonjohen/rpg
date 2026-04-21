"""Handler registration — wires all PTB handlers onto the Application."""

from __future__ import annotations

import logging

from telegram import Bot, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.commands import (
    cmd_diagnostics,
    cmd_forceresolve,
    cmd_help,
    cmd_join,
    cmd_newgame,
    cmd_nextturn,
    cmd_scene,
    cmd_start,
    cmd_status,
    cmd_who,
)
from bot.config import BotConfig
from bot.mapping import BotRegistry, UnknownUserError
from bot.onboarding import requires_onboarding, send_onboarding_prompt
from bot.outbound import send_private, send_public
from bot.parsers import parse_group_message, parse_private_message
from bot.routing import RouteTarget, route_message
from bot.turn_controls import CALLBACK_PASS, CALLBACK_READY

logger = logging.getLogger(__name__)


def register_handlers(app: Application) -> None:
    """Register all message, command, and callback handlers on ``app``."""
    # Ensure registry exists in bot_data
    if "registry" not in app.bot_data:
        app.bot_data["registry"] = BotRegistry()

    # --- Command handlers (work in both group and private) ---
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("join", cmd_join))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("newgame", cmd_newgame))
    app.add_handler(CommandHandler("nextturn", cmd_nextturn))
    app.add_handler(CommandHandler("forceresolve", cmd_forceresolve))
    app.add_handler(CommandHandler("diagnostics", cmd_diagnostics))
    app.add_handler(CommandHandler("scene", cmd_scene))
    app.add_handler(CommandHandler("who", cmd_who))

    # --- Group message handler ---
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND,
            _handle_group_message,
        )
    )

    # --- Private DM handler ---
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
            _handle_private_message,
        )
    )

    # --- Callback query handler for inline keyboard buttons ---
    app.add_handler(CallbackQueryHandler(_handle_callback_query))


async def _handle_group_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Dispatch a supergroup text message to the orchestrator."""
    message = update.effective_message
    if message is None:
        return

    config = context.application.bot_data.get("config")
    play_topic_id = config.play_topic_id if config else None

    parsed = parse_group_message(message, play_topic_id=play_topic_id)
    routed = route_message(message, config) if config else None

    target = routed.target if routed else RouteTarget.group_chat

    if target == RouteTarget.play_action:
        logger.debug(
            "play_action user=%s text=%r", parsed.telegram_user_id, parsed.text[:60]
        )
        orchestrator = context.application.bot_data.get("orchestrator")
        if orchestrator is None:
            return

        registry: BotRegistry = context.application.bot_data.get(
            "registry", BotRegistry()
        )
        try:
            player_id = registry.player_id_for(parsed.telegram_user_id)
        except UnknownUserError:
            if message.from_user:
                await message.reply_text(
                    "You need to /join the game first before taking actions."
                )
            return

        try:
            result = await orchestrator.handle_player_message(
                player_id, parsed.text, is_private=False
            )
        except Exception:
            logger.exception(
                "handle_player_message failed user=%s", parsed.telegram_user_id
            )
            await message.reply_text("Something went wrong processing your message.")
            return

        if result.response_text:
            await send_public(context.application.bot, config, result.response_text)

        # Update turn-control message if an action was submitted
        if result.action_submitted and config:
            await _update_control_after_action(
                context.application.bot, config, orchestrator, player_id
            )

        # Finalize control message if turn resolved
        if result.turn_resolved and config:
            await _finalize_control_after_resolve(
                context.application.bot, config, orchestrator, player_id, result
            )
    else:
        logger.debug(
            "group_chat user=%s text=%r", parsed.telegram_user_id, parsed.text[:60]
        )


async def _handle_private_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Dispatch a private DM text message to the orchestrator."""
    message = update.effective_message
    if message is None:
        return

    if not message.from_user:
        return

    registry: BotRegistry = context.application.bot_data.get("registry", BotRegistry())
    user_id = message.from_user.id

    if requires_onboarding(registry, user_id):
        await send_onboarding_prompt(message)
        return

    parsed = parse_private_message(message)
    logger.debug(
        "private_action user=%s text=%r", parsed.telegram_user_id, parsed.text[:60]
    )

    orchestrator = context.application.bot_data.get("orchestrator")
    if orchestrator is None:
        await message.reply_text(
            "No active game. Ask the GM to start one with /newgame."
        )
        return

    try:
        player_id = registry.player_id_for(parsed.telegram_user_id)
    except UnknownUserError:
        await message.reply_text(
            "You need to /join the game first. Send /join in the group chat."
        )
        return

    try:
        result = await orchestrator.handle_player_message(
            player_id, parsed.text, is_private=True
        )
    except Exception:
        logger.exception(
            "handle_player_message failed user=%s", parsed.telegram_user_id
        )
        await message.reply_text("Something went wrong processing your message.")
        return

    if result.response_text:
        await send_private(
            context.application.bot,
            registry,
            parsed.telegram_user_id,
            result.response_text,
        )


async def _handle_callback_query(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle Ready/Pass inline keyboard button presses."""
    query = update.callback_query
    if query is None:
        return

    data = query.data
    if data not in (CALLBACK_READY, CALLBACK_PASS):
        await query.answer("Unknown action.")
        return

    user = query.from_user
    if user is None:
        await query.answer("Could not identify user.")
        return

    registry: BotRegistry = context.application.bot_data.get("registry", BotRegistry())

    try:
        player_id = registry.player_id_for(user.id)
    except UnknownUserError:
        await query.answer("You need to /join the game first.")
        return

    orchestrator = context.application.bot_data.get("orchestrator")
    if orchestrator is None:
        await query.answer("No active game.")
        return

    # Check if player has an active turn
    scene = orchestrator.get_player_scene(player_id)
    if scene is None or scene.active_turn_window_id is None:
        await query.answer("No active turn.")
        return

    tw = orchestrator.get_turn_window(scene.active_turn_window_id)
    if tw is None:
        await query.answer("No active turn.")
        return

    from server.domain.enums import TurnWindowState

    if tw.state not in (TurnWindowState.open, TurnWindowState.all_ready):
        await query.answer("This turn has already been resolved.")
        return

    from server.domain.enums import ActionType

    action = orchestrator.submit_action(
        player_id=player_id,
        action_type=ActionType.hold if data == CALLBACK_READY else ActionType.pass_turn,
        public_text="",
    )

    if action is None:
        await query.answer("Could not submit — you may have already acted this turn.")
        return

    label = "Ready" if data == CALLBACK_READY else "Pass"
    await query.answer(f"{label} submitted!")

    config = context.application.bot_data.get("config")

    # Update control message with remaining players
    if config:
        await _update_control_after_action(
            context.application.bot, config, orchestrator, player_id
        )

    # Auto-resolve if all players are ready
    scene = orchestrator.get_player_scene(player_id)
    if scene and scene.active_turn_window_id:
        tw = orchestrator.get_turn_window(scene.active_turn_window_id)
        if tw and tw.state == TurnWindowState.all_ready:
            log_entry = orchestrator.resolve_turn(scene.active_turn_window_id)
            if log_entry:
                if config:
                    from bot.turn_controls import finalize_turn_control

                    msg_id = orchestrator.turn_control_message_ids.get(
                        scene.active_turn_window_id
                    )
                    if msg_id:
                        await finalize_turn_control(
                            context.application.bot, config, msg_id, tw.turn_number
                        )


async def _update_control_after_action(
    bot: Bot, config: BotConfig, orchestrator, player_id: str
) -> None:
    """Edit the turn-control message to show remaining players after an action."""
    from bot.turn_controls import update_turn_control

    scene = orchestrator.get_player_scene(player_id)
    if scene is None or scene.active_turn_window_id is None:
        return

    msg_id = orchestrator.turn_control_message_ids.get(scene.active_turn_window_id)
    if msg_id is None:
        return

    tw = orchestrator.get_turn_window(scene.active_turn_window_id)
    if tw is None:
        return

    # Get all players in scene and who has submitted
    actions = orchestrator.get_committed_actions_for_window(tw.turn_window_id)
    submitted_ids = {a.player_id for a in actions}
    scene_players = orchestrator.get_scene_players(scene.scene_id)
    remaining = [
        p.display_name for p in scene_players if p.player_id not in submitted_ids
    ]

    await update_turn_control(
        bot, config, msg_id, scene.name, tw.turn_number, remaining
    )


async def _finalize_control_after_resolve(
    bot: Bot, config: BotConfig, orchestrator, player_id: str, result
) -> None:
    """Edit the turn-control message to show resolution."""
    from bot.turn_controls import finalize_turn_control

    scene = orchestrator.get_player_scene(player_id)
    if scene is None:
        return

    # The turn_window_id is on the result's log entry
    log_entry = result.turn_log_entry
    if log_entry is None:
        return

    turn_window_id = getattr(log_entry, "turn_window_id", None)
    if turn_window_id is None:
        return

    msg_id = orchestrator.turn_control_message_ids.get(turn_window_id)
    if msg_id is None:
        return

    turn_number = getattr(log_entry, "turn_number", 0)
    await finalize_turn_control(bot, config, msg_id, turn_number)
