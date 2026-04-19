"""Declarative YAML-based scenario schema.

Dataclasses map 1:1 to the YAML structure.  A scenario is a directory
containing a ``scenario.yaml`` manifest and optional asset files.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Exit
# ---------------------------------------------------------------------------


@dataclass
class ExitDefinition:
    exit_id: str
    direction: str
    target_scene_id: str
    description: str = ""
    is_hidden: bool = False
    is_locked: bool = False
    unlock_condition: str = ""


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------


@dataclass
class SceneDefinition:
    scene_id: str
    name: str
    description: str = ""
    referee_notes: str = ""
    exits: list[ExitDefinition] = field(default_factory=list)
    item_ids: list[str] = field(default_factory=list)
    npc_ids: list[str] = field(default_factory=list)
    monster_ids: list[str] = field(default_factory=list)
    puzzle_ids: list[str] = field(default_factory=list)
    trigger_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# NPC Tell
# ---------------------------------------------------------------------------


@dataclass
class NpcTellDefinition:
    tell_id: str
    trigger_type: str  # "trust_above" | "trust_below" | "action_type" | "tag_present"
    trigger_value: str = ""
    behavior: str = ""
    scope: str = "public"  # "public" | "referee_only"


# ---------------------------------------------------------------------------
# NPC
# ---------------------------------------------------------------------------


@dataclass
class NpcDefinition:
    npc_id: str
    name: str
    description: str = ""
    personality_tags: list[str] = field(default_factory=list)
    goals: list[str] = field(default_factory=list)
    trust_initial: dict[str, int] = field(default_factory=dict)
    faction: str = ""
    scene_id: str = ""
    inventory_item_ids: list[str] = field(default_factory=list)
    dialogue_hints: list[str] = field(default_factory=list)
    referee_notes: str = ""
    tells: list[NpcTellDefinition] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Monster
# ---------------------------------------------------------------------------


@dataclass
class MonsterDefinition:
    monster_id: str
    unit_type: str
    count: int = 1
    behavior_mode: str = "patrol"
    awareness_state: str = "unaware"
    stats: dict[str, int] = field(default_factory=dict)
    special_rules: list[str] = field(default_factory=list)
    territory_id: str = ""
    scene_id: str = ""
    loot_item_ids: list[str] = field(default_factory=list)
    referee_notes: str = ""


# ---------------------------------------------------------------------------
# Item
# ---------------------------------------------------------------------------


@dataclass
class ItemDefinition:
    item_id: str
    name: str
    description: str = ""
    properties: dict[str, str] = field(default_factory=dict)
    is_hidden: bool = False
    is_key: bool = False
    unlocks_exit_ids: list[str] = field(default_factory=list)
    quantity: int = 1
    scene_id: str = ""  # empty means NPC inventory


# ---------------------------------------------------------------------------
# Puzzle
# ---------------------------------------------------------------------------


@dataclass
class PuzzleDefinition:
    puzzle_id: str
    name: str
    description: str = ""
    solution_hint: str = ""
    solution_actions: list[str] = field(default_factory=list)
    success_text: str = ""
    failure_text: str = ""
    max_attempts: int = 0
    effects_on_solve: list[str] = field(default_factory=list)
    scene_id: str = ""
    referee_notes: str = ""


# ---------------------------------------------------------------------------
# Quest
# ---------------------------------------------------------------------------


@dataclass
class QuestDefinition:
    quest_id: str
    title: str
    description: str = ""
    objectives: list[str] = field(default_factory=list)
    completion_condition: str = ""
    reward_description: str = ""
    referee_notes: str = ""


# ---------------------------------------------------------------------------
# Trigger
# ---------------------------------------------------------------------------


@dataclass
class TriggerDefinition:
    trigger_id: str
    kind: str  # maps to TriggerKind
    scene_id: str = ""
    condition_type: str = "always"
    condition_value: str = ""
    effect_type: str = "narrate"
    effect_value: str = ""
    scope: str = "public"
    is_repeatable: bool = False
    referee_notes: str = ""


# ---------------------------------------------------------------------------
# Scenario Manifest
# ---------------------------------------------------------------------------


@dataclass
class ScenarioManifest:
    scenario_id: str
    title: str
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    starting_scene_id: str = ""
    scenes: list[SceneDefinition] = field(default_factory=list)
    npcs: list[NpcDefinition] = field(default_factory=list)
    monsters: list[MonsterDefinition] = field(default_factory=list)
    items: list[ItemDefinition] = field(default_factory=list)
    puzzles: list[PuzzleDefinition] = field(default_factory=list)
    quests: list[QuestDefinition] = field(default_factory=list)
    triggers: list[TriggerDefinition] = field(default_factory=list)
