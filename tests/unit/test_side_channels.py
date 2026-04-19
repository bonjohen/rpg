"""Tests for Phase 11: Side-Channels and Private Coordination.

Covers:
  - SideChannelPolicy lifecycle & membership
  - SideChannelEngine creation & closure
  - send_side_channel DM relay
  - ScopeEngine visibility isolation & assert_no_side_channel_leakage
  - SideChannelAuditor audit facts
  - Full lifecycle integration
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from server.domain.enums import KnowledgeFactType, ScopeType
from server.scope.engine import ScopeEngine, ScopeViolationError
from server.scope.side_channel import SideChannelError, SideChannelPolicy
from server.scope.side_channel_audit import SideChannelAuditor
from server.scope.side_channel_engine import SideChannelEngine
from tests.fixtures.side_channel_scenario import (
    ALL_PLAYER_IDS,
    CAMPAIGN_ID,
    CHANNEL_ID,
    CHANNEL_LABEL,
    PLAYER_ALICE_ID,
    PLAYER_BOB_ID,
    PLAYER_CAROL_ID,
    SCENE_ID,
    SCOPE_CHANNEL_ID,
    SCOPE_PUBLIC_ID,
    SCOPE_REFEREE_ID,
    make_channel_scope,
    make_public_fact,
    make_public_scope,
    make_referee_scope,
    make_side_channel,
    make_side_channel_fact,
)


# =========================================================================
# SideChannelPolicy — lifecycle & membership
# =========================================================================


class TestSideChannelPolicyCreation:
    def setup_method(self) -> None:
        self.policy = SideChannelPolicy()

    def test_validate_creation_succeeds_with_two_members(self) -> None:
        self.policy.validate_creation(
            PLAYER_ALICE_ID,
            [PLAYER_ALICE_ID, PLAYER_BOB_ID],
            ALL_PLAYER_IDS,
        )

    def test_validate_creation_rejects_single_member(self) -> None:
        with pytest.raises(SideChannelError, match="at least 2"):
            self.policy.validate_creation(
                PLAYER_ALICE_ID, [PLAYER_ALICE_ID], ALL_PLAYER_IDS
            )

    def test_validate_creation_rejects_non_campaign_player(self) -> None:
        with pytest.raises(SideChannelError, match="Unknown player"):
            self.policy.validate_creation(
                PLAYER_ALICE_ID,
                [PLAYER_ALICE_ID, "player-unknown"],
                ALL_PLAYER_IDS,
            )

    def test_validate_creation_rejects_creator_not_in_campaign(self) -> None:
        with pytest.raises(SideChannelError, match="not a member"):
            self.policy.validate_creation(
                "player-outsider",
                ["player-outsider", PLAYER_BOB_ID],
                ALL_PLAYER_IDS,
            )

    def test_validate_creation_rejects_creator_not_in_member_list(self) -> None:
        with pytest.raises(SideChannelError, match="Creator must be included"):
            self.policy.validate_creation(
                PLAYER_ALICE_ID,
                [PLAYER_BOB_ID, PLAYER_CAROL_ID],
                ALL_PLAYER_IDS,
            )

    def test_validate_creation_three_members(self) -> None:
        self.policy.validate_creation(PLAYER_ALICE_ID, ALL_PLAYER_IDS, ALL_PLAYER_IDS)


class TestSideChannelPolicyMembership:
    def setup_method(self) -> None:
        self.policy = SideChannelPolicy()

    def test_add_member_succeeds(self) -> None:
        ch = make_side_channel()
        result = self.policy.add_member(ch, PLAYER_CAROL_ID, ALL_PLAYER_IDS)
        assert PLAYER_CAROL_ID in result.member_player_ids

    def test_add_duplicate_member_rejected(self) -> None:
        ch = make_side_channel()
        with pytest.raises(SideChannelError, match="already a member"):
            self.policy.add_member(ch, PLAYER_BOB_ID, ALL_PLAYER_IDS)

    def test_add_non_campaign_player_rejected(self) -> None:
        ch = make_side_channel()
        with pytest.raises(SideChannelError, match="not in this campaign"):
            self.policy.add_member(ch, "player-outsider", ALL_PLAYER_IDS)

    def test_add_member_to_closed_channel_rejected(self) -> None:
        ch = make_side_channel(is_open=False)
        with pytest.raises(SideChannelError, match="closed channel"):
            self.policy.add_member(ch, PLAYER_CAROL_ID, ALL_PLAYER_IDS)

    def test_remove_member_succeeds(self) -> None:
        ch = make_side_channel(
            members=[PLAYER_ALICE_ID, PLAYER_BOB_ID, PLAYER_CAROL_ID]
        )
        result = self.policy.remove_member(ch, PLAYER_CAROL_ID)
        assert PLAYER_CAROL_ID not in result.member_player_ids
        assert result.is_open is True

    def test_remove_member_auto_closes_below_min(self) -> None:
        ch = make_side_channel()  # 2 members
        result = self.policy.remove_member(ch, PLAYER_BOB_ID)
        assert result.is_open is False

    def test_remove_non_member_rejected(self) -> None:
        ch = make_side_channel()
        with pytest.raises(SideChannelError, match="not a member"):
            self.policy.remove_member(ch, PLAYER_CAROL_ID)

    def test_remove_from_closed_channel_rejected(self) -> None:
        ch = make_side_channel(is_open=False)
        with pytest.raises(SideChannelError, match="closed channel"):
            self.policy.remove_member(ch, PLAYER_BOB_ID)

    def test_is_member_true(self) -> None:
        ch = make_side_channel()
        assert self.policy.is_member(ch, PLAYER_ALICE_ID)

    def test_is_member_false(self) -> None:
        ch = make_side_channel()
        assert not self.policy.is_member(ch, PLAYER_CAROL_ID)

    def test_can_receive_message_open(self) -> None:
        ch = make_side_channel()
        assert self.policy.can_receive_message(ch, PLAYER_ALICE_ID)

    def test_can_receive_message_closed(self) -> None:
        ch = make_side_channel(is_open=False)
        assert not self.policy.can_receive_message(ch, PLAYER_ALICE_ID)

    def test_can_receive_message_non_member(self) -> None:
        ch = make_side_channel()
        assert not self.policy.can_receive_message(ch, PLAYER_CAROL_ID)

    def test_recipients_open(self) -> None:
        ch = make_side_channel()
        assert set(self.policy.recipients(ch)) == {
            PLAYER_ALICE_ID,
            PLAYER_BOB_ID,
        }

    def test_recipients_closed(self) -> None:
        ch = make_side_channel(is_open=False)
        assert self.policy.recipients(ch) == []


class TestSideChannelPolicyCanCreate:
    def setup_method(self) -> None:
        self.policy = SideChannelPolicy()

    def test_can_create_when_under_limit(self) -> None:
        assert self.policy.can_create(PLAYER_ALICE_ID, ALL_PLAYER_IDS, [])

    def test_can_create_false_when_at_limit(self) -> None:
        channels = [make_side_channel() for _ in range(5)]
        assert not self.policy.can_create(
            PLAYER_ALICE_ID, ALL_PLAYER_IDS, channels, max_per_player=5
        )

    def test_can_create_false_for_non_campaign_player(self) -> None:
        assert not self.policy.can_create("player-outsider", ALL_PLAYER_IDS, [])

    def test_can_create_ignores_closed_channels(self) -> None:
        channels = [make_side_channel(is_open=False) for _ in range(5)]
        assert self.policy.can_create(
            PLAYER_ALICE_ID, ALL_PLAYER_IDS, channels, max_per_player=5
        )

    def test_close_already_closed_raises(self) -> None:
        ch = make_side_channel(is_open=False)
        with pytest.raises(SideChannelError, match="already closed"):
            self.policy.close_channel(ch)

    def test_close_open_channel(self) -> None:
        ch = make_side_channel()
        result = self.policy.close_channel(ch)
        assert result.is_open is False


# =========================================================================
# SideChannelEngine — creation & closure
# =========================================================================


class TestSideChannelEngine:
    def setup_method(self) -> None:
        self.engine = SideChannelEngine()

    def test_create_success(self) -> None:
        result = self.engine.create_channel(
            PLAYER_ALICE_ID,
            [PLAYER_ALICE_ID, PLAYER_BOB_ID],
            CAMPAIGN_ID,
            ALL_PLAYER_IDS,
            "heist crew",
            channel_id=CHANNEL_ID,
            scope_id=SCOPE_CHANNEL_ID,
        )
        assert result.success
        assert result.channel is not None
        assert result.channel.label == "heist crew"
        assert result.channel.is_open
        assert result.scope is not None
        assert result.scope.scope_type == ScopeType.side_channel
        assert result.scope.side_channel_id == CHANNEL_ID

    def test_create_failure_single_member(self) -> None:
        result = self.engine.create_channel(
            PLAYER_ALICE_ID,
            [PLAYER_ALICE_ID],
            CAMPAIGN_ID,
            ALL_PLAYER_IDS,
            "solo",
        )
        assert not result.success
        assert "at least 2" in result.rejection_reason

    def test_create_failure_non_campaign_member(self) -> None:
        result = self.engine.create_channel(
            PLAYER_ALICE_ID,
            [PLAYER_ALICE_ID, "player-unknown"],
            CAMPAIGN_ID,
            ALL_PLAYER_IDS,
            "bad",
        )
        assert not result.success
        assert "Unknown" in result.rejection_reason

    def test_create_scope_type_is_side_channel(self) -> None:
        result = self.engine.create_channel(
            PLAYER_ALICE_ID,
            [PLAYER_ALICE_ID, PLAYER_BOB_ID],
            CAMPAIGN_ID,
            ALL_PLAYER_IDS,
            "test",
        )
        assert result.scope is not None
        assert result.scope.scope_type == ScopeType.side_channel

    def test_close_success(self) -> None:
        ch = make_side_channel()
        result = self.engine.close_channel(ch, PLAYER_ALICE_ID, CAMPAIGN_ID, SCENE_ID)
        assert result.success
        assert result.channel is not None
        assert not result.channel.is_open
        assert result.audit_fact is not None
        assert result.audit_fact.fact_type == KnowledgeFactType.custom
        assert "[side_channel_audit]" in result.audit_fact.payload

    def test_close_non_member_fails(self) -> None:
        ch = make_side_channel()
        result = self.engine.close_channel(ch, PLAYER_CAROL_ID, CAMPAIGN_ID, SCENE_ID)
        assert not result.success
        assert "not a member" in result.reason

    def test_close_already_closed_fails(self) -> None:
        ch = make_side_channel(is_open=False)
        result = self.engine.close_channel(ch, PLAYER_ALICE_ID, CAMPAIGN_ID, SCENE_ID)
        assert not result.success
        assert "already closed" in result.reason


# =========================================================================
# send_side_channel DM relay
# =========================================================================


class TestSendSideChannel:
    @pytest.mark.asyncio
    async def test_sends_to_all_members_except_sender(self) -> None:
        from bot.mapping import BotRegistry
        from bot.outbound import send_side_channel

        bot = AsyncMock()
        registry = BotRegistry()
        registry.register_player(1001, PLAYER_ALICE_ID)
        registry.register_player(1002, PLAYER_BOB_ID)

        ch = make_side_channel()
        delivered = await send_side_channel(
            bot, registry, ch, PLAYER_ALICE_ID, "Let's go", "Alice"
        )
        assert delivered == [PLAYER_BOB_ID]
        bot.send_message.assert_called_once()
        call_kwargs = bot.send_message.call_args
        assert "[heist crew]" in call_kwargs.kwargs.get(
            "text", call_kwargs.args[0] if call_kwargs.args else ""
        ) or "[heist crew]" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_closed_channel_delivers_nothing(self) -> None:
        from bot.mapping import BotRegistry
        from bot.outbound import send_side_channel

        bot = AsyncMock()
        registry = BotRegistry()
        registry.register_player(1001, PLAYER_ALICE_ID)
        registry.register_player(1002, PLAYER_BOB_ID)

        ch = make_side_channel(is_open=False)
        delivered = await send_side_channel(bot, registry, ch, PLAYER_ALICE_ID, "Hello")
        assert delivered == []
        bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_unregistered_member(self) -> None:
        from bot.mapping import BotRegistry
        from bot.outbound import send_side_channel

        bot = AsyncMock()
        registry = BotRegistry()
        registry.register_player(1001, PLAYER_ALICE_ID)
        # Bob not registered

        ch = make_side_channel()
        delivered = await send_side_channel(
            bot, registry, ch, PLAYER_ALICE_ID, "Secret"
        )
        assert delivered == []

    @pytest.mark.asyncio
    async def test_three_members_sends_to_two(self) -> None:
        from bot.mapping import BotRegistry
        from bot.outbound import send_side_channel

        bot = AsyncMock()
        registry = BotRegistry()
        registry.register_player(1001, PLAYER_ALICE_ID)
        registry.register_player(1002, PLAYER_BOB_ID)
        registry.register_player(1003, PLAYER_CAROL_ID)

        ch = make_side_channel(
            members=[PLAYER_ALICE_ID, PLAYER_BOB_ID, PLAYER_CAROL_ID]
        )
        delivered = await send_side_channel(
            bot, registry, ch, PLAYER_ALICE_ID, "Plan", "Alice"
        )
        assert set(delivered) == {PLAYER_BOB_ID, PLAYER_CAROL_ID}
        assert bot.send_message.call_count == 2


# =========================================================================
# ScopeEngine — visibility isolation
# =========================================================================


class TestScopeEngineVisibilityIsolation:
    def setup_method(self) -> None:
        self.engine = ScopeEngine()

    def test_member_can_see_side_channel_fact(self) -> None:
        ch = make_side_channel()
        fact = make_side_channel_fact()
        scope = make_channel_scope()
        assert self.engine.can_player_see_fact(PLAYER_ALICE_ID, fact, scope, [], ch)

    def test_non_member_cannot_see_side_channel_fact(self) -> None:
        ch = make_side_channel()
        fact = make_side_channel_fact()
        scope = make_channel_scope()
        assert not self.engine.can_player_see_fact(PLAYER_CAROL_ID, fact, scope, [], ch)

    def test_filter_facts_excludes_side_channel_for_non_member(self) -> None:
        ch = make_side_channel()
        pub_fact = make_public_fact()
        sc_fact = make_side_channel_fact()
        scopes = {
            SCOPE_PUBLIC_ID: make_public_scope(),
            SCOPE_CHANNEL_ID: make_channel_scope(),
        }
        result = self.engine.filter_facts_for_player(
            PLAYER_CAROL_ID,
            [pub_fact, sc_fact],
            scopes,
            {},
            {CHANNEL_ID: ch},
        )
        assert len(result) == 1
        assert result[0].fact_id == pub_fact.fact_id

    def test_filter_facts_includes_side_channel_for_member(self) -> None:
        ch = make_side_channel()
        pub_fact = make_public_fact()
        sc_fact = make_side_channel_fact()
        scopes = {
            SCOPE_PUBLIC_ID: make_public_scope(),
            SCOPE_CHANNEL_ID: make_channel_scope(),
        }
        result = self.engine.filter_facts_for_player(
            PLAYER_ALICE_ID,
            [pub_fact, sc_fact],
            scopes,
            {},
            {CHANNEL_ID: ch},
        )
        assert len(result) == 2

    def test_public_context_rejects_side_channel_fact(self) -> None:
        sc_fact = make_side_channel_fact()
        scopes = {SCOPE_CHANNEL_ID: make_channel_scope()}
        with pytest.raises(ScopeViolationError):
            self.engine.assemble_public_context([sc_fact], scopes)

    def test_assert_no_side_channel_leakage_passes_for_member(self) -> None:
        ch = make_side_channel()
        sc_fact = make_side_channel_fact()
        scopes = {SCOPE_CHANNEL_ID: make_channel_scope()}
        # Should not raise
        self.engine.assert_no_side_channel_leakage(
            [sc_fact], scopes, PLAYER_ALICE_ID, {CHANNEL_ID: ch}
        )

    def test_assert_no_side_channel_leakage_raises_for_non_member(self) -> None:
        ch = make_side_channel()
        sc_fact = make_side_channel_fact()
        scopes = {SCOPE_CHANNEL_ID: make_channel_scope()}
        with pytest.raises(ScopeViolationError, match="non-member"):
            self.engine.assert_no_side_channel_leakage(
                [sc_fact], scopes, PLAYER_CAROL_ID, {CHANNEL_ID: ch}
            )

    def test_assert_no_side_channel_leakage_ignores_public_facts(self) -> None:
        pub_fact = make_public_fact()
        scopes = {SCOPE_PUBLIC_ID: make_public_scope()}
        # Should not raise
        self.engine.assert_no_side_channel_leakage(
            [pub_fact], scopes, PLAYER_CAROL_ID, {}
        )

    def test_assert_no_side_channel_leakage_missing_channel(self) -> None:
        sc_fact = make_side_channel_fact()
        scopes = {SCOPE_CHANNEL_ID: make_channel_scope()}
        with pytest.raises(ScopeViolationError):
            self.engine.assert_no_side_channel_leakage(
                [sc_fact], scopes, PLAYER_ALICE_ID, {}
            )


# =========================================================================
# SideChannelAuditor
# =========================================================================


class TestSideChannelAuditor:
    def setup_method(self) -> None:
        self.auditor = SideChannelAuditor()

    def test_record_creation(self) -> None:
        ch = make_side_channel()
        fact = self.auditor.record_creation(
            ch, CAMPAIGN_ID, SCENE_ID, referee_scope_id=SCOPE_REFEREE_ID
        )
        assert fact.fact_type == KnowledgeFactType.custom
        assert "[side_channel_audit] Created channel" in fact.payload
        assert CHANNEL_LABEL in fact.payload
        assert PLAYER_ALICE_ID in fact.payload
        assert PLAYER_BOB_ID in fact.payload
        assert fact.owner_scope_id == SCOPE_REFEREE_ID

    def test_record_message(self) -> None:
        ch = make_side_channel()
        fact = self.auditor.record_message(
            ch,
            PLAYER_ALICE_ID,
            CAMPAIGN_ID,
            SCENE_ID,
            referee_scope_id=SCOPE_REFEREE_ID,
        )
        assert "[side_channel_audit] Message sent" in fact.payload
        assert PLAYER_ALICE_ID in fact.payload
        assert fact.owner_scope_id == SCOPE_REFEREE_ID

    def test_record_closure(self) -> None:
        ch = make_side_channel()
        fact = self.auditor.record_closure(
            ch,
            PLAYER_BOB_ID,
            CAMPAIGN_ID,
            SCENE_ID,
            referee_scope_id=SCOPE_REFEREE_ID,
        )
        assert "[side_channel_audit] Channel" in fact.payload
        assert "closed" in fact.payload
        assert PLAYER_BOB_ID in fact.payload
        assert fact.owner_scope_id == SCOPE_REFEREE_ID

    def test_audit_facts_are_referee_only_scope(self) -> None:
        ch = make_side_channel()
        for fact in [
            self.auditor.record_creation(
                ch, CAMPAIGN_ID, SCENE_ID, referee_scope_id=SCOPE_REFEREE_ID
            ),
            self.auditor.record_message(
                ch,
                PLAYER_ALICE_ID,
                CAMPAIGN_ID,
                SCENE_ID,
                referee_scope_id=SCOPE_REFEREE_ID,
            ),
            self.auditor.record_closure(
                ch,
                PLAYER_ALICE_ID,
                CAMPAIGN_ID,
                SCENE_ID,
                referee_scope_id=SCOPE_REFEREE_ID,
            ),
        ]:
            assert fact.owner_scope_id == SCOPE_REFEREE_ID

    def test_audit_facts_never_visible_to_players(self) -> None:
        """Audit facts with referee_only scope should never be visible."""
        engine = ScopeEngine()
        ch = make_side_channel()
        fact = self.auditor.record_creation(
            ch, CAMPAIGN_ID, SCENE_ID, referee_scope_id=SCOPE_REFEREE_ID
        )
        referee_scope = make_referee_scope()
        assert not engine.can_player_see_fact(PLAYER_ALICE_ID, fact, referee_scope, [])


# =========================================================================
# Full lifecycle integration
# =========================================================================


class TestSideChannelLifecycle:
    def test_create_send_close_lifecycle(self) -> None:
        """Create → verify membership → close → verify closed."""
        engine = SideChannelEngine()
        policy = SideChannelPolicy()
        auditor = SideChannelAuditor()
        scope_engine = ScopeEngine()

        # 1. Create
        create_result = engine.create_channel(
            PLAYER_ALICE_ID,
            [PLAYER_ALICE_ID, PLAYER_BOB_ID],
            CAMPAIGN_ID,
            ALL_PLAYER_IDS,
            "heist crew",
            channel_id=CHANNEL_ID,
            scope_id=SCOPE_CHANNEL_ID,
        )
        assert create_result.success
        ch = create_result.channel
        assert ch is not None

        # 2. Verify members can see channel facts
        sc_fact = make_side_channel_fact()
        ch_scope = make_channel_scope()
        assert scope_engine.can_player_see_fact(
            PLAYER_ALICE_ID, sc_fact, ch_scope, [], ch
        )
        assert not scope_engine.can_player_see_fact(
            PLAYER_CAROL_ID, sc_fact, ch_scope, [], ch
        )

        # 3. Audit creation
        audit_fact = auditor.record_creation(
            ch, CAMPAIGN_ID, SCENE_ID, referee_scope_id=SCOPE_REFEREE_ID
        )
        assert "[side_channel_audit]" in audit_fact.payload

        # 4. Close
        close_result = engine.close_channel(ch, PLAYER_ALICE_ID, CAMPAIGN_ID, SCENE_ID)
        assert close_result.success
        assert not ch.is_open

        # 5. Closed channel delivers nothing
        assert policy.recipients(ch) == []
        assert not policy.can_receive_message(ch, PLAYER_ALICE_ID)

    def test_add_member_then_remove_auto_close(self) -> None:
        """Add a third member, then remove two to trigger auto-close."""
        policy = SideChannelPolicy()
        ch = make_side_channel()

        # Add Carol
        policy.add_member(ch, PLAYER_CAROL_ID, ALL_PLAYER_IDS)
        assert len(ch.member_player_ids) == 3

        # Remove Bob — still 2 members, stays open
        policy.remove_member(ch, PLAYER_BOB_ID)
        assert ch.is_open
        assert len(ch.member_player_ids) == 2

        # Remove Carol — drops below MIN_MEMBERS, auto-close
        policy.remove_member(ch, PLAYER_CAROL_ID)
        assert not ch.is_open

    def test_closed_channel_cannot_receive_or_add(self) -> None:
        """A closed channel blocks all operations."""
        policy = SideChannelPolicy()
        ch = make_side_channel()
        policy.close_channel(ch)

        assert not policy.can_receive_message(ch, PLAYER_ALICE_ID)
        assert policy.recipients(ch) == []

        with pytest.raises(SideChannelError):
            policy.add_member(ch, PLAYER_CAROL_ID, ALL_PLAYER_IDS)

        with pytest.raises(SideChannelError):
            policy.remove_member(ch, PLAYER_ALICE_ID)

    def test_side_channel_fact_in_public_prompt_raises(self) -> None:
        """Side-channel facts must never appear in public prompts."""
        scope_engine = ScopeEngine()
        sc_fact = make_side_channel_fact()
        scopes = {SCOPE_CHANNEL_ID: make_channel_scope()}
        with pytest.raises(ScopeViolationError):
            scope_engine.assemble_public_context([sc_fact], scopes)

    def test_private_context_excludes_other_players_channel(self) -> None:
        """assemble_private_context should exclude side-channel facts for
        non-members."""
        scope_engine = ScopeEngine()
        ch = make_side_channel()
        sc_fact = make_side_channel_fact()
        pub_fact = make_public_fact()
        scopes = {
            SCOPE_CHANNEL_ID: make_channel_scope(),
            SCOPE_PUBLIC_ID: make_public_scope(),
        }
        result = scope_engine.assemble_private_context(
            PLAYER_CAROL_ID,
            [pub_fact, sc_fact],
            scopes,
            {},
            {CHANNEL_ID: ch},
        )
        assert len(result) == 1
        assert result[0].fact_id == pub_fact.fact_id

    def test_private_context_includes_member_channel_facts(self) -> None:
        """assemble_private_context should include side-channel facts for members."""
        scope_engine = ScopeEngine()
        ch = make_side_channel()
        sc_fact = make_side_channel_fact()
        pub_fact = make_public_fact()
        scopes = {
            SCOPE_CHANNEL_ID: make_channel_scope(),
            SCOPE_PUBLIC_ID: make_public_scope(),
        }
        result = scope_engine.assemble_private_context(
            PLAYER_ALICE_ID,
            [pub_fact, sc_fact],
            scopes,
            {},
            {CHANNEL_ID: ch},
        )
        assert len(result) == 2
