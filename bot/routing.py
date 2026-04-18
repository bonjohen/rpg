"""Topic-aware message routing.

Routes incoming PTB Updates to the correct handler based on:
  - Chat type (private DM vs supergroup)
  - Thread/topic ID (main play topic vs other group topics)

The router is a pure function: it receives the classified message kind and
the bot config and returns a RouteTarget.  The actual handler dispatch is
done by PTB filters inside handlers.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from telegram import Message

from bot.config import BotConfig
from bot.parsers import MessageKind, classify_message


class RouteTarget(str, Enum):
    """Where a message should be routed."""

    play_action = "play_action"
    """Player action text in the main play topic → game engine."""

    group_chat = "group_chat"
    """Group message outside the play topic → log only, no engine call."""

    private_command = "private_command"
    """Private DM containing a slash command → command dispatcher."""

    private_action = "private_action"
    """Private DM containing free text → game engine (if onboarded)."""

    ignored = "ignored"
    """Message does not need processing (bots, channel posts, etc.)."""


@dataclass
class RoutedMessage:
    """Result of routing a message."""

    target: RouteTarget
    kind: MessageKind


def route_message(message: Message, config: BotConfig) -> RoutedMessage:
    """Classify and route a Telegram Message.

    Args:
        message: The incoming PTB Message object.
        config:  BotConfig carrying play_topic_id and group_chat_id.

    Returns:
        A RoutedMessage with target and kind.
    """
    kind = classify_message(message, play_topic_id=config.play_topic_id)

    if kind == MessageKind.private_dm:
        text = message.text or ""
        if text.startswith("/"):
            return RoutedMessage(target=RouteTarget.private_command, kind=kind)
        return RoutedMessage(target=RouteTarget.private_action, kind=kind)

    if kind == MessageKind.play_topic:
        return RoutedMessage(target=RouteTarget.play_action, kind=kind)

    if kind == MessageKind.public_group:
        return RoutedMessage(target=RouteTarget.group_chat, kind=kind)

    return RoutedMessage(target=RouteTarget.ignored, kind=kind)
