"""Monster group behavior and morale engines.

Stateless engines — take current state, return updated state + decisions.
"""

from __future__ import annotations

from dataclasses import dataclass

from server.domain.entities import Character, MonsterGroup, Scene
from server.domain.enums import AwarenessState, BehaviorMode


# ---------------------------------------------------------------------------
# Monster AI
# ---------------------------------------------------------------------------


@dataclass
class MonsterActionDecision:
    monster_group_id: str
    action_type: str  # "attack" | "defend" | "flee" | "call_help" | "idle"
    target_player_id: str
    reason: str


class MonsterBehaviorEngine:
    """Decides what a monster group does on its turn."""

    def decide_action(
        self,
        group: MonsterGroup,
        characters: list[Character],
    ) -> MonsterActionDecision:
        alive_chars = [c for c in characters if c.is_alive]

        # Routed groups always flee
        if group.morale_state == "routed":
            return MonsterActionDecision(
                monster_group_id=group.monster_group_id,
                action_type="flee",
                target_player_id="",
                reason="Morale broken — routing",
            )

        # Flee mode
        if group.behavior_mode == BehaviorMode.flee:
            return MonsterActionDecision(
                monster_group_id=group.monster_group_id,
                action_type="flee",
                target_player_id="",
                reason="Flee behavior active",
            )

        # Call help
        if group.behavior_mode == BehaviorMode.call_help:
            return MonsterActionDecision(
                monster_group_id=group.monster_group_id,
                action_type="call_help",
                target_player_id="",
                reason="Calling for reinforcements",
            )

        # Idle
        if group.behavior_mode == BehaviorMode.idle:
            return MonsterActionDecision(
                monster_group_id=group.monster_group_id,
                action_type="idle",
                target_player_id="",
                reason="Idle — not engaged",
            )

        # Not engaged: stay idle
        if group.awareness_state != AwarenessState.engaged:
            return MonsterActionDecision(
                monster_group_id=group.monster_group_id,
                action_type="idle",
                target_player_id="",
                reason="Not engaged",
            )

        if not alive_chars:
            return MonsterActionDecision(
                monster_group_id=group.monster_group_id,
                action_type="idle",
                target_player_id="",
                reason="No targets available",
            )

        # Defend mode: only attack if targets share territory
        if group.behavior_mode == BehaviorMode.defend:
            in_territory = [c for c in alive_chars if c.scene_id == group.territory_id]
            if not in_territory:
                return MonsterActionDecision(
                    monster_group_id=group.monster_group_id,
                    action_type="defend",
                    target_player_id="",
                    reason="No targets in territory",
                )
            target = self._pick_target(group, in_territory)
            return MonsterActionDecision(
                monster_group_id=group.monster_group_id,
                action_type="attack",
                target_player_id=target.player_id,
                reason=f"Defending territory against {target.name}",
            )

        # Ambush: first-round bonus check
        if group.behavior_mode == BehaviorMode.ambush:
            if "ambush_used" not in group.special_rules:
                group.special_rules.append("ambush_used")

        # Patrol, guard, pursue, ambush: attack highest-threat
        target = self._pick_target(group, alive_chars)
        return MonsterActionDecision(
            monster_group_id=group.monster_group_id,
            action_type="attack",
            target_player_id=target.player_id,
            reason=f"Attacking {target.name} (highest threat)",
        )

    def _pick_target(
        self,
        group: MonsterGroup,
        candidates: list[Character],
    ) -> Character:
        if not group.threat_table:
            return candidates[0]

        best: Character | None = None
        best_threat = -1
        for c in candidates:
            threat = group.threat_table.get(c.player_id, 0)
            if threat > best_threat:
                best_threat = threat
                best = c
        return best if best is not None else candidates[0]

    def update_threat(
        self,
        group: MonsterGroup,
        player_id: str,
        delta: int,
    ) -> MonsterGroup:
        current = group.threat_table.get(player_id, 0)
        group.threat_table[player_id] = max(0, current + delta)
        return group

    def update_awareness(
        self,
        group: MonsterGroup,
        new_state: AwarenessState,
    ) -> MonsterGroup:
        group.awareness_state = new_state
        return group


# ---------------------------------------------------------------------------
# Morale
# ---------------------------------------------------------------------------


class MoraleEngine:
    """Checks and applies morale transitions for monster groups."""

    def check_morale(
        self,
        group: MonsterGroup,
        original_count: int,
    ) -> MonsterGroup:
        if original_count <= 0:
            return group

        ratio = group.count / original_count

        if group.morale_state == "steady" and ratio <= 0.5:
            group.morale_state = "shaken"

        if group.morale_state == "shaken":
            if ratio <= 0.25 or "leader_dead" in group.special_rules:
                group.morale_state = "routed"
                group.behavior_mode = BehaviorMode.flee

        return group

    def apply_flee(
        self,
        group: MonsterGroup,
        scene: Scene,
    ) -> tuple[MonsterGroup, Scene]:
        if group.monster_group_id in scene.monster_group_ids:
            scene.monster_group_ids.remove(group.monster_group_id)
        group.is_visible = False
        return group, scene
