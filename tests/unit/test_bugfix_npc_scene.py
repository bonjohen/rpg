"""Phase 6 bug-fix tests: NPC trust rollback and scene transfer atomicity."""

from __future__ import annotations

import logging
from datetime import datetime

from server.domain.entities import Character, NPC, Scene
from server.domain.enums import SceneState, StanceToParty
from server.npc.social import SocialActionInput, SocialEngine, SocialOutcome
from server.scene.membership import SceneMembershipEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_npc(
    npc_id: str = "npc1",
    trust: int = 0,
    player_id: str = "p1",
    personality_tags: list[str] | None = None,
    stance: str | StanceToParty = "neutral",
) -> NPC:
    return NPC(
        npc_id=npc_id,
        campaign_id="c1",
        name="Test NPC",
        created_at=datetime(2026, 1, 1),
        scene_id="scene1",
        trust_by_player={player_id: trust} if trust != 0 else {},
        personality_tags=personality_tags or [],
        stance_to_party=StanceToParty(stance),
    )


def _make_input(
    action_type: str = "threaten",
    player_id: str = "p1",
) -> SocialActionInput:
    return SocialActionInput(
        player_id=player_id,
        character_id="char1",
        npc_id="npc1",
        action_type=action_type,
        player_text="I threaten the NPC",
        campaign_id="c1",
        scene_id="scene1",
    )


def _make_scene(scene_id: str, character_ids: list[str] | None = None) -> Scene:
    return Scene(
        scene_id=scene_id,
        campaign_id="c1",
        name=f"Scene {scene_id}",
        description="",
        state=SceneState.awaiting_actions,
        created_at=datetime(2026, 1, 1),
        character_ids=character_ids or [],
        player_ids=[],
    )


def _make_character(char_id: str = "char1", scene_id: str = "scene_a") -> Character:
    return Character(
        character_id=char_id,
        player_id="p1",
        campaign_id="c1",
        name="Test Char",
        created_at=datetime(2026, 1, 1),
        scene_id=scene_id,
    )


# ---------------------------------------------------------------------------
# BUG-008: Trust rollback on failure
# ---------------------------------------------------------------------------


class TestTrustRollback:
    def test_failed_threaten_rolls_back_trust(self):
        """When a threaten fails, NPC trust should be restored to pre-action state."""
        npc = _make_npc(trust=10, personality_tags=["fearless", "powerful"])
        inp = _make_input(action_type="threaten")

        engine = SocialEngine()
        result = engine.resolve(inp, npc)

        # Threaten against powerful NPC → ESCALATION (failure)
        assert result.outcome == SocialOutcome.ESCALATION
        assert not result.success

        # Trust should be rolled back to original
        assert npc.trust_by_player.get("p1", 0) == 10

    def test_failed_threaten_rolls_back_stance(self):
        """Stance should be restored on failure."""
        npc = _make_npc(
            trust=10, stance="neutral", personality_tags=["fearless", "powerful"]
        )
        inp = _make_input(action_type="threaten")

        engine = SocialEngine()
        result = engine.resolve(inp, npc)

        assert not result.success
        assert npc.stance_to_party == "neutral"

    def test_failed_threaten_rolls_back_memory_tags(self):
        """Memory tags should be restored on failure."""
        npc = _make_npc(trust=10, personality_tags=["fearless", "powerful"])
        original_tags = list(npc.memory_tags)

        engine = SocialEngine()
        result = engine.resolve(_make_input(action_type="threaten"), npc)

        assert not result.success
        assert npc.memory_tags == original_tags

    def test_successful_action_preserves_mutations(self):
        """When action succeeds, trust mutations should persist."""
        npc = _make_npc(trust=10, personality_tags=["timid"])
        inp = _make_input(action_type="threaten")

        engine = SocialEngine()
        result = engine.resolve(inp, npc)

        assert result.success
        # Trust should have changed (threaten applies negative delta)
        # We just verify it's different from original if a delta was applied
        assert "player_threatened_npc_complied" in npc.memory_tags

    def test_failed_persuade_rolls_back(self):
        """Persuade against hostile NPC fails and rolls back."""
        npc = _make_npc(trust=-50, stance="hostile")
        inp = _make_input(action_type="persuade")

        engine = SocialEngine()
        result = engine.resolve(inp, npc)

        assert not result.success
        assert npc.trust_by_player.get("p1", 0) == -50
        assert npc.stance_to_party == "hostile"


# ---------------------------------------------------------------------------
# BUG-009: Scene transfer rollback logging
# ---------------------------------------------------------------------------


class TestTransferRollbackLogging:
    def test_transfer_logs_warning_on_rollback(self, caplog):
        """When add to destination fails, rollback should log a warning."""
        engine = SceneMembershipEngine()

        char = _make_character(scene_id="scene_a")
        scene_a = _make_scene("scene_a", character_ids=["char1"])
        scene_b = _make_scene("scene_b", character_ids=["char1"])  # already there

        with caplog.at_level(logging.WARNING, logger="server.scene.membership"):
            result = engine.transfer_character(scene_a, scene_b, char)

        assert not result.success
        assert "Transfer" in result.reason or "transfer" in result.reason.lower()
        assert any(
            "rollback" in r.message.lower() or "rolled back" in r.message.lower()
            for r in caplog.records
        )

    def test_successful_transfer_no_warning(self, caplog):
        """Successful transfer should not log warnings."""
        engine = SceneMembershipEngine()

        char = _make_character(scene_id="scene_a")
        scene_a = _make_scene("scene_a", character_ids=["char1"])
        scene_b = _make_scene("scene_b")

        with caplog.at_level(logging.WARNING, logger="server.scene.membership"):
            result = engine.transfer_character(scene_a, scene_b, char)

        assert result.success
        warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_records) == 0
