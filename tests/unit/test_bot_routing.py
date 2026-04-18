"""Unit tests for bot.routing."""

from __future__ import annotations

from bot.config import BotConfig
from bot.routing import RouteTarget, route_message
from tests.fixtures.telegram_builders import make_group_message, make_private_message


def _config(play_topic_id: int | None = 42) -> BotConfig:
    return BotConfig(group_chat_id=-9999, play_topic_id=play_topic_id)


class TestRouteMessage:
    def test_play_topic_routes_to_play_action(self):
        msg = make_group_message(thread_id=42, text="I search the room")
        result = route_message(msg, _config(play_topic_id=42))
        assert result.target == RouteTarget.play_action

    def test_group_outside_topic_routes_to_group_chat(self):
        msg = make_group_message(thread_id=99, text="OOC: brb")
        result = route_message(msg, _config(play_topic_id=42))
        assert result.target == RouteTarget.group_chat

    def test_group_no_topic_config_routes_to_group_chat(self):
        msg = make_group_message(thread_id=None)
        result = route_message(msg, _config(play_topic_id=None))
        assert result.target == RouteTarget.group_chat

    def test_private_text_routes_to_private_action(self):
        msg = make_private_message(text="What do I see?")
        result = route_message(msg, _config())
        assert result.target == RouteTarget.private_action

    def test_private_command_routes_to_private_command(self):
        msg = make_private_message(text="/status")
        result = route_message(msg, _config())
        assert result.target == RouteTarget.private_command
