"""Unit tests for bot.parsers."""

from __future__ import annotations

import pytest

from bot.parsers import (
    MessageKind,
    ParsedGroupMessage,
    ParsedPrivateMessage,
    classify_message,
    parse_group_message,
    parse_private_message,
)
from tests.fixtures.telegram_builders import make_group_message, make_private_message


class TestClassifyMessage:
    def test_private_dm(self):
        msg = make_private_message()
        assert classify_message(msg) == MessageKind.private_dm

    def test_supergroup_no_topic(self):
        msg = make_group_message(thread_id=None)
        assert classify_message(msg) == MessageKind.public_group

    def test_supergroup_wrong_topic(self):
        msg = make_group_message(thread_id=99)
        assert classify_message(msg, play_topic_id=42) == MessageKind.public_group

    def test_supergroup_matching_topic(self):
        msg = make_group_message(thread_id=42)
        assert classify_message(msg, play_topic_id=42) == MessageKind.play_topic

    def test_no_play_topic_configured(self):
        msg = make_group_message(thread_id=42)
        assert classify_message(msg, play_topic_id=None) == MessageKind.public_group


class TestParseGroupMessage:
    def test_parses_fields(self):
        msg = make_group_message(
            text="I attack the goblin",
            user_id=200,
            chat_id=-9999,
            message_id=7,
            thread_id=42,
        )
        parsed = parse_group_message(msg, play_topic_id=42)
        assert isinstance(parsed, ParsedGroupMessage)
        assert parsed.telegram_user_id == 200
        assert parsed.telegram_chat_id == -9999
        assert parsed.message_id == 7
        assert parsed.thread_id == 42
        assert parsed.text == "I attack the goblin"
        assert parsed.is_play_topic is True

    def test_not_play_topic_when_thread_differs(self):
        msg = make_group_message(thread_id=1)
        parsed = parse_group_message(msg, play_topic_id=42)
        assert parsed.is_play_topic is False

    def test_raises_for_private_chat(self):
        msg = make_private_message()
        with pytest.raises(ValueError, match="group"):
            parse_group_message(msg)


class TestParsePrivateMessage:
    def test_parses_fields(self):
        msg = make_private_message(text="What is my HP?", user_id=300, message_id=5)
        parsed = parse_private_message(msg)
        assert isinstance(parsed, ParsedPrivateMessage)
        assert parsed.telegram_user_id == 300
        assert parsed.message_id == 5
        assert parsed.text == "What is my HP?"

    def test_raises_for_group_chat(self):
        msg = make_group_message()
        with pytest.raises(ValueError, match="private"):
            parse_private_message(msg)
