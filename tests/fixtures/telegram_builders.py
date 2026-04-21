"""Telegram payload fixture builders.

Creates fake PTB objects (Message, Update, User, Chat) suitable for unit
testing bot handlers, parsers, and routing without a live Telegram connection.

These are plain MagicMock-based fakes, not full PTB object graphs.  They
set only the attributes the bot code actually reads.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock


def make_user(
    user_id: int = 100,
    first_name: str = "Alice",
    username: str | None = "alice",
) -> MagicMock:
    user = MagicMock()
    user.id = user_id
    user.first_name = first_name
    user.full_name = first_name
    user.username = username
    return user


def make_group_message(
    text: str = "hello",
    user_id: int = 100,
    chat_id: int = -1001234567890,
    message_id: int = 1,
    thread_id: int | None = None,
    chat_type: str = "supergroup",
) -> MagicMock:
    """Build a fake supergroup Message."""
    msg = MagicMock()
    msg.text = text
    msg.message_id = message_id
    msg.message_thread_id = thread_id
    msg.chat_id = chat_id
    msg.from_user = make_user(user_id=user_id)
    msg.reply_text = AsyncMock()

    chat = MagicMock()
    chat.id = chat_id
    chat.type = chat_type
    msg.chat = chat

    return msg


def make_private_message(
    text: str = "hello",
    user_id: int = 100,
    message_id: int = 1,
) -> MagicMock:
    """Build a fake private DM Message."""
    msg = MagicMock()
    msg.text = text
    msg.message_id = message_id
    msg.message_thread_id = None
    msg.chat_id = user_id  # private chats have chat_id == user_id
    msg.from_user = make_user(user_id=user_id)
    msg.reply_text = AsyncMock()

    chat = MagicMock()
    chat.id = user_id
    chat.type = "private"
    msg.chat = chat

    return msg


def make_update(
    message: MagicMock,
    update_id: int = 1,
) -> MagicMock:
    """Wrap a fake message in a fake Update."""
    update = MagicMock()
    update.update_id = update_id
    update.effective_message = message
    update.effective_user = message.from_user
    update.message = message
    return update


def make_context(
    registry=None,
    config=None,
    orchestrator=None,
) -> MagicMock:
    """Build a fake PTB ContextTypes.DEFAULT_TYPE."""
    from bot.mapping import BotRegistry

    ctx = MagicMock()
    ctx.application = MagicMock()
    bot_data = {
        "registry": registry or BotRegistry(),
        "config": config,
    }
    if orchestrator is not None:
        bot_data["orchestrator"] = orchestrator
    ctx.application.bot_data = bot_data
    ctx.application.bot = AsyncMock()
    return ctx
