"""Scoped prompts by subgroup for split-party play.

Each active scene gets its own narration prompt context.  Cross-scene facts
are excluded.  Stateless, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from server.domain.entities import (
    Character,
    ConversationScope,
    KnowledgeFact,
    MonsterGroup,
    NPC,
    Scene,
)
from server.domain.enums import ScopeType


@dataclass
class SubgroupPromptContext:
    """Everything needed to assemble a narration prompt for one scene."""

    scene: Scene
    characters: list[Character] = field(default_factory=list)
    player_ids: list[str] = field(default_factory=list)
    public_facts: list[KnowledgeFact] = field(default_factory=list)
    scene_npcs: list[NPC] = field(default_factory=list)
    scene_monster_groups: list[MonsterGroup] = field(default_factory=list)


class SubgroupPromptEngine:
    """Assembles per-scene prompt contexts for split-party play."""

    def filter_facts_for_scene(
        self, scene_id: str, facts: list[KnowledgeFact]
    ) -> list[KnowledgeFact]:
        """Return only facts whose scene_id matches."""
        return [f for f in facts if f.scene_id == scene_id]

    def assemble_subgroup_context(
        self,
        scene: Scene,
        all_characters: list[Character],
        all_facts: list[KnowledgeFact],
        scopes_by_id: dict[str, ConversationScope],
        all_npcs: list[NPC],
        all_monster_groups: list[MonsterGroup],
    ) -> SubgroupPromptContext:
        """Assemble prompt context for a single scene.

        Filters characters, NPCs, monster groups, and facts to only those
        belonging to this scene.  Only includes public-scoped facts.
        """
        characters = [
            c for c in all_characters if c.character_id in scene.character_ids
        ]
        player_ids = list(scene.player_ids)
        npcs = [n for n in all_npcs if n.npc_id in scene.npc_ids]
        groups = [
            g
            for g in all_monster_groups
            if g.monster_group_id in scene.monster_group_ids
        ]

        scene_facts = self.filter_facts_for_scene(scene.scene_id, all_facts)
        public_facts = [
            f
            for f in scene_facts
            if f.owner_scope_id in scopes_by_id
            and scopes_by_id[f.owner_scope_id].scope_type == ScopeType.public
        ]

        return SubgroupPromptContext(
            scene=scene,
            characters=characters,
            player_ids=player_ids,
            public_facts=public_facts,
            scene_npcs=npcs,
            scene_monster_groups=groups,
        )
