"""Privacy audit tests — systematic review of scope, visibility, and routing safety.

This audit covers:
  1. Scope boundary enforcement (public, private_referee, side_channel, referee_only)
  2. Context assembly safety (no leakage into LLM prompts)
  3. API endpoint safety (no cross-player data exposure)
  4. Model routing safety (main vs. fast tier separation)
  5. Edge cases (unknown scopes, closed channels, missing grants)
"""

from __future__ import annotations

import pytest

from server.domain.entities import (
    ConversationScope,
    KnowledgeFact,
    SideChannel,
    VisibilityGrant,
)
from server.domain.enums import KnowledgeFactType, ScopeType
from server.scope.engine import ScopeEngine, ScopeViolationError
from server.scope.facts import FactOwnershipPolicy
from server.scope.leakage_guard import LeakageGuard
from server.scope.referee import RefereeGuard
from server.scope.side_channel import SideChannelPolicy
from models.fast.router import is_fast_tier, is_main_tier_only
from models.main.router import is_main_tier
from server.domain.helpers import new_id as _uid, utc_now as _now


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scope(
    scope_type: ScopeType,
    player_id: str | None = None,
    side_channel_id: str | None = None,
) -> ConversationScope:
    return ConversationScope(
        scope_id=_uid(),
        campaign_id="c1",
        scope_type=scope_type,
        player_id=player_id,
        side_channel_id=side_channel_id,
    )


def _fact(
    owner_scope_id: str,
    fact_type: KnowledgeFactType = KnowledgeFactType.clue,
    payload: str = "test payload",
) -> KnowledgeFact:
    return KnowledgeFact(
        fact_id=_uid(),
        campaign_id="c1",
        scene_id="sc1",
        owner_scope_id=owner_scope_id,
        fact_type=fact_type,
        payload=payload,
        revealed_at=_now(),
    )


def _channel(member_ids: list[str], is_open: bool = True) -> SideChannel:
    return SideChannel(
        side_channel_id=_uid(),
        campaign_id="c1",
        created_by_player_id=member_ids[0],
        member_player_ids=list(member_ids),
        is_open=is_open,
        created_at=_now(),
    )


# ---------------------------------------------------------------------------
# 1. Scope boundary enforcement
# ---------------------------------------------------------------------------


class TestScopeBoundaryEnforcement:
    """Verify that each scope type enforces its visibility boundary."""

    def setup_method(self):
        self.engine = ScopeEngine()
        self.player_a = "player-a"
        self.player_b = "player-b"
        self.player_c = "player-c"
        self.all_players = [self.player_a, self.player_b, self.player_c]

    def test_public_fact_visible_to_all_players(self):
        scope = _scope(ScopeType.public)
        fact = _fact(scope.scope_id)
        for pid in self.all_players:
            assert self.engine.can_player_see_fact(pid, fact, scope, [])

    def test_private_referee_fact_visible_only_to_owner(self):
        scope = _scope(ScopeType.private_referee, player_id=self.player_a)
        fact = _fact(scope.scope_id)
        assert self.engine.can_player_see_fact(self.player_a, fact, scope, [])
        assert not self.engine.can_player_see_fact(self.player_b, fact, scope, [])
        assert not self.engine.can_player_see_fact(self.player_c, fact, scope, [])

    def test_side_channel_fact_visible_only_to_members(self):
        ch = _channel([self.player_a, self.player_b])
        scope = _scope(ScopeType.side_channel, side_channel_id=ch.side_channel_id)
        fact = _fact(scope.scope_id)
        assert self.engine.can_player_see_fact(
            self.player_a, fact, scope, [], side_channel=ch
        )
        assert self.engine.can_player_see_fact(
            self.player_b, fact, scope, [], side_channel=ch
        )
        assert not self.engine.can_player_see_fact(
            self.player_c, fact, scope, [], side_channel=ch
        )

    def test_referee_only_fact_invisible_to_all_players(self):
        scope = _scope(ScopeType.referee_only)
        fact = _fact(scope.scope_id)
        for pid in self.all_players:
            assert not self.engine.can_player_see_fact(pid, fact, scope, [])

    def test_referee_only_delivery_raises(self):
        scope = _scope(ScopeType.referee_only)
        with pytest.raises(ScopeViolationError, match="referee_only"):
            self.engine.delivery_targets_for(scope, self.all_players)

    def test_private_referee_missing_player_id_raises(self):
        scope = _scope(ScopeType.private_referee, player_id=None)
        with pytest.raises(ScopeViolationError, match="missing player_id"):
            self.engine.delivery_targets_for(scope, self.all_players)


# ---------------------------------------------------------------------------
# 2. Context assembly safety
# ---------------------------------------------------------------------------


class TestContextAssemblySafety:
    """Verify that context assembly functions never leak forbidden facts."""

    def setup_method(self):
        self.engine = ScopeEngine()
        self.guard = LeakageGuard()
        self.player_a = "player-a"
        self.player_b = "player-b"

    def test_public_context_rejects_private_referee_fact(self):
        pub_scope = _scope(ScopeType.public)
        priv_scope = _scope(ScopeType.private_referee, player_id=self.player_a)
        pub_fact = _fact(pub_scope.scope_id, payload="public info")
        priv_fact = _fact(priv_scope.scope_id, payload="secret clue")
        scopes = {pub_scope.scope_id: pub_scope, priv_scope.scope_id: priv_scope}

        with pytest.raises(ScopeViolationError):
            self.engine.assemble_public_context([pub_fact, priv_fact], scopes)

    def test_public_context_rejects_referee_only_fact(self):
        pub_scope = _scope(ScopeType.public)
        ref_scope = _scope(ScopeType.referee_only)
        pub_fact = _fact(pub_scope.scope_id)
        ref_fact = _fact(ref_scope.scope_id, payload="hidden trap location")
        scopes = {pub_scope.scope_id: pub_scope, ref_scope.scope_id: ref_scope}

        with pytest.raises(ScopeViolationError):
            self.engine.assemble_public_context([pub_fact, ref_fact], scopes)

    def test_public_context_rejects_side_channel_fact(self):
        pub_scope = _scope(ScopeType.public)
        ch = _channel([self.player_a, self.player_b])
        sc_scope = _scope(ScopeType.side_channel, side_channel_id=ch.side_channel_id)
        pub_fact = _fact(pub_scope.scope_id)
        sc_fact = _fact(sc_scope.scope_id, payload="whispered plan")
        scopes = {pub_scope.scope_id: pub_scope, sc_scope.scope_id: sc_scope}

        with pytest.raises(ScopeViolationError):
            self.engine.assemble_public_context([pub_fact, sc_fact], scopes)

    def test_private_context_excludes_referee_only(self):
        pub_scope = _scope(ScopeType.public)
        ref_scope = _scope(ScopeType.referee_only)
        pub_fact = _fact(pub_scope.scope_id)
        ref_fact = _fact(ref_scope.scope_id, payload="trap DC 15")
        scopes = {pub_scope.scope_id: pub_scope, ref_scope.scope_id: ref_scope}

        result = self.engine.assemble_private_context(
            self.player_a,
            [pub_fact, ref_fact],
            scopes,
            grants_by_fact_id={},
            side_channels_by_id={},
        )
        assert ref_fact not in result
        assert pub_fact in result

    def test_private_context_excludes_other_players_private_facts(self):
        priv_a = _scope(ScopeType.private_referee, player_id=self.player_a)
        priv_b = _scope(ScopeType.private_referee, player_id=self.player_b)
        fact_a = _fact(priv_a.scope_id, payload="A's secret")
        fact_b = _fact(priv_b.scope_id, payload="B's secret")
        scopes = {priv_a.scope_id: priv_a, priv_b.scope_id: priv_b}

        result = self.engine.assemble_private_context(
            self.player_a,
            [fact_a, fact_b],
            scopes,
            grants_by_fact_id={},
            side_channels_by_id={},
        )
        assert fact_a in result
        assert fact_b not in result

    def test_leakage_guard_blocks_referee_in_player_prompt(self):
        ref_scope = _scope(ScopeType.referee_only)
        ref_fact = _fact(ref_scope.scope_id, payload="secret NPC intent")
        scopes = {ref_scope.scope_id: ref_scope}

        with pytest.raises(ScopeViolationError, match="referee_only"):
            self.guard.check_player_prompt(
                self.player_a,
                [ref_fact],
                scopes,
                grants_by_fact_id={},
                side_channels_by_id={},
            )

    def test_leakage_guard_blocks_invisible_fact_in_player_prompt(self):
        priv_scope = _scope(ScopeType.private_referee, player_id=self.player_b)
        priv_fact = _fact(priv_scope.scope_id, payload="B's hidden clue")
        scopes = {priv_scope.scope_id: priv_scope}

        with pytest.raises(ScopeViolationError, match="not visible"):
            self.guard.check_player_prompt(
                self.player_a,
                [priv_fact],
                scopes,
                grants_by_fact_id={},
                side_channels_by_id={},
            )


# ---------------------------------------------------------------------------
# 3. Side-channel leakage prevention
# ---------------------------------------------------------------------------


class TestSideChannelLeakagePrevention:
    """Verify side-channel membership is respected in all paths."""

    def setup_method(self):
        self.engine = ScopeEngine()
        self.policy = SideChannelPolicy()
        self.player_a = "player-a"
        self.player_b = "player-b"
        self.player_c = "player-c"

    def test_assert_no_side_channel_leakage_blocks_non_member(self):
        ch = _channel([self.player_a, self.player_b])
        sc_scope = _scope(ScopeType.side_channel, side_channel_id=ch.side_channel_id)
        fact = _fact(sc_scope.scope_id)
        scopes = {sc_scope.scope_id: sc_scope}
        channels = {ch.side_channel_id: ch}

        # player_c is not a member
        with pytest.raises(ScopeViolationError, match="non-member"):
            self.engine.assert_no_side_channel_leakage(
                [fact], scopes, self.player_c, channels
            )

    def test_assert_no_side_channel_leakage_passes_for_member(self):
        ch = _channel([self.player_a, self.player_b])
        sc_scope = _scope(ScopeType.side_channel, side_channel_id=ch.side_channel_id)
        fact = _fact(sc_scope.scope_id)
        scopes = {sc_scope.scope_id: sc_scope}
        channels = {ch.side_channel_id: ch}

        # No exception for member
        self.engine.assert_no_side_channel_leakage(
            [fact], scopes, self.player_a, channels
        )

    def test_closed_channel_delivers_nothing(self):
        ch = _channel([self.player_a, self.player_b], is_open=False)
        sc_scope = _scope(ScopeType.side_channel, side_channel_id=ch.side_channel_id)
        target = self.engine.delivery_targets_for(
            sc_scope, [self.player_a, self.player_b], side_channel=ch
        )
        assert not target.send_public
        assert target.send_private_to == []

    def test_closed_channel_blocks_message_delivery(self):
        ch = _channel([self.player_a, self.player_b], is_open=False)
        assert not self.policy.can_receive_message(ch, self.player_a)
        assert self.policy.recipients(ch) == []


# ---------------------------------------------------------------------------
# 4. Referee guard
# ---------------------------------------------------------------------------


class TestRefereeGuardAudit:
    """Verify the referee guard catches all referee_only leakage paths."""

    def setup_method(self):
        self.guard = RefereeGuard()

    def test_strip_removes_referee_facts(self):
        pub_scope = _scope(ScopeType.public)
        ref_scope = _scope(ScopeType.referee_only)
        pub_fact = _fact(pub_scope.scope_id)
        ref_fact = _fact(ref_scope.scope_id, payload="trap info")
        scopes = {pub_scope.scope_id: pub_scope, ref_scope.scope_id: ref_scope}

        result = self.guard.strip_referee_facts([pub_fact, ref_fact], scopes)
        assert pub_fact in result
        assert ref_fact not in result

    def test_strip_removes_unknown_scope_facts(self):
        unknown_fact = _fact("nonexistent-scope-id", payload="orphan")
        result = self.guard.strip_referee_facts([unknown_fact], {})
        assert result == []

    def test_assert_no_referee_facts_raises_on_referee(self):
        ref_scope = _scope(ScopeType.referee_only)
        ref_fact = _fact(ref_scope.scope_id)
        scopes = {ref_scope.scope_id: ref_scope}
        with pytest.raises(ScopeViolationError, match="referee_only"):
            self.guard.assert_no_referee_facts([ref_fact], scopes)

    def test_assert_no_referee_facts_raises_on_unknown_scope(self):
        unknown_fact = _fact("missing-scope")
        with pytest.raises(ScopeViolationError, match="unknown scope"):
            self.guard.assert_no_referee_facts([unknown_fact], {})

    def test_referee_only_cannot_be_granted_to_player_scope(self):
        policy = FactOwnershipPolicy()
        ref_scope = _scope(ScopeType.referee_only)
        pub_scope = _scope(ScopeType.public)
        fact = policy.create_fact(
            "c1", "sc1", ref_scope, KnowledgeFactType.trap, "hidden trap"
        )
        with pytest.raises(ScopeViolationError, match="referee_only"):
            policy.create_visibility_grant(fact, ref_scope, pub_scope)


# ---------------------------------------------------------------------------
# 5. Model routing safety
# ---------------------------------------------------------------------------


class TestModelRoutingSafety:
    """Verify main/fast tier routing never misroutes tasks."""

    MAIN_ONLY_TASKS = [
        "scene_narration",
        "npc_dialogue",
        "combat_summary",
        "ruling_proposal",
        "social_arbitration",
        "puzzle_flavor",
        "unusual_action_interpretation",
    ]

    FAST_TASKS = [
        "intent_classification",
        "command_normalization",
        "action_packet_extraction",
        "scope_suggestion",
        "context_summarization",
        "clarification_generation",
        "schema_repair",
    ]

    def test_main_tasks_are_main_tier(self):
        for task in self.MAIN_ONLY_TASKS:
            assert is_main_tier(task), f"{task} should be main tier"

    def test_main_tasks_are_blocked_from_fast_tier(self):
        for task in self.MAIN_ONLY_TASKS:
            assert is_main_tier_only(task), f"{task} should be blocked from fast tier"

    def test_fast_tasks_are_not_main_tier_only(self):
        for task in self.FAST_TASKS:
            assert not is_main_tier_only(task), f"{task} should not be main-only"

    def test_fast_tasks_are_fast_eligible(self):
        for task in self.FAST_TASKS:
            assert is_fast_tier(task), f"{task} should be fast-eligible"

    def test_no_overlap_between_main_and_fast_task_lists(self):
        """Main-only tasks and fast tasks should be disjoint sets."""
        overlap = set(self.MAIN_ONLY_TASKS) & set(self.FAST_TASKS)
        assert not overlap, f"Overlap between main and fast tasks: {overlap}"


# ---------------------------------------------------------------------------
# 6. Filter and assembly edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases: unknown scopes, empty inputs, grant mechanics."""

    def setup_method(self):
        self.engine = ScopeEngine()

    def test_unknown_scope_id_denies_visibility(self):
        fact = _fact("nonexistent-scope")
        result = self.engine.filter_facts_for_player(
            "player-a",
            [fact],
            scopes_by_id={},
            grants_by_fact_id={},
            side_channels_by_id={},
        )
        assert result == []

    def test_empty_fact_list_assembles_safely(self):
        result = self.engine.assemble_public_context([], {})
        assert result == []

    def test_grant_broadens_private_fact_visibility(self):
        player_a = "player-a"
        player_b = "player-b"
        priv_scope = _scope(ScopeType.private_referee, player_id=player_a)
        fact = _fact(priv_scope.scope_id, payload="A discovers a clue")
        grant = VisibilityGrant(
            grant_id=_uid(),
            fact_id=fact.fact_id,
            campaign_id="c1",
            granted_to_scope_id="any-scope",
            granted_at=_now(),
            granted_by_player_id=player_a,
        )
        # With a grant, player_b can now see the fact
        assert self.engine.can_player_see_fact(player_b, fact, priv_scope, [grant])

    def test_without_grant_private_fact_stays_hidden(self):
        player_a = "player-a"
        player_b = "player-b"
        priv_scope = _scope(ScopeType.private_referee, player_id=player_a)
        fact = _fact(priv_scope.scope_id, payload="A's private discovery")
        # No grant - player_b cannot see
        assert not self.engine.can_player_see_fact(player_b, fact, priv_scope, [])

    def test_side_channel_missing_object_raises_on_delivery(self):
        sc_scope = _scope(ScopeType.side_channel, side_channel_id="ch-1")
        with pytest.raises(ScopeViolationError, match="requires a SideChannel"):
            self.engine.delivery_targets_for(sc_scope, ["player-a"], side_channel=None)

    def test_public_context_unknown_scope_raises(self):
        fact = _fact("unknown-scope-id")
        with pytest.raises(ScopeViolationError, match="unknown scope_id"):
            self.engine.assemble_public_context([fact], {})
