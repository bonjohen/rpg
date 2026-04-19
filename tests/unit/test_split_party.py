"""Tests for Phase 12: Split Party and Multi-Scene Handling.

Covers:
  - SceneMembershipEngine: add/remove characters and NPCs, transfer
  - MultiSceneEngine: active scenes, build active set, activate/deactivate
  - SubgroupPromptEngine: per-scene context isolation
  - SplitPartyTimingPolicy: independent and synchronized modes
  - InformationPropagationEngine: queue, check, deliver
  - Full integration: split, act, propagate, rejoin
"""

from __future__ import annotations

from server.domain.enums import SceneState
from server.scene.membership import SceneMembershipEngine
from server.scene.multi_scene import MultiSceneEngine
from server.scene.propagation import InformationPropagationEngine
from server.scene.scoped_prompts import SubgroupPromptEngine
from server.scene.timing import SplitPartyTimingPolicy
from tests.fixtures.split_party_scenario import (
    CAMPAIGN_ID,
    CHARACTER_ALARA_ID,
    CHARACTER_BREN_ID,
    CHARACTER_CORWIN_ID,
    NPC_MERCHANT_ID,
    PLAYER_ALARA_ID,
    PLAYER_BREN_ID,
    PLAYER_CORWIN_ID,
    SCENE_CAVE_ID,
    SCENE_VILLAGE_ID,
    SCOPE_PUBLIC_CAVE_ID,
    SCOPE_PUBLIC_VILLAGE_ID,
    TURN_WINDOW_CAVE_ID,
    TURN_WINDOW_VILLAGE_ID,
    make_alara,
    make_bat_swarm,
    make_bren,
    make_cave_fact,
    make_cave_scene,
    make_cave_turn_window,
    make_committed_action,
    make_corwin,
    make_idle_village_scene,
    make_merchant,
    make_public_cave_scope,
    make_public_village_scope,
    make_village_fact,
    make_village_scene,
    make_village_turn_window,
)


# =========================================================================
# SceneMembershipEngine
# =========================================================================


class TestMembershipAddCharacter:
    def setup_method(self) -> None:
        self.engine = SceneMembershipEngine()

    def test_add_character_succeeds(self) -> None:
        scene = make_village_scene()
        alara = make_alara()
        alara.scene_id = None
        scene.character_ids = [CHARACTER_CORWIN_ID]
        scene.player_ids = [PLAYER_CORWIN_ID]

        result = self.engine.add_character(scene, alara)
        assert result.success
        assert CHARACTER_ALARA_ID in scene.character_ids
        assert PLAYER_ALARA_ID in scene.player_ids
        assert alara.scene_id == SCENE_VILLAGE_ID

    def test_add_duplicate_character_rejected(self) -> None:
        scene = make_cave_scene()
        alara = make_alara()
        result = self.engine.add_character(scene, alara)
        assert not result.success
        assert "already in" in result.reason

    def test_add_character_updates_scene_id(self) -> None:
        scene = make_village_scene()
        char = make_alara()
        char.scene_id = None
        scene.character_ids = []
        scene.player_ids = []
        self.engine.add_character(scene, char)
        assert char.scene_id == SCENE_VILLAGE_ID


class TestMembershipRemoveCharacter:
    def setup_method(self) -> None:
        self.engine = SceneMembershipEngine()

    def test_remove_character_succeeds(self) -> None:
        scene = make_cave_scene()
        alara = make_alara()
        result = self.engine.remove_character(scene, alara)
        assert result.success
        assert CHARACTER_ALARA_ID not in scene.character_ids
        assert alara.scene_id is None

    def test_remove_character_not_in_scene_rejected(self) -> None:
        scene = make_village_scene()
        alara = make_alara()
        result = self.engine.remove_character(scene, alara)
        assert not result.success
        assert "not in" in result.reason

    def test_remove_character_clears_player_id(self) -> None:
        scene = make_cave_scene()
        alara = make_alara()
        self.engine.remove_character(scene, alara)
        assert PLAYER_ALARA_ID not in scene.player_ids


class TestMembershipNPC:
    def setup_method(self) -> None:
        self.engine = SceneMembershipEngine()

    def test_add_npc_succeeds(self) -> None:
        scene = make_cave_scene()
        merchant = make_merchant()
        merchant.scene_id = None
        result = self.engine.add_npc(scene, merchant)
        assert result.success
        assert NPC_MERCHANT_ID in scene.npc_ids
        assert merchant.scene_id == SCENE_CAVE_ID

    def test_add_duplicate_npc_rejected(self) -> None:
        scene = make_village_scene()
        merchant = make_merchant()
        result = self.engine.add_npc(scene, merchant)
        assert not result.success
        assert "already in" in result.reason

    def test_remove_npc_succeeds(self) -> None:
        scene = make_village_scene()
        merchant = make_merchant()
        result = self.engine.remove_npc(scene, merchant)
        assert result.success
        assert NPC_MERCHANT_ID not in scene.npc_ids
        assert merchant.scene_id is None

    def test_remove_npc_not_in_scene_rejected(self) -> None:
        scene = make_cave_scene()
        merchant = make_merchant()
        result = self.engine.remove_npc(scene, merchant)
        assert not result.success
        assert "not in" in result.reason


class TestMembershipTransfer:
    def setup_method(self) -> None:
        self.engine = SceneMembershipEngine()

    def test_transfer_character_succeeds(self) -> None:
        cave = make_cave_scene()
        village = make_village_scene()
        alara = make_alara()

        result = self.engine.transfer_character(cave, village, alara)
        assert result.success
        assert CHARACTER_ALARA_ID not in cave.character_ids
        assert CHARACTER_ALARA_ID in village.character_ids
        assert alara.scene_id == SCENE_VILLAGE_ID

    def test_transfer_from_wrong_scene_fails(self) -> None:
        cave = make_cave_scene()
        village = make_village_scene()
        corwin = make_corwin()  # In village, not cave

        result = self.engine.transfer_character(cave, village, corwin)
        assert not result.success
        assert "Transfer failed" in result.reason

    def test_transfer_updates_player_ids(self) -> None:
        cave = make_cave_scene()
        village = make_village_scene()
        alara = make_alara()

        self.engine.transfer_character(cave, village, alara)
        assert PLAYER_ALARA_ID not in cave.player_ids
        assert PLAYER_ALARA_ID in village.player_ids


class TestMembershipGetters:
    def setup_method(self) -> None:
        self.engine = SceneMembershipEngine()

    def test_get_scene_characters(self) -> None:
        scene = make_cave_scene()
        all_chars = [make_alara(), make_bren(), make_corwin()]
        result = self.engine.get_scene_characters(scene, all_chars)
        assert len(result) == 2
        ids = {c.character_id for c in result}
        assert ids == {CHARACTER_ALARA_ID, CHARACTER_BREN_ID}

    def test_get_scene_npcs(self) -> None:
        scene = make_village_scene()
        all_npcs = [make_merchant()]
        result = self.engine.get_scene_npcs(scene, all_npcs)
        assert len(result) == 1
        assert result[0].npc_id == NPC_MERCHANT_ID

    def test_get_scene_characters_empty(self) -> None:
        scene = make_cave_scene()
        result = self.engine.get_scene_characters(scene, [make_corwin()])
        assert result == []

    def test_get_scene_npcs_empty(self) -> None:
        scene = make_cave_scene()
        result = self.engine.get_scene_npcs(scene, [make_merchant()])
        assert result == []


# =========================================================================
# MultiSceneEngine
# =========================================================================


class TestMultiSceneEngine:
    def setup_method(self) -> None:
        self.engine = MultiSceneEngine()

    def test_get_active_scenes(self) -> None:
        cave = make_cave_scene()
        village = make_village_scene()
        idle = make_idle_village_scene()
        idle.scene_id = "scene-idle"

        result = self.engine.get_active_scenes([cave, village, idle])
        assert len(result) == 2
        ids = {s.scene_id for s in result}
        assert ids == {SCENE_CAVE_ID, SCENE_VILLAGE_ID}

    def test_get_active_scenes_excludes_empty_player_list(self) -> None:
        cave = make_cave_scene()
        cave.player_ids = []
        result = self.engine.get_active_scenes([cave])
        assert result == []

    def test_get_active_scenes_excludes_paused(self) -> None:
        cave = make_cave_scene()
        cave.state = SceneState.paused
        result = self.engine.get_active_scenes([cave])
        assert result == []

    def test_build_active_set(self) -> None:
        cave = make_cave_scene()
        village = make_village_scene()
        tw_cave = make_cave_turn_window()
        tw_village = make_village_turn_window()

        active_set = self.engine.build_active_set(
            CAMPAIGN_ID, [cave, village], [tw_cave, tw_village]
        )
        assert active_set.campaign_id == CAMPAIGN_ID
        assert len(active_set.scenes) == 2
        assert SCENE_CAVE_ID in active_set.turn_windows
        assert SCENE_VILLAGE_ID in active_set.turn_windows

    def test_build_active_set_missing_turn_window(self) -> None:
        cave = make_cave_scene()
        village = make_village_scene()
        village.active_turn_window_id = None

        active_set = self.engine.build_active_set(
            CAMPAIGN_ID, [cave, village], [make_cave_turn_window()]
        )
        assert SCENE_CAVE_ID in active_set.turn_windows
        assert SCENE_VILLAGE_ID not in active_set.turn_windows

    def test_activate_scene(self) -> None:
        scene = make_idle_village_scene()
        assert scene.state == SceneState.idle
        self.engine.activate_scene(scene)
        assert scene.state == SceneState.awaiting_actions

    def test_activate_already_active_no_change(self) -> None:
        scene = make_cave_scene()
        assert scene.state == SceneState.awaiting_actions
        self.engine.activate_scene(scene)
        assert scene.state == SceneState.awaiting_actions

    def test_deactivate_scene(self) -> None:
        scene = make_cave_scene()
        self.engine.deactivate_scene(scene)
        assert scene.state == SceneState.idle
        assert scene.active_turn_window_id is None

    def test_deactivate_does_not_affect_other_scene(self) -> None:
        cave = make_cave_scene()
        village = make_village_scene()
        self.engine.deactivate_scene(cave)
        assert cave.state == SceneState.idle
        assert village.state == SceneState.awaiting_actions


# =========================================================================
# SubgroupPromptEngine
# =========================================================================


class TestSubgroupPromptEngine:
    def setup_method(self) -> None:
        self.engine = SubgroupPromptEngine()

    def test_filter_facts_for_scene(self) -> None:
        cave_fact = make_cave_fact()
        village_fact = make_village_fact()
        result = self.engine.filter_facts_for_scene(
            SCENE_CAVE_ID, [cave_fact, village_fact]
        )
        assert len(result) == 1
        assert result[0].fact_id == cave_fact.fact_id

    def test_filter_facts_empty(self) -> None:
        village_fact = make_village_fact()
        result = self.engine.filter_facts_for_scene(SCENE_CAVE_ID, [village_fact])
        assert result == []

    def test_assemble_cave_context(self) -> None:
        cave = make_cave_scene()
        all_chars = [make_alara(), make_bren(), make_corwin()]
        all_facts = [make_cave_fact(), make_village_fact()]
        scopes = {
            SCOPE_PUBLIC_CAVE_ID: make_public_cave_scope(),
            SCOPE_PUBLIC_VILLAGE_ID: make_public_village_scope(),
        }
        all_npcs = [make_merchant()]
        all_groups = [make_bat_swarm()]

        ctx = self.engine.assemble_subgroup_context(
            cave, all_chars, all_facts, scopes, all_npcs, all_groups
        )
        assert ctx.scene.scene_id == SCENE_CAVE_ID
        assert len(ctx.characters) == 2
        assert len(ctx.public_facts) == 1
        assert ctx.public_facts[0].scene_id == SCENE_CAVE_ID
        assert len(ctx.scene_npcs) == 0  # merchant not in cave
        assert len(ctx.scene_monster_groups) == 1

    def test_assemble_village_context(self) -> None:
        village = make_village_scene()
        all_chars = [make_alara(), make_bren(), make_corwin()]
        all_facts = [make_cave_fact(), make_village_fact()]
        scopes = {
            SCOPE_PUBLIC_CAVE_ID: make_public_cave_scope(),
            SCOPE_PUBLIC_VILLAGE_ID: make_public_village_scope(),
        }
        all_npcs = [make_merchant()]
        all_groups = [make_bat_swarm()]

        ctx = self.engine.assemble_subgroup_context(
            village, all_chars, all_facts, scopes, all_npcs, all_groups
        )
        assert ctx.scene.scene_id == SCENE_VILLAGE_ID
        assert len(ctx.characters) == 1
        assert ctx.characters[0].character_id == CHARACTER_CORWIN_ID
        assert len(ctx.public_facts) == 1
        assert ctx.public_facts[0].scene_id == SCENE_VILLAGE_ID
        assert len(ctx.scene_npcs) == 1
        assert len(ctx.scene_monster_groups) == 0

    def test_cross_scene_facts_excluded(self) -> None:
        cave = make_cave_scene()
        village_fact = make_village_fact()
        scopes = {SCOPE_PUBLIC_VILLAGE_ID: make_public_village_scope()}

        ctx = self.engine.assemble_subgroup_context(
            cave, [], [village_fact], scopes, [], []
        )
        assert len(ctx.public_facts) == 0

    def test_player_ids_match_scene(self) -> None:
        cave = make_cave_scene()
        ctx = self.engine.assemble_subgroup_context(cave, [], [], {}, [], [])
        assert set(ctx.player_ids) == {PLAYER_ALARA_ID, PLAYER_BREN_ID}


# =========================================================================
# SplitPartyTimingPolicy
# =========================================================================


class TestSplitPartyTimingIndependent:
    def setup_method(self) -> None:
        self.policy = SplitPartyTimingPolicy(sync_mode="independent")
        self.multi = MultiSceneEngine()

    def _make_active_set(self):
        cave = make_cave_scene()
        village = make_village_scene()
        return self.multi.build_active_set(
            CAMPAIGN_ID,
            [cave, village],
            [make_cave_turn_window(), make_village_turn_window()],
        )

    def test_cave_resolves_when_cave_players_ready(self) -> None:
        active_set = self._make_active_set()
        actions = {
            SCENE_CAVE_ID: [
                make_committed_action(
                    PLAYER_ALARA_ID, CHARACTER_ALARA_ID, TURN_WINDOW_CAVE_ID
                ),
                make_committed_action(
                    PLAYER_BREN_ID, CHARACTER_BREN_ID, TURN_WINDOW_CAVE_ID
                ),
            ]
        }
        players = {
            SCENE_CAVE_ID: [PLAYER_ALARA_ID, PLAYER_BREN_ID],
            SCENE_VILLAGE_ID: [PLAYER_CORWIN_ID],
        }
        assert self.policy.should_resolve_scene(
            SCENE_CAVE_ID, active_set, actions, players
        )

    def test_cave_does_not_resolve_when_missing_player(self) -> None:
        active_set = self._make_active_set()
        actions = {
            SCENE_CAVE_ID: [
                make_committed_action(
                    PLAYER_ALARA_ID, CHARACTER_ALARA_ID, TURN_WINDOW_CAVE_ID
                ),
            ]
        }
        players = {
            SCENE_CAVE_ID: [PLAYER_ALARA_ID, PLAYER_BREN_ID],
        }
        assert not self.policy.should_resolve_scene(
            SCENE_CAVE_ID, active_set, actions, players
        )

    def test_village_resolves_independently(self) -> None:
        active_set = self._make_active_set()
        actions = {
            SCENE_VILLAGE_ID: [
                make_committed_action(
                    PLAYER_CORWIN_ID,
                    CHARACTER_CORWIN_ID,
                    TURN_WINDOW_VILLAGE_ID,
                ),
            ]
        }
        players = {
            SCENE_CAVE_ID: [PLAYER_ALARA_ID, PLAYER_BREN_ID],
            SCENE_VILLAGE_ID: [PLAYER_CORWIN_ID],
        }
        # Village resolves even though cave isn't ready
        assert self.policy.should_resolve_scene(
            SCENE_VILLAGE_ID, active_set, actions, players
        )

    def test_empty_scene_resolves(self) -> None:
        active_set = self._make_active_set()
        assert self.policy.should_resolve_scene(SCENE_CAVE_ID, active_set, {}, {})


class TestSplitPartyTimingSynchronized:
    def setup_method(self) -> None:
        self.policy = SplitPartyTimingPolicy(sync_mode="synchronized")
        self.multi = MultiSceneEngine()

    def _make_active_set(self):
        cave = make_cave_scene()
        village = make_village_scene()
        return self.multi.build_active_set(
            CAMPAIGN_ID,
            [cave, village],
            [make_cave_turn_window(), make_village_turn_window()],
        )

    def test_cave_does_not_resolve_when_village_not_ready(self) -> None:
        active_set = self._make_active_set()
        actions = {
            SCENE_CAVE_ID: [
                make_committed_action(
                    PLAYER_ALARA_ID, CHARACTER_ALARA_ID, TURN_WINDOW_CAVE_ID
                ),
                make_committed_action(
                    PLAYER_BREN_ID, CHARACTER_BREN_ID, TURN_WINDOW_CAVE_ID
                ),
            ]
        }
        players = {
            SCENE_CAVE_ID: [PLAYER_ALARA_ID, PLAYER_BREN_ID],
            SCENE_VILLAGE_ID: [PLAYER_CORWIN_ID],
        }
        assert not self.policy.should_resolve_scene(
            SCENE_CAVE_ID, active_set, actions, players
        )

    def test_both_resolve_when_all_ready(self) -> None:
        active_set = self._make_active_set()
        actions = {
            SCENE_CAVE_ID: [
                make_committed_action(
                    PLAYER_ALARA_ID, CHARACTER_ALARA_ID, TURN_WINDOW_CAVE_ID
                ),
                make_committed_action(
                    PLAYER_BREN_ID, CHARACTER_BREN_ID, TURN_WINDOW_CAVE_ID
                ),
            ],
            SCENE_VILLAGE_ID: [
                make_committed_action(
                    PLAYER_CORWIN_ID,
                    CHARACTER_CORWIN_ID,
                    TURN_WINDOW_VILLAGE_ID,
                ),
            ],
        }
        players = {
            SCENE_CAVE_ID: [PLAYER_ALARA_ID, PLAYER_BREN_ID],
            SCENE_VILLAGE_ID: [PLAYER_CORWIN_ID],
        }
        assert self.policy.should_resolve_scene(
            SCENE_CAVE_ID, active_set, actions, players
        )
        assert self.policy.should_resolve_scene(
            SCENE_VILLAGE_ID, active_set, actions, players
        )

    def test_all_scenes_ready(self) -> None:
        active_set = self._make_active_set()
        actions = {
            SCENE_CAVE_ID: [
                make_committed_action(
                    PLAYER_ALARA_ID, CHARACTER_ALARA_ID, TURN_WINDOW_CAVE_ID
                ),
                make_committed_action(
                    PLAYER_BREN_ID, CHARACTER_BREN_ID, TURN_WINDOW_CAVE_ID
                ),
            ],
            SCENE_VILLAGE_ID: [
                make_committed_action(
                    PLAYER_CORWIN_ID,
                    CHARACTER_CORWIN_ID,
                    TURN_WINDOW_VILLAGE_ID,
                ),
            ],
        }
        players = {
            SCENE_CAVE_ID: [PLAYER_ALARA_ID, PLAYER_BREN_ID],
            SCENE_VILLAGE_ID: [PLAYER_CORWIN_ID],
        }
        assert self.policy.all_scenes_ready(active_set, actions, players)

    def test_all_scenes_not_ready(self) -> None:
        active_set = self._make_active_set()
        actions = {
            SCENE_CAVE_ID: [
                make_committed_action(
                    PLAYER_ALARA_ID, CHARACTER_ALARA_ID, TURN_WINDOW_CAVE_ID
                ),
            ],
        }
        players = {
            SCENE_CAVE_ID: [PLAYER_ALARA_ID, PLAYER_BREN_ID],
            SCENE_VILLAGE_ID: [PLAYER_CORWIN_ID],
        }
        assert not self.policy.all_scenes_ready(active_set, actions, players)


# =========================================================================
# InformationPropagationEngine
# =========================================================================


class TestPropagationQueue:
    def setup_method(self) -> None:
        self.engine = InformationPropagationEngine()

    def test_queue_propagation(self) -> None:
        fact = make_cave_fact()
        event = self.engine.queue_propagation(
            fact, SCENE_CAVE_ID, SCENE_VILLAGE_ID, delay_turns=2, current_turn=1
        )
        assert event.source_scene_id == SCENE_CAVE_ID
        assert event.target_scene_id == SCENE_VILLAGE_ID
        assert event.delay_turns == 2
        assert event.queued_at_turn == 1
        assert not event.delivered

    def test_queue_with_custom_event_id(self) -> None:
        fact = make_cave_fact()
        event = self.engine.queue_propagation(
            fact,
            SCENE_CAVE_ID,
            SCENE_VILLAGE_ID,
            delay_turns=1,
            current_turn=1,
            event_id="custom-id",
        )
        assert event.event_id == "custom-id"


class TestPropagationCheck:
    def setup_method(self) -> None:
        self.engine = InformationPropagationEngine()

    def test_not_deliverable_before_delay(self) -> None:
        fact = make_cave_fact()
        event = self.engine.queue_propagation(
            fact, SCENE_CAVE_ID, SCENE_VILLAGE_ID, delay_turns=3, current_turn=1
        )
        result = self.engine.check_deliverable([event], current_turn=2)
        assert result == []

    def test_deliverable_after_delay(self) -> None:
        fact = make_cave_fact()
        event = self.engine.queue_propagation(
            fact, SCENE_CAVE_ID, SCENE_VILLAGE_ID, delay_turns=2, current_turn=1
        )
        result = self.engine.check_deliverable([event], current_turn=3)
        assert len(result) == 1
        assert result[0].event_id == event.event_id

    def test_deliverable_at_exact_turn(self) -> None:
        fact = make_cave_fact()
        event = self.engine.queue_propagation(
            fact, SCENE_CAVE_ID, SCENE_VILLAGE_ID, delay_turns=2, current_turn=1
        )
        result = self.engine.check_deliverable([event], current_turn=3)
        assert len(result) == 1

    def test_zero_delay_deliverable_immediately(self) -> None:
        fact = make_cave_fact()
        event = self.engine.queue_propagation(
            fact, SCENE_CAVE_ID, SCENE_VILLAGE_ID, delay_turns=0, current_turn=5
        )
        result = self.engine.check_deliverable([event], current_turn=5)
        assert len(result) == 1

    def test_already_delivered_excluded(self) -> None:
        fact = make_cave_fact()
        event = self.engine.queue_propagation(
            fact, SCENE_CAVE_ID, SCENE_VILLAGE_ID, delay_turns=1, current_turn=1
        )
        event.delivered = True
        result = self.engine.check_deliverable([event], current_turn=10)
        assert result == []

    def test_multiple_events_filtered(self) -> None:
        f1 = make_cave_fact("fact-1")
        f2 = make_cave_fact("fact-2")
        e1 = self.engine.queue_propagation(
            f1, SCENE_CAVE_ID, SCENE_VILLAGE_ID, delay_turns=1, current_turn=1
        )
        e2 = self.engine.queue_propagation(
            f2, SCENE_CAVE_ID, SCENE_VILLAGE_ID, delay_turns=5, current_turn=1
        )
        result = self.engine.check_deliverable([e1, e2], current_turn=3)
        assert len(result) == 1
        assert result[0].event_id == e1.event_id


class TestPropagationDeliver:
    def setup_method(self) -> None:
        self.engine = InformationPropagationEngine()

    def test_deliver_marks_delivered(self) -> None:
        fact = make_cave_fact()
        event = self.engine.queue_propagation(
            fact, SCENE_CAVE_ID, SCENE_VILLAGE_ID, delay_turns=1, current_turn=1
        )
        updated_event, new_fact = self.engine.deliver(event, SCOPE_PUBLIC_VILLAGE_ID)
        assert updated_event.delivered
        assert event.delivered  # same object

    def test_deliver_creates_fact_in_target_scene(self) -> None:
        fact = make_cave_fact()
        event = self.engine.queue_propagation(
            fact, SCENE_CAVE_ID, SCENE_VILLAGE_ID, delay_turns=1, current_turn=1
        )
        _, new_fact = self.engine.deliver(event, SCOPE_PUBLIC_VILLAGE_ID)
        assert new_fact.scene_id == SCENE_VILLAGE_ID
        assert new_fact.owner_scope_id == SCOPE_PUBLIC_VILLAGE_ID

    def test_deliver_prefixes_payload(self) -> None:
        fact = make_cave_fact()
        event = self.engine.queue_propagation(
            fact, SCENE_CAVE_ID, SCENE_VILLAGE_ID, delay_turns=1, current_turn=1
        )
        _, new_fact = self.engine.deliver(event, SCOPE_PUBLIC_VILLAGE_ID)
        assert new_fact.payload.startswith("[delayed] ")
        assert fact.payload in new_fact.payload

    def test_deliver_preserves_fact_type(self) -> None:
        fact = make_cave_fact()
        event = self.engine.queue_propagation(
            fact, SCENE_CAVE_ID, SCENE_VILLAGE_ID, delay_turns=1, current_turn=1
        )
        _, new_fact = self.engine.deliver(event, SCOPE_PUBLIC_VILLAGE_ID)
        assert new_fact.fact_type == fact.fact_type

    def test_deliver_with_custom_fact_id(self) -> None:
        fact = make_cave_fact()
        event = self.engine.queue_propagation(
            fact, SCENE_CAVE_ID, SCENE_VILLAGE_ID, delay_turns=1, current_turn=1
        )
        _, new_fact = self.engine.deliver(
            event, SCOPE_PUBLIC_VILLAGE_ID, new_fact_id="custom-fact"
        )
        assert new_fact.fact_id == "custom-fact"


# =========================================================================
# Full integration
# =========================================================================


class TestSplitPartyIntegration:
    def test_split_act_rejoin(self) -> None:
        """Full flow: split party → each scene acts → rejoin."""
        membership = SceneMembershipEngine()
        multi = MultiSceneEngine()
        prompts = SubgroupPromptEngine()

        cave = make_cave_scene()
        village = make_village_scene()
        alara = make_alara()
        bren = make_bren()
        corwin = make_corwin()
        merchant = make_merchant()

        # Verify initial split
        active = multi.get_active_scenes([cave, village])
        assert len(active) == 2

        # Verify cave context isolation
        cave_ctx = prompts.assemble_subgroup_context(
            cave,
            [alara, bren, corwin],
            [make_cave_fact(), make_village_fact()],
            {
                SCOPE_PUBLIC_CAVE_ID: make_public_cave_scope(),
                SCOPE_PUBLIC_VILLAGE_ID: make_public_village_scope(),
            },
            [merchant],
            [make_bat_swarm()],
        )
        assert len(cave_ctx.characters) == 2
        assert len(cave_ctx.public_facts) == 1
        assert cave_ctx.public_facts[0].scene_id == SCENE_CAVE_ID
        assert len(cave_ctx.scene_npcs) == 0  # merchant is in village
        assert len(cave_ctx.scene_monster_groups) == 1

        # Transfer Alara from cave to village (rejoin)
        result = membership.transfer_character(cave, village, alara)
        assert result.success
        assert alara.scene_id == SCENE_VILLAGE_ID
        assert CHARACTER_ALARA_ID not in cave.character_ids
        assert CHARACTER_ALARA_ID in village.character_ids

        # After rejoin, village context includes Alara
        village_ctx = prompts.assemble_subgroup_context(
            village,
            [alara, bren, corwin],
            [make_cave_fact(), make_village_fact()],
            {
                SCOPE_PUBLIC_CAVE_ID: make_public_cave_scope(),
                SCOPE_PUBLIC_VILLAGE_ID: make_public_village_scope(),
            },
            [merchant],
            [make_bat_swarm()],
        )
        assert len(village_ctx.characters) == 2  # Corwin + Alara
        char_ids = {c.character_id for c in village_ctx.characters}
        assert char_ids == {CHARACTER_CORWIN_ID, CHARACTER_ALARA_ID}
        assert len(village_ctx.public_facts) == 1
        assert village_ctx.public_facts[0].scene_id == SCENE_VILLAGE_ID

    def test_propagation_full_cycle(self) -> None:
        """Queue → not ready → ready → deliver → verify target fact."""
        prop = InformationPropagationEngine()
        cave_fact = make_cave_fact()

        event = prop.queue_propagation(
            cave_fact,
            SCENE_CAVE_ID,
            SCENE_VILLAGE_ID,
            delay_turns=2,
            current_turn=1,
        )

        # Turn 2: not ready yet
        assert prop.check_deliverable([event], current_turn=2) == []

        # Turn 3: ready
        deliverable = prop.check_deliverable([event], current_turn=3)
        assert len(deliverable) == 1

        # Deliver
        updated, new_fact = prop.deliver(event, SCOPE_PUBLIC_VILLAGE_ID)
        assert updated.delivered
        assert new_fact.scene_id == SCENE_VILLAGE_ID
        assert "[delayed]" in new_fact.payload

        # Re-check: should not re-deliver
        assert prop.check_deliverable([event], current_turn=10) == []

    def test_activate_deactivate_cycle(self) -> None:
        """Activate idle scene → verify active → deactivate → verify idle."""
        multi = MultiSceneEngine()
        scene = make_idle_village_scene()

        assert scene.state == SceneState.idle
        assert multi.get_active_scenes([scene]) == []

        multi.activate_scene(scene)
        # Need to add a player to make it count as active
        scene.player_ids = [PLAYER_CORWIN_ID]
        assert len(multi.get_active_scenes([scene])) == 1

        multi.deactivate_scene(scene)
        assert scene.state == SceneState.idle
        assert multi.get_active_scenes([scene]) == []
