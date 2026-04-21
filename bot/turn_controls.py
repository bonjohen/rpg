"""Turn-control message lifecycle: post, update, and finalize inline keyboards.

When a turn opens, the bot posts a control message with [Ready] [Pass] buttons.
As players submit actions, the message is edited to show who's still pending.
On resolution, the keyboard is removed and the text shows "Turn N resolved."
"""

from __future__ import annotations

import logging

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

from bot.config import BotConfig

logger = logging.getLogger(__name__)

# Callback data constants
CALLBACK_READY = "turn:ready"
CALLBACK_PASS = "turn:pass"


def build_turn_keyboard() -> InlineKeyboardMarkup:
    """Build the [Ready] [Pass] inline keyboard for a turn-control message."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Ready", callback_data=CALLBACK_READY),
                InlineKeyboardButton("Pass", callback_data=CALLBACK_PASS),
            ]
        ]
    )


async def post_turn_control(
    bot: Bot,
    config: BotConfig,
    scene_name: str,
    turn_number: int,
    player_names: list[str],
) -> int | None:
    """Post the turn-control message and return its message_id.

    Returns None if the send fails (logged, not raised).
    """
    waiting = ", ".join(player_names) if player_names else "no one"
    text = (
        f"Turn {turn_number} — {scene_name}\n"
        f"What do you do? (Type your action, or tap a button.)\n\n"
        f"Waiting for: {waiting}"
    )
    try:
        msg = await bot.send_message(
            chat_id=config.group_chat_id,
            text=text,
            reply_markup=build_turn_keyboard(),
            message_thread_id=config.play_topic_id,
        )
        return msg.message_id
    except TelegramError:
        logger.exception("Failed to post turn-control message")
        return None


async def update_turn_control(
    bot: Bot,
    config: BotConfig,
    message_id: int,
    scene_name: str,
    turn_number: int,
    remaining_names: list[str],
) -> None:
    """Edit the turn-control message to show remaining players."""
    if not remaining_names:
        waiting = "all players ready!"
    else:
        waiting = ", ".join(remaining_names)
    text = (
        f"Turn {turn_number} — {scene_name}\n"
        f"What do you do? (Type your action, or tap a button.)\n\n"
        f"Waiting for: {waiting}"
    )
    try:
        await bot.edit_message_text(
            chat_id=config.group_chat_id,
            message_id=message_id,
            text=text,
            reply_markup=build_turn_keyboard(),
        )
    except TelegramError:
        logger.exception("Failed to update turn-control message")


async def finalize_turn_control(
    bot: Bot,
    config: BotConfig,
    message_id: int,
    turn_number: int,
) -> None:
    """Edit the turn-control message to show resolution and remove keyboard."""
    text = f"Turn {turn_number} resolved."
    try:
        await bot.edit_message_text(
            chat_id=config.group_chat_id,
            message_id=message_id,
            text=text,
            reply_markup=None,
        )
    except TelegramError:
        logger.exception("Failed to finalize turn-control message")
