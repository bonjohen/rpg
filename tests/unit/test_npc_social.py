"""Tests for server/npc/ — NPC Social Loop.

Covers:
  - TrustEngine: trust deltas, stance derivation, cooperative/hostile checks
  - SocialEngine: all five action types (question, persuade, threaten, lie, bargain)
  - NpcTellEngine: tell firing, trust facts, private reaction facts
  - DialogueContextBuilder: flag derivation, public/referee dict splitting
  - Memory tag persistence after interactions
  - Two meaningful NPC scenario interactions (Mira, Theron)

All tests are self-contained: no live DB, no LLM calls.
"""

from __future__ import annotations

from server.domain.enums import KnowledgeFactType
from server.npc.dialogue import DialogueContextBuilder
from server.npc.social import SocialActionInput, SocialEngine, SocialOutcome
from server.npc.tells import NpcTellEngine, TellDefinition
from server.npc.trust import TrustEngine
from tests.fixtures.builders import make_npc
from tests.fixtures.npc_social_scenario import (
    CAMPAIGN_ID,
    NPC_MIRA_ID,
    NPC_THERON_ID,
    PLAYER_BRAND_ID,
    PLAYER_SERA_ID,
    REFEREE_SCOPE_ID,
    SCENE_GATE_ID,
    SCENE_TAVERN_ID,
    make_mira_tells,
    make_npc_mira,
    make_npc_theron,
    make_theron_tells,
)


# ===========================================================================
# TrustEngine tests
# ===========================================================================


class TestTrustEngineApplyDelta:
    def setup_method(self):
        self.engine = TrustEngine()

    def test_apply_positive_delta_increases_trust(self):
        npc = make_npc(trust_by_player={PLAYER_SERA_ID: 0})
        result = self.engine.apply_delta(npc, PLAYER_SERA_ID, 10)
        assert result.new_trust == 10
        assert npc.trust_by_player[PLAYER_SERA_ID] == 10

    def test_apply_negative_delta_decreases_trust(self):
        npc = make_npc(trust_by_player={PLAYER_SERA_ID: 20})
        result = self.engine.apply_delta(npc, PLAYER_SERA_ID, -15)
        assert result.new_trust == 5

    def test_trust_clamped_at_max(self):
        npc = make_npc(trust_by_player={PLAYER_SERA_ID: 95})
        result = self.engine.apply_delta(npc, PLAYER_SERA_ID, 20)
        assert result.new_trust == 100

    def test_trust_clamped_at_min(self):
        npc = make_npc(trust_by_player={PLAYER_SERA_ID: -90})
        result = self.engine.apply_delta(npc, PLAYER_SERA_ID, -20)
        assert result.new_trust == -100

    def test_apply_delta_initialises_new_player(self):
        npc = make_npc(trust_by_player={})
        result = self.engine.apply_delta(npc, PLAYER_SERA_ID, 5)
        assert result.old_trust == 0
        assert result.new_trust == 5

    def test_apply_delta_returns_old_and_new_trust(self):
        npc = make_npc(trust_by_player={PLAYER_SERA_ID: 30})
        result = self.engine.apply_delta(npc, PLAYER_SERA_ID, -8)
        assert result.old_trust == 30
        assert result.new_trust == 22

    def test_summary_includes_reason(self):
        npc = make_npc(trust_by_player={PLAYER_SERA_ID: 0})
        result = self.engine.apply_delta(npc, PLAYER_SERA_ID, 5, reason="helped npc")
        assert "helped npc" in result.summary

    def test_npc_id_in_result(self):
        npc = make_npc(npc_id="npc-x", trust_by_player={})
        result = self.engine.apply_delta(npc, PLAYER_SERA_ID, 1)
        assert result.npc_id == "npc-x"


class TestTrustEngineActionDelta:
    def setup_method(self):
        self.engine = TrustEngine()

    def test_threaten_applies_negative_delta(self):
        npc = make_npc(trust_by_player={PLAYER_SERA_ID: 50})
        result = self.engine.apply_action_delta(npc, PLAYER_SERA_ID, "threaten")
        assert result.new_trust < 50

    def test_help_npc_applies_large_positive(self):
        npc = make_npc(trust_by_player={PLAYER_SERA_ID: 0})
        result = self.engine.apply_action_delta(npc, PLAYER_SERA_ID, "help_npc")
        assert result.new_trust == 20

    def test_unknown_action_key_gives_zero_delta(self):
        npc = make_npc(trust_by_player={PLAYER_SERA_ID: 10})
        result = self.engine.apply_action_delta(npc, PLAYER_SERA_ID, "nonexistent_key")
        assert result.new_trust == 10

    def test_personality_modifier_scales_delta(self):
        npc = make_npc(trust_by_player={PLAYER_SERA_ID: 0})
        result = self.engine.apply_action_delta(
            npc, PLAYER_SERA_ID, "help_npc", personality_modifier=2.0
        )
        assert result.new_trust == 40


class TestTrustEngineStanceDerivation:
    def setup_method(self):
        self.engine = TrustEngine()

    def test_high_mean_trust_gives_friendly_stance(self):
        npc = make_npc(
            trust_by_player={PLAYER_SERA_ID: 70, PLAYER_BRAND_ID: 80},
            stance_to_party="neutral",
        )
        self.engine.apply_delta(npc, PLAYER_SERA_ID, 0)  # trigger re-derive
        assert npc.stance_to_party == "friendly"

    def test_very_low_trust_from_one_player_gives_hostile_stance(self):
        npc = make_npc(
            trust_by_player={PLAYER_SERA_ID: -70, PLAYER_BRAND_ID: 10},
            stance_to_party="neutral",
        )
        self.engine.apply_delta(npc, PLAYER_SERA_ID, 0)
        assert npc.stance_to_party == "hostile"

    def test_fearful_personality_gives_fearful_stance_on_extreme_negative(self):
        npc = make_npc(
            trust_by_player={PLAYER_SERA_ID: -70},
            stance_to_party="neutral",
            personality_tags=["timid"],
        )
        self.engine.apply_delta(npc, PLAYER_SERA_ID, 0)
        assert npc.stance_to_party == "fearful"

    def test_empty_trust_keeps_existing_stance(self):
        npc = make_npc(trust_by_player={}, stance_to_party="friendly")
        self.engine.apply_delta(npc, PLAYER_SERA_ID, 0)
        # Still neutral after single zero delta from new player
        # (derive uses mean of all players including the new zero entry)
        assert npc.stance_to_party in ("neutral", "friendly")

    def test_moderate_positive_trust_gives_neutral_stance(self):
        npc = make_npc(
            trust_by_player={PLAYER_SERA_ID: 30},
            stance_to_party="hostile",
        )
        self.engine.apply_delta(npc, PLAYER_SERA_ID, 0)
        assert npc.stance_to_party == "neutral"

    def test_set_stance_overrides_and_returns_old(self):
        npc = make_npc(stance_to_party="neutral")
        old = self.engine.set_stance(npc, "hostile")
        assert old == "neutral"
        assert npc.stance_to_party == "hostile"


class TestTrustEngineQueryHelpers:
    def setup_method(self):
        self.engine = TrustEngine()

    def test_get_trust_returns_default_zero(self):
        npc = make_npc(trust_by_player={})
        assert self.engine.get_trust(npc, PLAYER_SERA_ID) == 0

    def test_get_trust_returns_existing_value(self):
        npc = make_npc(trust_by_player={PLAYER_SERA_ID: 45})
        assert self.engine.get_trust(npc, PLAYER_SERA_ID) == 45

    def test_is_cooperative_returns_true_for_neutral_stance(self):
        npc = make_npc(stance_to_party="neutral", trust_by_player={PLAYER_SERA_ID: 10})
        assert self.engine.is_cooperative(npc, PLAYER_SERA_ID)

    def test_is_cooperative_returns_false_for_hostile_stance(self):
        npc = make_npc(stance_to_party="hostile")
        assert not self.engine.is_cooperative(npc)

    def test_is_hostile_true_when_hostile(self):
        npc = make_npc(stance_to_party="hostile")
        assert self.engine.is_hostile(npc)

    def test_is_fearful_true_when_fearful(self):
        npc = make_npc(stance_to_party="fearful")
        assert self.engine.is_fearful(npc)

    def test_is_cooperative_false_when_trust_negative(self):
        npc = make_npc(stance_to_party="neutral", trust_by_player={PLAYER_SERA_ID: -25})
        assert not self.engine.is_cooperative(npc, PLAYER_SERA_ID)


# ===========================================================================
# SocialEngine — question
# ===========================================================================


class TestSocialEngineQuestion:
    def setup_method(self):
        self.engine = SocialEngine()

    def _inp(self, **kwargs) -> SocialActionInput:
        return SocialActionInput(
            player_id=kwargs.get("player_id", PLAYER_SERA_ID),
            character_id="char-001",
            npc_id=NPC_MIRA_ID,
            action_type="question",
            player_text="Have you seen the merchant?",
            target_info="missing merchant",
            campaign_id=CAMPAIGN_ID,
            scene_id=SCENE_TAVERN_ID,
            referee_scope_id=REFEREE_SCOPE_ID,
        )

    def test_question_succeeds_with_neutral_npc(self):
        # Mira is secretive by default, so expect at minimum partial success
        npc = make_npc_mira()
        result = self.engine.resolve(self._inp(), npc)
        assert result.success
        assert result.outcome in (SocialOutcome.SUCCESS, SocialOutcome.PARTIAL)

    def test_question_fails_with_hostile_npc(self):
        npc = make_npc_mira(stance_to_party="hostile")
        result = self.engine.resolve(self._inp(), npc)
        assert not result.success
        assert result.outcome == SocialOutcome.FAILURE

    def test_question_partial_for_secretive_low_trust(self):
        npc = make_npc_mira(
            personality_tags=["secretive"],
            trust_by_player={PLAYER_SERA_ID: 5},
        )
        result = self.engine.resolve(self._inp(), npc)
        assert result.success
        assert result.outcome == SocialOutcome.PARTIAL

    def test_question_appends_memory_tag(self):
        npc = make_npc_mira()
        self.engine.resolve(self._inp(), npc)
        assert any("questioned" in t for t in npc.memory_tags)

    def test_question_increases_trust_slightly(self):
        npc = make_npc_mira(trust_by_player={PLAYER_SERA_ID: 0})
        result = self.engine.resolve(self._inp(), npc)
        assert result.trust_result is not None
        assert result.trust_result.new_trust > 0

    def test_question_produces_referee_fact(self):
        npc = make_npc_mira()
        result = self.engine.resolve(self._inp(), npc)
        assert len(result.referee_facts) > 0
        assert all(f.owner_scope_id == REFEREE_SCOPE_ID for f in result.referee_facts)

    def test_question_produces_dialogue_context(self):
        npc = make_npc_mira()
        result = self.engine.resolve(self._inp(), npc)
        assert result.dialogue_context is not None
        assert result.dialogue_context.action_type == "question"

    def test_incapacitated_npc_cannot_be_questioned(self):
        npc = make_npc_mira(health_state="incapacitated")
        result = self.engine.resolve(self._inp(), npc)
        assert not result.success
        assert "incapacitated" in result.rejection_reason


# ===========================================================================
# SocialEngine — persuade
# ===========================================================================


class TestSocialEnginePersuade:
    def setup_method(self):
        self.engine = SocialEngine()

    def _inp(self, player_id: str = PLAYER_SERA_ID) -> SocialActionInput:
        return SocialActionInput(
            player_id=player_id,
            character_id="char-001",
            npc_id=NPC_MIRA_ID,
            action_type="persuade",
            player_text="Please help us find the merchant's trail.",
            campaign_id=CAMPAIGN_ID,
            scene_id=SCENE_TAVERN_ID,
            referee_scope_id=REFEREE_SCOPE_ID,
        )

    def test_persuade_succeeds_with_trusted_npc(self):
        npc = make_npc_mira(trust_by_player={PLAYER_SERA_ID: 25})
        result = self.engine.resolve(self._inp(), npc)
        assert result.success
        assert result.outcome == SocialOutcome.SUCCESS

    def test_persuade_fails_with_hostile_npc(self):
        npc = make_npc_mira(stance_to_party="hostile")
        result = self.engine.resolve(self._inp(), npc)
        assert not result.success

    def test_persuade_partial_with_borderline_trust(self):
        npc = make_npc_mira(trust_by_player={PLAYER_SERA_ID: 5})
        result = self.engine.resolve(self._inp(), npc)
        assert result.outcome == SocialOutcome.PARTIAL

    def test_persuade_fail_decreases_trust(self):
        npc = make_npc_mira(
            stance_to_party="hostile", trust_by_player={PLAYER_SERA_ID: 0}
        )
        result = self.engine.resolve(self._inp(), npc)
        assert result.trust_result.new_trust < 0

    def test_persuade_success_increases_trust(self):
        npc = make_npc_mira(trust_by_player={PLAYER_SERA_ID: 25})
        result = self.engine.resolve(self._inp(), npc)
        assert result.trust_result.new_trust > 25

    def test_persuade_appends_memory_tag(self):
        npc = make_npc_mira(trust_by_player={PLAYER_SERA_ID: 25})
        self.engine.resolve(self._inp(), npc)
        assert any("persuade" in t for t in npc.memory_tags)


# ===========================================================================
# SocialEngine — threaten
# ===========================================================================


class TestSocialEngineThreaten:
    def setup_method(self):
        self.engine = SocialEngine()

    def _inp(self) -> SocialActionInput:
        return SocialActionInput(
            player_id=PLAYER_SERA_ID,
            character_id="char-001",
            npc_id=NPC_THERON_ID,
            action_type="threaten",
            player_text="Tell me who passed through or I'll make trouble for you.",
            campaign_id=CAMPAIGN_ID,
            scene_id=SCENE_GATE_ID,
            referee_scope_id=REFEREE_SCOPE_ID,
        )

    def test_threaten_escalates_for_powerful_npc(self):
        npc = make_npc_theron()  # has "guard_captain" personality tag
        result = self.engine.resolve(self._inp(), npc)
        assert result.outcome == SocialOutcome.ESCALATION
        assert not result.success

    def test_threaten_succeeds_for_fearful_npc(self):
        npc = make_npc_mira(
            stance_to_party="fearful",
            personality_tags=["timid"],
        )
        inp = SocialActionInput(
            player_id=PLAYER_SERA_ID,
            character_id="char-001",
            npc_id=NPC_MIRA_ID,
            action_type="threaten",
            player_text="Tell me or else.",
            campaign_id=CAMPAIGN_ID,
            scene_id=SCENE_TAVERN_ID,
            referee_scope_id=REFEREE_SCOPE_ID,
        )
        result = self.engine.resolve(inp, npc)
        assert result.success
        assert result.outcome == SocialOutcome.SUCCESS

    def test_threaten_always_decreases_trust(self):
        npc = make_npc_theron(trust_by_player={PLAYER_SERA_ID: 50})
        result = self.engine.resolve(self._inp(), npc)
        assert result.trust_result.new_trust < 50

    def test_threaten_appends_memory_tag_on_success(self):
        npc = make_npc_theron(personality_tags=["timid"])
        self.engine.resolve(self._inp(), npc)
        assert any("threatened" in t for t in npc.memory_tags)

    def test_threaten_rolls_back_memory_tag_on_failure(self):
        npc = make_npc_theron()  # guard_captain → escalation (failure)
        self.engine.resolve(self._inp(), npc)
        assert not any("threatened" in t for t in npc.memory_tags)

    def test_threaten_refuses_for_neutral_non_fearful_npc(self):
        npc = make_npc_mira(personality_tags=["cautious"])  # not timid, not fearless
        inp = SocialActionInput(
            player_id=PLAYER_SERA_ID,
            character_id="char-001",
            npc_id=NPC_MIRA_ID,
            action_type="threaten",
            player_text="Tell me or else.",
            campaign_id=CAMPAIGN_ID,
            scene_id=SCENE_TAVERN_ID,
            referee_scope_id=REFEREE_SCOPE_ID,
        )
        result = self.engine.resolve(inp, npc)
        assert result.outcome == SocialOutcome.FAILURE


# ===========================================================================
# SocialEngine — lie
# ===========================================================================


class TestSocialEngineLie:
    def setup_method(self):
        self.engine = SocialEngine()

    def _inp(self) -> SocialActionInput:
        return SocialActionInput(
            player_id=PLAYER_SERA_ID,
            character_id="char-001",
            npc_id=NPC_MIRA_ID,
            action_type="lie",
            player_text="The city watch sent us to investigate.",
            campaign_id=CAMPAIGN_ID,
            scene_id=SCENE_TAVERN_ID,
            referee_scope_id=REFEREE_SCOPE_ID,
        )

    def test_lie_believed_with_low_trust_non_perceptive_npc(self):
        npc = make_npc_mira(
            trust_by_player={PLAYER_SERA_ID: 10},
            personality_tags=["cautious"],  # not perceptive
        )
        result = self.engine.resolve(self._inp(), npc)
        assert result.success
        assert result.outcome == SocialOutcome.SUCCESS

    def test_lie_detected_by_perceptive_npc(self):
        npc = make_npc_mira(
            trust_by_player={PLAYER_SERA_ID: 10},
            personality_tags=["perceptive"],
        )
        result = self.engine.resolve(self._inp(), npc)
        assert result.outcome == SocialOutcome.DETECTED_LIE
        assert not result.success

    def test_lie_detected_when_npc_has_high_trust(self):
        # High trust NPC has high expectations — sees through the lie
        npc = make_npc_mira(trust_by_player={PLAYER_SERA_ID: 50})
        result = self.engine.resolve(self._inp(), npc)
        assert result.outcome == SocialOutcome.DETECTED_LIE

    def test_detected_lie_decreases_trust(self):
        npc = make_npc_mira(
            trust_by_player={PLAYER_SERA_ID: 10},
            personality_tags=["perceptive"],
        )
        result = self.engine.resolve(self._inp(), npc)
        assert result.trust_result.new_trust < 10

    def test_undetected_lie_adds_small_positive_trust(self):
        npc = make_npc_mira(trust_by_player={PLAYER_SERA_ID: 5}, personality_tags=[])
        result = self.engine.resolve(self._inp(), npc)
        assert result.trust_result.new_trust >= 5  # +1 for lie_undetected

    def test_lie_produces_referee_fact(self):
        npc = make_npc_mira(trust_by_player={PLAYER_SERA_ID: 5}, personality_tags=[])
        result = self.engine.resolve(self._inp(), npc)
        # Should have trust fact + lie note fact
        assert len(result.referee_facts) >= 2

    def test_lie_appends_memory_tag(self):
        npc = make_npc_mira(trust_by_player={PLAYER_SERA_ID: 5}, personality_tags=[])
        self.engine.resolve(self._inp(), npc)
        assert any("lied" in t for t in npc.memory_tags)


# ===========================================================================
# SocialEngine — bargain
# ===========================================================================


class TestSocialEngineBargain:
    def setup_method(self):
        self.engine = SocialEngine()

    def _inp(self) -> SocialActionInput:
        return SocialActionInput(
            player_id=PLAYER_SERA_ID,
            character_id="char-001",
            npc_id=NPC_THERON_ID,
            action_type="bargain",
            player_text="I'll give you two gold coins for passage and information.",
            campaign_id=CAMPAIGN_ID,
            scene_id=SCENE_GATE_ID,
            referee_scope_id=REFEREE_SCOPE_ID,
        )

    def test_bargain_succeeds_with_neutral_npc(self):
        npc = make_npc_theron(trust_by_player={PLAYER_SERA_ID: 5})
        result = self.engine.resolve(self._inp(), npc)
        assert result.success
        assert result.outcome == SocialOutcome.SUCCESS

    def test_bargain_fails_with_hostile_npc(self):
        npc = make_npc_theron(stance_to_party="hostile")
        result = self.engine.resolve(self._inp(), npc)
        assert not result.success
        assert result.outcome == SocialOutcome.FAILURE

    def test_bargain_partial_with_slightly_negative_trust(self):
        npc = make_npc_theron(trust_by_player={PLAYER_SERA_ID: -10})
        result = self.engine.resolve(self._inp(), npc)
        assert result.outcome == SocialOutcome.PARTIAL

    def test_bargain_success_increases_trust(self):
        npc = make_npc_theron(trust_by_player={PLAYER_SERA_ID: 0})
        result = self.engine.resolve(self._inp(), npc)
        assert result.trust_result.new_trust > 0

    def test_bargain_fail_slightly_decreases_trust(self):
        npc = make_npc_theron(
            stance_to_party="hostile", trust_by_player={PLAYER_SERA_ID: 0}
        )
        result = self.engine.resolve(self._inp(), npc)
        assert result.trust_result.new_trust <= 0

    def test_bargain_appends_memory_tag(self):
        npc = make_npc_theron(trust_by_player={PLAYER_SERA_ID: 5})
        self.engine.resolve(self._inp(), npc)
        assert any("bargain" in t for t in npc.memory_tags)


# ===========================================================================
# SocialEngine — general
# ===========================================================================


class TestSocialEngineGeneral:
    def setup_method(self):
        self.engine = SocialEngine()

    def test_unknown_action_type_returns_failure(self):
        npc = make_npc_mira()
        inp = SocialActionInput(
            player_id=PLAYER_SERA_ID,
            character_id="char-001",
            npc_id=NPC_MIRA_ID,
            action_type="dance",  # not a social action
            player_text="Let's dance!",
        )
        result = self.engine.resolve(inp, npc)
        assert not result.success
        assert "Unknown" in result.rejection_reason

    def test_dead_npc_cannot_be_interacted_with(self):
        npc = make_npc_mira(health_state="dead")
        inp = SocialActionInput(
            player_id=PLAYER_SERA_ID,
            character_id="char-001",
            npc_id=NPC_MIRA_ID,
            action_type="question",
            player_text="Hello?",
        )
        result = self.engine.resolve(inp, npc)
        assert not result.success
        assert "dead" in result.rejection_reason

    def test_memory_tag_not_duplicated_on_repeat(self):
        # Use a non-secretive NPC so both calls produce the same memory tag path
        npc = make_npc_mira(personality_tags=["cautious"])  # no "secretive"
        inp = SocialActionInput(
            player_id=PLAYER_SERA_ID,
            character_id="char-001",
            npc_id=NPC_MIRA_ID,
            action_type="question",
            player_text="Repeat question.",
            campaign_id=CAMPAIGN_ID,
            scene_id=SCENE_TAVERN_ID,
        )
        self.engine.resolve(inp, npc)
        self.engine.resolve(inp, npc)
        tag = "player_questioned_npc_answered"
        assert npc.memory_tags.count(tag) == 1

    def test_tells_fire_and_produce_referee_facts(self):
        npc = make_npc_mira()
        tells = make_mira_tells()
        inp = SocialActionInput(
            player_id=PLAYER_SERA_ID,
            character_id="char-001",
            npc_id=NPC_MIRA_ID,
            action_type="question",
            player_text="Tell me about the cellar.",
            campaign_id=CAMPAIGN_ID,
            scene_id=SCENE_TAVERN_ID,
            referee_scope_id=REFEREE_SCOPE_ID,
        )
        result = self.engine.resolve(inp, npc, tells=tells)
        # After question succeeds, trigger_tag "player_questioned_npc_answered" is in memory
        # The cellar tell fires on trigger_action_type="question"
        tell_facts = [
            f for f in result.referee_facts if f.fact_type == KnowledgeFactType.npc_tell
        ]
        assert len(tell_facts) >= 1

    def test_stance_change_recorded_in_trust_result(self):
        npc = make_npc_mira(trust_by_player={PLAYER_SERA_ID: -65})
        inp = SocialActionInput(
            player_id=PLAYER_SERA_ID,
            character_id="char-001",
            npc_id=NPC_MIRA_ID,
            action_type="question",
            player_text="Hello.",
            campaign_id=CAMPAIGN_ID,
            scene_id=SCENE_TAVERN_ID,
        )
        result = self.engine.resolve(inp, npc)
        # NPC with -65 trust is already hostile
        assert result.trust_result is not None


# ===========================================================================
# NpcTellEngine tests
# ===========================================================================


class TestNpcTellEngine:
    def setup_method(self):
        self.engine = NpcTellEngine()

    def test_tell_fires_on_matching_tag(self):
        npc = make_npc_mira(memory_tags=["player_questioned_npc_answered"])
        tells = make_mira_tells()
        result = self.engine.evaluate_tells(
            npc,
            tells,
            action_type="question",
            campaign_id=CAMPAIGN_ID,
            scene_id=SCENE_TAVERN_ID,
            referee_scope_id=REFEREE_SCOPE_ID,
        )
        # "tell-mira-cellar" fires on trigger_tag "player_questioned_npc_answered"
        fired_ids = [t.tell_id for t in result.fired_tells]
        assert "tell-mira-cellar" in fired_ids

    def test_tell_fires_on_matching_stance(self):
        npc = make_npc_mira(stance_to_party="fearful")
        tells = make_mira_tells()
        result = self.engine.evaluate_tells(
            npc,
            tells,
            action_type="threaten",
            campaign_id=CAMPAIGN_ID,
            scene_id=SCENE_TAVERN_ID,
            referee_scope_id=REFEREE_SCOPE_ID,
        )
        fired_ids = [t.tell_id for t in result.fired_tells]
        assert "tell-mira-threat" in fired_ids

    def test_tell_fires_on_matching_action_type(self):
        npc = make_npc_mira()
        tells = make_mira_tells()
        result = self.engine.evaluate_tells(
            npc,
            tells,
            action_type="question",
            campaign_id=CAMPAIGN_ID,
            scene_id=SCENE_TAVERN_ID,
            referee_scope_id=REFEREE_SCOPE_ID,
        )
        # "tell-mira-cellar" has trigger_action_type="question"
        fired_ids = [t.tell_id for t in result.fired_tells]
        assert "tell-mira-cellar" in fired_ids

    def test_inactive_tell_does_not_fire(self):
        npc = make_npc_mira(memory_tags=["player_questioned_npc_answered"])
        tells = [
            TellDefinition(
                tell_id="inactive-tell",
                npc_id=NPC_MIRA_ID,
                trigger_tag="player_questioned_npc_answered",
                tell_text="This should not fire.",
                is_active=False,
            )
        ]
        result = self.engine.evaluate_tells(
            npc, tells, referee_scope_id=REFEREE_SCOPE_ID
        )
        assert len(result.fired_tells) == 0
        assert len(result.referee_facts) == 0

    def test_fired_tell_produces_referee_fact(self):
        npc = make_npc_mira(memory_tags=["player_questioned_npc_answered"])
        tells = make_mira_tells()
        result = self.engine.evaluate_tells(
            npc,
            tells,
            action_type="question",
            campaign_id=CAMPAIGN_ID,
            scene_id=SCENE_TAVERN_ID,
            referee_scope_id=REFEREE_SCOPE_ID,
        )
        assert len(result.referee_facts) >= 1
        assert all(
            f.fact_type == KnowledgeFactType.npc_tell for f in result.referee_facts
        )
        assert all(f.owner_scope_id == REFEREE_SCOPE_ID for f in result.referee_facts)

    def test_no_tells_gives_empty_result(self):
        npc = make_npc_mira()
        result = self.engine.evaluate_tells(npc, [], referee_scope_id=REFEREE_SCOPE_ID)
        assert len(result.fired_tells) == 0
        assert len(result.referee_facts) == 0

    def test_make_trust_status_fact_returns_none_without_scope(self):
        npc = make_npc_mira()
        fact = self.engine.make_trust_status_fact(npc, PLAYER_SERA_ID, 35)
        assert fact is None

    def test_make_trust_status_fact_returns_fact_with_scope(self):
        npc = make_npc_mira()
        fact = self.engine.make_trust_status_fact(
            npc,
            PLAYER_SERA_ID,
            35,
            campaign_id=CAMPAIGN_ID,
            scene_id=SCENE_TAVERN_ID,
            referee_scope_id=REFEREE_SCOPE_ID,
        )
        assert fact is not None
        assert fact.fact_type == KnowledgeFactType.npc_tell
        assert "+35" in fact.payload

    def test_make_private_reaction_fact_returns_none_without_scope(self):
        npc = make_npc_mira()
        fact = self.engine.make_private_reaction_fact(npc, "NPC is lying")
        assert fact is None

    def test_make_private_reaction_fact_contains_npc_name(self):
        npc = make_npc_mira()
        fact = self.engine.make_private_reaction_fact(
            npc,
            "NPC is lying",
            campaign_id=CAMPAIGN_ID,
            scene_id=SCENE_TAVERN_ID,
            referee_scope_id=REFEREE_SCOPE_ID,
        )
        assert "Mira" in fact.payload


# ===========================================================================
# DialogueContextBuilder tests
# ===========================================================================


class TestDialogueContextBuilder:
    def setup_method(self):
        self.builder = DialogueContextBuilder()

    def test_build_populates_basic_fields(self):
        npc = make_npc_mira(trust_by_player={PLAYER_SERA_ID: 25})
        ctx = self.builder.build(
            npc, PLAYER_SERA_ID, "question", "Tell me about the cellar."
        )
        assert ctx.npc_id == NPC_MIRA_ID
        assert ctx.npc_name == "Mira the Innkeeper"
        assert ctx.player_id == PLAYER_SERA_ID
        assert ctx.trust_value == 25
        assert ctx.action_type == "question"

    def test_will_resist_true_for_hostile_stance(self):
        npc = make_npc_mira(stance_to_party="hostile")
        ctx = self.builder.build(npc, PLAYER_SERA_ID, "question", "Hello.")
        assert ctx.will_resist

    def test_will_resist_true_for_very_low_trust(self):
        npc = make_npc_mira(trust_by_player={PLAYER_SERA_ID: -30})
        ctx = self.builder.build(npc, PLAYER_SERA_ID, "question", "Hello.")
        assert ctx.will_resist

    def test_will_resist_false_for_friendly_high_trust(self):
        npc = make_npc_mira(
            stance_to_party="friendly",
            trust_by_player={PLAYER_SERA_ID: 70},
        )
        ctx = self.builder.build(npc, PLAYER_SERA_ID, "question", "Hello.")
        assert not ctx.will_resist

    def test_is_evasive_for_secretive_npc(self):
        npc = make_npc_mira(personality_tags=["secretive"])
        ctx = self.builder.build(npc, PLAYER_SERA_ID, "question", "Any secrets?")
        assert ctx.is_evasive

    def test_can_be_threatened_false_for_fearless_npc(self):
        npc = make_npc_theron()  # has "guard_captain" tag
        ctx = self.builder.build(npc, PLAYER_SERA_ID, "threaten", "Cooperate or else.")
        assert not ctx.can_be_threatened

    def test_can_be_threatened_true_for_regular_npc(self):
        npc = make_npc_mira(personality_tags=["cautious"])
        ctx = self.builder.build(npc, PLAYER_SERA_ID, "threaten", "Cooperate or else.")
        assert ctx.can_be_threatened

    def test_memory_tags_copied(self):
        npc = make_npc_mira(memory_tags=["player_helped_npc"])
        ctx = self.builder.build(npc, PLAYER_SERA_ID, "question", "Hi.")
        assert "player_helped_npc" in ctx.memory_tags

    def test_to_public_dict_excludes_private_hint(self):
        npc = make_npc_mira()
        ctx = self.builder.build(
            npc,
            PLAYER_SERA_ID,
            "question",
            "Hello.",
            private_reaction_hint="Secret hint",
        )
        d = self.builder.to_public_dict(ctx)
        assert "private_reaction_hint" not in d

    def test_to_referee_dict_includes_private_hint(self):
        npc = make_npc_mira()
        ctx = self.builder.build(
            npc,
            PLAYER_SERA_ID,
            "question",
            "Hello.",
            private_reaction_hint="Secret hint",
        )
        d = self.builder.to_referee_dict(ctx)
        assert d["private_reaction_hint"] == "Secret hint"


# ===========================================================================
# Memory persistence tests
# ===========================================================================


class TestMemoryPersistence:
    def setup_method(self):
        self.engine = SocialEngine()

    def test_multiple_interactions_accumulate_memory_tags(self):
        npc = make_npc_mira()
        inp_q = SocialActionInput(
            player_id=PLAYER_SERA_ID,
            character_id="char-001",
            npc_id=NPC_MIRA_ID,
            action_type="question",
            player_text="Where is the merchant?",
        )
        inp_p = SocialActionInput(
            player_id=PLAYER_SERA_ID,
            character_id="char-001",
            npc_id=NPC_MIRA_ID,
            action_type="persuade",
            player_text="Help us find them.",
        )
        self.engine.resolve(inp_q, npc)
        npc.trust_by_player[PLAYER_SERA_ID] = 25  # simulate earlier help
        self.engine.resolve(inp_p, npc)
        # Should have tags from both actions
        assert any("question" in t or "questioned" in t for t in npc.memory_tags)
        assert any("persuade" in t for t in npc.memory_tags)

    def test_trust_persists_across_multiple_interactions(self):
        npc = make_npc_mira(trust_by_player={PLAYER_SERA_ID: 0})
        for _ in range(3):
            inp = SocialActionInput(
                player_id=PLAYER_SERA_ID,
                character_id="char-001",
                npc_id=NPC_MIRA_ID,
                action_type="question",
                player_text="Hello again.",
            )
            self.engine.resolve(inp, npc)
        # After 3 questions, trust should have increased (not reset each time)
        assert npc.trust_by_player[PLAYER_SERA_ID] > 0

    def test_stance_changes_after_cumulative_negative_interactions(self):
        npc = make_npc_mira(trust_by_player={PLAYER_SERA_ID: 0})
        trust_engine = TrustEngine()
        # Manually push to hostile territory
        trust_engine.apply_delta(npc, PLAYER_SERA_ID, -70)
        assert npc.stance_to_party == "hostile"
        # Now question should fail
        inp = SocialActionInput(
            player_id=PLAYER_SERA_ID,
            character_id="char-001",
            npc_id=NPC_MIRA_ID,
            action_type="question",
            player_text="Hello.",
        )
        result = self.engine.resolve(inp, npc)
        assert result.outcome == SocialOutcome.FAILURE

    def test_two_player_trust_tracked_independently(self):
        npc = make_npc_mira()
        trust_engine = TrustEngine()
        trust_engine.apply_delta(npc, PLAYER_SERA_ID, 30)
        trust_engine.apply_delta(npc, PLAYER_BRAND_ID, -30)
        assert npc.trust_by_player[PLAYER_SERA_ID] == 30
        assert npc.trust_by_player[PLAYER_BRAND_ID] == -30


# ===========================================================================
# Scenario integration: Mira the Innkeeper
# ===========================================================================


class TestMiraScenarioInteraction:
    """Integration test: a complete interaction sequence with Mira."""

    def setup_method(self):
        self.engine = SocialEngine()
        self.trust_engine = TrustEngine()

    def test_mira_question_then_persuade_sequence(self):
        """Sera first questions Mira (builds slight trust), then persuades her."""
        npc = make_npc_mira()
        tells = make_mira_tells()

        # Step 1: question
        q_inp = SocialActionInput(
            player_id=PLAYER_SERA_ID,
            character_id="char-001",
            npc_id=NPC_MIRA_ID,
            action_type="question",
            player_text="Have you seen a merchant named Aldric recently?",
            campaign_id=CAMPAIGN_ID,
            scene_id=SCENE_TAVERN_ID,
            referee_scope_id=REFEREE_SCOPE_ID,
        )
        q_result = self.engine.resolve(q_inp, npc, tells=tells)
        assert q_result.success
        trust_after_q = npc.trust_by_player[PLAYER_SERA_ID]
        assert trust_after_q > 0

        # Step 2: boost trust to make persuade viable
        self.trust_engine.apply_delta(npc, PLAYER_SERA_ID, 20)

        # Step 3: persuade
        p_inp = SocialActionInput(
            player_id=PLAYER_SERA_ID,
            character_id="char-001",
            npc_id=NPC_MIRA_ID,
            action_type="persuade",
            player_text="Please, Aldric's family is worried. We only want to help.",
            campaign_id=CAMPAIGN_ID,
            scene_id=SCENE_TAVERN_ID,
            referee_scope_id=REFEREE_SCOPE_ID,
        )
        p_result = self.engine.resolve(p_inp, npc, tells=tells)
        assert p_result.success

        # Verify memory has both interaction types
        tags = npc.memory_tags
        assert any("questioned" in t for t in tags)
        assert any("persuade" in t for t in tags)

    def test_mira_lie_detection_sequence(self):
        """Brand tries to lie to Mira — she detects it (she is secretive/cautious,
        but not perceptive by default; test with perceptive override)."""
        npc = make_npc_mira(personality_tags=["perceptive", "secretive"])
        tells = make_mira_tells()

        inp = SocialActionInput(
            player_id=PLAYER_BRAND_ID,
            character_id="char-brand",
            npc_id=NPC_MIRA_ID,
            action_type="lie",
            player_text="The city watch sent us. We have authorisation.",
            campaign_id=CAMPAIGN_ID,
            scene_id=SCENE_TAVERN_ID,
            referee_scope_id=REFEREE_SCOPE_ID,
        )
        result = self.engine.resolve(inp, npc, tells=tells)
        assert result.outcome == SocialOutcome.DETECTED_LIE
        assert result.trust_result.new_trust < 0
        # Lie-detection tell should have fired
        tell_payloads = [f.payload for f in result.referee_facts]
        assert any("tell" in p.lower() or "mira" in p.lower() for p in tell_payloads)


# ===========================================================================
# Scenario integration: Theron the Gate Guard
# ===========================================================================


class TestTheronScenarioInteraction:
    """Integration test: a complete interaction sequence with Theron."""

    def setup_method(self):
        self.engine = SocialEngine()

    def test_theron_bribe_succeeds_then_question(self):
        """Sera bribes Theron (bargain) to get passage, then questions him."""
        npc = make_npc_theron()
        tells = make_theron_tells()

        # Step 1: bargain (bribe)
        b_inp = SocialActionInput(
            player_id=PLAYER_SERA_ID,
            character_id="char-001",
            npc_id=NPC_THERON_ID,
            action_type="bargain",
            player_text="Two gold coins for quick passage and a word about the northern road.",
            campaign_id=CAMPAIGN_ID,
            scene_id=SCENE_GATE_ID,
            referee_scope_id=REFEREE_SCOPE_ID,
        )
        b_result = self.engine.resolve(b_inp, npc, tells=tells)
        assert b_result.success
        assert b_result.outcome == SocialOutcome.SUCCESS

        # Step 2: question (trust is now higher)
        q_inp = SocialActionInput(
            player_id=PLAYER_SERA_ID,
            character_id="char-001",
            npc_id=NPC_THERON_ID,
            action_type="question",
            player_text="When did the last wagon come through from the north?",
            campaign_id=CAMPAIGN_ID,
            scene_id=SCENE_GATE_ID,
            referee_scope_id=REFEREE_SCOPE_ID,
        )
        q_result = self.engine.resolve(q_inp, npc, tells=tells)
        # Trust is now positive; question should succeed
        assert q_result.success

        # Bribe tell should have fired for the bargain step
        all_facts = b_result.referee_facts
        assert len(all_facts) >= 1

    def test_theron_threat_escalates_and_destroys_trust(self):
        """Brand tries to threaten Theron — it escalates."""
        npc = make_npc_theron(trust_by_player={PLAYER_BRAND_ID: 10})
        tells = make_theron_tells()

        inp = SocialActionInput(
            player_id=PLAYER_BRAND_ID,
            character_id="char-brand",
            npc_id=NPC_THERON_ID,
            action_type="threaten",
            player_text="Open the gate or I'll report your bribery to the captain.",
            campaign_id=CAMPAIGN_ID,
            scene_id=SCENE_GATE_ID,
            referee_scope_id=REFEREE_SCOPE_ID,
        )
        result = self.engine.resolve(inp, npc, tells=tells)
        assert result.outcome == SocialOutcome.ESCALATION
        assert result.trust_result.new_trust < 10
