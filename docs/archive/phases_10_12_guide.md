# Phases 10–12 Implementation Plan + Configuration Guide

## Context

Phases 7–9 completed the intelligence layers (main model contracts, exploration loop, NPC social loop). Phases 10–12 build the remaining gameplay systems: combat, private coordination, and split-party play. All follow the established pure-domain architecture — stateless engines, result dataclasses, KnowledgeFact audit trail, scope enforcement, fixture-based testing.

This document provides step-by-step implementation instructions for each task in Phases 10, 11, and 12, plus a configuration section for Telegram and Ollama setup.

---

## Configuration & Setup

### Telegram Bot Token (`BOT_TOKEN`)

1. Open Telegram, search for **@BotFather**, send `/newbot`.
2. Choose a display name and a username ending in `bot`.
3. BotFather replies with a token like `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`.
4. Save it: `set BOT_TOKEN=123456:ABC-DEF...` (or add to a `.env` file at `C:\Projects\rpg\.env`).

### Group Chat ID (`GROUP_CHAT_ID`)

1. Create a Telegram **supergroup** and add your bot as an admin.
2. Send any message in the group.
3. Call `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser.
4. Find `"chat":{"id":-100XXXXXXXXXX}` in the response — that negative number is your Group Chat ID.
5. Save it: `set GROUP_CHAT_ID=-100XXXXXXXXXX`.

### Play Topic ID (`PLAY_TOPIC_ID`, optional)

1. In the supergroup, enable **Topics** (group Settings → Topics).
2. Create a topic called "Play".
3. Send a message in that topic, then call `getUpdates` again.
4. Find `"message_thread_id": <number>` — that's your Play Topic ID.
5. Save it: `set PLAY_TOPIC_ID=<number>`.
6. If omitted, the bot sends messages to the top-level group chat.

### Webhook (optional — polling is the default)

Only needed if deploying behind a public HTTPS endpoint:
- `set WEBHOOK_URL=https://yourdomain.com/webhook`
- `set WEBHOOK_PORT=8443`

For local dev, leave both unset — the bot uses long-polling automatically via `bot/__main__.py`.

### Ollama Setup

1. Install Ollama from `https://ollama.com`.
2. Set model storage: `set OLLAMA_MODELS=D:\ollama\models`.
3. Pull the fast model: `ollama pull qwen2.5:1.5b`
4. Pull the main model: `ollama pull gemma3:27b` (or substitute when gemma4 is available).
5. Start the server: `ollama serve` (default: `http://localhost:11434`).
6. Override the base URL via `FAST_MODEL_BASE_URL` or `GEMMA_BASE_URL` env vars if Ollama runs elsewhere.

### Running the Project

```bash
cd C:\Projects\rpg
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
pytest                          # run all tests
ruff check . && ruff format --check .  # lint
python -m bot                   # start the Telegram bot
```

---

## Phase 10: Combat Loop

**Package:** `server/combat/` (new). Create `server/combat/__init__.py`.

### Task 1: Define combat entry and exit conditions

**File:** `server/combat/conditions.py`

Create a `CombatConditionEngine` (stateless, no `__init__` state):

```
CombatEntryResult:
    entered: bool
    reason: str

CombatExitResult:
    exited: bool
    exit_type: str  # "victory" | "flee" | "truce" | "annihilation"
    reason: str

CombatConditionEngine:
    check_entry(scene, monster_groups, characters) → CombatEntryResult
    check_exit(scene, monster_groups, characters) → CombatExitResult
```

**Entry logic:** Combat begins when any MonsterGroup has `awareness_state == AwarenessState.engaged`. If no groups are engaged, `entered=False`.

**Exit logic:**
- "victory": all MonsterGroups have `count == 0` (defeated).
- "flee": all remaining MonsterGroups have `morale_state == "routed"`.
- "annihilation": all Characters have `is_alive == False`.
- "truce": (future — return False for now; needs explicit flag).
- If none met, `exited=False`.

### Task 2: Implement attack, move, defend, assist, use item, and ability actions

**File:** `server/combat/actions.py`

Result types per action:

```
AttackResult:    hit: bool, damage_dealt: int, target_id: str, target_new_health: str, status_effects_applied: list[str]
DefendResult:    character: Character (with "defended" in status_effects), armor_bonus: int
AssistResult:    success: bool, target_id: str, effect: str (e.g. "heal", "buff")
UseItemResult:   success: bool, item_id: str, effect: str, rejection_reason: str
UseAbilityResult: success: bool, ability_id: str, effect: str, rejection_reason: str
CombatMoveResult: success: bool, character: Character, from_scene_id: str, to_scene_id: str, rejection_reason: str
```

`CombatActionEngine` methods:

- `resolve_attack(attacker: Character, target_id: str, target_groups: list[MonsterGroup], target_characters: list[Character]) → AttackResult`
  - Damage formula: `attacker.stats.get("attack", 5) - target_defense`. Clamp at 0.
  - Target defense: look up `stats.get("defense", 0)` for Characters, or use a base defense (e.g. 2) for MonsterGroups.
  - Apply damage to Character HP or reduce MonsterGroup count.
  - Return result with updated health state.

- `resolve_defend(character: Character) → DefendResult`
  - Add `"defended"` to `character.status_effects` (grants +3 armor bonus until next turn).

- `resolve_assist(character: Character, target_id: str, allies: list[Character]) → AssistResult`
  - Heal: if target has `stats["hp"] < stats["max_hp"]`, restore min(5, max_hp - hp).
  - Buff: if target at full HP, add `"assisted"` status effect (future use).

- `resolve_use_item(character: Character, item: InventoryItem) → UseItemResult`
  - Check item exists. Apply effect from `item.properties` (e.g. `{"effect": "heal", "amount": 10}`). Reduce quantity.

- `resolve_use_ability(character: Character, ability_id: str) → UseAbilityResult`
  - Placeholder: return success=True with ability_id echoed. Abilities are content-defined in later phases.

- `resolve_combat_move(character: Character, scene: Scene, destination: Scene) → CombatMoveResult`
  - Reuse exploration movement validation. Moving during combat is allowed but the character loses their attack action.

**Key:** All outcomes are deterministic. No randomness. Server is referee authority.

### Task 3: Implement grouped monster encounter behavior

**File:** `server/combat/monsters.py`

```
MonsterActionDecision:
    monster_group_id: str
    action_type: str  # "attack" | "defend" | "flee" | "call_help" | "idle"
    target_player_id: str
    reason: str

MonsterBehaviorEngine:
    decide_action(group: MonsterGroup, characters: list[Character]) → MonsterActionDecision
    update_threat(group: MonsterGroup, player_id: str, delta: int) → MonsterGroup
    update_awareness(group: MonsterGroup, new_state: AwarenessState) → MonsterGroup
```

**`decide_action` dispatch on `group.behavior_mode`:**
- `patrol`/`guard`: attack highest-threat target in `threat_table` (if engaged).
- `ambush`: same as patrol but tag first-round bonus (check `"ambush_used"` in `special_rules`).
- `defend`: attack only if targets are in same scene as `territory_id`. Never pursue.
- `pursue`: attack highest-threat. If target leaves scene, follow (return action_type="pursue").
- `flee`: disengage. If `morale_state == "routed"`, always flee.
- `call_help`: set self to idle and return action_type="call_help" (caller applies awareness to adjacent groups).
- `idle`: do nothing.

**Target selection:** pick player_id with highest `threat_table[player_id]`. Fallback to first alive character if threat_table is empty.

**Threat updates:** +10 for attacking the group, +5 for assisting against them, -5 per turn of not targeting them (clamp at 0).

### Task 4: Implement damage, armor, status effects, and defeat states

**File:** `server/combat/resolution.py`

```
DamageResult:
    raw_damage: int, armor_reduction: int, final_damage: int
    new_hp: int, is_defeated: bool
    status_effects_applied: list[str]

CombatResolutionEngine:
    apply_damage_to_character(character: Character, raw_damage: int) → tuple[Character, DamageResult]
    apply_damage_to_group(group: MonsterGroup, damage: int, original_count: int) → tuple[MonsterGroup, DamageResult]
    apply_status_effect(character: Character, effect: str) → Character
    remove_status_effect(character: Character, effect: str) → Character
    process_status_effects(character: Character) → tuple[Character, list[str]]  # returns effects that fired
    check_defeat(character: Character) → bool
```

**Character damage:** `armor = stats.get("defense", 0)`. If `"defended"` in `status_effects`, add 3. `final_damage = max(0, raw_damage - armor)`. `new_hp = stats["hp"] - final_damage`. If `new_hp <= 0`, set `is_alive = False`.

**MonsterGroup damage:** Each hit reduces count by 1 when cumulative damage exceeds a threshold (use `count * 5` as total HP pool, or keep it simple: each hit of damage >= 3 kills one unit). Update `health_state`: count > 50% original → "healthy", > 25% → "injured", > 0 → "critical", 0 → "dead".

**Status effects:**
- `"poisoned"`: deal 1 damage at start of turn via `process_status_effects`.
- `"stunned"`: skip action (checked by action engine, not resolution).
- `"blinded"`: attacks deal 0 damage (checked by action engine).
- `"defended"`: armor bonus +3, removed at end of turn.

### Task 5: Implement morale and flee behavior

**Add to `server/combat/monsters.py`:**

```
MoraleEngine:
    check_morale(group: MonsterGroup, original_count: int) → MonsterGroup
    apply_flee(group: MonsterGroup, scene: Scene) → tuple[MonsterGroup, Scene]
```

**Morale transitions:**
- `"steady"` → `"shaken"` when `count <= original_count * 0.5`.
- `"shaken"` → `"routed"` when `count <= original_count * 0.25` OR `"leader_dead"` in `special_rules`.
- `"routed"` forces `behavior_mode = BehaviorMode.flee`.

**Flee:** Remove group from `scene.monster_group_ids`. Set `group.is_visible = False`.

### Task 6: Implement combat visibility and awareness rules

**File:** `server/combat/visibility.py`

```
CombatVisibilityResult:
    visible_groups: list[MonsterGroup]
    hidden_groups: list[MonsterGroup]

CombatVisibilityEngine:
    compute_visibility(groups: list[MonsterGroup]) → CombatVisibilityResult
    transition_awareness(group: MonsterGroup, event: str) → MonsterGroup
```

**Awareness transitions:**
- `unaware` → `alert`: on event "noise" or "nearby_combat".
- `alert` → `aware`: on event "spotted" or "searched".
- `aware` → `engaged`: on event "attacked" or "entered_territory".
- `engaged` → `aware`: on event "truce" or "flee_success".

**Visibility rule:** `is_visible = True` when `awareness_state` in {`aware`, `engaged`}. Players cannot target groups with `is_visible == False`.

### Task 7: Implement battlefield summaries for public turn posts

**File:** `server/combat/summaries.py`

```
BattlefieldSummary:
    round_number: int
    combatant_lines: list[str]  # one per combatant: "Kira — 15/20 HP — [poisoned]"
    event_lines: list[str]      # one per action result: "Kira attacks Goblin Patrol — 5 damage"
    status_line: str            # "Combat ongoing" | "Victory!" | etc.

BattlefieldSummaryBuilder:
    build(characters, groups, turn_number, action_results) → BattlefieldSummary
```

This is pure text assembly. Each character line: `"{name} — {hp}/{max_hp} HP{' — [' + ', '.join(effects) + ']' if effects else ''}"`. Each monster line: `"{unit_type} (x{count}) — {health_state}{' — ' + morale_state if morale != 'steady' else ''}"`. This feeds into the main model's `combat_summary` prompt context.

### Task 8: Starter combat content

**File:** `tests/fixtures/combat_scenario.py`

Fixed IDs and builder functions following `tests/fixtures/exploration_scenario.py` pattern:

- `make_forest_clearing()` → Scene with two players, one goblin patrol.
- `make_kira()`, `make_dain()` → Characters with stats `{"hp": 20, "max_hp": 20, "attack": 8, "defense": 3}`.
- `make_goblin_patrol()` → MonsterGroup: `count=3`, `behavior_mode=patrol`, `morale_state="steady"`, `awareness_state=engaged` (combat-ready).
- `make_wolf_pack()` → MonsterGroup for variety: `count=4`, `behavior_mode=ambush`.

### Task 9: Tests

**File:** `tests/unit/test_combat.py`

Target ~80 tests covering:

- **Entry/exit conditions:** engaged groups → entry; all dead → victory; all characters dead → annihilation; all routed → flee; no engaged → no entry.
- **Attack:** damage = attack - defense (clamped at 0); defended bonus applies; attack against invisible group rejected.
- **Defend:** adds "defended" status effect; armor bonus of 3.
- **Assist:** heal restores HP up to max; buff at full HP.
- **Use item:** valid item applies effect; missing item rejected.
- **Morale:** count at 50% → shaken; 25% → routed; routed forces flee behavior.
- **Monster AI:** highest-threat target selected; empty threat table → first alive character; patrol vs ambush vs defend behavior.
- **Status effects:** poisoned ticks 1/turn; stunned skips action; defended expires; blinded zeroes damage.
- **Visibility:** unaware/alert → hidden; aware/engaged → visible; transition events fire correctly.
- **Battlefield summary:** correct combatant lines; correct event lines.
- **Full scenario:** goblin patrol encounter from starter content: entry → attack round → morale check → exit.

---

## Phase 11: Side-Channels and Private Coordination

Most of the infrastructure already exists in `server/scope/side_channel.py` (SideChannelPolicy) and `server/scope/engine.py` (ScopeEngine handles side_channel scope type). This phase adds lifecycle management, DM relay, and audit.

### Task 1: Define side-channel lifecycle and membership rules

**Modify:** `server/scope/side_channel.py`

Add methods to `SideChannelPolicy`:

```
add_member(channel, player_id, all_campaign_player_ids) → SideChannel
    # Validate player is in campaign and not already a member. Mutate and return.

remove_member(channel, player_id) → SideChannel
    # Remove player. If member count < MIN_MEMBERS (2), auto-close channel.

can_create(creator_id, campaign_player_ids, existing_channels, max_per_player=5) → bool
    # Check creator hasn't exceeded active channel limit.
```

### Task 2: Implement side-channel creation and closure

**File:** `server/scope/side_channel_engine.py` (new)

```
SideChannelCreateResult:
    success: bool, channel: SideChannel | None, scope: ConversationScope | None, rejection_reason: str

SideChannelCloseResult:
    success: bool, channel: SideChannel | None, audit_fact: KnowledgeFact | None, reason: str

SideChannelEngine:
    create_channel(creator_player_id, member_player_ids, campaign_id, all_campaign_player_ids, label) → SideChannelCreateResult
        # Delegates validation to SideChannelPolicy.validate_creation
        # Creates SideChannel entity + ConversationScope(scope_type=side_channel, side_channel_id=...)
        # Returns both in result

    close_channel(channel, closing_player_id, campaign_id, scene_id) → SideChannelCloseResult
        # Validates closer is a member
        # Calls SideChannelPolicy.close_channel
        # Produces referee-only audit KnowledgeFact
```

### Task 3: Implement DM-relay delivery for side-channel messages

**Modify:** `bot/outbound.py`

Add function:

```python
async def send_side_channel(
    bot: Bot, registry: BotRegistry, channel: SideChannel,
    sender_player_id: str, text: str,
    sender_display_name: str = "",
    parse_mode: str = ParseMode.HTML,
) -> list[str]:
```

Iterates `channel.member_player_ids`, looks up each player's telegram_user_id via the registry's reverse map (same pattern as `send_private_by_player_id`), sends a DM to each member with the format: `"[{channel.label}] {sender_display_name}: {text}"`. Returns list of player_ids that received the message successfully. Skips the sender themselves.

### Task 4: Implement visibility isolation for side-channel content

**Existing code already handles this.** The ScopeEngine's `can_player_see_fact()` checks `side_channel.member_player_ids` for side_channel scoped facts. `assemble_public_context()` raises `ScopeViolationError` for non-public facts.

**Add one guardrail** to `server/scope/engine.py`:

```python
def assert_no_side_channel_leakage(
    self, facts, scopes_by_id, target_player_id, side_channels_by_id
) -> None:
    # Raise ScopeViolationError if any side_channel fact would be delivered
    # to a player who is NOT a member of that channel.
```

This is called before any prompt assembly that includes side-channel scoped facts, as a pre-flight check.

### Task 5: Implement audit entries for side-channel activity

**File:** `server/scope/side_channel_audit.py` (new)

```
SideChannelAuditor:
    record_creation(channel, campaign_id, scene_id) → KnowledgeFact
        # fact_type=custom, payload="[side_channel_audit] Created channel '{label}' with members: ..."
        # owner_scope_id = referee_only scope

    record_message(channel, sender_player_id, campaign_id, scene_id) → KnowledgeFact
        # fact_type=custom, payload="[side_channel_audit] Message sent in '{label}' by {sender}"

    record_closure(channel, closer_player_id, campaign_id, scene_id) → KnowledgeFact
        # fact_type=custom, payload="[side_channel_audit] Channel '{label}' closed by {closer}"
```

All audit facts use `scope_type=referee_only` so they never reach players or the LLM.

### Task 6: Tests

**File:** `tests/unit/test_side_channels.py` (new)

Target ~50 tests:

- **Creation:** valid 2+ members succeeds; 1 member rejected; non-campaign player rejected; scope created with correct type.
- **Membership:** add member works; add duplicate rejected; remove member works; auto-close on < 2 members.
- **Delivery:** `send_side_channel` sends to all members except sender; closed channel delivers nothing.
- **Visibility isolation:** non-member cannot see side_channel facts; `assert_no_side_channel_leakage` raises for non-member.
- **Public isolation:** side_channel facts in `assemble_public_context` → ScopeViolationError.
- **Audit:** creation/message/closure each produce referee-only KnowledgeFact with correct payload prefix.
- **Lifecycle:** create → send messages → close → verify closed channel cannot receive.

---

## Phase 12: Split Party and Multi-Scene Handling

**Package:** `server/scene/` (new). Create `server/scene/__init__.py`.

### Task 1: Implement explicit scene membership for players and NPCs

**File:** `server/scene/membership.py`

```
MembershipChangeResult:
    success: bool, scene: Scene, character: Character | None, npc: NPC | None, reason: str

SceneMembershipEngine:
    add_character(scene, character) → MembershipChangeResult
        # Add character.character_id to scene.character_ids and character.player_id to scene.player_ids
        # Set character.scene_id = scene.scene_id
        # Reject if already in this scene

    remove_character(scene, character) → MembershipChangeResult
        # Remove from scene lists, set character.scene_id = None
        # Reject if not in this scene

    add_npc(scene, npc) → MembershipChangeResult
        # Add npc.npc_id to scene.npc_ids, set npc.scene_id = scene.scene_id

    remove_npc(scene, npc) → MembershipChangeResult
        # Remove from scene.npc_ids, set npc.scene_id = None

    transfer_character(from_scene, to_scene, character) → MembershipChangeResult
        # remove_character from source + add_character to target in one call

    get_scene_characters(scene, all_characters) → list[Character]
        # Filter all_characters by scene.character_ids

    get_scene_npcs(scene, all_npcs) → list[NPC]
        # Filter all_npcs by scene.npc_ids
```

### Task 2: Implement multiple active scene contexts in a campaign

**File:** `server/scene/multi_scene.py`

```
ActiveSceneSet:
    campaign_id: str
    scenes: list[Scene]
    turn_windows: dict[str, TurnWindow]  # scene_id → active TurnWindow (if any)

MultiSceneEngine:
    get_active_scenes(all_scenes: list[Scene]) → list[Scene]
        # Return scenes where state is not idle/paused AND player_ids is non-empty

    build_active_set(campaign_id, all_scenes, all_turn_windows) → ActiveSceneSet
        # Collects active scenes and maps each to its active_turn_window_id

    activate_scene(scene) → Scene
        # Set scene.state to awaiting_actions if currently idle

    deactivate_scene(scene) → Scene
        # Set scene.state to idle, clear active_turn_window_id
```

Multiple scenes can be active simultaneously. Each has its own TurnWindow lifecycle.

### Task 3: Implement scoped prompts by subgroup

**File:** `server/scene/scoped_prompts.py`

```
SubgroupPromptContext:
    scene: Scene
    characters: list[Character]
    player_ids: list[str]
    public_facts: list[KnowledgeFact]
    scene_npcs: list[NPC]
    scene_monster_groups: list[MonsterGroup]

SubgroupPromptEngine:
    assemble_subgroup_context(
        scene, all_characters, all_facts, scopes_by_id,
        all_npcs, all_monster_groups
    ) → SubgroupPromptContext
        # Filter everything by scene membership
        # Only include facts where fact.scene_id matches

    filter_facts_for_scene(scene_id, facts) → list[KnowledgeFact]
        # Simple filter on fact.scene_id
```

Each active scene gets its own narration prompt. Cross-scene facts are excluded from prompts.

### Task 4: Implement coordinated timing policy for split-party play

**File:** `server/scene/timing.py`

```
SplitPartyTimingPolicy:
    INDEPENDENT = "independent"   # each scene resolves on its own timer
    SYNCHRONIZED = "synchronized" # all scenes wait for the slowest

    __init__(sync_mode="independent")

    should_resolve_scene(
        scene_id, active_set: ActiveSceneSet,
        actions_by_scene: dict[str, list[CommittedAction]],
        players_by_scene: dict[str, list[str]]
    ) → bool
        # Independent: True if this scene's players have all submitted/timed out
        # Synchronized: True only if ALL active scenes' players are ready

    all_scenes_ready(active_set, actions_by_scene, players_by_scene) → bool
        # True when every scene has all expected players submitted or timed out
```

Default is independent mode — scenes resolve at their own pace.

### Task 5: Implement delayed information propagation between subgroups

**File:** `server/scene/propagation.py`

```
PropagationEvent:
    event_id: str
    fact: KnowledgeFact
    source_scene_id: str
    target_scene_id: str
    delay_turns: int
    queued_at_turn: int
    delivered: bool = False

InformationPropagationEngine:
    queue_propagation(fact, source_scene_id, target_scene_id,
                      delay_turns, current_turn) → PropagationEvent

    check_deliverable(events, current_turn) → list[PropagationEvent]
        # Return events where current_turn >= queued_at_turn + delay_turns and not delivered

    deliver(event, target_scope_id) → tuple[PropagationEvent, KnowledgeFact]
        # Mark event.delivered = True
        # Create new KnowledgeFact in target scene with target scope
        # Payload prefixed with "[delayed] " or similar
```

Use cases: "You hear sounds of distant battle" (1 turn delay), "A messenger arrives" (3 turn delay).

### Task 6: Split-party scenario and tests

**File:** `tests/fixtures/split_party_scenario.py`

Two-scene scenario:
- `SCENE_CAVE`: Alara + Bren (exploring a cave)
- `SCENE_VILLAGE`: Corwin (gathering supplies in village)
- Each scene has its own TurnWindow

**File:** `tests/unit/test_split_party.py`

Target ~60 tests:

- **Membership:** add/remove character updates both scene and character; transfer between scenes works; duplicate add rejected.
- **Multi-scene:** two active scenes coexist; each has own TurnWindow; deactivate one doesn't affect other.
- **Prompt isolation:** cave context has only cave characters/facts; village context has only village content.
- **Independent timing:** cave resolves when cave players ready, even if village isn't.
- **Synchronized timing:** neither resolves until both scenes' players are ready.
- **Propagation:** queue event → not deliverable before delay → deliverable after delay → deliver creates new fact in target scene.
- **Propagation edge cases:** already-delivered event not re-delivered; zero-delay delivered immediately.
- **Rejoin:** character transfers from cave to village → scene memberships correct → sees village facts only.

---

## Verification

After each phase:
1. `pytest` — all tests pass.
2. `ruff check . && ruff format --check .` — lint clean.
3. Review test count growth (currently 435+; expect ~550 after Phase 10, ~600 after 11, ~660 after 12).
4. One commit per phase, never push without explicit authorization.
