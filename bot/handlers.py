"""Handler registration — wires all PTB handlers onto the Application."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import (
    Application,
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
from bot.mapping import BotRegistry
from bot.onboarding import requires_onboarding, send_onboarding_prompt
from bot.parsers import parse_group_message, parse_private_message
from bot.routing import RouteTarget, route_message

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


async def _handle_group_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Dispatch a supergroup text message."""
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
        # Game engine dispatch added in Phase 7+
    else:
        logger.debug(
            "group_chat user=%s text=%r", parsed.telegram_user_id, parsed.text[:60]
        )


async def _handle_private_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Dispatch a private DM text message."""
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
    # Game engine dispatch added in Phase 7+
