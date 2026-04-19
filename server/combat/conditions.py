"""Combat entry and exit condition evaluation.

Stateless engine — takes current state, returns results.
"""

from __future__ import annotations

from dataclasses import dataclass

from server.domain.entities import Character, MonsterGroup, Scene
from server.domain.enums import AwarenessState


@dataclass
class CombatEntryResult:
    entered: bool
    reason: str


@dataclass
class CombatExitResult:
    exited: bool
    exit_type: str  # "victory" | "flee" | "truce" | "annihilation"
    reason: str


class CombatConditionEngine:
    """Evaluates whether combat should begin or end."""

    def check_entry(
        self,
        scene: Scene,
        monster_groups: list[MonsterGroup],
        characters: list[Character],
    ) -> CombatEntryResult:
        scene_groups = [g for g in monster_groups if g.scene_id == scene.scene_id]
        engaged = [
            g for g in scene_groups if g.awareness_state == AwarenessState.engaged
        ]
        if engaged:
            names = ", ".join(g.unit_type for g in engaged)
            return CombatEntryResult(entered=True, reason=f"Engaged groups: {names}")
        return CombatEntryResult(entered=False, reason="No engaged monster groups")

    def check_exit(
        self,
        scene: Scene,
        monster_groups: list[MonsterGroup],
        characters: list[Character],
    ) -> CombatExitResult:
        scene_groups = [g for g in monster_groups if g.scene_id == scene.scene_id]
        scene_chars = [
            c for c in characters if c.scene_id == scene.scene_id and c.is_alive
        ]

        # Annihilation: all characters dead
        if not scene_chars:
            return CombatExitResult(
                exited=True,
                exit_type="annihilation",
                reason="All characters defeated",
            )

        # Victory: all monster groups defeated
        if scene_groups and all(g.count <= 0 for g in scene_groups):
            return CombatExitResult(
                exited=True,
                exit_type="victory",
                reason="All monster groups defeated",
            )

        # Flee: all remaining groups routed
        alive_groups = [g for g in scene_groups if g.count > 0]
        if alive_groups and all(g.morale_state == "routed" for g in alive_groups):
            return CombatExitResult(
                exited=True,
                exit_type="flee",
                reason="All remaining groups routed",
            )

        # Truce: not implemented yet
        return CombatExitResult(exited=False, exit_type="", reason="Combat ongoing")
