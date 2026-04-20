"""Tests for the combat loop — Phase 10.

Covers: entry/exit conditions, all action types, monster AI, damage/armor,
status effects, morale, visibility/awareness, battlefield summaries,
and a full goblin patrol scenario integration.
"""

from __future__ import annotations

from server.combat.actions import CombatActionEngine
from server.combat.conditions import CombatConditionEngine
from server.combat.monsters import MonsterBehaviorEngine, MoraleEngine
from server.combat.resolution import CombatResolutionEngine
from server.combat.summaries import BattlefieldSummaryBuilder
from server.combat.visibility import CombatVisibilityEngine
from server.domain.enums import AwarenessState, BehaviorMode
from tests.fixtures.combat_scenario import (
    CHARACTER_DAIN_ID,
    GOBLIN_PATROL_ID,
    PLAYER_DAIN_ID,
    PLAYER_KIRA_ID,
    SCENE_CLEARING_ID,
    WOLF_PACK_ID,
    make_dain,
    make_empty_flask,
    make_forest_clearing,
    make_forest_trail,
    make_goblin_patrol,
    make_healing_potion,
    make_kira,
    make_wolf_pack,
)


# ===========================================================================
# Combat Entry / Exit Conditions
# ===========================================================================


class TestCombatEntryConditions:
    def setup_method(self):
        self.engine = CombatConditionEngine()

    def test_entry_with_engaged_group(self):
        scene = make_forest_clearing()
        goblins = make_goblin_patrol(awareness=AwarenessState.engaged)
        result = self.engine.check_entry(scene, [goblins], [make_kira()])
        assert result.entered is True
        assert "goblin" in result.reason

    def test_no_entry_without_engaged(self):
        scene = make_forest_clearing()
        goblins = make_goblin_patrol(awareness=AwarenessState.aware)
        result = self.engine.check_entry(scene, [goblins], [make_kira()])
        assert result.entered is False

    def test_no_entry_with_unaware_groups(self):
        scene = make_forest_clearing()
        wolves = make_wolf_pack(awareness=AwarenessState.unaware)
        result = self.engine.check_entry(scene, [wolves], [make_kira()])
        assert result.entered is False

    def test_entry_filters_by_scene(self):
        scene = make_forest_clearing()
        goblins = make_goblin_patrol(awareness=AwarenessState.engaged)
        goblins.scene_id = "other-scene"
        result = self.engine.check_entry(scene, [goblins], [make_kira()])
        assert result.entered is False

    def test_entry_multiple_groups_one_engaged(self):
        scene = make_forest_clearing()
        goblins = make_goblin_patrol(awareness=AwarenessState.engaged)
        wolves = make_wolf_pack(awareness=AwarenessState.unaware)
        wolves.scene_id = SCENE_CLEARING_ID
        result = self.engine.check_entry(scene, [goblins, wolves], [make_kira()])
        assert result.entered is True


class TestCombatExitConditions:
    def setup_method(self):
        self.engine = CombatConditionEngine()

    def test_victory_all_groups_defeated(self):
        scene = make_forest_clearing()
        goblins = make_goblin_patrol()
        goblins.count = 0
        result = self.engine.check_exit(scene, [goblins], [make_kira()])
        assert result.exited is True
        assert result.exit_type == "victory"

    def test_annihilation_all_characters_dead(self):
        scene = make_forest_clearing()
        goblins = make_goblin_patrol()
        kira = make_kira()
        kira.is_alive = False
        dain = make_dain()
        dain.is_alive = False
        result = self.engine.check_exit(scene, [goblins], [kira, dain])
        assert result.exited is True
        assert result.exit_type == "annihilation"

    def test_flee_all_groups_routed(self):
        scene = make_forest_clearing()
        goblins = make_goblin_patrol()
        goblins.morale_state = "routed"
        goblins.count = 1
        result = self.engine.check_exit(scene, [goblins], [make_kira()])
        assert result.exited is True
        assert result.exit_type == "flee"

    def test_no_exit_combat_ongoing(self):
        scene = make_forest_clearing()
        goblins = make_goblin_patrol()
        result = self.engine.check_exit(scene, [goblins], [make_kira()])
        assert result.exited is False

    def test_victory_ignores_already_dead_groups(self):
        scene = make_forest_clearing()
        g1 = make_goblin_patrol()
        g1.count = 0
        g2 = make_wolf_pack()
        g2.count = 0
        g2.scene_id = SCENE_CLEARING_ID
        result = self.engine.check_exit(scene, [g1, g2], [make_kira()])
        assert result.exited is True
        assert result.exit_type == "victory"

    def test_flee_only_counts_alive_groups(self):
        scene = make_forest_clearing()
        g1 = make_goblin_patrol()
        g1.count = 0  # dead
        g2 = make_wolf_pack()
        g2.count = 2
        g2.morale_state = "routed"
        g2.scene_id = SCENE_CLEARING_ID
        result = self.engine.check_exit(scene, [g1, g2], [make_kira()])
        # g1 dead + g2 routed → check victory first (all count==0? no, g2 has 2)
        # alive_groups = [g2], all routed → flee
        assert result.exited is True
        assert result.exit_type == "flee"


# ===========================================================================
# Combat Actions
# ===========================================================================


class TestAttackAction:
    def setup_method(self):
        self.engine = CombatActionEngine()

    def test_attack_monster_group(self):
        kira = make_kira()
        goblins = make_goblin_patrol()
        result = self.engine.resolve_attack(kira, GOBLIN_PATROL_ID, [goblins], [])
        # attack=8, defense=2 → damage=6
        assert result.hit is True
        assert result.damage_dealt == 6

    def test_attack_character(self):
        kira = make_kira()
        dain = make_dain()
        result = self.engine.resolve_attack(kira, CHARACTER_DAIN_ID, [], [dain])
        # attack=8, defense=3 → damage=5
        assert result.hit is True
        assert result.damage_dealt == 5

    def test_attack_defended_character(self):
        kira = make_kira()
        dain = make_dain()
        dain.status_effects.append("defended")
        result = self.engine.resolve_attack(kira, CHARACTER_DAIN_ID, [], [dain])
        # attack=8, defense=3+3=6 → damage=2
        assert result.hit is True
        assert result.damage_dealt == 2

    def test_attack_invisible_group_fails(self):
        kira = make_kira()
        wolves = make_wolf_pack()
        wolves.is_visible = False
        result = self.engine.resolve_attack(kira, WOLF_PACK_ID, [wolves], [])
        assert result.hit is False
        assert result.target_new_health == "hidden"

    def test_attack_missing_target(self):
        kira = make_kira()
        result = self.engine.resolve_attack(kira, "nonexistent", [], [])
        assert result.hit is False
        assert result.target_new_health == "target not found"

    def test_blinded_attacker_deals_no_damage(self):
        kira = make_kira()
        kira.status_effects.append("blinded")
        goblins = make_goblin_patrol()
        result = self.engine.resolve_attack(kira, GOBLIN_PATROL_ID, [goblins], [])
        assert result.hit is False
        assert result.damage_dealt == 0

    def test_stunned_attacker_cannot_attack(self):
        kira = make_kira()
        kira.status_effects.append("stunned")
        goblins = make_goblin_patrol()
        result = self.engine.resolve_attack(kira, GOBLIN_PATROL_ID, [goblins], [])
        assert result.hit is False
        assert result.damage_dealt == 0

    def test_attack_zero_damage_clamped(self):
        kira = make_kira()
        kira.stats["attack"] = 1  # 1 - 2 = -1 → clamped to 0
        goblins = make_goblin_patrol()
        result = self.engine.resolve_attack(kira, GOBLIN_PATROL_ID, [goblins], [])
        assert result.hit is False
        assert result.damage_dealt == 0


class TestDefendAction:
    def setup_method(self):
        self.engine = CombatActionEngine()

    def test_defend_adds_status_effect(self):
        kira = make_kira()
        result = self.engine.resolve_defend(kira)
        assert "defended" in result.character.status_effects
        assert result.armor_bonus == 3

    def test_defend_idempotent(self):
        kira = make_kira()
        self.engine.resolve_defend(kira)
        self.engine.resolve_defend(kira)
        assert kira.status_effects.count("defended") == 1


class TestAssistAction:
    def setup_method(self):
        self.engine = CombatActionEngine()

    def test_assist_heals_damaged_ally(self):
        kira = make_kira()
        dain = make_dain()
        dain.stats["hp"] = 10
        result = self.engine.resolve_assist(kira, CHARACTER_DAIN_ID, [dain])
        assert result.success is True
        assert result.effect == "heal 5"
        assert dain.stats["hp"] == 15

    def test_assist_heal_capped_at_max_hp(self):
        kira = make_kira()
        dain = make_dain()
        dain.stats["hp"] = 18
        result = self.engine.resolve_assist(kira, CHARACTER_DAIN_ID, [dain])
        assert result.effect == "heal 2"
        assert dain.stats["hp"] == 20

    def test_assist_buffs_at_full_hp(self):
        kira = make_kira()
        dain = make_dain()
        result = self.engine.resolve_assist(kira, CHARACTER_DAIN_ID, [dain])
        assert result.success is True
        assert result.effect == "buff"
        assert "assisted" in dain.status_effects

    def test_assist_missing_target(self):
        kira = make_kira()
        result = self.engine.resolve_assist(kira, "nonexistent", [])
        assert result.success is False


class TestUseItemAction:
    def setup_method(self):
        self.engine = CombatActionEngine()

    def test_use_healing_potion(self):
        kira = make_kira()
        kira.stats["hp"] = 10
        potion = make_healing_potion()
        result = self.engine.resolve_use_item(kira, potion)
        assert result.success is True
        assert result.effect == "heal 10"
        assert kira.stats["hp"] == 20
        assert potion.quantity == 0

    def test_use_item_none(self):
        kira = make_kira()
        result = self.engine.resolve_use_item(kira, None)
        assert result.success is False
        assert result.rejection_reason == "Item not found"

    def test_use_item_no_effect(self):
        kira = make_kira()
        flask = make_empty_flask()
        result = self.engine.resolve_use_item(kira, flask)
        assert result.success is False
        assert result.rejection_reason == "Item has no usable effect"


class TestUseAbilityAction:
    def setup_method(self):
        self.engine = CombatActionEngine()

    def test_use_ability_placeholder(self):
        kira = make_kira()
        result = self.engine.resolve_use_ability(kira, "fireball")
        assert result.success is True
        assert "fireball" in result.effect


class TestCombatMoveAction:
    def setup_method(self):
        self.engine = CombatActionEngine()

    def test_move_to_valid_exit(self):
        kira = make_kira()
        clearing = make_forest_clearing()
        trail = make_forest_trail()
        result = self.engine.resolve_combat_move(kira, clearing, trail)
        assert result.success is True
        assert kira.scene_id == trail.scene_id

    def test_move_to_invalid_exit(self):
        kira = make_kira()
        clearing = make_forest_clearing()
        from tests.fixtures.combat_scenario import _now, CAMPAIGN_ID
        from server.domain.entities import Scene
        from server.domain.enums import SceneState

        fake_scene = Scene(
            scene_id="scene-nowhere",
            campaign_id=CAMPAIGN_ID,
            name="Nowhere",
            description="",
            created_at=_now(),
            state=SceneState.idle,
        )
        result = self.engine.resolve_combat_move(kira, clearing, fake_scene)
        assert result.success is False
        assert result.rejection_reason == "No exit to destination"


# ===========================================================================
# Monster Behavior
# ===========================================================================


class TestMonsterBehavior:
    def setup_method(self):
        self.engine = MonsterBehaviorEngine()

    def test_patrol_attacks_highest_threat(self):
        goblins = make_goblin_patrol()
        goblins.threat_table = {PLAYER_KIRA_ID: 10, PLAYER_DAIN_ID: 20}
        kira = make_kira()
        dain = make_dain()
        decision = self.engine.decide_action(goblins, [kira, dain])
        assert decision.action_type == "attack"
        assert decision.target_player_id == PLAYER_DAIN_ID

    def test_empty_threat_table_attacks_first(self):
        goblins = make_goblin_patrol()
        kira = make_kira()
        dain = make_dain()
        decision = self.engine.decide_action(goblins, [kira, dain])
        assert decision.action_type == "attack"
        assert decision.target_player_id == PLAYER_KIRA_ID

    def test_routed_group_flees(self):
        goblins = make_goblin_patrol()
        goblins.morale_state = "routed"
        decision = self.engine.decide_action(goblins, [make_kira()])
        assert decision.action_type == "flee"

    def test_flee_mode_flees(self):
        goblins = make_goblin_patrol()
        goblins.behavior_mode = BehaviorMode.flee
        decision = self.engine.decide_action(goblins, [make_kira()])
        assert decision.action_type == "flee"

    def test_idle_mode_does_nothing(self):
        goblins = make_goblin_patrol()
        goblins.behavior_mode = BehaviorMode.idle
        decision = self.engine.decide_action(goblins, [make_kira()])
        assert decision.action_type == "idle"

    def test_call_help_mode(self):
        goblins = make_goblin_patrol()
        goblins.behavior_mode = BehaviorMode.call_help
        decision = self.engine.decide_action(goblins, [make_kira()])
        assert decision.action_type == "call_help"

    def test_not_engaged_stays_idle(self):
        goblins = make_goblin_patrol(awareness=AwarenessState.aware)
        goblins.behavior_mode = BehaviorMode.patrol
        decision = self.engine.decide_action(goblins, [make_kira()])
        assert decision.action_type == "idle"

    def test_defend_mode_no_targets_in_territory(self):
        goblins = make_goblin_patrol()
        goblins.behavior_mode = BehaviorMode.defend
        goblins.territory_id = "other-scene"
        kira = make_kira()
        decision = self.engine.decide_action(goblins, [kira])
        assert decision.action_type == "defend"

    def test_defend_mode_attacks_in_territory(self):
        goblins = make_goblin_patrol()
        goblins.behavior_mode = BehaviorMode.defend
        goblins.territory_id = SCENE_CLEARING_ID
        kira = make_kira()
        decision = self.engine.decide_action(goblins, [kira])
        assert decision.action_type == "attack"

    def test_no_alive_targets_idles(self):
        goblins = make_goblin_patrol()
        kira = make_kira()
        kira.is_alive = False
        decision = self.engine.decide_action(goblins, [kira])
        assert decision.action_type == "idle"


class TestThreatUpdates:
    def setup_method(self):
        self.engine = MonsterBehaviorEngine()

    def test_increase_threat(self):
        goblins = make_goblin_patrol()
        self.engine.update_threat(goblins, PLAYER_KIRA_ID, 10)
        assert goblins.threat_table[PLAYER_KIRA_ID] == 10

    def test_decrease_threat_clamped(self):
        goblins = make_goblin_patrol()
        goblins.threat_table[PLAYER_KIRA_ID] = 3
        self.engine.update_threat(goblins, PLAYER_KIRA_ID, -10)
        assert goblins.threat_table[PLAYER_KIRA_ID] == 0

    def test_cumulative_threat(self):
        goblins = make_goblin_patrol()
        self.engine.update_threat(goblins, PLAYER_KIRA_ID, 10)
        self.engine.update_threat(goblins, PLAYER_KIRA_ID, 5)
        assert goblins.threat_table[PLAYER_KIRA_ID] == 15


# ===========================================================================
# Damage / Resolution
# ===========================================================================


class TestDamageResolution:
    def setup_method(self):
        self.engine = CombatResolutionEngine()

    def test_damage_to_character(self):
        kira = make_kira()
        _, result = self.engine.apply_damage_to_character(kira, 10)
        # defense=3, raw=10, final=7, new_hp=13
        assert result.final_damage == 7
        assert result.new_hp == 13
        assert result.is_defeated is False

    def test_damage_with_defend_bonus(self):
        kira = make_kira()
        kira.status_effects.append("defended")
        _, result = self.engine.apply_damage_to_character(kira, 10)
        # defense=3+3=6, raw=10, final=4, new_hp=16
        assert result.armor_reduction == 6
        assert result.final_damage == 4

    def test_lethal_damage(self):
        kira = make_kira()
        _, result = self.engine.apply_damage_to_character(kira, 30)
        assert result.is_defeated is True
        assert kira.is_alive is False

    def test_damage_clamped_at_zero(self):
        kira = make_kira()
        _, result = self.engine.apply_damage_to_character(kira, 1)
        # defense=3, raw=1 → final=0
        assert result.final_damage == 0
        assert result.new_hp == 20

    def test_damage_to_group_kills_unit(self):
        goblins = make_goblin_patrol(count=3)
        _, result = self.engine.apply_damage_to_group(goblins, 5, 3)
        assert goblins.count == 2
        assert result.is_defeated is False

    def test_damage_to_group_below_threshold(self):
        goblins = make_goblin_patrol(count=3)
        _, result = self.engine.apply_damage_to_group(goblins, 2, 3)
        # damage < 3 → no kill
        assert goblins.count == 3

    def test_damage_group_health_states(self):
        goblins = make_goblin_patrol(count=4)
        # 4/4 → healthy
        self.engine.apply_damage_to_group(goblins, 5, 4)
        assert goblins.count == 3
        assert goblins.health_state == "healthy"  # 3/4 > 0.5

        self.engine.apply_damage_to_group(goblins, 5, 4)
        assert goblins.count == 2
        assert goblins.health_state == "injured"  # 2/4 = 0.5 → <=0.5

        self.engine.apply_damage_to_group(goblins, 5, 4)
        assert goblins.count == 1
        assert goblins.health_state == "critical"  # 1/4 = 0.25 → <=0.25

        self.engine.apply_damage_to_group(goblins, 5, 4)
        assert goblins.count == 0
        assert goblins.health_state == "dead"

    def test_group_defeated(self):
        goblins = make_goblin_patrol(count=1)
        _, result = self.engine.apply_damage_to_group(goblins, 5, 1)
        assert result.is_defeated is True
        assert goblins.count == 0


# ===========================================================================
# Status Effects
# ===========================================================================


class TestStatusEffects:
    def setup_method(self):
        self.engine = CombatResolutionEngine()

    def test_apply_status_effect(self):
        kira = make_kira()
        self.engine.apply_status_effect(kira, "poisoned")
        assert "poisoned" in kira.status_effects

    def test_apply_status_effect_idempotent(self):
        kira = make_kira()
        self.engine.apply_status_effect(kira, "poisoned")
        self.engine.apply_status_effect(kira, "poisoned")
        assert kira.status_effects.count("poisoned") == 1

    def test_remove_status_effect(self):
        kira = make_kira()
        kira.status_effects.append("defended")
        self.engine.remove_status_effect(kira, "defended")
        assert "defended" not in kira.status_effects

    def test_remove_missing_effect_noop(self):
        kira = make_kira()
        self.engine.remove_status_effect(kira, "nonexistent")
        assert kira.status_effects == []

    def test_poison_ticks_damage(self):
        kira = make_kira()
        kira.status_effects.append("poisoned")
        _, fired = self.engine.process_status_effects(kira)
        assert "poisoned" in fired
        assert kira.stats["hp"] == 19

    def test_poison_can_kill(self):
        kira = make_kira()
        kira.stats["hp"] = 1
        kira.status_effects.append("poisoned")
        self.engine.process_status_effects(kira)
        assert kira.stats["hp"] == 0
        assert kira.is_alive is False

    def test_check_defeat(self):
        kira = make_kira()
        assert self.engine.check_defeat(kira) is False
        kira.stats["hp"] = 0
        assert self.engine.check_defeat(kira) is True


# ===========================================================================
# Morale
# ===========================================================================


class TestMorale:
    def setup_method(self):
        self.engine = MoraleEngine()

    def test_steady_to_shaken_at_half(self):
        goblins = make_goblin_patrol(count=2)
        self.engine.check_morale(goblins, 4)
        assert goblins.morale_state == "shaken"

    def test_steady_stays_above_half(self):
        goblins = make_goblin_patrol(count=3)
        self.engine.check_morale(goblins, 4)
        assert goblins.morale_state == "steady"

    def test_shaken_to_routed_at_quarter(self):
        goblins = make_goblin_patrol(count=1)
        goblins.morale_state = "shaken"
        self.engine.check_morale(goblins, 4)
        assert goblins.morale_state == "routed"
        assert goblins.behavior_mode == BehaviorMode.flee

    def test_leader_dead_forces_rout(self):
        goblins = make_goblin_patrol(count=2)
        goblins.morale_state = "shaken"
        goblins.special_rules.append("leader_dead")
        self.engine.check_morale(goblins, 4)
        assert goblins.morale_state == "routed"

    def test_flee_removes_from_scene(self):
        goblins = make_goblin_patrol()
        scene = make_forest_clearing()
        goblins, scene = self.engine.apply_flee(goblins, scene)
        assert GOBLIN_PATROL_ID not in scene.monster_group_ids
        assert goblins.is_visible is False

    def test_zero_original_count_noop(self):
        goblins = make_goblin_patrol(count=0)
        self.engine.check_morale(goblins, 0)
        assert goblins.morale_state == "steady"


# ===========================================================================
# Visibility / Awareness
# ===========================================================================


class TestVisibility:
    def setup_method(self):
        self.engine = CombatVisibilityEngine()

    def test_aware_and_engaged_are_visible(self):
        g1 = make_goblin_patrol(awareness=AwarenessState.aware)
        g2 = make_goblin_patrol(awareness=AwarenessState.engaged)
        g2.monster_group_id = "g2"
        result = self.engine.compute_visibility([g1, g2])
        assert len(result.visible_groups) == 2
        assert len(result.hidden_groups) == 0

    def test_unaware_and_alert_are_hidden(self):
        g1 = make_wolf_pack(awareness=AwarenessState.unaware)
        g2 = make_wolf_pack(awareness=AwarenessState.alert)
        g2.monster_group_id = "g2-alert"
        result = self.engine.compute_visibility([g1, g2])
        assert len(result.visible_groups) == 0
        assert len(result.hidden_groups) == 2

    def test_mixed_visibility(self):
        g_visible = make_goblin_patrol(awareness=AwarenessState.engaged)
        g_hidden = make_wolf_pack(awareness=AwarenessState.unaware)
        result = self.engine.compute_visibility([g_visible, g_hidden])
        assert len(result.visible_groups) == 1
        assert len(result.hidden_groups) == 1


class TestAwarenessTransitions:
    def setup_method(self):
        self.engine = CombatVisibilityEngine()

    def test_unaware_noise_to_alert(self):
        g = make_wolf_pack(awareness=AwarenessState.unaware)
        self.engine.transition_awareness(g, "noise")
        assert g.awareness_state == AwarenessState.alert

    def test_unaware_nearby_combat_to_alert(self):
        g = make_wolf_pack(awareness=AwarenessState.unaware)
        self.engine.transition_awareness(g, "nearby_combat")
        assert g.awareness_state == AwarenessState.alert

    def test_alert_spotted_to_aware(self):
        g = make_wolf_pack(awareness=AwarenessState.alert)
        self.engine.transition_awareness(g, "spotted")
        assert g.awareness_state == AwarenessState.aware
        assert g.is_visible is True

    def test_alert_searched_to_aware(self):
        g = make_wolf_pack(awareness=AwarenessState.alert)
        self.engine.transition_awareness(g, "searched")
        assert g.awareness_state == AwarenessState.aware

    def test_aware_attacked_to_engaged(self):
        g = make_wolf_pack(awareness=AwarenessState.aware)
        self.engine.transition_awareness(g, "attacked")
        assert g.awareness_state == AwarenessState.engaged

    def test_aware_entered_territory_to_engaged(self):
        g = make_wolf_pack(awareness=AwarenessState.aware)
        self.engine.transition_awareness(g, "entered_territory")
        assert g.awareness_state == AwarenessState.engaged

    def test_engaged_truce_to_aware(self):
        g = make_goblin_patrol(awareness=AwarenessState.engaged)
        self.engine.transition_awareness(g, "truce")
        assert g.awareness_state == AwarenessState.aware

    def test_engaged_flee_success_to_aware(self):
        g = make_goblin_patrol(awareness=AwarenessState.engaged)
        self.engine.transition_awareness(g, "flee_success")
        assert g.awareness_state == AwarenessState.aware

    def test_invalid_transition_noop(self):
        g = make_wolf_pack(awareness=AwarenessState.unaware)
        self.engine.transition_awareness(g, "attacked")
        assert g.awareness_state == AwarenessState.unaware


# ===========================================================================
# Battlefield Summary
# ===========================================================================


class TestBattlefieldSummary:
    def setup_method(self):
        self.builder = BattlefieldSummaryBuilder()

    def test_character_line_format(self):
        kira = make_kira()
        summary = self.builder.build([kira], [], 1)
        assert "Kira — 20/20 HP" in summary.combatant_lines[0]

    def test_character_with_effects(self):
        kira = make_kira()
        kira.status_effects = ["poisoned", "defended"]
        summary = self.builder.build([kira], [], 1)
        assert "[poisoned, defended]" in summary.combatant_lines[0]

    def test_defeated_character(self):
        kira = make_kira()
        kira.is_alive = False
        summary = self.builder.build([kira], [], 1)
        assert "DEFEATED" in summary.combatant_lines[0]

    def test_monster_group_line(self):
        goblins = make_goblin_patrol()
        summary = self.builder.build([], [goblins], 1)
        assert "goblin (x3) — healthy" in summary.combatant_lines[0]

    def test_shaken_morale_shown(self):
        goblins = make_goblin_patrol()
        goblins.morale_state = "shaken"
        summary = self.builder.build([], [goblins], 1)
        assert "shaken" in summary.combatant_lines[0]

    def test_hidden_group_excluded(self):
        wolves = make_wolf_pack()
        wolves.is_visible = False
        summary = self.builder.build([], [wolves], 1)
        assert len(summary.combatant_lines) == 0

    def test_event_lines_passed_through(self):
        events = ["Kira attacks Goblin Patrol — 6 damage"]
        summary = self.builder.build([], [], 1, action_results=events)
        assert summary.event_lines == events

    def test_round_number(self):
        summary = self.builder.build([], [], 5)
        assert summary.round_number == 5

    def test_custom_status(self):
        summary = self.builder.build([], [], 1, combat_status="Victory!")
        assert summary.status_line == "Victory!"


# ===========================================================================
# Full Scenario Integration
# ===========================================================================


class TestGoblinPatrolScenario:
    """Full combat encounter: entry → attack rounds → morale → exit."""

    def test_full_encounter(self):
        # Setup
        scene = make_forest_clearing()
        kira = make_kira()
        dain = make_dain()
        goblins = make_goblin_patrol(count=3)
        original_count = goblins.count

        condition_engine = CombatConditionEngine()
        action_engine = CombatActionEngine()
        morale_engine = MoraleEngine()
        monster_engine = MonsterBehaviorEngine()
        summary_builder = BattlefieldSummaryBuilder()

        # --- Entry ---
        entry = condition_engine.check_entry(scene, [goblins], [kira, dain])
        assert entry.entered is True

        # --- Round 1: Kira attacks goblins ---
        attack_result = action_engine.resolve_attack(
            kira, GOBLIN_PATROL_ID, [goblins], []
        )
        assert attack_result.hit is True
        # resolve_attack now applies damage internally via resolution engine
        # damage=6 (8 attack - 2 defense), kills = 6 // 3 = 2
        assert goblins.count == 1

        # Update threat
        monster_engine.update_threat(goblins, PLAYER_KIRA_ID, 10)

        # Check morale: 1/3 ≈ 0.33 → shaken (<=0.5)
        morale_engine.check_morale(goblins, original_count)
        assert goblins.morale_state == "shaken"

        # Monster turn: attacks highest threat (Kira)
        decision = monster_engine.decide_action(goblins, [kira, dain])
        assert decision.target_player_id == PLAYER_KIRA_ID

        # --- Round 2: Dain finishes off last goblin ---
        action_engine.resolve_attack(dain, GOBLIN_PATROL_ID, [goblins], [])
        assert goblins.count == 0

        # Morale: 0/3 → routed
        morale_engine.check_morale(goblins, original_count)
        assert goblins.morale_state == "routed"

        # --- Exit ---
        exit_result = condition_engine.check_exit(scene, [goblins], [kira, dain])
        assert exit_result.exited is True
        assert exit_result.exit_type == "victory"

        # --- Summary ---
        summary = summary_builder.build(
            [kira, dain],
            [goblins],
            2,
            action_results=["Kira attacks Goblin Patrol — 6 damage"],
            combat_status="Victory!",
        )
        assert summary.round_number == 2
        assert summary.status_line == "Victory!"
        assert any("Kira" in line for line in summary.combatant_lines)
        assert any("Dain" in line for line in summary.combatant_lines)
