"""Message parsers — extract structured data from Telegram Update objects.

These are pure functions: they accept PTB objects and return plain dataclasses.
No I/O, no async, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from telegram import Message


class MessageKind(str, Enum):
    """Coarse classification of an incoming message."""

    public_group = "public_group"
    """Message in the campaign supergroup (any topic)."""

    play_topic = "play_topic"
    """Message in the designated play topic of the supergroup."""

    private_dm = "private_dm"
    """Private DM to the bot from a player."""

    other = "other"
    """Anything else (other bots, channel posts, etc.)."""


@dataclass
class ParsedGroupMessage:
    """Structured result of parsing a supergroup message."""

    telegram_user_id: int
    telegram_chat_id: int
    message_id: int
    thread_id: int | None
    text: str
    is_play_topic: bool
    username: str | None
    first_name: str


@dataclass
class ParsedPrivateMessage:
    """Structured result of parsing a private DM."""

    telegram_user_id: int
    message_id: int
    text: str
    username: str | None
    first_name: str


def classify_message(message: Message, play_topic_id: int | None = None) -> MessageKind:
    """Classify a Telegram Message into a MessageKind."""
    if message.chat.type == "private":
        return MessageKind.private_dm

    if message.chat.type in {"group", "supergroup"}:
        if play_topic_id is not None and message.message_thread_id == play_topic_id:
            return MessageKind.play_topic
        return MessageKind.public_group

    return MessageKind.other


def parse_group_message(
    message: Message, play_topic_id: int | None = None
) -> ParsedGroupMessage:
    """Extract structured data from a supergroup Message.

    Raises ValueError if the message is not from a group/supergroup chat.
    """
    if message.chat.type not in {"group", "supergroup"}:
        raise ValueError(
            f"Expected group/supergroup message, got chat type {message.chat.type!r}"
        )

    sender = message.from_user
    return ParsedGroupMessage(
        telegram_user_id=sender.id if sender else 0,
        telegram_chat_id=message.chat_id,
        message_id=message.message_id,
        thread_id=message.message_thread_id,
        text=message.text or "",
        is_play_topic=(
            play_topic_id is not None and message.message_thread_id == play_topic_id
        ),
        username=sender.username if sender else None,
        first_name=sender.first_name if sender else "",
    )


def parse_private_message(message: Message) -> ParsedPrivateMessage:
    """Extract structured data from a private DM Message.

    Raises ValueError if the message is not a private chat.
    """
    if message.chat.type != "private":
        raise ValueError(
            f"Expected private message, got chat type {message.chat.type!r}"
        )

    sender = message.from_user
    return ParsedPrivateMessage(
        telegram_user_id=sender.id if sender else 0,
        message_id=message.message_id,
        text=message.text or "",
        username=sender.username if sender else None,
        first_name=sender.first_name if sender else "",
    )
