"""Outbound message helpers.

All game-engine-to-Telegram delivery goes through these functions so the
rest of the codebase never calls bot.send_message directly.

Each function is async and accepts the PTB Bot instance plus addressing
information.  ParseMode defaults to HTML so narration can use basic
formatting tags.
"""

from __future__ import annotations

import logging

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from bot.config import BotConfig
from bot.mapping import BotRegistry, UnknownUserError

logger = logging.getLogger(__name__)


async def send_public(
    bot: Bot,
    config: BotConfig,
    text: str,
    parse_mode: str = ParseMode.HTML,
) -> None:
    """Send a message to the campaign supergroup's play topic.

    If play_topic_id is set, the message is sent into that topic thread.
    Falls back to the top-level group chat if play_topic_id is None.
    """
    if not config.group_chat_id:
        logger.error("send_public called but group_chat_id is not configured")
        return
    try:
        await bot.send_message(
            chat_id=config.group_chat_id,
            text=text,
            parse_mode=parse_mode,
            message_thread_id=config.play_topic_id,
        )
    except TelegramError as exc:
        logger.error("send_public failed: %s", exc)
        raise


async def send_private(
    bot: Bot,
    registry: BotRegistry,
    telegram_user_id: int,
    text: str,
    parse_mode: str = ParseMode.HTML,
) -> None:
    """Send a private DM to a registered player.

    Raises UnknownUserError if the user has no player mapping (they haven't
    completed onboarding).  The caller decides whether to swallow or surface.
    """
    if not registry.is_known_player(telegram_user_id):
        raise UnknownUserError(
            f"Cannot send private message: user {telegram_user_id} is not registered."
        )
    try:
        await bot.send_message(
            chat_id=telegram_user_id,
            text=text,
            parse_mode=parse_mode,
        )
    except TelegramError as exc:
        logger.error("send_private user=%s failed: %s", telegram_user_id, exc)
        raise


async def send_private_by_player_id(
    bot: Bot,
    registry: BotRegistry,
    player_id: str,
    text: str,
    parse_mode: str = ParseMode.HTML,
) -> None:
    """Send a private DM looked up by game player_id rather than Telegram user_id.

    Iterates the registry's reverse map.  Raises UnknownUserError if no
    Telegram user is mapped to this player_id.
    """
    # Build reverse map on the fly (registry is small; no caching needed)
    for tg_uid, pid in registry._user_to_player.items():
        if pid == player_id:
            await send_private(bot, registry, tg_uid, text, parse_mode)
            return
    raise UnknownUserError(
        f"Cannot send private message: player_id {player_id!r} not found in registry."
    )
