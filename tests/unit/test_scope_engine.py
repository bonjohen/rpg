"""Unit tests for server.scope — scope engine, fact ownership, side-channel
policy, referee guard, and leakage guard.

Scenario coverage:
  - Public scope delivery
  - Private-referee scope delivery (awareness checks, hidden clues)
  - Side-channel scope delivery
  - Referee-only storage (stealth, hidden traps, secret objectives)
  - KnowledgeFact ownership and VisibilityGrant mechanics
  - Leakage guard blocking non-public facts from public prompts
  - Leakage guard blocking invisible facts from player prompts
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
from server.scope.side_channel import SideChannelError, SideChannelPolicy
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
        created_at=_now(),
        created_by_player_id=member_ids[0] if member_ids else _uid(),
        member_player_ids=list(member_ids),
        is_open=is_open,
    )


# ---------------------------------------------------------------------------
# ScopeEngine.delivery_targets_for
# ---------------------------------------------------------------------------


class TestDeliveryTargets:
    def setup_method(self):
        self.engine = ScopeEngine()

    def test_public_sends_to_group(self):
        scope = _scope(ScopeType.public)
        target = self.engine.delivery_targets_for(scope, ["p1", "p2"])
        assert target.send_public is True
        assert target.send_private_to == []

    def test_private_referee_sends_to_one_player(self):
        """Awareness result or hidden clue → only the owning player's DM."""
        scope = _scope(ScopeType.private_referee, player_id="p1")
        target = self.engine.delivery_targets_for(scope, ["p1", "p2"])
        assert target.send_public is False
        assert target.send_private_to == ["p1"]

    def test_private_referee_missing_player_id_raises(self):
        scope = _scope(ScopeType.private_referee, player_id=None)
        with pytest.raises(ScopeViolationError):
            self.engine.delivery_targets_for(scope, ["p1"])

    def test_side_channel_sends_to_members(self):
        ch = _channel(["p1", "p2"])
        scope = _scope(ScopeType.side_channel, side_channel_id=ch.side_channel_id)
        target = self.engine.delivery_targets_for(
            scope, ["p1", "p2", "p3"], side_channel=ch
        )
        assert target.send_public is False
        assert set(target.send_private_to) == {"p1", "p2"}

    def test_side_channel_closed_delivers_nothing(self):
        ch = _channel(["p1", "p2"], is_open=False)
        scope = _scope(ScopeType.side_channel, side_channel_id=ch.side_channel_id)
        target = self.engine.delivery_targets_for(scope, ["p1", "p2"], side_channel=ch)
        assert target.send_private_to == []
        assert target.send_public is False

    def test_side_channel_missing_object_raises(self):
        scope = _scope(ScopeType.side_channel)
        with pytest.raises(ScopeViolationError, match="SideChannel"):
            self.engine.delivery_targets_for(scope, ["p1"])

    def test_referee_only_raises(self):
        """referee_only must never be delivered."""
        scope = _scope(ScopeType.referee_only)
        with pytest.raises(ScopeViolationError, match="referee_only"):
            self.engine.delivery_targets_for(scope, ["p1"])


# ---------------------------------------------------------------------------
# ScopeEngine.can_player_see_fact  (awareness, hidden clues, stealth, secrets)
# ---------------------------------------------------------------------------


class TestCanPlayerSeeFact:
    def setup_method(self):
        self.engine = ScopeEngine()

    def test_public_fact_visible_to_all(self):
        scope = _scope(ScopeType.public)
        fact = _fact(scope.scope_id)
        for pid in ["p1", "p2", "p3"]:
            assert self.engine.can_player_see_fact(pid, fact, scope, []) is True

    def test_private_fact_visible_only_to_owner(self):
        """Hidden clue or awareness result — only the target player sees it."""
        scope = _scope(ScopeType.private_referee, player_id="p1")
        fact = _fact(scope.scope_id, KnowledgeFactType.clue, "You notice a tripwire")
        assert self.engine.can_player_see_fact("p1", fact, scope, []) is True
        assert self.engine.can_player_see_fact("p2", fact, scope, []) is False

    def test_referee_only_fact_invisible_to_all(self):
        """Stealth tracker, NPC true intent — no player ever sees it."""
        scope = _scope(ScopeType.referee_only)
        fact = _fact(scope.scope_id, KnowledgeFactType.trap, "Spike trap behind door")
        for pid in ["p1", "p2", "gm"]:
            assert self.engine.can_player_see_fact(pid, fact, scope, []) is False

    def test_side_channel_fact_visible_to_members(self):
        ch = _channel(["p1", "p2"])
        scope = _scope(ScopeType.side_channel, side_channel_id=ch.side_channel_id)
        fact = _fact(scope.scope_id)
        assert (
            self.engine.can_player_see_fact("p1", fact, scope, [], side_channel=ch)
            is True
        )
        assert (
            self.engine.can_player_see_fact("p2", fact, scope, [], side_channel=ch)
            is True
        )
        assert (
            self.engine.can_player_see_fact("p3", fact, scope, [], side_channel=ch)
            is False
        )

    def test_secret_objective_private_to_owner(self):
        scope = _scope(ScopeType.private_referee, player_id="p2")
        fact = _fact(
            scope.scope_id,
            KnowledgeFactType.secret_objective,
            "Steal the artifact without the others knowing",
        )
        assert self.engine.can_player_see_fact("p2", fact, scope, []) is True
        assert self.engine.can_player_see_fact("p1", fact, scope, []) is False

    def test_visibility_grant_broadens_access(self):
        """Player p1 shares their private clue with the whole party via a grant."""
        priv_scope = _scope(ScopeType.private_referee, player_id="p1")
        fact = _fact(priv_scope.scope_id, KnowledgeFactType.clue, "The rune glows")
        pub_scope = _scope(ScopeType.public)
        grant = VisibilityGrant(
            grant_id=_uid(),
            fact_id=fact.fact_id,
            campaign_id="c1",
            granted_to_scope_id=pub_scope.scope_id,
            granted_at=_now(),
            granted_by_player_id="p1",
        )
        scopes = {priv_scope.scope_id: priv_scope, pub_scope.scope_id: pub_scope}
        # p2 can now see via the grant to a public scope
        assert (
            self.engine.can_player_see_fact(
                "p2", fact, priv_scope, [grant], scopes_by_id=scopes
            )
            is True
        )

    def test_grant_to_different_player_not_visible(self):
        """Grant to player B's private scope should NOT be visible to player C."""
        priv_scope_a = _scope(ScopeType.private_referee, player_id="p1")
        priv_scope_b = _scope(ScopeType.private_referee, player_id="p2")
        fact = _fact(priv_scope_a.scope_id)
        grant = VisibilityGrant(
            grant_id=_uid(),
            fact_id=fact.fact_id,
            campaign_id="c1",
            granted_to_scope_id=priv_scope_b.scope_id,
            granted_at=_now(),
            granted_by_player_id="p1",
        )
        scopes = {
            priv_scope_a.scope_id: priv_scope_a,
            priv_scope_b.scope_id: priv_scope_b,
        }
        # p2 (the grantee) can see it
        assert (
            self.engine.can_player_see_fact(
                "p2", fact, priv_scope_a, [grant], scopes_by_id=scopes
            )
            is True
        )
        # p3 (not the grantee) cannot see it
        assert (
            self.engine.can_player_see_fact(
                "p3", fact, priv_scope_a, [grant], scopes_by_id=scopes
            )
            is False
        )

    def test_no_grant_no_cross_player_visibility(self):
        priv_scope = _scope(ScopeType.private_referee, player_id="p1")
        fact = _fact(priv_scope.scope_id)
        assert self.engine.can_player_see_fact("p2", fact, priv_scope, []) is False

    def test_grant_without_scopes_by_id_denies(self):
        """Legacy callers without scopes_by_id should deny grants by default."""
        priv_scope = _scope(ScopeType.private_referee, player_id="p1")
        pub_scope = _scope(ScopeType.public)
        fact = _fact(priv_scope.scope_id)
        grant = VisibilityGrant(
            grant_id=_uid(),
            fact_id=fact.fact_id,
            campaign_id="c1",
            granted_to_scope_id=pub_scope.scope_id,
            granted_at=_now(),
            granted_by_player_id="p1",
        )
        # Without scopes_by_id, grants are denied
        assert self.engine.can_player_see_fact("p2", fact, priv_scope, [grant]) is False


# ---------------------------------------------------------------------------
# ScopeEngine.filter_facts_for_player
# ---------------------------------------------------------------------------


class TestFilterFactsForPlayer:
    def setup_method(self):
        self.engine = ScopeEngine()

    def test_filters_to_visible_only(self):
        pub = _scope(ScopeType.public)
        priv_p1 = _scope(ScopeType.private_referee, player_id="p1")
        priv_p2 = _scope(ScopeType.private_referee, player_id="p2")
        ref = _scope(ScopeType.referee_only)

        f_pub = _fact(pub.scope_id)
        f_p1 = _fact(priv_p1.scope_id)
        f_p2 = _fact(priv_p2.scope_id)
        f_ref = _fact(ref.scope_id)

        scopes = {s.scope_id: s for s in [pub, priv_p1, priv_p2, ref]}
        visible = self.engine.filter_facts_for_player(
            "p1", [f_pub, f_p1, f_p2, f_ref], scopes, {}, {}
        )
        ids = {f.fact_id for f in visible}
        assert f_pub.fact_id in ids
        assert f_p1.fact_id in ids
        assert f_p2.fact_id not in ids
        assert f_ref.fact_id not in ids


# ---------------------------------------------------------------------------
# ScopeEngine.assemble_public_context / assemble_private_context
# ---------------------------------------------------------------------------


class TestAssembleContext:
    def setup_method(self):
        self.engine = ScopeEngine()

    def test_public_context_rejects_private_fact(self):
        priv = _scope(ScopeType.private_referee, player_id="p1")
        fact = _fact(priv.scope_id)
        with pytest.raises(ScopeViolationError):
            self.engine.assemble_public_context([fact], {priv.scope_id: priv})

    def test_public_context_rejects_referee_fact(self):
        ref = _scope(ScopeType.referee_only)
        fact = _fact(ref.scope_id)
        with pytest.raises(ScopeViolationError):
            self.engine.assemble_public_context([fact], {ref.scope_id: ref})

    def test_private_context_strips_referee_facts(self):
        pub = _scope(ScopeType.public)
        ref = _scope(ScopeType.referee_only)
        f_pub = _fact(pub.scope_id)
        f_ref = _fact(ref.scope_id)
        scopes = {pub.scope_id: pub, ref.scope_id: ref}
        result = self.engine.assemble_private_context(
            "p1", [f_pub, f_ref], scopes, {}, {}
        )
        assert f_pub.fact_id in {f.fact_id for f in result}
        assert f_ref.fact_id not in {f.fact_id for f in result}

    def test_referee_context_includes_all(self):
        pub = _scope(ScopeType.public)
        ref = _scope(ScopeType.referee_only)
        scopes = {pub.scope_id: pub, ref.scope_id: ref}
        f_pub = _fact(pub.scope_id)
        f_ref = _fact(ref.scope_id)
        result = self.engine.assemble_referee_context([f_pub, f_ref], scopes)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# RefereeGuard
# ---------------------------------------------------------------------------


class TestRefereeGuard:
    def setup_method(self):
        self.referee = RefereeGuard()

    def test_is_referee_only(self):
        scope = _scope(ScopeType.referee_only)
        assert self.referee.is_referee_only(scope) is True

    def test_not_referee_only(self):
        assert self.referee.is_referee_only(_scope(ScopeType.public)) is False

    def test_assert_raises_for_referee_scope(self):
        scope = _scope(ScopeType.referee_only)
        with pytest.raises(ScopeViolationError):
            self.referee.assert_not_referee_only(scope)

    def test_strip_referee_facts(self):
        pub = _scope(ScopeType.public)
        ref = _scope(ScopeType.referee_only)
        scopes = {pub.scope_id: pub, ref.scope_id: ref}
        facts = [_fact(pub.scope_id), _fact(ref.scope_id)]
        stripped = self.referee.strip_referee_facts(facts, scopes)
        assert len(stripped) == 1
        assert stripped[0].owner_scope_id == pub.scope_id

    def test_assert_no_referee_facts_raises_on_referee(self):
        ref = _scope(ScopeType.referee_only)
        fact = _fact(ref.scope_id)
        with pytest.raises(ScopeViolationError):
            self.referee.assert_no_referee_facts([fact], {ref.scope_id: ref})


# ---------------------------------------------------------------------------
# FactOwnershipPolicy
# ---------------------------------------------------------------------------


class TestFactOwnershipPolicy:
    def setup_method(self):
        self.policy = FactOwnershipPolicy()

    def test_create_fact_returns_knowledge_fact(self):
        scope = _scope(ScopeType.public)
        fact = self.policy.create_fact(
            campaign_id="c1",
            scene_id="sc1",
            owner_scope=scope,
            fact_type=KnowledgeFactType.clue,
            payload="You find a key",
        )
        assert fact.owner_scope_id == scope.scope_id
        assert fact.payload == "You find a key"
        assert fact.fact_id  # non-empty

    def test_create_visibility_grant(self):
        priv = _scope(ScopeType.private_referee, player_id="p1")
        pub = _scope(ScopeType.public)
        fact = self.policy.create_fact(
            "c1", "sc1", priv, KnowledgeFactType.clue, "clue"
        )
        grant = self.policy.create_visibility_grant(
            fact, priv, pub, granting_player_id="p1"
        )
        assert grant.fact_id == fact.fact_id
        assert grant.granted_to_scope_id == pub.scope_id

    def test_cannot_grant_referee_only_fact(self):
        ref = _scope(ScopeType.referee_only)
        pub = _scope(ScopeType.public)
        fact = self.policy.create_fact("c1", "sc1", ref, KnowledgeFactType.trap, "trap")
        with pytest.raises(ScopeViolationError, match="referee_only"):
            self.policy.create_visibility_grant(fact, ref, pub)

    def test_cannot_grant_to_referee_only_scope(self):
        pub = _scope(ScopeType.public)
        ref = _scope(ScopeType.referee_only)
        fact = self.policy.create_fact("c1", "sc1", pub, KnowledgeFactType.clue, "c")
        with pytest.raises(ScopeViolationError, match="referee_only"):
            self.policy.create_visibility_grant(fact, pub, ref)


# ---------------------------------------------------------------------------
# SideChannelPolicy
# ---------------------------------------------------------------------------


class TestSideChannelPolicy:
    def setup_method(self):
        self.policy = SideChannelPolicy()

    def test_valid_creation(self):
        self.policy.validate_creation("p1", ["p1", "p2"], ["p1", "p2", "p3"])

    def test_creation_requires_min_members(self):
        with pytest.raises(SideChannelError, match="at least"):
            self.policy.validate_creation("p1", ["p1"], ["p1", "p2"])

    def test_creator_must_be_member(self):
        with pytest.raises(SideChannelError, match="Creator must"):
            self.policy.validate_creation("p1", ["p2", "p3"], ["p1", "p2", "p3"])

    def test_unknown_member_raises(self):
        with pytest.raises(SideChannelError, match="Unknown"):
            self.policy.validate_creation("p1", ["p1", "unknown"], ["p1", "p2"])

    def test_is_member_true(self):
        ch = _channel(["p1", "p2"])
        assert self.policy.is_member(ch, "p1") is True

    def test_is_member_false(self):
        ch = _channel(["p1", "p2"])
        assert self.policy.is_member(ch, "p3") is False

    def test_can_receive_when_open(self):
        ch = _channel(["p1", "p2"])
        assert self.policy.can_receive_message(ch, "p1") is True

    def test_cannot_receive_when_closed(self):
        ch = _channel(["p1", "p2"], is_open=False)
        assert self.policy.can_receive_message(ch, "p1") is False

    def test_close_channel(self):
        ch = _channel(["p1", "p2"])
        self.policy.close_channel(ch)
        assert ch.is_open is False

    def test_close_already_closed_raises(self):
        ch = _channel(["p1", "p2"], is_open=False)
        with pytest.raises(SideChannelError, match="already closed"):
            self.policy.close_channel(ch)

    def test_recipients_empty_when_closed(self):
        ch = _channel(["p1", "p2"], is_open=False)
        assert self.policy.recipients(ch) == []


# ---------------------------------------------------------------------------
# LeakageGuard
# ---------------------------------------------------------------------------


class TestLeakageGuard:
    def setup_method(self):
        self.guard = LeakageGuard()

    def test_public_prompt_passes_with_public_facts(self):
        pub = _scope(ScopeType.public)
        facts = [_fact(pub.scope_id), _fact(pub.scope_id)]
        self.guard.check_public_prompt(facts, {pub.scope_id: pub})

    def test_public_prompt_blocks_private_fact(self):
        priv = _scope(ScopeType.private_referee, player_id="p1")
        fact = _fact(priv.scope_id)
        with pytest.raises(ScopeViolationError):
            self.guard.check_public_prompt([fact], {priv.scope_id: priv})

    def test_public_prompt_blocks_referee_fact(self):
        ref = _scope(ScopeType.referee_only)
        fact = _fact(ref.scope_id)
        with pytest.raises(ScopeViolationError):
            self.guard.check_public_prompt([fact], {ref.scope_id: ref})

    def test_player_prompt_allows_own_private_fact(self):
        priv = _scope(ScopeType.private_referee, player_id="p1")
        fact = _fact(priv.scope_id)
        self.guard.check_player_prompt("p1", [fact], {priv.scope_id: priv}, {}, {})

    def test_player_prompt_blocks_other_players_private_fact(self):
        """p1 must not see p2's hidden clue."""
        priv = _scope(ScopeType.private_referee, player_id="p2")
        fact = _fact(priv.scope_id, KnowledgeFactType.clue, "Only p2 sees this")
        with pytest.raises(ScopeViolationError, match="not visible"):
            self.guard.check_player_prompt("p1", [fact], {priv.scope_id: priv}, {}, {})

    def test_player_prompt_blocks_referee_only_fact(self):
        """Stealth result must never reach any player prompt."""
        ref = _scope(ScopeType.referee_only)
        fact = _fact(ref.scope_id, KnowledgeFactType.trap, "Hidden trap")
        with pytest.raises(ScopeViolationError):
            self.guard.check_player_prompt("p1", [fact], {ref.scope_id: ref}, {}, {})

    def test_player_prompt_blocks_unknown_scope(self):
        fact = _fact("nonexistent-scope-id")
        with pytest.raises(ScopeViolationError):
            self.guard.check_player_prompt("p1", [fact], {}, {}, {})
