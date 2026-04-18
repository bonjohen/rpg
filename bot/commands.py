"""Slash command handlers: /start, /join, /help, /status.

Each handler is an async PTB callback.  They are registered onto the
Application in handlers.py via CommandHandler.

The registry is retrieved from application.bot_data["registry"]; the config
from application.bot_data["config"].  Both are injected at startup.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.mapping import BotRegistry, UnknownUserError
from bot.onboarding import ONBOARDING_PROMPT

logger = logging.getLogger(__name__)

_HELP_TEXT = (
    "Available commands:\n"
    "  /start   — Start a conversation with the bot\n"
    "  /join    — Register as a player (send this in the group)\n"
    "  /help    — Show this message\n"
    "  /status  — Show your current game status\n"
)


def _registry(context: ContextTypes.DEFAULT_TYPE) -> BotRegistry:
    return context.application.bot_data.get("registry", BotRegistry())


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start — greet the user and prompt onboarding if needed."""
    user = update.effective_user
    registry = _registry(context)

    if not registry.is_known_player(user.id):
        await update.message.reply_text(
            f"Hello, {user.first_name}!\n\n{ONBOARDING_PROMPT}"
        )
    else:
        await update.message.reply_text(
            f"Welcome back, {user.first_name}! You're registered as a player.\n"
            "Use /help to see available commands."
        )


async def cmd_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/join — register the sender as a player in the current campaign.

    Must be sent from the campaign supergroup; the chat_id is used to look
    up the campaign.  If the user is already registered, confirm idempotently.
    """
    user = update.effective_user
    registry = _registry(context)

    if update.message.chat.type == "private":
        await update.message.reply_text(
            "Please send /join in the campaign group, not here."
        )
        return

    if registry.is_known_player(user.id):
        await update.message.reply_text(
            f"You're already registered, {user.first_name}. Good to go!"
        )
        return

    # Stub: in Phase 3 we create a minimal player record and register it.
    # Full character creation happens in later phases.
    import uuid

    player_id = str(uuid.uuid4())
    registry.register_player(user.id, player_id)

    logger.info("Player joined: telegram_user_id=%s player_id=%s", user.id, player_id)
    await update.message.reply_text(
        f"Welcome, {user.first_name}! You've been registered as a player.\n"
        "You can now DM me directly for private game actions."
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/help — show the command list."""
    await update.message.reply_text(_HELP_TEXT)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/status — show the player's current game state (stub)."""
    user = update.effective_user
    registry = _registry(context)

    try:
        player_id = registry.player_id_for(user.id)
    except UnknownUserError:
        await update.message.reply_text(
            "You're not registered yet. Send /join in the campaign group to get started."
        )
        return

    # Full status assembly happens in later phases; return stub for now.
    await update.message.reply_text(
        f"Player ID: {player_id}\nStatus: registered (full status available after character creation)"
    )
