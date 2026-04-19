"""Explicit scene membership for players and NPCs.

SceneMembershipEngine manages which characters and NPCs belong to which
scene.  All methods are stateless — they mutate the passed-in entities
and return a result.  No I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from server.domain.entities import Character, NPC, Scene


@dataclass
class MembershipChangeResult:
    success: bool
    scene: Scene
    character: Optional[Character] = None
    npc: Optional[NPC] = None
    reason: str = ""


class SceneMembershipEngine:
    """Manages character and NPC membership in scenes."""

    def add_character(
        self, scene: Scene, character: Character
    ) -> MembershipChangeResult:
        """Add a character to a scene.

        Updates scene.character_ids, scene.player_ids, and character.scene_id.
        Rejects if the character is already in this scene.
        """
        if character.character_id in scene.character_ids:
            return MembershipChangeResult(
                success=False,
                scene=scene,
                character=character,
                reason=f"Character {character.character_id!r} is already in "
                f"scene {scene.scene_id!r}.",
            )
        scene.character_ids.append(character.character_id)
        if character.player_id not in scene.player_ids:
            scene.player_ids.append(character.player_id)
        character.scene_id = scene.scene_id
        return MembershipChangeResult(success=True, scene=scene, character=character)

    def remove_character(
        self, scene: Scene, character: Character
    ) -> MembershipChangeResult:
        """Remove a character from a scene.

        Updates scene.character_ids, scene.player_ids, and character.scene_id.
        Rejects if the character is not in this scene.
        """
        if character.character_id not in scene.character_ids:
            return MembershipChangeResult(
                success=False,
                scene=scene,
                character=character,
                reason=f"Character {character.character_id!r} is not in "
                f"scene {scene.scene_id!r}.",
            )
        scene.character_ids.remove(character.character_id)
        # Remove player_id — re-added by add_character if another character
        # of the same player remains (simple single-character-per-player model).
        if character.player_id in scene.player_ids:
            scene.player_ids.remove(character.player_id)
        character.scene_id = None
        return MembershipChangeResult(success=True, scene=scene, character=character)

    def add_npc(self, scene: Scene, npc: NPC) -> MembershipChangeResult:
        """Add an NPC to a scene.

        Rejects if the NPC is already in this scene.
        """
        if npc.npc_id in scene.npc_ids:
            return MembershipChangeResult(
                success=False,
                scene=scene,
                npc=npc,
                reason=f"NPC {npc.npc_id!r} is already in scene {scene.scene_id!r}.",
            )
        scene.npc_ids.append(npc.npc_id)
        npc.scene_id = scene.scene_id
        return MembershipChangeResult(success=True, scene=scene, npc=npc)

    def remove_npc(self, scene: Scene, npc: NPC) -> MembershipChangeResult:
        """Remove an NPC from a scene.

        Rejects if the NPC is not in this scene.
        """
        if npc.npc_id not in scene.npc_ids:
            return MembershipChangeResult(
                success=False,
                scene=scene,
                npc=npc,
                reason=f"NPC {npc.npc_id!r} is not in scene {scene.scene_id!r}.",
            )
        scene.npc_ids.remove(npc.npc_id)
        npc.scene_id = None
        return MembershipChangeResult(success=True, scene=scene, npc=npc)

    def transfer_character(
        self,
        from_scene: Scene,
        to_scene: Scene,
        character: Character,
    ) -> MembershipChangeResult:
        """Transfer a character from one scene to another.

        Atomic: removes from source then adds to target.
        If the removal fails, the transfer fails without touching the target.
        """
        remove_result = self.remove_character(from_scene, character)
        if not remove_result.success:
            return MembershipChangeResult(
                success=False,
                scene=from_scene,
                character=character,
                reason=f"Transfer failed: {remove_result.reason}",
            )
        add_result = self.add_character(to_scene, character)
        if not add_result.success:
            # Rollback: put the character back in the source scene
            self.add_character(from_scene, character)
            return MembershipChangeResult(
                success=False,
                scene=to_scene,
                character=character,
                reason=f"Transfer failed: {add_result.reason}",
            )
        return MembershipChangeResult(success=True, scene=to_scene, character=character)

    def get_scene_characters(
        self, scene: Scene, all_characters: list[Character]
    ) -> list[Character]:
        """Return only the characters that belong to this scene."""
        return [c for c in all_characters if c.character_id in scene.character_ids]

    def get_scene_npcs(self, scene: Scene, all_npcs: list[NPC]) -> list[NPC]:
        """Return only the NPCs that belong to this scene."""
        return [n for n in all_npcs if n.npc_id in scene.npc_ids]
