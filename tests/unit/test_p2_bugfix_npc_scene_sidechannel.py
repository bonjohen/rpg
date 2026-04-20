"""Tests for P2 Phase 4: NPC type safety, scene membership, side channel uniqueness."""

from __future__ import annotations

import logging

from server.domain.entities import Character, NPC, Scene, SideChannel
from server.domain.helpers import utc_now
from server.npc.social import SocialOutcome
from server.npc.trust import TrustEngine
from server.scene.membership import SceneMembershipEngine
from server.scope.side_channel_audit import SideChannelAuditor
from server.scope.side_channel_engine import SideChannelEngine


# -------------------------------------------------------------------
# BUG-036: SocialOutcome is str Enum (backward-compatible)
# -------------------------------------------------------------------


class TestBUG036SocialOutcomeEnum:
    def test_social_outcome_is_str_enum(self):
        assert isinstance(SocialOutcome.SUCCESS, str)
        assert SocialOutcome.SUCCESS == "success"
        assert SocialOutcome.DETECTED_LIE == "detected_lie"

    def test_social_outcome_values_iterable(self):
        values = [o.value for o in SocialOutcome]
        assert "success" in values
        assert "failure" in values
        assert "escalation" in values


# -------------------------------------------------------------------
# BUG-037: Unknown action_key logs warning
# -------------------------------------------------------------------


class TestBUG037UnknownActionKeyWarning:
    def test_unknown_action_key_logs_warning(self, caplog):
        engine = TrustEngine()
        npc = NPC(
            npc_id="npc1",
            campaign_id="c1",
            name="Guard",
            created_at=utc_now(),
        )
        with caplog.at_level(logging.WARNING, logger="server.npc.trust"):
            engine.apply_action_delta(npc, "player1", "totally_unknown_action")
        assert any("Unknown trust action_key" in r.message for r in caplog.records)

    def test_known_action_key_no_warning(self, caplog):
        engine = TrustEngine()
        npc = NPC(
            npc_id="npc1",
            campaign_id="c1",
            name="Guard",
            created_at=utc_now(),
        )
        with caplog.at_level(logging.WARNING, logger="server.npc.trust"):
            engine.apply_action_delta(npc, "player1", "question")
        assert not any("Unknown trust action_key" in r.message for r in caplog.records)


# -------------------------------------------------------------------
# BUG-038: _derive_stance includes "suspicious" zone
# -------------------------------------------------------------------


class TestBUG038SuspiciousZone:
    def test_negative_mean_trust_returns_suspicious(self):
        engine = TrustEngine()
        npc = NPC(
            npc_id="npc1",
            campaign_id="c1",
            name="Guard",
            created_at=utc_now(),
            trust_by_player={"p1": -40},
        )
        stance = engine._derive_stance(npc)
        assert stance == "suspicious"

    def test_mildly_negative_trust_returns_neutral(self):
        engine = TrustEngine()
        npc = NPC(
            npc_id="npc1",
            campaign_id="c1",
            name="Guard",
            created_at=utc_now(),
            trust_by_player={"p1": -10},
        )
        stance = engine._derive_stance(npc)
        assert stance == "neutral"


# -------------------------------------------------------------------
# BUG-039: remove_character checks remaining characters
# -------------------------------------------------------------------


class TestBUG039RemoveCharacterPlayerCheck:
    def test_player_id_kept_when_another_character_remains(self):
        engine = SceneMembershipEngine()
        scene = Scene(
            scene_id="s1",
            campaign_id="c1",
            name="Hall",
            description="A hall",
            created_at=utc_now(),
            character_ids=["ch1", "ch2"],
            player_ids=["p1"],
        )
        char1 = Character(
            character_id="ch1",
            campaign_id="c1",
            player_id="p1",
            name="Hero A",
            scene_id="s1",
            created_at=utc_now(),
        )
        char2 = Character(
            character_id="ch2",
            campaign_id="c1",
            player_id="p1",
            name="Hero B",
            scene_id="s1",
            created_at=utc_now(),
        )
        result = engine.remove_character(
            scene, char1, all_scene_characters=[char1, char2]
        )
        assert result.success is True
        # Player still has char2 in scene, so player_id should remain
        assert "p1" in scene.player_ids

    def test_player_id_removed_when_no_characters_remain(self):
        engine = SceneMembershipEngine()
        scene = Scene(
            scene_id="s1",
            campaign_id="c1",
            name="Hall",
            description="A hall",
            created_at=utc_now(),
            character_ids=["ch1"],
            player_ids=["p1"],
        )
        char = Character(
            character_id="ch1",
            campaign_id="c1",
            player_id="p1",
            name="Hero",
            scene_id="s1",
            created_at=utc_now(),
        )
        result = engine.remove_character(scene, char, all_scene_characters=[char])
        assert result.success is True
        assert "p1" not in scene.player_ids


# -------------------------------------------------------------------
# BUG-025: Audit fact_id uses new_id() for uniqueness
# -------------------------------------------------------------------


class TestBUG025AuditFactIdUniqueness:
    def test_audit_fact_ids_are_unique(self):
        auditor = SideChannelAuditor()
        channel = SideChannel(
            side_channel_id="sc-1",
            campaign_id="c1",
            created_at=utc_now(),
            created_by_player_id="p1",
            member_player_ids=["p1", "p2"],
            is_open=True,
            label="Secret Chat",
        )
        fact1 = auditor.record_creation(channel, "c1", "s1")
        fact2 = auditor.record_creation(channel, "c1", "s1")
        # Each call should produce a unique fact_id
        assert fact1.fact_id != fact2.fact_id

    def test_message_audit_fact_ids_unique(self):
        auditor = SideChannelAuditor()
        channel = SideChannel(
            side_channel_id="sc-1",
            campaign_id="c1",
            created_at=utc_now(),
            created_by_player_id="p1",
            member_player_ids=["p1", "p2"],
            is_open=True,
            label="Secret Chat",
        )
        fact1 = auditor.record_message(channel, "p1", "c1", "s1")
        fact2 = auditor.record_message(channel, "p1", "c1", "s1")
        assert fact1.fact_id != fact2.fact_id


# -------------------------------------------------------------------
# BUG-026: Channel ID includes UUID suffix for uniqueness
# -------------------------------------------------------------------


class TestBUG026ChannelIdUniqueness:
    def test_channel_ids_unique_for_same_label(self):
        engine = SideChannelEngine()
        r1 = engine.create_channel(
            creator_player_id="p1",
            member_player_ids=["p1", "p2"],
            campaign_id="c1",
            all_campaign_player_ids=["p1", "p2"],
            label="whisper",
        )
        r2 = engine.create_channel(
            creator_player_id="p1",
            member_player_ids=["p1", "p2"],
            campaign_id="c1",
            all_campaign_player_ids=["p1", "p2"],
            label="whisper",
        )
        assert r1.success and r2.success
        assert r1.channel.side_channel_id != r2.channel.side_channel_id
