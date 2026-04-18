"""Player onboarding gate.

When a private DM arrives from an unregistered user, the bot must not
route it to the game engine.  Instead it prompts the user to complete
onboarding by sending /join in the campaign group first.

This module provides a single guard function used by the DM handler.
"""

from __future__ import annotations

from telegram import Message

from bot.mapping import BotRegistry

ONBOARDING_PROMPT = (
    "Hi! I don't recognise you yet.\n\n"
    "To join the game, please open the campaign group and send /join there. "
    "Once you're registered you can DM me freely."
)


def requires_onboarding(
    registry: BotRegistry, telegram_user_id: int
) -> bool:
    """Return True if the user has NOT completed onboarding.

    Callers should send ONBOARDING_PROMPT and drop the message when this
    returns True.
    """
    return not registry.is_known_player(telegram_user_id)


async def send_onboarding_prompt(message: Message) -> None:
    """Reply to the message with the onboarding prompt text."""
    await message.reply_text(ONBOARDING_PROMPT)
