"""Tests for P2 Phase 7: Datetime hardening and replay warning."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from server.domain.helpers import utc_now
from server.domain.entities import CommittedAction, TurnLogEntry
from server.domain.enums import ActionType
from server.engine.turn_engine import TurnEngine


# -------------------------------------------------------------------
# BUG-027: utc_now() used consistently instead of replace(tzinfo=None)
# -------------------------------------------------------------------


class TestBUG027UtcNowConsistency:
    def test_utc_now_returns_naive_datetime(self):
        now = utc_now()
        assert now.tzinfo is None

    def test_utc_now_close_to_utc(self):
        now_aware = datetime.now(timezone.utc)
        now_naive = utc_now()
        # Should be within 1 second
        diff = abs((now_aware.replace(tzinfo=None) - now_naive).total_seconds())
        assert diff < 1.0

    def test_timer_controller_uses_utc_now(self):
        """Verify timer _now_utc delegates to utc_now."""
        from server.timer.controller import _now_utc

        result = _now_utc()
        assert result.tzinfo is None

    def test_side_channel_engine_no_raw_datetime_now(self):
        """Verify side_channel_engine imports and uses utc_now."""
        import inspect
        import server.scope.side_channel_engine as mod

        source = inspect.getsource(mod)
        # Should not contain the raw pattern
        assert "datetime.now(timezone.utc).replace(tzinfo=None)" not in source

    def test_facts_no_raw_datetime_now(self):
        """Verify scope/facts.py imports and uses utc_now."""
        import inspect
        import server.scope.facts as mod

        source = inspect.getsource(mod)
        assert "datetime.now(timezone.utc).replace(tzinfo=None)" not in source

    def test_propagation_no_raw_datetime_now(self):
        """Verify scene/propagation.py uses utc_now."""
        import inspect
        import server.scene.propagation as mod

        source = inspect.getsource(mod)
        assert "datetime.now(timezone.utc).replace(tzinfo=None)" not in source


# -------------------------------------------------------------------
# BUG-028: replay_turn warns on missing action IDs
# -------------------------------------------------------------------


class TestBUG028ReplayTurnWarning:
    def test_replay_logs_warning_on_missing_ids(self, caplog):
        engine = TurnEngine.__new__(TurnEngine)
        log_entry = TurnLogEntry(
            log_entry_id="log-1",
            campaign_id="c-1",
            scene_id="s-1",
            turn_window_id="tw-1",
            turn_number=1,
            committed_at=utc_now(),
            action_ids=["a-1", "a-2", "a-missing"],
            narration="test",
        )
        actions = [
            CommittedAction(
                action_id="a-1",
                turn_window_id="tw-1",
                player_id="p-1",
                character_id="ch-1",
                scope_id="scope-1",
                declared_action_type=ActionType.attack,
                public_text="attack",
            ),
            CommittedAction(
                action_id="a-2",
                turn_window_id="tw-1",
                player_id="p-2",
                character_id="ch-2",
                scope_id="scope-1",
                declared_action_type=ActionType.defend,
                public_text="defend",
            ),
        ]
        with caplog.at_level(logging.WARNING, logger="server.engine.turn_engine"):
            result = engine.replay_turn(log_entry, actions)

        assert len(result) == 2
        assert any("a-missing" in r.message for r in caplog.records)

    def test_replay_no_warning_when_all_present(self, caplog):
        engine = TurnEngine.__new__(TurnEngine)
        log_entry = TurnLogEntry(
            log_entry_id="log-1",
            campaign_id="c-1",
            scene_id="s-1",
            turn_window_id="tw-1",
            turn_number=1,
            committed_at=utc_now(),
            action_ids=["a-1"],
            narration="test",
        )
        actions = [
            CommittedAction(
                action_id="a-1",
                turn_window_id="tw-1",
                player_id="p-1",
                character_id="ch-1",
                scope_id="scope-1",
                declared_action_type=ActionType.attack,
                public_text="attack",
            ),
        ]
        with caplog.at_level(logging.WARNING, logger="server.engine.turn_engine"):
            result = engine.replay_turn(log_entry, actions)

        assert len(result) == 1
        assert not any("missing" in r.message for r in caplog.records)
