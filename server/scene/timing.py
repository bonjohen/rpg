"""Coordinated timing policy for split-party play.

Two modes:
  - independent: each scene resolves on its own timer.
  - synchronized: all scenes wait for the slowest.

Stateless, no I/O.
"""

from __future__ import annotations

from server.domain.entities import CommittedAction
from server.scene.multi_scene import ActiveSceneSet


class SplitPartyTimingPolicy:
    """Determines when a scene is ready to resolve during split-party play."""

    INDEPENDENT = "independent"
    SYNCHRONIZED = "synchronized"

    def __init__(self, sync_mode: str = "independent") -> None:
        self.sync_mode = sync_mode

    def _scene_ready(
        self,
        scene_id: str,
        actions_by_scene: dict[str, list[CommittedAction]],
        players_by_scene: dict[str, list[str]],
    ) -> bool:
        """Return True if all expected players in this scene have submitted."""
        expected = set(players_by_scene.get(scene_id, []))
        if not expected:
            return True
        submitted = {a.player_id for a in actions_by_scene.get(scene_id, [])}
        return expected <= submitted

    def should_resolve_scene(
        self,
        scene_id: str,
        active_set: ActiveSceneSet,
        actions_by_scene: dict[str, list[CommittedAction]],
        players_by_scene: dict[str, list[str]],
    ) -> bool:
        """Return True if the given scene should resolve now.

        Independent mode: True if this scene's players are all ready.
        Synchronized mode: True only if ALL scenes' players are ready.
        """
        if self.sync_mode == self.INDEPENDENT:
            return self._scene_ready(scene_id, actions_by_scene, players_by_scene)

        # Synchronized: all scenes must be ready
        return self.all_scenes_ready(active_set, actions_by_scene, players_by_scene)

    def all_scenes_ready(
        self,
        active_set: ActiveSceneSet,
        actions_by_scene: dict[str, list[CommittedAction]],
        players_by_scene: dict[str, list[str]],
    ) -> bool:
        """Return True when every active scene has all expected players ready."""
        for scene in active_set.scenes:
            if not self._scene_ready(
                scene.scene_id, actions_by_scene, players_by_scene
            ):
                return False
        return True
