"""Unit tests for bot.mapping.BotRegistry."""

from __future__ import annotations

import pytest

from bot.mapping import BotRegistry, UnknownChatError, UnknownUserError


class TestBotRegistry:
    def test_register_and_lookup_player(self):
        r = BotRegistry()
        r.register_player(101, "player-uuid")
        assert r.player_id_for(101) == "player-uuid"

    def test_unknown_player_raises(self):
        r = BotRegistry()
        with pytest.raises(UnknownUserError):
            r.player_id_for(999)

    def test_register_and_lookup_campaign(self):
        r = BotRegistry()
        r.register_campaign(-10001, "campaign-uuid")
        assert r.campaign_id_for(-10001) == "campaign-uuid"

    def test_unknown_campaign_raises(self):
        r = BotRegistry()
        with pytest.raises(UnknownChatError):
            r.campaign_id_for(-88888)

    def test_is_known_player_true(self):
        r = BotRegistry()
        r.register_player(5, "p")
        assert r.is_known_player(5) is True

    def test_is_known_player_false(self):
        assert BotRegistry().is_known_player(5) is False

    def test_is_known_chat_true(self):
        r = BotRegistry()
        r.register_campaign(-1, "c")
        assert r.is_known_chat(-1) is True

    def test_unregister_player(self):
        r = BotRegistry()
        r.register_player(10, "p")
        r.unregister_player(10)
        assert not r.is_known_player(10)

    def test_unregister_nonexistent_is_noop(self):
        r = BotRegistry()
        r.unregister_player(999)  # should not raise

    def test_overwrite_player_mapping(self):
        r = BotRegistry()
        r.register_player(1, "old")
        r.register_player(1, "new")
        assert r.player_id_for(1) == "new"
