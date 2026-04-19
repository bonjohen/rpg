"""Combat visibility and awareness state management."""

from __future__ import annotations

from dataclasses import dataclass

from server.domain.entities import MonsterGroup
from server.domain.enums import AwarenessState


@dataclass
class CombatVisibilityResult:
    visible_groups: list[MonsterGroup]
    hidden_groups: list[MonsterGroup]


class CombatVisibilityEngine:
    """Computes which monster groups are visible and manages awareness transitions."""

    AWARENESS_TRANSITIONS: dict[tuple[AwarenessState, str], AwarenessState] = {
        (AwarenessState.unaware, "noise"): AwarenessState.alert,
        (AwarenessState.unaware, "nearby_combat"): AwarenessState.alert,
        (AwarenessState.alert, "spotted"): AwarenessState.aware,
        (AwarenessState.alert, "searched"): AwarenessState.aware,
        (AwarenessState.aware, "attacked"): AwarenessState.engaged,
        (AwarenessState.aware, "entered_territory"): AwarenessState.engaged,
        (AwarenessState.engaged, "truce"): AwarenessState.aware,
        (AwarenessState.engaged, "flee_success"): AwarenessState.aware,
    }

    def compute_visibility(
        self,
        groups: list[MonsterGroup],
    ) -> CombatVisibilityResult:
        visible = []
        hidden = []
        for g in groups:
            if g.awareness_state in (AwarenessState.aware, AwarenessState.engaged):
                g.is_visible = True
                visible.append(g)
            else:
                g.is_visible = False
                hidden.append(g)
        return CombatVisibilityResult(visible_groups=visible, hidden_groups=hidden)

    def transition_awareness(
        self,
        group: MonsterGroup,
        event: str,
    ) -> MonsterGroup:
        key = (group.awareness_state, event)
        new_state = self.AWARENESS_TRANSITIONS.get(key)
        if new_state is not None:
            group.awareness_state = new_state
            # Update visibility to match
            group.is_visible = new_state in (
                AwarenessState.aware,
                AwarenessState.engaged,
            )
        return group
