# Phases 13-15 Implementation Plan + Detailed Guide

## Context

Phases 10-12 completed the gameplay systems (combat, side-channels, split-party). Phases 13-15 build the content pipeline, prompt engineering layer, and operational reliability layer. All follow the established pure-domain architecture -- stateless engines, result dataclasses, KnowledgeFact audit trail, scope enforcement, fixture-based testing.

This document provides step-by-step implementation instructions for each task in Phases 13, 14, and 15.

---

## Phase 13: Scenario Authoring Format

**Goal:** Define a declarative YAML-based scenario format that lets authors describe scenes, exits, items, NPCs, monsters, puzzles, and triggers without writing Python. Implement validation and import tooling so scenarios load cleanly into the domain model.

**Package:** `scenarios/` (new top-level package). Create `scenarios/__init__.py`.

### Task 1: Define scenario file structure and schema

**File:** `scenarios/schema.py`

A scenario is a directory containing a `scenario.yaml` manifest and optional asset files. Define the schema as dataclasses that map 1:1 to the YAML structure:

```
ScenarioManifest:
    scenario_id: str              # unique slug, e.g. "goblin_caves"
    title: str
    description: str
    version: str                  # semver string, e.g. "1.0.0"
    author: str
    starting_scene_id: str        # which scene players begin in
    scenes: list[SceneDefinition]
    npcs: list[NpcDefinition]
    monsters: list[MonsterDefinition]
    items: list[ItemDefinition]
    puzzles: list[PuzzleDefinition]
    triggers: list[TriggerDefinition]
    quests: list[QuestDefinition]

SceneDefinition:
    scene_id: str
    name: str
    description: str              # public description players see on entry
    referee_notes: str            # referee-only notes (hidden from players)
    exits: list[ExitDefinition]
    item_ids: list[str]           # items initially placed in this scene
    npc_ids: list[str]            # NPCs initially placed in this scene
    monster_ids: list[str]        # monster groups initially placed in this scene
    puzzle_ids: list[str]         # puzzles in this scene
    trigger_ids: list[str]        # triggers active in this scene
    tags: list[str]               # freeform tags: "dark", "underwater", etc.

ExitDefinition:
    exit_id: str
    direction: str                # "north", "east", "up", "through the door", etc.
    target_scene_id: str
    description: str              # flavor text: "A narrow passage leads north"
    is_hidden: bool               # if True, only discoverable via search/inspect
    is_locked: bool               # if True, requires a key or puzzle to unlock
    unlock_condition: str         # freeform: "requires rusty_key" or "puzzle:lever_puzzle"
```

**Rationale:** YAML is human-readable and diff-friendly. The dataclass layer gives us type safety and validation hooks without needing a full schema registry.

### Task 2: Define scene, exit, item, NPC, monster, puzzle, and trigger formats

**File:** `scenarios/schema.py` (continued)

Add the remaining definition dataclasses:

```
NpcDefinition:
    npc_id: str
    name: str
    description: str              # public appearance text
    personality_tags: list[str]   # ["cautious", "greedy", "loyal"]
    goals: list[str]              # durable mind goals
    trust_initial: dict[str, int] # player_id → initial trust (optional, usually empty)
    faction: str
    scene_id: str                 # starting scene
    inventory_item_ids: list[str]
    dialogue_hints: list[str]     # style guidance for main model: ["speaks in riddles"]
    referee_notes: str            # hidden GM notes about this NPC
    tells: list[NpcTellDefinition]

NpcTellDefinition:
    tell_id: str
    trigger_type: str             # "trust_above" | "trust_below" | "action_type" | "tag_present"
    trigger_value: str            # e.g. "50", "-20", "threaten", "has_key"
    behavior: str                 # what the NPC does: "fidgets nervously", "glances at the locked chest"
    scope: str                    # "public" | "referee_only"

MonsterDefinition:
    monster_id: str
    unit_type: str                # "goblin", "dire_wolf", etc.
    count: int
    behavior_mode: str            # maps to BehaviorMode enum
    awareness_state: str          # maps to AwarenessState enum
    stats: dict[str, int]         # {"attack": 6, "defense": 2, "hp_per_unit": 5}
    special_rules: list[str]      # ["ambush_first_round", "leader_dead_routs"]
    territory_id: str             # scene_id for territorial behavior
    scene_id: str                 # starting scene
    loot_item_ids: list[str]      # items dropped on defeat
    referee_notes: str

ItemDefinition:
    item_id: str
    name: str
    description: str
    properties: dict[str, str]    # {"effect": "heal", "amount": "10", "use_verb": "drink"}
    is_hidden: bool               # requires search to find
    is_key: bool                  # can unlock exits
    unlocks_exit_ids: list[str]   # which exits this key opens
    quantity: int
    scene_id: str                 # where the item starts (empty = NPC inventory)

PuzzleDefinition:
    puzzle_id: str
    name: str
    description: str              # public description of the puzzle
    solution_hint: str            # referee-only hint
    solution_actions: list[str]   # valid solution action strings: ["pull lever", "rotate dial to 3"]
    success_text: str             # narrated on solve
    failure_text: str             # narrated on wrong attempt
    max_attempts: int             # 0 = unlimited
    effects_on_solve: list[str]   # ["unlock:east_gate", "reveal:hidden_passage"]
    scene_id: str
    referee_notes: str

QuestDefinition:
    quest_id: str
    title: str
    description: str
    objectives: list[str]         # human-readable objective list
    completion_condition: str     # freeform: "all goblins defeated AND chest opened"
    reward_description: str
    referee_notes: str

TriggerDefinition:
    trigger_id: str
    kind: str                     # maps to TriggerKind: "on_enter", "on_search", "trap", etc.
    scene_id: str
    condition_type: str           # "always" | "first_visit" | "has_item" | "puzzle_solved"
    condition_value: str          # item_id or puzzle_id for conditional triggers
    effect_type: str              # "narrate" | "damage" | "spawn_monster" | "reveal_exit" | "grant_fact"
    effect_value: str             # text, damage amount, monster_id, exit_id, or fact payload
    scope: str                    # "public" | "private_referee" | "referee_only"
    is_repeatable: bool
    referee_notes: str
```

### Task 3: Define public versus hidden content authoring rules

**File:** `scenarios/visibility_rules.py`

Create an `AuthoringVisibilityPolicy` that defines how scenario fields map to scope types at load time:

```
AuthoringVisibilityPolicy:
    REFEREE_ONLY_FIELDS: set[str]
        # Fields that produce referee_only KnowledgeFacts on load:
        # "referee_notes", "solution_hint", "tells" with scope=="referee_only"
        # These are NEVER included in player-visible narration prompts.

    HIDDEN_FIELDS: set[str]
        # Fields that are present in state but not in initial scene descriptions:
        # "is_hidden" items, hidden exits, trap triggers
        # Discoverable via search/inspect actions.

    PUBLIC_FIELDS: set[str]
        # Everything else: scene description, NPC description, item name/description,
        # visible exit directions, puzzle description.

    classify_field(definition_type: str, field_name: str, field_value: Any) -> ScopeType
        # Returns the scope type for a given field value.
        # Used during scenario import to assign correct scope to generated KnowledgeFacts.

    validate_no_leakage(manifest: ScenarioManifest) -> list[str]
        # Returns a list of warnings if any referee_notes text appears in a public field.
        # Heuristic: checks if any referee_notes substring (>10 chars) appears in description
        # or success_text fields.
```

**Authoring rules to enforce:**
1. `referee_notes` fields never appear in player-facing prompts.
2. `solution_hint` and `solution_actions` are referee-only -- players learn solutions through play.
3. Hidden items and exits exist in state but are excluded from initial scene descriptions.
4. NPC `tells` with `scope="referee_only"` produce only referee KnowledgeFacts.
5. Trigger `effect_value` text respects the trigger's `scope` field.

### Task 4: Implement scenario validation tools

**File:** `scenarios/validator.py`

```
ValidationResult:
    is_valid: bool
    errors: list[str]       # fatal: scenario cannot load
    warnings: list[str]     # non-fatal: scenario loads but may have issues

ScenarioValidator:
    validate(manifest: ScenarioManifest) -> ValidationResult

    # Internal checks:
    _check_ids_unique(manifest) -> list[str]
        # All IDs across scenes, npcs, items, etc. must be globally unique.

    _check_references_valid(manifest) -> list[str]
        # Every target_scene_id in exits must reference a defined scene.
        # Every npc.scene_id must reference a defined scene.
        # Every item in npc inventory_item_ids must be defined.
        # Every trigger.scene_id must reference a defined scene.
        # Every puzzle.scene_id must reference a defined scene.
        # Every exit unlock_condition referencing an item must point to a defined item.
        # Every monster.territory_id must reference a defined scene.

    _check_starting_scene_exists(manifest) -> list[str]
        # starting_scene_id must be in the scene list.

    _check_no_orphan_scenes(manifest) -> list[str]
        # Warning if a scene has no exits leading TO it (except the starting scene).

    _check_no_dead_end_scenes(manifest) -> list[str]
        # Warning if a scene has no exits leading OUT of it.

    _check_enum_values(manifest) -> list[str]
        # behavior_mode values map to BehaviorMode enum.
        # awareness_state values map to AwarenessState enum.
        # trigger kind values map to TriggerKind.
        # scope values map to ScopeType.

    _check_puzzle_solvability(manifest) -> list[str]
        # Warning if a puzzle has effects_on_solve referencing undefined exits or items.

    _check_visibility_rules(manifest) -> list[str]
        # Delegates to AuthoringVisibilityPolicy.validate_no_leakage().
```

### Task 5: Implement scenario import and load flow

**File:** `scenarios/loader.py`

```
ScenarioLoadResult:
    success: bool
    campaign_id: str              # newly generated campaign_id
    scenes: list[Scene]           # domain entities ready for use
    characters: list[Character]   # (empty -- players create characters at join time)
    npcs: list[NPC]
    monster_groups: list[MonsterGroup]
    items: list[InventoryItem]
    puzzles: list[PuzzleState]
    quests: list[QuestState]
    knowledge_facts: list[KnowledgeFact]    # initial facts from referee_notes, hidden items, etc.
    scopes: list[ConversationScope]         # scope entities for all scenes
    triggers: list                          # TriggerDefinition objects for TriggerEngine
    errors: list[str]

ScenarioLoader:
    load_from_yaml(yaml_path: str) -> ScenarioLoadResult
        # 1. Read and parse YAML file
        # 2. Deserialize into ScenarioManifest
        # 3. Validate via ScenarioValidator -- abort on errors
        # 4. Generate UUIDs for campaign, etc. (or use scenario-defined IDs)
        # 5. Convert each definition to its domain entity:
        #    SceneDefinition -> Scene (with state=idle, empty player_ids)
        #    NpcDefinition -> NPC (with durable_mind populated from definition)
        #    MonsterDefinition -> MonsterGroup
        #    ItemDefinition -> InventoryItem
        #    PuzzleDefinition -> PuzzleState
        #    QuestDefinition -> QuestState
        # 6. Generate KnowledgeFacts:
        #    - One referee_only fact per referee_notes field
        #    - One referee_only fact per puzzle solution_hint
        #    - One hidden fact per hidden item (discoverable via search)
        #    - One hidden fact per hidden exit
        # 7. Generate ConversationScope entities for each scene (one public scope per scene)
        # 8. Return ScenarioLoadResult

    _parse_yaml(yaml_path: str) -> dict
        # PyYAML safe_load, wrapped in try/except for parse errors

    _deserialize(data: dict) -> ScenarioManifest
        # Dict -> dataclass conversion with field validation

    _convert_scene(defn: SceneDefinition, campaign_id: str) -> Scene
    _convert_npc(defn: NpcDefinition) -> NPC
    _convert_monster(defn: MonsterDefinition) -> MonsterGroup
    _convert_item(defn: ItemDefinition) -> InventoryItem
    _convert_puzzle(defn: PuzzleDefinition) -> PuzzleState
    _convert_quest(defn: QuestDefinition) -> QuestState
    _generate_initial_facts(manifest: ScenarioManifest, campaign_id: str) -> list[KnowledgeFact]
```

**Dependency:** Add `pyyaml>=6.0` to `requirements.txt`.

### Task 6: Create starter scenario package in the new format

**File:** `scenarios/starters/goblin_caves.yaml`

A complete scenario that exercises all definition types:

```yaml
scenario_id: goblin_caves
title: "The Goblin Caves"
description: "A party of adventurers investigates reports of goblin raids."
version: "1.0.0"
author: "rpg-system"
starting_scene_id: cave_entrance

scenes:
  - scene_id: cave_entrance
    name: "Cave Entrance"
    description: >
      A dark mouth in the hillside, flanked by dead bushes. Claw marks
      score the stone around the opening. A faint smell of smoke drifts out.
    referee_notes: "The goblins have a lookout posted just inside (see goblin_lookout trigger)."
    exits:
      - exit_id: entrance_to_main_hall
        direction: "north (into the cave)"
        target_scene_id: main_hall
        description: "A rough tunnel leads deeper into the hill."
        is_hidden: false
        is_locked: false
        unlock_condition: ""
    item_ids: [discarded_torch]
    npc_ids: []
    monster_ids: [goblin_scouts]
    puzzle_ids: []
    trigger_ids: [goblin_lookout]
    tags: [outdoor, dark]

  - scene_id: main_hall
    name: "Main Hall"
    description: >
      A wide cavern lit by a sputtering fire pit. Crude shelves line the walls,
      holding stolen goods and scraps of food. Three tunnels branch off.
    referee_notes: "The goblin chief is here if not alerted. The locked chest contains the merchant's ledger."
    exits:
      - exit_id: hall_to_entrance
        direction: south
        target_scene_id: cave_entrance
        description: "The tunnel back to the entrance."
        is_hidden: false
        is_locked: false
        unlock_condition: ""
      - exit_id: hall_to_prison
        direction: east
        target_scene_id: prison_cells
        description: "A narrow passage with iron-banded doors."
        is_hidden: false
        is_locked: true
        unlock_condition: "requires iron_key"
      - exit_id: hall_to_treasury
        direction: "hidden passage behind shelves"
        target_scene_id: treasury
        description: "A cleverly concealed passage behind the supply shelves."
        is_hidden: true
        is_locked: false
        unlock_condition: ""
    item_ids: [iron_key, stolen_goods]
    npc_ids: [goblin_chief_grix]
    monster_ids: [goblin_guards]
    puzzle_ids: [locked_chest]
    trigger_ids: [fire_pit_trap]
    tags: [indoor, lit]

  - scene_id: prison_cells
    name: "Prison Cells"
    description: >
      A damp corridor lined with crude iron cages. One cage holds a
      disheveled merchant, the others are empty.
    referee_notes: "The merchant (Aldric) knows about the hidden treasury passage."
    exits:
      - exit_id: prison_to_hall
        direction: west
        target_scene_id: main_hall
        description: "Back to the main hall."
        is_hidden: false
        is_locked: false
        unlock_condition: ""
    item_ids: [cage_key]
    npc_ids: [merchant_aldric]
    monster_ids: []
    puzzle_ids: []
    trigger_ids: []
    tags: [indoor, dark, damp]

  - scene_id: treasury
    name: "Hidden Treasury"
    description: >
      A small chamber crammed with stolen valuables: coin pouches, a silver
      candelabra, and a locked wooden box.
    referee_notes: "The wooden box contains the merchant's ledger -- quest objective."
    exits:
      - exit_id: treasury_to_hall
        direction: "back through the passage"
        target_scene_id: main_hall
        description: "The concealed passage back to the main hall."
        is_hidden: false
        is_locked: false
        unlock_condition: ""
    item_ids: [merchants_ledger, silver_candelabra, coin_pouch]
    npc_ids: []
    monster_ids: []
    puzzle_ids: [wooden_box]
    trigger_ids: []
    tags: [indoor, hidden]

npcs:
  - npc_id: goblin_chief_grix
    name: "Grix, the Goblin Chief"
    description: "A scarred goblin wearing a dented crown, bigger than the others."
    personality_tags: [aggressive, cunning, cowardly_when_losing]
    goals: ["protect the tribe", "hoard treasure"]
    trust_initial: {}
    faction: goblin_tribe
    scene_id: main_hall
    inventory_item_ids: [iron_key]
    dialogue_hints: ["speaks in broken Common", "refers to self as 'Grix the Mighty'"]
    referee_notes: "Will negotiate if outnumbered. Knows about the hidden treasury."
    tells:
      - tell_id: grix_nervous
        trigger_type: trust_below
        trigger_value: "-30"
        behavior: "Grix's eyes dart toward the supply shelves."
        scope: public
      - tell_id: grix_secret_path
        trigger_type: trust_above
        trigger_value: "40"
        behavior: "Grix knows about the hidden passage behind the shelves."
        scope: referee_only

  - npc_id: merchant_aldric
    name: "Aldric the Merchant"
    description: "A middle-aged man in torn travel clothes, caged and frightened."
    personality_tags: [grateful, cautious, knowledgeable]
    goals: ["escape the caves", "recover his ledger"]
    trust_initial: {}
    faction: neutral
    scene_id: prison_cells
    inventory_item_ids: []
    dialogue_hints: ["speaks formally", "offers rewards for rescue"]
    referee_notes: "Knows about the hidden passage if asked about the treasury."
    tells:
      - tell_id: aldric_passage_hint
        trigger_type: action_type
        trigger_value: "question"
        behavior: "Aldric mentions hearing goblins moving things behind the shelves."
        scope: public

monsters:
  - monster_id: goblin_scouts
    unit_type: goblin_scout
    count: 2
    behavior_mode: patrol
    awareness_state: alert
    stats: {attack: 4, defense: 1, hp_per_unit: 5}
    special_rules: []
    territory_id: cave_entrance
    scene_id: cave_entrance
    loot_item_ids: []
    referee_notes: "Lookouts -- will call for help if engaged."

  - monster_id: goblin_guards
    unit_type: goblin_guard
    count: 4
    behavior_mode: guard
    awareness_state: unaware
    stats: {attack: 6, defense: 2, hp_per_unit: 8}
    special_rules: [leader_dead_routs]
    territory_id: main_hall
    scene_id: main_hall
    loot_item_ids: [stolen_goods]
    referee_notes: "Will rout if Grix is defeated."

items:
  - item_id: discarded_torch
    name: "Discarded Torch"
    description: "A half-burned torch, still usable."
    properties: {effect: light, duration: "30 minutes"}
    is_hidden: false
    is_key: false
    unlocks_exit_ids: []
    quantity: 1
    scene_id: cave_entrance

  - item_id: iron_key
    name: "Iron Key"
    description: "A heavy iron key on a leather cord."
    properties: {}
    is_hidden: false
    is_key: true
    unlocks_exit_ids: [hall_to_prison]
    quantity: 1
    scene_id: ""  # in Grix's inventory

  - item_id: cage_key
    name: "Cage Key"
    description: "A small rusted key hanging on a wall hook."
    properties: {}
    is_hidden: false
    is_key: true
    unlocks_exit_ids: []
    quantity: 1
    scene_id: prison_cells

  - item_id: stolen_goods
    name: "Stolen Goods"
    description: "A pile of looted trade goods."
    properties: {value: "50 gold"}
    is_hidden: false
    is_key: false
    unlocks_exit_ids: []
    quantity: 1
    scene_id: main_hall

  - item_id: merchants_ledger
    name: "Merchant's Ledger"
    description: "A leather-bound book of trade records."
    properties: {quest_item: "true"}
    is_hidden: false
    is_key: false
    unlocks_exit_ids: []
    quantity: 1
    scene_id: treasury

  - item_id: silver_candelabra
    name: "Silver Candelabra"
    description: "An ornate candelabra, clearly stolen from a manor house."
    properties: {value: "25 gold"}
    is_hidden: false
    is_key: false
    unlocks_exit_ids: []
    quantity: 1
    scene_id: treasury

  - item_id: coin_pouch
    name: "Coin Pouch"
    description: "A leather pouch heavy with mixed coins."
    properties: {value: "30 gold"}
    is_hidden: false
    is_key: false
    unlocks_exit_ids: []
    quantity: 1
    scene_id: treasury

puzzles:
  - puzzle_id: locked_chest
    name: "Locked Iron Chest"
    description: "A heavy iron chest with a complex lock mechanism."
    solution_hint: "The key is hidden in the fire pit ashes."
    solution_actions: ["use iron_key on chest", "pick lock"]
    success_text: "The chest clicks open, revealing trade documents inside."
    failure_text: "The lock doesn't budge."
    max_attempts: 0
    effects_on_solve: ["reveal:merchants_ledger_copy"]
    scene_id: main_hall
    referee_notes: "Contains copies of Aldric's trade routes."

  - puzzle_id: wooden_box
    name: "Locked Wooden Box"
    description: "A sturdy wooden box with a brass latch."
    solution_hint: "Can be forced open with strength or unlocked with cage_key."
    solution_actions: ["force open", "use cage_key"]
    success_text: "The box opens to reveal Aldric's ledger."
    failure_text: "The latch holds firm."
    max_attempts: 3
    effects_on_solve: []
    scene_id: treasury
    referee_notes: "The ledger is the main quest objective."

quests:
  - quest_id: rescue_aldric
    title: "Rescue the Merchant"
    description: "Find and free the captured merchant Aldric from the goblin caves."
    objectives:
      - "Enter the goblin caves"
      - "Find the prison cells"
      - "Free Aldric from his cage"
    completion_condition: "Aldric freed from cage AND escorted to cave_entrance"
    reward_description: "Aldric offers 100 gold and information about trade routes."
    referee_notes: "Aldric will also reveal the hidden passage if rescued."

  - quest_id: recover_ledger
    title: "The Lost Ledger"
    description: "Recover Aldric's stolen trade ledger from the goblin treasury."
    objectives:
      - "Locate the hidden treasury"
      - "Recover the merchant's ledger"
    completion_condition: "merchants_ledger in party inventory"
    reward_description: "Aldric's gratitude and a trade route map."
    referee_notes: "Secondary objective -- can be discovered through Aldric or exploration."

triggers:
  - trigger_id: goblin_lookout
    kind: on_enter
    scene_id: cave_entrance
    condition_type: first_visit
    condition_value: ""
    effect_type: narrate
    effect_value: "A sharp whistle echoes from inside the cave -- you've been spotted!"
    scope: public
    is_repeatable: false
    referee_notes: "Alerts goblin_guards in main_hall to 'alert' awareness."

  - trigger_id: fire_pit_trap
    kind: trap
    scene_id: main_hall
    condition_type: always
    condition_value: ""
    effect_type: damage
    effect_value: "3"
    scope: public
    is_repeatable: false
    referee_notes: "Hidden coals around the fire pit. Triggers on 'search fire pit' or 'interact fire pit'."
```

### Task 7: Add validation tests and content fixtures

**File:** `tests/fixtures/scenario_fixtures.py`

```
# Provide helper functions:

make_minimal_manifest() -> ScenarioManifest
    # Two scenes, one exit, one NPC, one item. Minimal valid scenario.

make_goblin_caves_manifest() -> ScenarioManifest
    # Load and parse scenarios/starters/goblin_caves.yaml

make_invalid_manifest_broken_ref() -> ScenarioManifest
    # Scene with exit pointing to nonexistent target_scene_id

make_invalid_manifest_duplicate_ids() -> ScenarioManifest
    # Two items with the same item_id

make_manifest_with_leakage() -> ScenarioManifest
    # referee_notes text duplicated in a public description field
```

**File:** `tests/unit/test_scenario.py`

Target ~70 tests:

- **Schema deserialization:** YAML round-trips to dataclasses; missing required fields raise errors; extra fields ignored.
- **Validation -- IDs:** duplicate IDs across entity types produce error; unique IDs pass.
- **Validation -- references:** invalid target_scene_id in exit produces error; valid refs pass. Invalid npc.scene_id produces error. Invalid item in inventory_item_ids produces error.
- **Validation -- starting scene:** missing starting_scene_id produces error; valid starting scene passes.
- **Validation -- orphan scenes:** scene with no inbound exits (non-starting) produces warning.
- **Validation -- dead ends:** scene with no outbound exits produces warning.
- **Validation -- enums:** invalid behavior_mode produces error; valid enums pass.
- **Validation -- visibility:** referee_notes text in public description produces warning.
- **Loader:** goblin_caves.yaml loads successfully; produces correct number of Scene, NPC, MonsterGroup, InventoryItem entities. Starting scene is `cave_entrance`.
- **Loader -- facts:** referee_notes produce referee_only KnowledgeFacts. Hidden exits produce hidden KnowledgeFacts. Solution hints produce referee_only facts.
- **Loader -- scopes:** each scene gets a public ConversationScope. Referee_only scope created for campaign.
- **Loader -- error handling:** malformed YAML returns success=False with error. Valid YAML with broken refs returns success=False with validation errors.
- **Visibility policy:** classify_field returns correct scope for each field type. validate_no_leakage catches duplicated referee text.
- **Full round-trip:** load goblin_caves -> verify scene count, NPC count, item count, quest count, trigger count, fact count all match the YAML.

---

## Phase 14: Prompt Contracts and Context Assembly

**Goal:** Formalize every LLM prompt as a versioned contract with explicit input schema, output schema, scope rules, and size limits. Refactor the existing `models/main/context.py` and `models/fast/tasks.py` prompt assembly into a shared contract registry so prompts are testable, auditable, and scope-safe.

**Package:** Extend `models/` with `models/contracts/` (new). Create `models/contracts/__init__.py`.

### Task 1: Define fast-model prompt contracts

**File:** `models/contracts/fast_contracts.py`

Define a `PromptContract` dataclass and register each fast-tier task:

```
PromptContract:
    contract_id: str                  # "fast.intent_classification"
    version: str                      # "1.0.0"
    tier: str                         # "fast" | "main"
    task_type: str                    # matches TaskType or MainTaskType
    system_prompt_template: str       # Jinja2-style or f-string template
    user_prompt_template: str
    input_fields: list[str]           # required input field names
    output_schema: dict               # JSON schema for expected output
    output_example: str               # example valid JSON output
    max_input_tokens: int             # per model_routing.md: 2K target, 4K hard limit
    max_output_tokens: int
    scope_rules: list[str]            # e.g. ["no_referee_facts", "public_only"]
    fallback_output: dict             # deterministic fallback if model fails

FAST_CONTRACTS: dict[str, PromptContract]
    # Registry keyed by contract_id. One entry per fast-tier task:
    # - fast.intent_classification
    # - fast.command_normalization
    # - fast.action_extraction
    # - fast.scope_suggestion
    # - fast.context_summarization
    # - fast.clarification_generation
    # - fast.schema_repair

get_fast_contract(task_type: str) -> PromptContract
    # Lookup by task_type, raise KeyError if not found.
```

Each contract codifies the system prompt, user prompt template, expected JSON schema, and deterministic fallback currently scattered across `models/fast/tasks.py`. The existing task functions in `tasks.py` should delegate to the contract for prompt assembly (refactor in-place; do not duplicate).

**Contract for intent_classification example:**

```python
PromptContract(
    contract_id="fast.intent_classification",
    version="1.0.0",
    tier="fast",
    task_type="intent_classification",
    system_prompt_template=(
        "You are a message classifier for a text RPG. "
        "Classify the player message and reply with valid JSON only. "
        'Schema: {output_schema_inline}'
    ),
    user_prompt_template='Classify this player message:\n"""\n{message_text}\n"""',
    input_fields=["message_text"],
    output_schema={
        "type": "object",
        "required": ["intent", "confidence"],
        "properties": {
            "intent": {"type": "string", "enum": ["action", "question", "chat", "command"]},
            "confidence": {"type": "string", "enum": ["high", "low"]},
        },
    },
    output_example='{"intent": "action", "confidence": "high"}',
    max_input_tokens=2048,
    max_output_tokens=128,
    scope_rules=["public_only"],
    fallback_output={"intent": "unknown", "confidence": "low"},
)
```

### Task 2: Define Gemma gameplay prompt contracts

**File:** `models/contracts/main_contracts.py`

Same `PromptContract` structure. One contract per main-tier task:

```
MAIN_CONTRACTS: dict[str, PromptContract]
    # - main.scene_narration
    # - main.npc_dialogue
    # - main.combat_summary
    # - main.ruling_proposal
    # - main.social_arbitration
    # - main.puzzle_flavor
    # - main.unusual_action

get_main_contract(task_type: str) -> PromptContract
```

**Key contracts:**

**`main.scene_narration`:**
- System prompt: "You are the narrator for a multiplayer text RPG. Write vivid, concise scene narration. Use second-person plural ('you'). Do not reveal hidden information. Stay within the facts provided."
- Input fields: `scene_context`, `committed_actions`, `public_facts`, `active_players`, `tone_hint`
- Output schema: `{"narration": str, "private_notes": str, "tone": str}`
- Scope rules: `["no_referee_facts", "no_side_channel_facts", "public_facts_only"]`
- Max input: 16K tokens. Max output: 2K tokens.

**`main.npc_dialogue`:**
- System prompt: "You are voicing an NPC in a text RPG. Stay in character based on the personality, goals, and trust level provided. Do not reveal information the NPC would not share at this trust level."
- Input fields: `npc_context`, `action_context`, `scene_context`, `dialogue_hints`
- Output schema: `{"dialogue": str, "internal_thought": str, "trust_shift_suggestion": int}`
- Scope rules: `["npc_scoped", "no_other_npc_facts"]`
- Max input: 8K tokens. Max output: 1K tokens.

**`main.combat_summary`:**
- Input fields: `battlefield_summary`, `action_results`, `scene_context`
- Output schema: `{"narration": str, "tone": str}`
- Scope rules: `["public_only", "no_hidden_monster_stats"]`
- Max input: 8K tokens. Max output: 1K tokens.

**`main.ruling_proposal`:**
- Input fields: `action_text`, `character_context`, `scene_context`, `relevant_rules`
- Output schema: `{"ruling": str, "success": bool, "confidence": str, "reasoning": str}`
- Scope rules: `["minimal_private_facts"]`
- Max input: 8K tokens. Max output: 512 tokens.

### Task 3: Define context assembly rules for narration, arbitration, dialogue, and summaries

**File:** `models/contracts/context_assembly.py`

Refactor and formalize the assembly logic from `models/main/context.py`:

```
ContextAssembler:
    __init__(contracts: dict[str, PromptContract])

    assemble(
        contract_id: str,
        scene: Scene,
        characters: list[Character],
        npcs: list[NPC],
        monster_groups: list[MonsterGroup],
        facts: list[KnowledgeFact],
        scopes: list[ConversationScope],
        committed_actions: list[CommittedAction] = None,
        target_npc: NPC = None,
        action_text: str = "",
        recent_history: list[TurnLogEntry] = None,
    ) -> AssembledPrompt

AssembledPrompt:
    system_prompt: str          # fully rendered system prompt
    user_prompt: str            # fully rendered user prompt
    contract_id: str
    token_estimate: int         # rough estimate (chars / 4)
    was_truncated: bool         # True if history was dropped to fit
    scope_violations: list[str] # empty if clean; populated if assembly detected a leak

    # Internal assembly steps:
    # 1. Look up the PromptContract by contract_id
    # 2. Filter facts by contract's scope_rules:
    #    - "public_only": exclude all non-public facts
    #    - "no_referee_facts": exclude referee_only facts
    #    - "no_side_channel_facts": exclude side_channel facts
    #    - "npc_scoped": include only facts the target NPC would know
    #    - "minimal_private_facts": include only facts directly relevant to the action
    # 3. Assemble scene context (location, description, active players)
    # 4. Assemble character/NPC/monster context as needed
    # 5. Assemble recent history (truncate oldest first if over budget)
    # 6. Render templates with assembled context
    # 7. Estimate token count; if over max_input_tokens, truncate history further
    # 8. Run scope violation check: scan rendered prompt for referee_only fact text
    # 9. Return AssembledPrompt
```

### Task 4: Define prompt size limits and truncation policies

**File:** `models/contracts/truncation.py`

```
TruncationPolicy:
    FAST_TARGET_TOKENS: int = 2048
    FAST_HARD_LIMIT_TOKENS: int = 4096
    MAIN_TARGET_TOKENS: int = 16384
    MAIN_HARD_LIMIT_TOKENS: int = 32768
    MAIN_DEEP_CONTEXT_TOKENS: int = 262144  # 256K for long campaigns

    CHARS_PER_TOKEN: int = 4  # conservative estimate

    estimate_tokens(text: str) -> int
        # len(text) // CHARS_PER_TOKEN

    truncate_history(
        history_entries: list[str],
        current_prompt_tokens: int,
        max_tokens: int,
    ) -> tuple[list[str], bool]
        # Drop oldest entries first until current_prompt_tokens fits.
        # Return (remaining entries, was_truncated).
        # Never truncate scene state or player facts -- only chat history.

    truncate_facts(
        facts: list[KnowledgeFact],
        current_tokens: int,
        max_tokens: int,
    ) -> tuple[list[KnowledgeFact], bool]
        # If history truncation is insufficient, drop oldest facts.
        # Preserve facts tagged as "critical" or "quest_objective".
        # Return (remaining facts, was_truncated).

    check_limit(text: str, tier: str) -> TruncationResult

TruncationResult:
    within_target: bool
    within_hard_limit: bool
    estimated_tokens: int
    tier: str
```

### Task 5: Define schema validation and output-repair rules

**File:** `models/contracts/output_repair.py`

Formalize the repair pipeline that currently lives scattered across `models/main/tasks.py` and `models/fast/tasks.py`:

```
RepairPipeline:
    __init__(fast_adapter: OllamaFastAdapter)

    validate_output(contract_id: str, raw_output: str) -> ValidationResult
        # 1. Try JSON parse
        # 2. Check against contract's output_schema (required fields, types, enum values)
        # 3. Return ValidationResult with is_valid, parsed_data, errors

    repair_output(contract_id: str, raw_output: str) -> RepairResult
        # 1. Call validate_output -- if valid, return as-is
        # 2. Send to fast model with schema_repair contract:
        #    "Fix this JSON to match the schema: {schema}. Broken input: {raw_output}"
        # 3. Validate repaired output
        # 4. If still invalid, return contract's fallback_output
        # 5. Log all steps via ModelCallLog

    get_fallback(contract_id: str) -> dict
        # Return the contract's fallback_output

ValidationResult:
    is_valid: bool
    parsed_data: dict | None
    errors: list[str]

RepairResult:
    success: bool
    data: dict               # parsed valid data (or fallback)
    repair_attempted: bool
    repair_succeeded: bool
    fallback_used: bool
    log: ModelCallLog | None
```

### Task 6: Add prompt-assembly regression fixtures

**File:** `tests/fixtures/prompt_fixtures.py`

```
# Provide builder functions for each contract type:

make_narration_inputs() -> dict
    # scene_context, committed_actions, public_facts for a tavern scene
    # Expected: prompt contains scene description, action summaries, no referee facts

make_npc_dialogue_inputs() -> dict
    # npc_context (Mira the Innkeeper), action (question), scene_context
    # Expected: prompt contains NPC personality + goals, not other NPC private facts

make_combat_summary_inputs() -> dict
    # battlefield_summary from combat_scenario, action_results
    # Expected: prompt contains combatant lines, no hidden monster awareness

make_ruling_inputs() -> dict
    # unusual action text, character_context, scene_context
    # Expected: prompt contains action + character state, minimal private facts

make_oversized_history() -> list[str]
    # 200 history entries to test truncation at both fast and main limits

make_broken_json_outputs() -> dict[str, str]
    # One broken JSON string per contract type, for repair pipeline testing

make_valid_json_outputs() -> dict[str, str]
    # One valid JSON string per contract type
```

### Task 7: Add tests for scope-safe context assembly and leakage prevention

**File:** `tests/unit/test_prompt_contracts.py`

Target ~80 tests:

- **Contract registry:** all fast contracts registered; all main contracts registered. get_fast_contract and get_main_contract return correct contracts. Unknown task_type raises KeyError.
- **Contract fields:** each contract has non-empty system_prompt_template, user_prompt_template, output_schema, fallback_output. Max token limits match model_routing.md.
- **Context assembly -- narration:** assembled prompt contains scene description, player names, committed actions. Does NOT contain referee_only facts. Does NOT contain side_channel facts.
- **Context assembly -- NPC dialogue:** assembled prompt contains target NPC personality and goals. Does NOT contain other NPCs' private facts. Contains NPC's trust level toward the acting player.
- **Context assembly -- combat:** assembled prompt contains battlefield summary and action results. Does NOT contain hidden monster awareness states for unaware groups.
- **Context assembly -- ruling:** assembled prompt contains the action text and character context. Contains minimal private facts (only those relevant to the specific action).
- **Scope violation detection:** if a referee_only fact text is found in a public narration prompt, scope_violations is non-empty.
- **Truncation -- history:** 200 history entries truncated to fit within 16K target. Oldest entries removed first. Scene state and player facts preserved.
- **Truncation -- fast tier:** prompt exceeding 4K hard limit is truncated. Result fits within 4K.
- **Truncation -- facts:** if history truncation isn't enough, oldest non-critical facts dropped.
- **Token estimation:** estimate_tokens returns reasonable values (within 2x of expected).
- **Output validation:** valid JSON matching schema passes. Missing required field fails. Wrong enum value fails.
- **Output repair:** broken JSON sent to fast model for repair; repaired output validates. If repair fails, fallback used.
- **Repair pipeline:** full pipeline: validate -> repair -> fallback. Each step logged.
- **Fallback values:** each contract's fallback_output validates against its own schema.
- **Template rendering:** system and user prompts render with supplied inputs without template errors. Missing input field raises clear error.

---

## Phase 15: Reliability, Recovery, and Observability

**Goal:** Make the system production-grade: structured logging with trace IDs, retry logic for Telegram delivery, idempotency for duplicate messages, graceful model timeouts, crash recovery for in-progress turns, admin diagnostics, and metrics collection.

**Package:** Extend `server/` with `server/reliability/` (new). Create `server/reliability/__init__.py`. Also extend `bot/` and add `server/observability/`.

### Task 1: Implement structured logging and trace IDs

**File:** `server/observability/logging.py`

```
TraceContext:
    trace_id: str             # UUID, created per incoming request/turn
    campaign_id: str
    scene_id: str
    turn_window_id: str
    player_id: str            # the acting player, if applicable
    span: str                 # "turn_resolution", "model_call", "telegram_delivery", etc.

    @classmethod
    def new(cls, campaign_id, scene_id="", turn_window_id="", player_id="") -> TraceContext

    def child(self, span: str) -> TraceContext
        # Same trace_id, new span

configure_logging(log_level: str = "INFO", log_format: str = "json") -> None
    # Configure Python logging with structured JSON output.
    # Each log record includes: timestamp, level, message, trace_id, campaign_id,
    # scene_id, turn_window_id, player_id, span.
    # Uses logging.config.dictConfig or structlog if available.

get_logger(name: str) -> logging.Logger
    # Return a logger with the given name, pre-configured by configure_logging.

class TraceFilter(logging.Filter):
    # Attaches TraceContext fields to every log record.
    # Uses contextvars.ContextVar to store the current TraceContext per-task.
```

**File:** `server/observability/__init__.py`

```python
from server.observability.logging import TraceContext, configure_logging, get_logger
```

**Integration points:**
- `bot/gateway.py`: create TraceContext on each incoming update, store in contextvar.
- `server/engine/turn_engine.py`: create child trace for turn resolution.
- `models/fast/tasks.py` and `models/main/tasks.py`: use trace_id from context (already passed as parameter).
- `bot/outbound.py`: create child trace for each delivery.

### Task 2: Implement retry handling for Telegram delivery failures

**File:** `server/reliability/telegram_retry.py`

```
RetryPolicy:
    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    retryable_errors: set[int] = {429, 500, 502, 503, 504}
        # HTTP status codes that warrant retry.
        # 429 = rate limited (respect Retry-After header).
        # 5xx = transient server errors.

DeliveryAttempt:
    attempt_number: int
    success: bool
    error: str
    http_status: int
    timestamp: datetime
    retry_after_seconds: float  # from 429 Retry-After header, or 0

DeliveryResult:
    success: bool
    message_id: int | None      # Telegram message_id if delivered
    attempts: list[DeliveryAttempt]
    total_duration_ms: float
    trace_id: str

async def send_with_retry(
    send_fn: Callable,           # the actual bot.send_message / bot.edit_message call
    retry_policy: RetryPolicy,
    trace_id: str = "",
) -> DeliveryResult:
    # 1. Call send_fn
    # 2. If succeeds, return DeliveryResult(success=True, ...)
    # 3. If fails with retryable error:
    #    a. Log warning with trace_id, attempt number, error
    #    b. Wait with exponential backoff (base * 2^attempt, capped at max_delay)
    #    c. For 429: use Retry-After header value instead of exponential backoff
    #    d. Retry up to max_retries
    # 4. If all retries exhausted, return DeliveryResult(success=False, ...)
    # 5. If non-retryable error (e.g. 400, 403), fail immediately
```

### Task 3: Implement duplicate-delivery and replay protection

**File:** `server/reliability/idempotency.py`

```
IdempotencyStore:
    """In-memory store of processed message/update IDs to prevent duplicate handling."""

    __init__(max_size: int = 10000, ttl_seconds: int = 3600)

    _seen: OrderedDict[str, datetime]  # key -> timestamp

    mark_seen(key: str) -> bool
        # Returns True if this is the FIRST time seeing this key.
        # Returns False if already seen (duplicate).
        # Evicts entries older than ttl_seconds.
        # Evicts oldest entries if max_size exceeded.

    is_seen(key: str) -> bool
        # Check without marking.

    clear() -> None
        # Reset store (for testing).

# Key generation helpers:

def telegram_update_key(update_id: int) -> str:
    # "tg_update:{update_id}"

def turn_action_key(turn_window_id: str, player_id: str) -> str:
    # "turn_action:{turn_window_id}:{player_id}"

def delivery_key(campaign_id: str, scene_id: str, turn_number: int, scope: str) -> str:
    # "delivery:{campaign_id}:{scene_id}:{turn_number}:{scope}"
```

**Integration points:**
- `bot/gateway.py`: check `telegram_update_key(update.update_id)` before processing. Skip duplicates.
- `server/engine/turn_engine.py`: check `turn_action_key` before accepting a CommittedAction.
- `bot/outbound.py`: check `delivery_key` before sending narration to prevent double-posting on crash recovery.

### Task 4: Implement model timeout and recovery behavior

**File:** `server/reliability/model_recovery.py`

```
ModelTimeoutPolicy:
    fast_timeout_seconds: float = 5.0
    main_timeout_seconds: float = 30.0
    repair_timeout_seconds: float = 10.0

ModelCallResult:
    success: bool
    data: dict | None
    fallback_used: bool
    timeout: bool
    error: str
    duration_ms: float
    trace_id: str

async def call_with_timeout(
    call_fn: Callable,
    timeout_seconds: float,
    fallback_fn: Callable,
    trace_id: str = "",
) -> ModelCallResult:
    # 1. Wrap call_fn in asyncio.wait_for(timeout=timeout_seconds)
    # 2. If completes within timeout, return result
    # 3. If times out:
    #    a. Log warning with trace_id and duration
    #    b. Cancel the task
    #    c. Call fallback_fn to get deterministic result
    #    d. Return ModelCallResult(success=True, fallback_used=True, timeout=True, ...)
    # 4. If call_fn raises exception:
    #    a. Log error with trace_id and exception
    #    b. Call fallback_fn
    #    c. Return ModelCallResult(success=True, fallback_used=True, ...)
    # Key: the turn is NEVER blocked. Fallback always produces a usable result.
```

### Task 5: Implement crash-safe turn recovery

**File:** `server/reliability/turn_recovery.py`

```
TurnRecoveryState:
    turn_window_id: str
    campaign_id: str
    scene_id: str
    state_at_crash: str           # TurnWindowState value
    committed_actions: list[str]  # action IDs that were committed before crash
    pending_players: list[str]    # player IDs who hadn't submitted
    recovered_at: datetime
    recovery_action: str          # "resumed" | "force_resolved" | "aborted"

TurnRecoveryEngine:
    diagnose(turn_window: TurnWindow, scene: Scene, players: list[Player]) -> TurnRecoveryState
        # Inspect the turn window state and determine what happened:
        # - If state == "open" or "all_ready": turn was mid-collection.
        #   Action: resume timer from remaining time, or force-close if timer expired.
        # - If state == "locked" or "resolving": turn was mid-resolution.
        #   Action: re-resolve from committed actions (deterministic, idempotent).
        # - If state == "committed": turn was resolved but narration may not have been delivered.
        #   Action: re-deliver narration.
        # - If state == "aborted": no action needed.

    recover(
        turn_window: TurnWindow,
        scene: Scene,
        players: list[Player],
        committed_actions: list[CommittedAction],
    ) -> TurnRecoveryResult
        # Execute the recovery action determined by diagnose():
        # 1. "resumed": synthesize timeout fallback actions for pending players,
        #    lock the turn, proceed to resolution.
        # 2. "force_resolved": re-run resolution engine with existing committed actions.
        # 3. "aborted": mark turn as aborted, open a new turn window.
        # All recovery actions are logged with trace_id.

    find_stuck_turns(
        all_turn_windows: list[TurnWindow],
        max_age_minutes: int = 30,
    ) -> list[TurnWindow]
        # Return turn windows that have been in "open", "locked", or "resolving"
        # state for longer than max_age_minutes.

TurnRecoveryResult:
    success: bool
    turn_window: TurnWindow       # updated state
    recovery_action: str
    new_actions_synthesized: int   # fallback actions created for missing players
    narration_redelivered: bool
    trace_id: str
```

### Task 6: Implement admin diagnostics for stuck turns and failed deliveries

**File:** `server/observability/diagnostics.py`

```
DiagnosticReport:
    timestamp: datetime
    campaign_id: str
    stuck_turns: list[StuckTurnInfo]
    failed_deliveries: list[FailedDeliveryInfo]
    model_health: ModelHealthInfo
    player_status: list[PlayerStatusInfo]

StuckTurnInfo:
    turn_window_id: str
    scene_id: str
    state: str
    age_minutes: float
    pending_players: list[str]
    recommended_action: str       # "wait", "force_resolve", "abort"

FailedDeliveryInfo:
    target: str                   # "public:{scene_id}" or "private:{player_id}"
    last_attempt: datetime
    error: str
    retry_count: int

ModelHealthInfo:
    fast_model_responsive: bool
    main_model_responsive: bool
    fast_avg_latency_ms: float
    main_avg_latency_ms: float
    recent_failures: int          # in last 10 minutes
    recent_fallbacks: int

PlayerStatusInfo:
    player_id: str
    display_name: str
    has_dm_open: bool
    current_scene_id: str
    pending_action: bool          # has a turn window waiting for their action

DiagnosticsEngine:
    build_report(
        campaign_id: str,
        turn_windows: list[TurnWindow],
        scenes: list[Scene],
        players: list[Player],
        delivery_log: list[DeliveryResult],
        model_call_log: list[ModelCallLog],
    ) -> DiagnosticReport
        # Assemble all diagnostic information.
        # Stuck turns: find_stuck_turns with 30-minute threshold.
        # Failed deliveries: filter delivery_log for success=False.
        # Model health: compute from recent ModelCallLog entries.
        # Player status: current scene, pending actions, DM status.

    format_report(report: DiagnosticReport) -> str
        # Human-readable text summary for admin DM.
        # Example:
        # === Campaign Diagnostics ===
        # Stuck turns: 1
        #   - Turn abc123 in "Dark Cave" (45 min, state=resolving)
        #     Recommended: force_resolve
        # Failed deliveries: 2
        #   - public:scene_001 — 429 rate limit (3 retries exhausted)
        #   - private:player_042 — 403 bot blocked by user
        # Model health: fast OK (avg 120ms), main OK (avg 2100ms)
        #   Recent failures: 0, fallbacks: 1
        # Players: 4 active, 1 pending action
```

**Bot integration:** Add a `/diagnostics` admin command in `bot/commands.py` that calls `DiagnosticsEngine.build_report()` and sends the formatted report to the requesting admin via DM.

### Task 7: Implement metrics for latency, routing, and failures

**File:** `server/observability/metrics.py`

```
MetricsCollector:
    """In-memory metrics aggregator. Collects counters and histograms."""

    __init__()

    # Counters
    _counters: dict[str, int]

    increment(name: str, value: int = 1, tags: dict[str, str] = None) -> None
        # Increment a named counter. Tags allow dimensional breakdown.
        # Key format: "{name}:{tag1=val1,tag2=val2}"

    get_counter(name: str, tags: dict[str, str] = None) -> int

    # Histograms (latency tracking)
    _histograms: dict[str, list[float]]

    record(name: str, value: float, tags: dict[str, str] = None) -> None
        # Append a value to a named histogram.

    get_percentile(name: str, percentile: float, tags: dict[str, str] = None) -> float
        # Return the Nth percentile of recorded values.

    get_stats(name: str, tags: dict[str, str] = None) -> MetricStats

    # Snapshot
    snapshot() -> MetricsSnapshot
        # Return current state of all counters and histograms.

    reset() -> None
        # Clear all metrics (for testing).

MetricStats:
    count: int
    min: float
    max: float
    mean: float
    p50: float
    p95: float
    p99: float

MetricsSnapshot:
    timestamp: datetime
    counters: dict[str, int]
    histograms: dict[str, MetricStats]

# Pre-defined metric names (constants):
METRIC_MODEL_CALLS = "model.calls"              # tags: tier, task_type, success
METRIC_MODEL_LATENCY = "model.latency_ms"       # tags: tier, task_type
METRIC_MODEL_FALLBACKS = "model.fallbacks"       # tags: tier, task_type
METRIC_DELIVERY_ATTEMPTS = "delivery.attempts"   # tags: scope, success
METRIC_DELIVERY_LATENCY = "delivery.latency_ms"  # tags: scope
METRIC_TURN_DURATION = "turn.duration_ms"        # tags: scene_type
METRIC_TURN_TIMEOUTS = "turn.timeouts"           # tags: scene_id
METRIC_ACTIONS_SUBMITTED = "actions.submitted"   # tags: action_type
METRIC_DUPLICATE_BLOCKED = "idempotency.blocked" # tags: key_type
```

**Integration points:**
- `models/fast/tasks.py` and `models/main/tasks.py`: record METRIC_MODEL_CALLS, METRIC_MODEL_LATENCY, METRIC_MODEL_FALLBACKS after each call.
- `bot/outbound.py`: record METRIC_DELIVERY_ATTEMPTS and METRIC_DELIVERY_LATENCY.
- `server/engine/turn_engine.py`: record METRIC_TURN_DURATION on turn commit, METRIC_TURN_TIMEOUTS on timeout.
- `server/reliability/idempotency.py`: record METRIC_DUPLICATE_BLOCKED when a duplicate is rejected.

### Task 8: Add failure-path tests for retries, duplicates, and restart recovery

**File:** `tests/fixtures/reliability_fixtures.py`

```
make_stuck_turn_window(state: str = "resolving", age_minutes: int = 45) -> TurnWindow
    # A turn window stuck in the given state for the given duration.

make_failed_delivery_results(count: int = 3) -> list[DeliveryResult]
    # Delivery results with various failure modes: 429, 500, 403.

make_model_call_logs(failures: int = 2, fallbacks: int = 1) -> list[ModelCallLog]
    # Mix of successful and failed model calls.

make_crash_recovery_scenario() -> dict
    # Turn window in "resolving" state with 2 of 3 actions committed.
    # Simulates a crash mid-resolution.
```

**File:** `tests/unit/test_reliability.py`

Target ~80 tests:

- **Retry -- success on first try:** send_with_retry returns immediately on success.
- **Retry -- success on retry:** first call returns 500, second returns success. Two attempts logged.
- **Retry -- 429 rate limit:** respects Retry-After header delay.
- **Retry -- all retries exhausted:** three 500 errors, returns success=False with 3 attempts.
- **Retry -- non-retryable error:** 400 error, no retries, immediate failure.
- **Retry -- exponential backoff:** delays increase: 1s, 2s, 4s (capped at max).
- **Idempotency -- first seen:** mark_seen returns True, is_seen returns True.
- **Idempotency -- duplicate:** second mark_seen returns False.
- **Idempotency -- TTL expiry:** entry older than ttl_seconds is evicted, mark_seen returns True again.
- **Idempotency -- max size:** oldest entries evicted when store exceeds max_size.
- **Idempotency -- key generation:** telegram_update_key, turn_action_key, delivery_key produce expected formats.
- **Model timeout -- completes in time:** call_with_timeout returns model result.
- **Model timeout -- times out:** call_with_timeout returns fallback result, timeout=True.
- **Model timeout -- exception:** call_with_timeout catches exception, returns fallback.
- **Model timeout -- fallback is valid:** fallback result validates against contract schema.
- **Turn recovery -- diagnose open turn:** returns "resumed" recovery action.
- **Turn recovery -- diagnose resolving turn:** returns "force_resolved" recovery action.
- **Turn recovery -- diagnose committed turn:** returns re-deliver narration.
- **Turn recovery -- recover open turn:** synthesizes fallback actions for missing players, resolves turn.
- **Turn recovery -- recover resolving turn:** re-resolves with existing actions, produces same result (idempotent).
- **Turn recovery -- find stuck turns:** correctly identifies turns older than threshold.
- **Turn recovery -- find stuck turns ignores committed:** committed turns not flagged as stuck.
- **Diagnostics -- report assembly:** produces correct stuck turn count, failed delivery count, model health stats.
- **Diagnostics -- format report:** produces human-readable text with all sections.
- **Diagnostics -- empty report:** no stuck turns, no failures produces clean report.
- **Metrics -- counter increment:** increment and get_counter return correct values.
- **Metrics -- histogram stats:** record values, get_stats returns correct min/max/mean/p50/p95/p99.
- **Metrics -- percentile edge cases:** single value, empty histogram.
- **Metrics -- tags:** same metric name with different tags tracked independently.
- **Metrics -- snapshot:** returns all counters and histograms.
- **Metrics -- reset:** clears all data.
- **Structured logging -- trace context:** TraceContext.new creates valid trace_id. child() preserves trace_id with new span.
- **Structured logging -- contextvar:** TraceContext stored in contextvar is accessible from child coroutines.

---

## Verification

After each phase:
1. `pytest` -- all tests pass.
2. `ruff check . && ruff format --check .` -- lint clean.
3. Review test count growth (currently 728; expect ~800 after Phase 13, ~880 after Phase 14, ~960 after Phase 15).
4. One commit per phase, never push without explicit authorization.

## Dependencies to Add

| Phase | Package | Purpose | Version |
|-------|---------|---------|---------|
| 13 | `pyyaml` | YAML scenario parsing | `>=6.0` |
| 15 | (none) | All Phase 15 uses stdlib only (`logging`, `asyncio`, `contextvars`, `collections.OrderedDict`) | -- |
