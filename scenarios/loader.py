"""Scenario import and load flow.

Reads YAML, deserializes into ScenarioManifest, validates, and converts
to domain entities ready for use.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
import yaml

from server.domain.entities import (
    ConversationScope,
    InventoryItem,
    KnowledgeFact,
    MonsterGroup,
    NPC,
    PuzzleState,
    QuestState,
    Scene,
)
from server.domain.enums import (
    AwarenessState,
    BehaviorMode,
    KnowledgeFactType,
    SceneState,
    ScopeType,
)
from server.exploration.triggers import (
    TriggerCondition,
    TriggerDefinition as DomainTriggerDefinition,
    TriggerEffect,
    TriggerKind,
)

from scenarios.schema import (
    ExitDefinition,
    ItemDefinition,
    MonsterDefinition,
    NpcDefinition,
    NpcTellDefinition,
    PuzzleDefinition,
    QuestDefinition,
    ScenarioManifest,
    SceneDefinition,
    TriggerDefinition,
)
from scenarios.validator import ScenarioValidator


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Load result
# ---------------------------------------------------------------------------


@dataclass
class ScenarioLoadResult:
    success: bool = False
    campaign_id: str = ""
    scenes: list[Scene] = field(default_factory=list)
    npcs: list[NPC] = field(default_factory=list)
    monster_groups: list[MonsterGroup] = field(default_factory=list)
    items: list[InventoryItem] = field(default_factory=list)
    puzzles: list[PuzzleState] = field(default_factory=list)
    quests: list[QuestState] = field(default_factory=list)
    knowledge_facts: list[KnowledgeFact] = field(default_factory=list)
    scopes: list[ConversationScope] = field(default_factory=list)
    triggers: list[DomainTriggerDefinition] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class ScenarioLoader:
    """Load a scenario from YAML into domain entities."""

    def __init__(self, validator: ScenarioValidator | None = None):
        self._validator = validator or ScenarioValidator()

    def load_from_yaml(self, yaml_path: str) -> ScenarioLoadResult:
        """Parse, validate, and convert a YAML scenario file."""
        # 1. Parse YAML
        data = self._parse_yaml(yaml_path)
        if data is None:
            return ScenarioLoadResult(
                success=False,
                errors=[f"Failed to parse YAML file: {yaml_path}"],
            )

        # 2. Deserialize
        try:
            manifest = self._deserialize(data)
        except (KeyError, TypeError, ValueError) as exc:
            return ScenarioLoadResult(
                success=False,
                errors=[f"Deserialization error: {exc}"],
            )

        return self.load_from_manifest(manifest)

    def load_from_manifest(self, manifest: ScenarioManifest) -> ScenarioLoadResult:
        """Validate and convert a pre-built manifest to domain entities."""
        # 3. Validate
        validation = self._validator.validate(manifest)
        if not validation.is_valid:
            return ScenarioLoadResult(
                success=False,
                errors=validation.errors,
            )

        # 4. Generate campaign ID
        campaign_id = _new_id()
        now = _now()

        # 5. Create referee-only scope for the campaign
        referee_scope = ConversationScope(
            scope_id=_new_id(),
            campaign_id=campaign_id,
            scope_type=ScopeType.referee_only,
        )
        scopes: list[ConversationScope] = [referee_scope]

        # 6. Convert scenes + create public scopes
        scenes: list[Scene] = []
        scene_scope_map: dict[str, str] = {}  # scene_id -> public scope_id
        for scene_def in manifest.scenes:
            scene = self._convert_scene(scene_def, campaign_id, now)
            scenes.append(scene)
            scope = ConversationScope(
                scope_id=_new_id(),
                campaign_id=campaign_id,
                scope_type=ScopeType.public,
            )
            scopes.append(scope)
            scene_scope_map[scene_def.scene_id] = scope.scope_id

        # 7. Convert NPCs
        npcs = [self._convert_npc(n, campaign_id, now) for n in manifest.npcs]

        # 8. Convert monsters
        monster_groups = [
            self._convert_monster(m, campaign_id, now) for m in manifest.monsters
        ]

        # 9. Convert items
        items = [self._convert_item(i, campaign_id, now) for i in manifest.items]

        # 10. Convert puzzles
        puzzles = [self._convert_puzzle(p, campaign_id, now) for p in manifest.puzzles]

        # 11. Convert quests
        quests = [self._convert_quest(q, campaign_id, now) for q in manifest.quests]

        # 12. Convert triggers
        triggers = [
            self._convert_trigger(
                t, campaign_id, scene_scope_map, referee_scope.scope_id
            )
            for t in manifest.triggers
        ]

        # 13. Generate initial KnowledgeFacts
        facts = self._generate_initial_facts(
            manifest, campaign_id, referee_scope.scope_id, scene_scope_map, now
        )

        return ScenarioLoadResult(
            success=True,
            campaign_id=campaign_id,
            scenes=scenes,
            npcs=npcs,
            monster_groups=monster_groups,
            items=items,
            puzzles=puzzles,
            quests=quests,
            knowledge_facts=facts,
            scopes=scopes,
            triggers=triggers,
            errors=[],
        )

    # ------------------------------------------------------------------
    # YAML parsing
    # ------------------------------------------------------------------

    def _parse_yaml(self, yaml_path: str) -> dict | None:
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except (OSError, yaml.YAMLError):
            return None

    # ------------------------------------------------------------------
    # Deserialization
    # ------------------------------------------------------------------

    def _deserialize(self, data: dict) -> ScenarioManifest:
        return ScenarioManifest(
            scenario_id=data["scenario_id"],
            title=data["title"],
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            author=data.get("author", ""),
            starting_scene_id=data.get("starting_scene_id", ""),
            scenes=[self._deserialize_scene(s) for s in data.get("scenes", [])],
            npcs=[self._deserialize_npc(n) for n in data.get("npcs", [])],
            monsters=[self._deserialize_monster(m) for m in data.get("monsters", [])],
            items=[self._deserialize_item(i) for i in data.get("items", [])],
            puzzles=[self._deserialize_puzzle(p) for p in data.get("puzzles", [])],
            quests=[self._deserialize_quest(q) for q in data.get("quests", [])],
            triggers=[self._deserialize_trigger(t) for t in data.get("triggers", [])],
        )

    def _deserialize_scene(self, d: dict) -> SceneDefinition:
        exits = [self._deserialize_exit(e) for e in d.get("exits", [])]
        return SceneDefinition(
            scene_id=d["scene_id"],
            name=d["name"],
            description=d.get("description", ""),
            referee_notes=d.get("referee_notes", ""),
            exits=exits,
            item_ids=d.get("item_ids", []),
            npc_ids=d.get("npc_ids", []),
            monster_ids=d.get("monster_ids", []),
            puzzle_ids=d.get("puzzle_ids", []),
            trigger_ids=d.get("trigger_ids", []),
            tags=d.get("tags", []),
        )

    def _deserialize_exit(self, d: dict) -> ExitDefinition:
        return ExitDefinition(
            exit_id=d["exit_id"],
            direction=d["direction"],
            target_scene_id=d["target_scene_id"],
            description=d.get("description", ""),
            is_hidden=d.get("is_hidden", False),
            is_locked=d.get("is_locked", False),
            unlock_condition=d.get("unlock_condition", ""),
        )

    def _deserialize_npc(self, d: dict) -> NpcDefinition:
        tells = [self._deserialize_tell(t) for t in d.get("tells", [])]
        return NpcDefinition(
            npc_id=d["npc_id"],
            name=d["name"],
            description=d.get("description", ""),
            personality_tags=d.get("personality_tags", []),
            goals=d.get("goals", []),
            trust_initial=d.get("trust_initial", {}),
            faction=d.get("faction", ""),
            scene_id=d.get("scene_id", ""),
            inventory_item_ids=d.get("inventory_item_ids", []),
            dialogue_hints=d.get("dialogue_hints", []),
            referee_notes=d.get("referee_notes", ""),
            tells=tells,
        )

    def _deserialize_tell(self, d: dict) -> NpcTellDefinition:
        return NpcTellDefinition(
            tell_id=d["tell_id"],
            trigger_type=d["trigger_type"],
            trigger_value=d.get("trigger_value", ""),
            behavior=d.get("behavior", ""),
            scope=d.get("scope", "public"),
        )

    def _deserialize_monster(self, d: dict) -> MonsterDefinition:
        return MonsterDefinition(
            monster_id=d["monster_id"],
            unit_type=d["unit_type"],
            count=d.get("count", 1),
            behavior_mode=d.get("behavior_mode", "patrol"),
            awareness_state=d.get("awareness_state", "unaware"),
            stats=d.get("stats", {}),
            special_rules=d.get("special_rules", []),
            territory_id=d.get("territory_id", ""),
            scene_id=d.get("scene_id", ""),
            loot_item_ids=d.get("loot_item_ids", []),
            referee_notes=d.get("referee_notes", ""),
        )

    def _deserialize_item(self, d: dict) -> ItemDefinition:
        return ItemDefinition(
            item_id=d["item_id"],
            name=d["name"],
            description=d.get("description", ""),
            properties=d.get("properties", {}),
            is_hidden=d.get("is_hidden", False),
            is_key=d.get("is_key", False),
            unlocks_exit_ids=d.get("unlocks_exit_ids", []),
            quantity=d.get("quantity", 1),
            scene_id=d.get("scene_id", ""),
        )

    def _deserialize_puzzle(self, d: dict) -> PuzzleDefinition:
        return PuzzleDefinition(
            puzzle_id=d["puzzle_id"],
            name=d["name"],
            description=d.get("description", ""),
            solution_hint=d.get("solution_hint", ""),
            solution_actions=d.get("solution_actions", []),
            success_text=d.get("success_text", ""),
            failure_text=d.get("failure_text", ""),
            max_attempts=d.get("max_attempts", 0),
            effects_on_solve=d.get("effects_on_solve", []),
            scene_id=d.get("scene_id", ""),
            referee_notes=d.get("referee_notes", ""),
        )

    def _deserialize_quest(self, d: dict) -> QuestDefinition:
        return QuestDefinition(
            quest_id=d["quest_id"],
            title=d["title"],
            description=d.get("description", ""),
            objectives=d.get("objectives", []),
            completion_condition=d.get("completion_condition", ""),
            reward_description=d.get("reward_description", ""),
            referee_notes=d.get("referee_notes", ""),
        )

    def _deserialize_trigger(self, d: dict) -> TriggerDefinition:
        return TriggerDefinition(
            trigger_id=d["trigger_id"],
            kind=d["kind"],
            scene_id=d.get("scene_id", ""),
            condition_type=d.get("condition_type", "always"),
            condition_value=d.get("condition_value", ""),
            effect_type=d.get("effect_type", "narrate"),
            effect_value=d.get("effect_value", ""),
            scope=d.get("scope", "public"),
            is_repeatable=d.get("is_repeatable", False),
            referee_notes=d.get("referee_notes", ""),
        )

    # ------------------------------------------------------------------
    # Converters: scenario definitions -> domain entities
    # ------------------------------------------------------------------

    def _convert_scene(
        self, defn: SceneDefinition, campaign_id: str, now: datetime
    ) -> Scene:
        exits_map: dict[str, str] = {}
        for exit_def in defn.exits:
            if not exit_def.is_hidden:
                exits_map[exit_def.direction] = exit_def.target_scene_id

        return Scene(
            scene_id=defn.scene_id,
            campaign_id=campaign_id,
            name=defn.name,
            description=defn.description,
            created_at=now,
            state=SceneState.idle,
            npc_ids=list(defn.npc_ids),
            monster_group_ids=list(defn.monster_ids),
            item_ids=list(defn.item_ids),
            exits=exits_map,
            hidden_description=defn.referee_notes,
        )

    def _convert_npc(self, defn: NpcDefinition, campaign_id: str, now: datetime) -> NPC:
        return NPC(
            npc_id=defn.npc_id,
            campaign_id=campaign_id,
            name=defn.name,
            created_at=now,
            scene_id=defn.scene_id or None,
            inventory_item_ids=list(defn.inventory_item_ids),
            faction_id=defn.faction or None,
            goal_tags=list(defn.goals),
            personality_tags=list(defn.personality_tags),
            trust_by_player=dict(defn.trust_initial),
        )

    def _convert_monster(
        self, defn: MonsterDefinition, campaign_id: str, now: datetime
    ) -> MonsterGroup:
        return MonsterGroup(
            monster_group_id=defn.monster_id,
            campaign_id=campaign_id,
            scene_id=defn.scene_id,
            unit_type=defn.unit_type,
            count=defn.count,
            created_at=now,
            behavior_mode=BehaviorMode(defn.behavior_mode),
            awareness_state=AwarenessState(defn.awareness_state),
            territory_id=defn.territory_id or None,
            special_rules=list(defn.special_rules),
        )

    def _convert_item(
        self, defn: ItemDefinition, campaign_id: str, now: datetime
    ) -> InventoryItem:
        return InventoryItem(
            item_id=defn.item_id,
            campaign_id=campaign_id,
            item_type=defn.name.lower().replace(" ", "_"),
            name=defn.name,
            created_at=now,
            owner_scene_id=defn.scene_id or None,
            quantity=defn.quantity,
            properties=dict(defn.properties),
            is_hidden=defn.is_hidden,
        )

    def _convert_puzzle(
        self, defn: PuzzleDefinition, campaign_id: str, now: datetime
    ) -> PuzzleState:
        return PuzzleState(
            puzzle_state_id=_new_id(),
            campaign_id=campaign_id,
            scene_id=defn.scene_id,
            puzzle_id=defn.puzzle_id,
        )

    def _convert_quest(
        self, defn: QuestDefinition, campaign_id: str, now: datetime
    ) -> QuestState:
        return QuestState(
            quest_state_id=_new_id(),
            campaign_id=campaign_id,
            quest_id=defn.quest_id,
        )

    def _convert_trigger(
        self,
        defn: TriggerDefinition,
        campaign_id: str,
        scene_scope_map: dict[str, str],
        referee_scope_id: str,
    ) -> DomainTriggerDefinition:
        # Map scenario condition_type to domain TriggerCondition
        condition_map: dict[str, TriggerCondition] = {
            "always": TriggerCondition.always,
            "first_visit": TriggerCondition.once,
            "has_item": TriggerCondition.if_item_present,
            "puzzle_solved": TriggerCondition.always,
        }
        condition = condition_map.get(defn.condition_type, TriggerCondition.always)

        # Map effect_type to TriggerEffect
        effect = TriggerEffect()
        if defn.effect_type == "narrate":
            if defn.scope == "public":
                effect.public_narrative = defn.effect_value
            else:
                effect.private_narrative = defn.effect_value
        elif defn.effect_type == "damage":
            effect.trap_damage = defn.effect_value
            effect.public_narrative = f"A trap triggers! ({defn.effect_value} damage)"
        elif defn.effect_type == "grant_fact":
            fact_type = KnowledgeFactType.lore
            effect.new_fact_payloads = [(fact_type, defn.effect_value)]

        public_scope_id = scene_scope_map.get(defn.scene_id, "")
        private_scope_id = referee_scope_id if defn.scope == "referee_only" else ""

        return DomainTriggerDefinition(
            trigger_id=defn.trigger_id,
            scene_id=defn.scene_id,
            kind=TriggerKind(defn.kind),
            condition=condition,
            effect=effect,
            label=defn.trigger_id,
            condition_item_id=defn.condition_value
            if defn.condition_type == "has_item"
            else "",
            has_fired=False,
            public_scope_id=public_scope_id,
            private_scope_id=private_scope_id,
            campaign_id=campaign_id,
        )

    # ------------------------------------------------------------------
    # KnowledgeFact generation
    # ------------------------------------------------------------------

    def _generate_initial_facts(
        self,
        manifest: ScenarioManifest,
        campaign_id: str,
        referee_scope_id: str,
        scene_scope_map: dict[str, str],
        now: datetime,
    ) -> list[KnowledgeFact]:
        facts: list[KnowledgeFact] = []

        # Referee notes from scenes
        for scene in manifest.scenes:
            if scene.referee_notes:
                facts.append(
                    KnowledgeFact(
                        fact_id=_new_id(),
                        campaign_id=campaign_id,
                        scene_id=scene.scene_id,
                        owner_scope_id=referee_scope_id,
                        fact_type=KnowledgeFactType.lore,
                        payload=f"[scene:{scene.scene_id}] {scene.referee_notes}",
                        revealed_at=now,
                    )
                )

        # Referee notes from NPCs
        for npc in manifest.npcs:
            if npc.referee_notes:
                facts.append(
                    KnowledgeFact(
                        fact_id=_new_id(),
                        campaign_id=campaign_id,
                        scene_id=npc.scene_id or "",
                        owner_scope_id=referee_scope_id,
                        fact_type=KnowledgeFactType.npc_tell,
                        payload=f"[npc:{npc.npc_id}] {npc.referee_notes}",
                        revealed_at=now,
                    )
                )

        # Referee notes from monsters
        for monster in manifest.monsters:
            if monster.referee_notes:
                facts.append(
                    KnowledgeFact(
                        fact_id=_new_id(),
                        campaign_id=campaign_id,
                        scene_id=monster.scene_id or "",
                        owner_scope_id=referee_scope_id,
                        fact_type=KnowledgeFactType.lore,
                        payload=f"[monster:{monster.monster_id}] {monster.referee_notes}",
                        revealed_at=now,
                    )
                )

        # Puzzle solution hints
        for puzzle in manifest.puzzles:
            if puzzle.solution_hint:
                facts.append(
                    KnowledgeFact(
                        fact_id=_new_id(),
                        campaign_id=campaign_id,
                        scene_id=puzzle.scene_id or "",
                        owner_scope_id=referee_scope_id,
                        fact_type=KnowledgeFactType.lore,
                        payload=f"[puzzle:{puzzle.puzzle_id}:hint] {puzzle.solution_hint}",
                        revealed_at=now,
                    )
                )
            if puzzle.referee_notes:
                facts.append(
                    KnowledgeFact(
                        fact_id=_new_id(),
                        campaign_id=campaign_id,
                        scene_id=puzzle.scene_id or "",
                        owner_scope_id=referee_scope_id,
                        fact_type=KnowledgeFactType.lore,
                        payload=f"[puzzle:{puzzle.puzzle_id}] {puzzle.referee_notes}",
                        revealed_at=now,
                    )
                )

        # Quest referee notes
        for quest in manifest.quests:
            if quest.referee_notes:
                facts.append(
                    KnowledgeFact(
                        fact_id=_new_id(),
                        campaign_id=campaign_id,
                        scene_id="",
                        owner_scope_id=referee_scope_id,
                        fact_type=KnowledgeFactType.lore,
                        payload=f"[quest:{quest.quest_id}] {quest.referee_notes}",
                        revealed_at=now,
                    )
                )

        # Trigger referee notes
        for trigger in manifest.triggers:
            if trigger.referee_notes:
                facts.append(
                    KnowledgeFact(
                        fact_id=_new_id(),
                        campaign_id=campaign_id,
                        scene_id=trigger.scene_id or "",
                        owner_scope_id=referee_scope_id,
                        fact_type=KnowledgeFactType.lore,
                        payload=f"[trigger:{trigger.trigger_id}] {trigger.referee_notes}",
                        revealed_at=now,
                    )
                )

        # Hidden exits
        for scene in manifest.scenes:
            for exit_def in scene.exits:
                if exit_def.is_hidden:
                    facts.append(
                        KnowledgeFact(
                            fact_id=_new_id(),
                            campaign_id=campaign_id,
                            scene_id=scene.scene_id,
                            owner_scope_id=referee_scope_id,
                            fact_type=KnowledgeFactType.hidden_object,
                            payload=(
                                f"Hidden exit '{exit_def.direction}' in "
                                f"{scene.scene_id} leads to {exit_def.target_scene_id}"
                            ),
                            revealed_at=now,
                        )
                    )

        # Hidden items
        for item in manifest.items:
            if item.is_hidden:
                facts.append(
                    KnowledgeFact(
                        fact_id=_new_id(),
                        campaign_id=campaign_id,
                        scene_id=item.scene_id or "",
                        owner_scope_id=referee_scope_id,
                        fact_type=KnowledgeFactType.hidden_object,
                        payload=f"Hidden item '{item.name}' ({item.item_id})",
                        revealed_at=now,
                    )
                )

        return facts
