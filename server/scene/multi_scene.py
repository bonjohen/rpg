"""Multiple active scene contexts in a campaign.

Manages which scenes are active simultaneously and maps each to its
TurnWindow.  Stateless, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from server.domain.entities import Scene, TurnWindow
from server.domain.enums import SceneState


@dataclass
class ActiveSceneSet:
    """Snapshot of all active scenes in a campaign plus their turn windows."""

    campaign_id: str
    scenes: list[Scene] = field(default_factory=list)
    turn_windows: dict[str, TurnWindow] = field(default_factory=dict)


class MultiSceneEngine:
    """Manages multiple concurrent active scenes within a campaign."""

    _ACTIVE_STATES: frozenset[SceneState] = frozenset(
        {
            SceneState.prompting,
            SceneState.awaiting_actions,
            SceneState.resolving,
            SceneState.narrated,
        }
    )

    def get_active_scenes(self, all_scenes: list[Scene]) -> list[Scene]:
        """Return scenes whose state is active and have at least one player."""
        return [
            s
            for s in all_scenes
            if s.state in self._ACTIVE_STATES and len(s.player_ids) > 0
        ]

    def build_active_set(
        self,
        campaign_id: str,
        all_scenes: list[Scene],
        all_turn_windows: list[TurnWindow],
    ) -> ActiveSceneSet:
        """Build an ActiveSceneSet from all campaign scenes and turn windows."""
        active = self.get_active_scenes(all_scenes)
        tw_by_id = {tw.turn_window_id: tw for tw in all_turn_windows}
        tw_map: dict[str, TurnWindow] = {}
        for scene in active:
            if scene.active_turn_window_id:
                tw = tw_by_id.get(scene.active_turn_window_id)
                if tw is not None:
                    tw_map[scene.scene_id] = tw
        return ActiveSceneSet(
            campaign_id=campaign_id, scenes=active, turn_windows=tw_map
        )

    def activate_scene(self, scene: Scene) -> Scene:
        """Activate a scene (transition from idle to awaiting_actions)."""
        if scene.state == SceneState.idle:
            scene.state = SceneState.awaiting_actions
        return scene

    def deactivate_scene(self, scene: Scene) -> Scene:
        """Deactivate a scene (set to idle, clear active turn window)."""
        scene.state = SceneState.idle
        scene.active_turn_window_id = None
        return scene
