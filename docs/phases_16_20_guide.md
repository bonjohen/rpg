# Phases 16-20 Implementation Plan + Detailed Guide

## Context

Phases 1-15 built the complete backend: domain model, turn engine, bot gateway, scope enforcement, timer, fast/main model routing, exploration/social/combat loops, side-channels, split-party, scenario authoring, prompt contracts, and reliability/observability. Total: 1078 tests across 18 test files.

Phases 16-20 move from backend to integration and frontend: playtest validation, Mini App foundation, Mini App gameplay utilities, content expansion, and pre-release stabilization. These phases shift from pure-domain Python to include HTML/JS/CSS for the Mini App (Phases 17-18), end-to-end integration (Phase 16), and polish (Phases 19-20).

---

## Phase 16: Internal Playtest Release

**Goal:** Wire everything together into a runnable end-to-end system, run a structured playtest against the goblin_caves scenario, capture defects, patch the worst ones, and add regression tests. This is the first time the system runs as a complete loop — bot receives messages, server resolves turns, models generate narration, bot delivers results.

**Package:** New `server/orchestrator/` for the top-level game loop. Extend `bot/` with new commands. No new top-level packages.

### Task 1: Prepare internal playtest build locally

**File:** `server/orchestrator/__init__.py`, `server/orchestrator/game_loop.py`

Create the orchestrator that wires all subsystems together into a running game:

```
GameOrchestrator:
    """Top-level coordinator that connects bot gateway, turn engine, model adapters,
    scope engine, timer, and all game loop subsystems into a single runnable loop."""

    __init__(
        fast_adapter: OllamaFastAdapter,
        main_adapter: OllamaMainAdapter,
        bot_registry: BotRegistry,
        config: BotConfig,
    )

    # State (in-memory for playtest; persistent later)
    campaign: Campaign | None
    scenes: dict[str, Scene]
    characters: dict[str, Character]
    players: dict[str, Player]
    npcs: dict[str, NPC]
    monster_groups: dict[str, MonsterGroup]
    items: dict[str, InventoryItem]
    puzzles: dict[str, PuzzleState]
    quests: dict[str, QuestState]
    knowledge_facts: dict[str, KnowledgeFact]
    scopes: dict[str, ConversationScope]
    triggers: list[TriggerDefinition]
    turn_windows: dict[str, TurnWindow]
    committed_actions: dict[str, CommittedAction]
    turn_log: list[TurnLogEntry]
    metrics: MetricsCollector
    idempotency: IdempotencyStore

    # Core engines (instantiated in __init__)
    turn_engine: TurnEngine
    scope_engine: ScopeEngine
    movement_engine: MovementEngine
    exploration_engine: ExplorationEngine
    trigger_engine: TriggerEngine
    combat_condition_engine: CombatConditionEngine
    social_engine: SocialEngine
    trust_engine: TrustEngine
    timer_controller: TimerController
    diagnostics_engine: DiagnosticsEngine
    context_assembler: ContextAssembler
    repair_pipeline: RepairPipeline
    scenario_loader: ScenarioLoader

    async def load_scenario(self, yaml_path: str) -> bool
        # Load a scenario via ScenarioLoader, populate all state dicts.
        # Return True on success.

    async def handle_player_message(self, player_id: str, text: str, is_private: bool) -> None
        # 1. Check idempotency
        # 2. Classify intent via fast model (classify_intent)
        # 3. If action: extract action packet, validate, submit to active turn window
        # 4. If question: route to private-referee handling
        # 5. If command: delegate to command handler
        # 6. If chat: log but don't process

    async def open_turn(self, scene_id: str, duration_seconds: int = 90) -> TurnWindow
        # Create a new TurnWindow for the scene, post situation to public chat,
        # deliver private facts, start timer.

    async def resolve_turn(self, turn_window_id: str) -> TurnLogEntry
        # 1. Lock the turn window
        # 2. Synthesize fallback actions for missing players
        # 3. Resolve all actions through appropriate engines
        #    (movement, exploration, combat, social based on scene state)
        # 4. Generate narration via main model
        # 5. Commit the turn, append to log
        # 6. Deliver narration to appropriate scopes
        # 7. Open next turn if scene continues

    async def run_timer_tick(self) -> None
        # Check all active timers. If any expired, trigger resolve_turn.
        # If all players ready, trigger early close.

    def get_player_scene(self, player_id: str) -> Scene | None
        # Look up which scene a player's character is in.

    def get_scene_players(self, scene_id: str) -> list[Player]
        # Return all players whose characters are in this scene.
```

**File:** `server/orchestrator/message_dispatcher.py`

```
MessageDispatcher:
    """Routes incoming player messages through the fast model pipeline
    and into the appropriate game subsystem."""

    __init__(orchestrator: GameOrchestrator)

    async def dispatch(self, player_id: str, text: str, is_private: bool) -> DispatchResult

DispatchResult:
    handled: bool
    response_text: str          # text to send back (empty if handled silently)
    scope: str                  # "public" | "private"
    action_submitted: bool
    error: str
```

**Integration points — wire into bot handlers:**

Extend `bot/handlers.py` to call the orchestrator when a game message arrives:
- `_handle_group_message`: look up player → call `orchestrator.handle_player_message(player_id, text, is_private=False)`
- `_handle_private_message`: look up player → call `orchestrator.handle_player_message(player_id, text, is_private=True)`

Extend `bot/commands.py` with game-active commands:
- `/newgame <scenario_path>` — load a scenario, create campaign, register the group chat
- `/nextturn` — manually open the next turn (admin/debug)
- `/forceresolve` — force-resolve the current turn window (admin/debug)
- `/diagnostics` — run DiagnosticsEngine.build_report and DM the formatted report to the admin
- `/scene` — show the current scene description and exits to the requesting player
- `/who` — show which players are in which scenes

### Task 2: Select and stage starter scenario for playtest

Use `scenarios/starters/goblin_caves.yaml`. Verify it loads cleanly via the orchestrator:

**File:** `tests/integration/test_playtest_setup.py`

```
test_goblin_caves_loads_into_orchestrator()
    # Create an orchestrator with mock adapters
    # Load goblin_caves.yaml
    # Assert: 4 scenes, 2 NPCs, 2 monster groups, 7 items, all state populated

test_newgame_command_loads_scenario()
    # Simulate /newgame command with the goblin_caves path
    # Assert: campaign created, scenes populated, starting scene is cave_entrance

test_player_join_and_scene_assignment()
    # Simulate 3 players joining via /join
    # Assert: all players assigned to starting scene (cave_entrance)
    # Assert: each player has a character

test_first_turn_opens_correctly()
    # After players join, open a turn
    # Assert: TurnWindow created for cave_entrance
    # Assert: timer started
```

### Task 3: Run structured multiplayer playtest session

**File:** `tests/integration/test_playtest_session.py`

Create a scripted playtest that simulates a multi-turn session through the orchestrator without hitting live Telegram or live models. Use mock adapters that return fixture narration.

```
PlaytestHarness:
    """Drives a scripted playtest session through the orchestrator.
    Uses mock model adapters that return pre-defined responses."""

    __init__()
    orchestrator: GameOrchestrator  # with mock adapters

    async def setup(self) -> None
        # Load goblin_caves, register 3 simulated players

    async def simulate_turn(self, actions: dict[str, str]) -> TurnLogEntry
        # For each player_id → action_text, submit actions
        # Then resolve the turn
        # Return the log entry

    async def run_exploration_sequence(self) -> list[TurnLogEntry]
        # Turn 1: All players move north into cave
        # Turn 2: Player 1 inspects surroundings, Player 2 searches, Player 3 passes
        # Turn 3: Players move into main hall
        # Return all log entries

    async def run_social_sequence(self) -> list[TurnLogEntry]
        # Interact with Grix: Player 1 questions, Player 2 threatens
        # Check trust changes, NPC tell firing

    async def run_combat_sequence(self) -> list[TurnLogEntry]
        # Combat with goblin guards
        # Player 1 attacks, Player 2 defends, Player 3 uses item
```

Write tests that run these sequences and verify:
- Turn log entries produced for each turn
- Scene state changes (player locations update after movement)
- NPC trust changes after social actions
- Combat state changes (damage applied, morale checked)
- Scope enforcement (private facts not in public narration)
- Timer fallback (simulate one player timing out)

Target ~30 tests.

### Task 4: Capture logs, transcripts, and issues

**File:** `tests/integration/test_playtest_logging.py`

```
test_all_turns_logged_with_trace_ids()
    # Run a playtest sequence
    # Assert every turn has a trace_id in logs
    # Assert turn_log is append-only and complete

test_model_calls_instrumented()
    # Run a turn with model calls
    # Assert ModelCallLog entries created for each call
    # Assert latency and token counts recorded

test_delivery_results_tracked()
    # Run a turn and check outbound delivery tracking
    # Assert DeliveryResult objects created for each message sent

test_transcript_reconstruction()
    # From turn_log entries, reconstruct a readable transcript
    # Assert transcript contains scene narrations in order
    # Assert no gaps in turn numbering
```

### Task 5: Categorize defects by timing, clarity, leakage, routing, and rules

This is an analysis task. Create a defect tracker document:

**File:** `docs/playtest_findings.md`

```markdown
# Playtest Findings

## Defect Categories

| Category | Description | Severity |
|---|---|---|
| Timing | Turn timer, early-close, timeout fallback issues | P1 |
| Clarity | Narration quality, confusing output | P2 |
| Leakage | Private facts appearing in public output | P0 |
| Routing | Wrong model tier selected, routing errors | P2 |
| Rules | Incorrect resolution, state machine violations | P1 |

## Findings

(Populated during playtest execution. Each finding gets an ID, category,
description, steps to reproduce, and severity.)
```

Write validation tests that check for each defect category:

**File:** `tests/integration/test_defect_categories.py`

```
# Timing defects
test_timeout_fallback_applied_when_player_missing()
test_early_close_triggers_when_all_ready()
test_late_submission_rejected_after_lock()

# Leakage defects
test_referee_notes_not_in_public_narration_prompt()
test_hidden_exit_not_in_scene_description()
test_npc_private_tell_not_in_public_output()
test_side_channel_facts_not_in_other_scope()

# Routing defects
test_action_classified_before_submission()
test_narration_uses_main_model_not_fast()

# Rules defects
test_movement_blocked_by_locked_exit()
test_combat_entry_conditions_checked()
test_one_action_per_player_per_turn_enforced()
```

Target ~15 tests.

### Task 6: Patch highest-severity issues found in playtest

This task is reactive — fix issues discovered during the scripted playtest. Common anticipated patches:

- **Orchestrator wiring bugs:** Missing connections between subsystems that only surface in integration.
- **Scope leakage in assembled prompts:** Context assembler passing referee facts to public narration. Fix in `models/contracts/context_assembly.py`.
- **Timer edge cases:** All-ready check not firing when some actions are fallback-synthesized. Fix in `server/timer/integration.py`.
- **Action submission flow:** Fast model intent classification returning wrong type for edge-case player messages. Add more deterministic fallback handling.

For each patch, the fix goes in the source file where the bug lives. No new files expected — this is a bug-fix task.

### Task 7: Add regression tests for discovered failures

For each bug patched in Task 6, add a focused regression test in the most specific layer:

- Unit-level bugs → `tests/unit/test_<module>.py`
- Integration-level bugs → `tests/integration/test_playtest_*.py`

Target ~10 regression tests (depends on bugs found).

### Task 8: Update architecture, prompts, and phase notes from findings

Update:
- `docs/architecture.md` — add orchestrator layer to the system diagram
- `docs/playtest_findings.md` — finalize findings and resolutions
- `STARTUP.md` — advance to Phase 17
- `docs/phase_status.md` — mark Phase 16 complete

---

## Phase 17: Mini App Foundation

**Goal:** Build a Telegram Mini App shell that players can open from the bot to view read-only game state: character sheet, inventory, and turn recap. The Mini App is a lightweight web application served locally and launched from Telegram inline buttons.

**Package:** New `webapp/` top-level directory for the Mini App. New `server/api/` for the HTTP API that the Mini App consumes.

### Task 1: Define Mini App architecture and launch flow

**File:** `docs/miniapp_architecture.md`

Document the Mini App design:

```markdown
# Mini App Architecture

## Overview

The Mini App is a single-page web application served by a local HTTP server.
Telegram's WebApp API provides the launch context (user identity, theme,
viewport size). The Mini App communicates with the game server via a REST API.

## Technology Stack

| Concern | Choice | Rationale |
|---|---|---|
| HTTP server | FastAPI | Lightweight, async, serves both API and static files |
| Frontend | Vanilla HTML/CSS/JS | No build step, minimal dependencies, Telegram WebApp SDK compatible |
| Auth | Telegram WebApp.initData | Validates user identity via HMAC; no separate auth system needed |
| Styling | CSS custom properties | Inherits Telegram theme colors via WebApp API |

## Launch Flow

1. Player taps an inline button in Telegram (e.g. "Open Sheet" on turn-control message)
2. Telegram opens the Mini App URL as a WebApp overlay
3. Mini App loads, reads `Telegram.WebApp.initData` for user identity
4. Mini App calls the game server API to fetch state
5. Mini App renders the requested view (sheet, inventory, recap)

## URL Scheme

| URL | View |
|---|---|
| /app/ | Main menu (links to all views) |
| /app/sheet | Character sheet |
| /app/inventory | Inventory |
| /app/recap | Turn recap |
| /app/quest-log | Quest log (Phase 18) |
| /app/inbox | Private inbox (Phase 18) |
| /app/action | Action builder (Phase 18) |

## API Endpoints (served by FastAPI)

| Method | Path | Purpose |
|---|---|---|
| GET | /api/player/{player_id} | Player info + character |
| GET | /api/character/{character_id} | Full character sheet |
| GET | /api/character/{character_id}/inventory | Character's items |
| GET | /api/scene/{scene_id} | Current scene state |
| GET | /api/campaign/{campaign_id}/recap | Recent turn log entries |
| POST | /api/auth/validate | Validate Telegram initData |
```

### Task 2: Implement Telegram-linked Mini App shell

**File:** `server/api/__init__.py`, `server/api/app.py`

```
create_api_app(orchestrator: GameOrchestrator) -> FastAPI
    # Create a FastAPI app with:
    # - CORS middleware (allow Telegram WebApp origin)
    # - Static file mount at /app/ serving webapp/ directory
    # - API routes under /api/
    # - Orchestrator dependency injection

@router.post("/api/auth/validate")
async def validate_auth(init_data: str, bot_token: str) -> AuthResult
    # Validate Telegram WebApp initData using HMAC-SHA256
    # Extract user_id, first_name, etc.
    # Return AuthResult with player_id mapping

AuthResult:
    valid: bool
    player_id: str
    display_name: str
    error: str
```

**File:** `server/api/routes.py`

```
# Player routes
@router.get("/api/player/{player_id}")
async def get_player(player_id: str) -> PlayerResponse

# Character routes
@router.get("/api/character/{character_id}")
async def get_character(character_id: str) -> CharacterResponse

# Inventory routes
@router.get("/api/character/{character_id}/inventory")
async def get_inventory(character_id: str) -> InventoryResponse

# Scene routes
@router.get("/api/scene/{scene_id}")
async def get_scene(scene_id: str) -> SceneResponse

# Recap routes
@router.get("/api/campaign/{campaign_id}/recap")
async def get_recap(campaign_id: str, limit: int = 10) -> RecapResponse
```

**Response dataclasses:**

```
PlayerResponse:
    player_id: str
    display_name: str
    character_id: str
    current_scene_id: str
    is_active: bool

CharacterResponse:
    character_id: str
    name: str
    stats: dict
    status_effects: list[str]
    is_alive: bool
    scene_id: str

InventoryResponse:
    character_id: str
    items: list[ItemResponse]

ItemResponse:
    item_id: str
    name: str
    description: str
    quantity: int
    properties: dict

SceneResponse:
    scene_id: str
    name: str
    description: str
    exits: dict[str, str]
    players_present: list[str]
    npcs_present: list[str]

RecapResponse:
    campaign_id: str
    entries: list[RecapEntry]

RecapEntry:
    turn_number: int
    scene_name: str
    narration: str
    committed_at: str
```

**File:** `webapp/index.html`

```html
<!-- Mini App shell -->
<!-- Loads Telegram WebApp SDK -->
<!-- Provides navigation to Sheet, Inventory, Recap -->
<!-- Uses Telegram.WebApp.initData for auth -->
<!-- Fetches data from /api/ endpoints -->
<!-- Styled with Telegram theme colors via CSS custom properties -->
```

**File:** `webapp/css/style.css`

```css
/* Telegram theme integration */
:root {
    --tg-bg: var(--tg-theme-bg-color, #ffffff);
    --tg-text: var(--tg-theme-text-color, #000000);
    --tg-hint: var(--tg-theme-hint-color, #999999);
    --tg-link: var(--tg-theme-link-color, #2481cc);
    --tg-button: var(--tg-theme-button-color, #2481cc);
    --tg-button-text: var(--tg-theme-button-text-color, #ffffff);
    --tg-secondary-bg: var(--tg-theme-secondary-bg-color, #f0f0f0);
}

/* Card-based layout for mobile-first display */
/* Stat bars, item cards, narration blocks */
```

**File:** `webapp/js/app.js`

```javascript
// Telegram WebApp SDK initialization
// API client wrapper
// View router (hash-based: #sheet, #inventory, #recap)
// Render functions for each view
```

**Dependency:** Add `fastapi>=0.100` and `uvicorn>=0.20` to `requirements.txt`.

### Task 3: Implement read-only character sheet view

**File:** `webapp/js/views/sheet.js`

```javascript
async function renderSheet(characterId) {
    // GET /api/character/{characterId}
    // Display: name, stats (as labeled bars or key-value pairs),
    //          status effects (as colored tags),
    //          alive/dead status, current scene name
    // Use Telegram theme colors
    // Mobile-friendly layout (single column, large touch targets)
}
```

**API backing:** `GET /api/character/{character_id}` returns CharacterResponse.

The sheet view should display:
- Character name as header
- Stats as a key-value grid (generic, since stats are a flexible dict)
- Status effects as colored pill tags
- Current scene name as a subtitle
- Health status indicator

### Task 4: Implement read-only inventory view

**File:** `webapp/js/views/inventory.js`

```javascript
async function renderInventory(characterId) {
    // GET /api/character/{characterId}/inventory
    // Display: list of ItemResponse cards
    //   Each card: item name, description, quantity, properties
    // Empty state: "No items" message
    // Group by: equipped vs. carried (if applicable from properties)
}
```

**API backing:** `GET /api/character/{character_id}/inventory` returns InventoryResponse.

Each item card should show:
- Item name (bold)
- Description (secondary text)
- Quantity badge (if > 1)
- Key properties rendered as tags (e.g. "Key", "Quest Item", "Light")

### Task 5: Implement read-only turn recap view

**File:** `webapp/js/views/recap.js`

```javascript
async function renderRecap(campaignId) {
    // GET /api/campaign/{campaignId}/recap?limit=20
    // Display: reverse-chronological list of RecapEntry cards
    //   Each card: turn number, scene name, narration text, timestamp
    // Scrollable list with lazy loading
    // Narration text rendered as styled prose blocks
}
```

**API backing:** `GET /api/campaign/{campaign_id}/recap` returns RecapResponse.

Each recap entry should show:
- Turn number as a badge
- Scene name as subtitle
- Narration text as the main block (preserve paragraph breaks)
- Timestamp in relative format ("5 minutes ago")

### Task 6: Add Mini App state-hydration tests

**File:** `tests/unit/test_api_routes.py`

Test the API layer without running a real server. Use FastAPI's `TestClient`:

```
# Auth
test_validate_auth_with_valid_initdata()
test_validate_auth_with_invalid_initdata()
test_validate_auth_maps_to_player_id()

# Character sheet
test_get_character_returns_full_state()
test_get_character_not_found_returns_404()
test_get_character_includes_status_effects()

# Inventory
test_get_inventory_returns_items()
test_get_inventory_empty_returns_empty_list()
test_get_inventory_includes_properties()

# Scene
test_get_scene_returns_description_and_exits()
test_get_scene_includes_present_players()
test_get_scene_excludes_hidden_description()

# Recap
test_get_recap_returns_recent_entries()
test_get_recap_respects_limit_param()
test_get_recap_ordered_by_turn_number_desc()
test_get_recap_excludes_referee_facts()

# Integration
test_full_hydration_flow()
    # Load scenario, join players, play one turn
    # Then call all API endpoints and verify consistent state
```

Target ~20 tests.

---

## Phase 18: Mini App Gameplay Utilities

**Goal:** Extend the Mini App with interactive gameplay features: draft action builder (compose and submit actions from the Mini App), private inbox (view private-referee messages), side-channel management, quest log, and an optional scene/map view.

**Package:** Extend `webapp/` and `server/api/`. No new top-level packages.

### Task 1: Implement draft action builder

**File:** `webapp/js/views/action.js`

```javascript
async function renderActionBuilder(characterId, sceneId) {
    // Fetch current scene context from API
    // Display action type selector (move, inspect, search, interact, attack, etc.)
    // For "move": show available exits as buttons
    // For "attack": show valid targets (monsters, NPCs)
    // For "use_item": show inventory items as options
    // For "interact": show interactable objects in scene
    // Free-text field for custom actions or public statement
    // Private referee note field (optional)
    // "Submit Action" button → POST /api/action/submit
    // "Save Draft" button → stores locally until submitted
    // Confirm dialog before final submission
}
```

**API endpoints to add:**

**File:** `server/api/routes.py` (extend)

```
@router.get("/api/scene/{scene_id}/context")
async def get_scene_context(scene_id: str) -> SceneContextResponse
    # Returns scene details + available actions + valid targets + interactable objects

@router.post("/api/action/submit")
async def submit_action(action: ActionSubmission) -> ActionSubmitResponse
    # Validates the action via TurnEngine
    # Submits to the active turn window
    # Returns success/rejection

@router.get("/api/action/draft/{player_id}")
async def get_draft(player_id: str) -> DraftResponse
    # Returns the player's current draft (if any) for the active turn window

SceneContextResponse:
    scene_id: str
    scene_name: str
    description: str
    exits: list[ExitInfo]           # direction, target_scene_name, is_locked
    targets: list[TargetInfo]       # id, name, type (npc/monster/player)
    objects: list[ObjectInfo]       # id, name, current_state
    inventory_items: list[ItemInfo] # items the player can use
    active_turn_window_id: str | None

ExitInfo:
    direction: str
    target_scene_name: str
    is_locked: bool

TargetInfo:
    target_id: str
    name: str
    target_type: str                # "npc" | "monster_group" | "player"

ObjectInfo:
    object_id: str
    name: str
    state: str

ActionSubmission:
    player_id: str
    turn_window_id: str
    action_type: str
    target_id: str
    item_id: str
    public_text: str
    private_ref_text: str
    movement_target: str

ActionSubmitResponse:
    accepted: bool
    action_id: str
    rejection_reason: str
```

### Task 2: Implement private inbox view

**File:** `webapp/js/views/inbox.js`

```javascript
async function renderInbox(playerId) {
    // GET /api/player/{playerId}/inbox
    // Display: chronological list of private-referee messages
    //   Each message: fact_type badge, payload text, revealed_at timestamp
    // Unread indicator for facts revealed since last inbox open
    // Filter by fact type (clue, awareness, npc_tell, etc.)
    // Tap to expand full text
}
```

**API endpoint:**

```
@router.get("/api/player/{player_id}/inbox")
async def get_inbox(player_id: str, since: str = "") -> InboxResponse

InboxResponse:
    player_id: str
    messages: list[InboxMessage]
    unread_count: int

InboxMessage:
    fact_id: str
    fact_type: str
    payload: str
    scene_id: str
    scene_name: str
    revealed_at: str
    is_read: bool
```

**Implementation notes:**
- The inbox shows all KnowledgeFacts owned by the player's private-referee scope.
- "Read" state is tracked in-memory on the orchestrator (or via a simple dict mapping fact_id → read timestamp).
- Only facts from scopes where `scope_type == private_referee` and `player_id == requesting_player_id` are returned.
- Side-channel facts are NOT shown here — they have their own view.

### Task 3: Implement side-channel management UI

**File:** `webapp/js/views/channels.js`

```javascript
async function renderChannels(playerId) {
    // GET /api/player/{playerId}/channels
    // Display: list of active side channels the player is a member of
    //   Each channel: label, member names, message count
    // "Create Channel" button → modal to select members from current scene
    // "Leave Channel" button on each channel card
    // Tap channel → view messages in that channel

    // Channel detail view:
    //   Show chronological messages (from SideChannelAuditor facts)
    //   Input field + Send button for new messages
    //   POST /api/channel/{channel_id}/send
}
```

**API endpoints:**

```
@router.get("/api/player/{player_id}/channels")
async def get_channels(player_id: str) -> ChannelListResponse

@router.get("/api/channel/{channel_id}/messages")
async def get_channel_messages(channel_id: str) -> ChannelMessagesResponse

@router.post("/api/channel/create")
async def create_channel(request: CreateChannelRequest) -> CreateChannelResponse

@router.post("/api/channel/{channel_id}/send")
async def send_channel_message(channel_id: str, request: SendMessageRequest) -> SendMessageResponse

@router.post("/api/channel/{channel_id}/leave")
async def leave_channel(channel_id: str, request: LeaveChannelRequest) -> LeaveChannelResponse

ChannelListResponse:
    channels: list[ChannelInfo]

ChannelInfo:
    channel_id: str
    label: str
    members: list[str]          # display names
    message_count: int
    is_open: bool

ChannelMessagesResponse:
    channel_id: str
    messages: list[ChannelMessage]

ChannelMessage:
    sender_name: str
    text: str
    sent_at: str

CreateChannelRequest:
    creator_player_id: str
    member_player_ids: list[str]
    label: str

SendMessageRequest:
    sender_player_id: str
    text: str

LeaveChannelRequest:
    player_id: str
```

### Task 4: Implement quest log and clue journal views

**File:** `webapp/js/views/quests.js`

```javascript
async function renderQuestLog(campaignId, playerId) {
    // GET /api/campaign/{campaignId}/quests
    // Display quests grouped by status: Active, Completed, Failed
    //   Each quest: title, description, objectives with checkmarks
    // Player-specific progress shown if available
}
```

**File:** `webapp/js/views/clues.js`

```javascript
async function renderClueJournal(playerId) {
    // GET /api/player/{playerId}/clues
    // Display: all discovered clues (KnowledgeFacts of type 'clue')
    //   Grouped by scene where discovered
    //   Each clue: payload text, discovery timestamp
    // Only shows facts the player has access to (via scope)
}
```

**API endpoints:**

```
@router.get("/api/campaign/{campaign_id}/quests")
async def get_quests(campaign_id: str) -> QuestListResponse

@router.get("/api/player/{player_id}/clues")
async def get_clues(player_id: str) -> ClueListResponse

QuestListResponse:
    quests: list[QuestInfo]

QuestInfo:
    quest_id: str
    title: str
    description: str
    status: str                     # "inactive" | "active" | "completed" | "failed"
    objectives: list[str]
    player_progress: dict[str, str]

ClueListResponse:
    clues: list[ClueInfo]

ClueInfo:
    fact_id: str
    payload: str
    scene_name: str
    discovered_at: str
```

### Task 5: Implement optional map or scene view

**File:** `webapp/js/views/map.js`

```javascript
async function renderMap(campaignId) {
    // GET /api/campaign/{campaignId}/map
    // Display: graph of discovered scenes as connected nodes
    //   Nodes: scene name, "you are here" indicator
    //   Edges: exits (direction labels)
    //   Undiscovered scenes shown as "?" nodes if connected to a discovered scene
    //   Hidden exits not shown until discovered
    // Rendered as SVG or Canvas (simple node-link diagram)
    // Tap a scene node to see its description
}
```

**API endpoint:**

```
@router.get("/api/campaign/{campaign_id}/map")
async def get_map(campaign_id: str, player_id: str) -> MapResponse

MapResponse:
    nodes: list[MapNode]
    edges: list[MapEdge]
    current_scene_id: str

MapNode:
    scene_id: str
    name: str
    discovered: bool                # False for "?" nodes

MapEdge:
    from_scene_id: str
    to_scene_id: str
    direction: str
    discovered: bool
```

**Implementation notes:**
- Only show scenes the player has visited (from MemoryEngine.scenes_visited_by_character).
- Show exits to undiscovered scenes as "?" nodes (the player knows there's an exit but hasn't been there).
- Hidden exits are excluded until the player has discovered them (via KnowledgeFact of type hidden_object).
- Simple force-directed or grid layout. No complex map rendering library needed — SVG with basic positioning is sufficient.

### Task 6: Add Mini App submission-flow tests

**File:** `tests/unit/test_api_gameplay.py`

```
# Action builder
test_get_scene_context_returns_exits_and_targets()
test_get_scene_context_excludes_hidden_exits()
test_submit_action_accepted()
test_submit_action_rejected_after_lock()
test_submit_action_rejected_duplicate_player()
test_submit_action_validates_action_type()
test_get_draft_returns_current_draft()
test_get_draft_empty_when_no_draft()

# Inbox
test_get_inbox_returns_private_facts_only()
test_get_inbox_excludes_public_facts()
test_get_inbox_excludes_other_player_facts()
test_get_inbox_unread_count()

# Channels
test_get_channels_returns_player_channels()
test_get_channels_excludes_non_member()
test_create_channel_success()
test_create_channel_validates_members()
test_send_channel_message()
test_leave_channel()

# Quests
test_get_quests_grouped_by_status()
test_get_quests_includes_objectives()

# Clues
test_get_clues_returns_player_discoverable_facts()
test_get_clues_grouped_by_scene()

# Map
test_get_map_returns_discovered_scenes()
test_get_map_excludes_unvisited()
test_get_map_shows_adjacent_undiscovered_as_question()
test_get_map_excludes_hidden_exits()
```

Target ~25 tests.

---

## Phase 19: Content Expansion and Quality Pass

**Goal:** Add additional starter scenarios, expand puzzle/trigger patterns, add NPC archetypes and monster templates, improve narration guidance, and expand scenario validation coverage. This phase is about content and quality, not new features.

**Package:** Extend `scenarios/starters/`, extend `scenarios/`, extend `tests/`.

### Task 1: Add additional starter scenarios

Create 2-3 new scenarios that exercise different gameplay patterns:

**File:** `scenarios/starters/haunted_manor.yaml`

A mystery/exploration scenario (3-5 scenes):
- Focus: puzzle-heavy, social investigation, low combat
- Scenes: Manor entrance, Grand hall, Library, Cellar, Hidden study
- NPCs: Ghost of Lady Ashworth (cryptic, helpful if treated respectfully), Butler Graves (suspicious, hiding something)
- Puzzles: Bookshelf cipher (combine clues from multiple rooms), Locked cellar door (key hidden in painting)
- Triggers: Ghost appears on first visit to library, trap in cellar stairs
- Quests: Discover the truth about Lady Ashworth's death, Find the hidden will
- Design goal: Exercise puzzle chaining (puzzle A reveals clue for puzzle B), multi-room clue assembly, NPC trust thresholds for information reveal

**File:** `scenarios/starters/forest_ambush.yaml`

A combat-focused scenario (2-3 scenes):
- Focus: tactical combat, environmental interaction, morale mechanics
- Scenes: Forest trail, Bandit camp clearing, River crossing
- NPCs: Captured traveler (rescue objective), Bandit leader (negotiable if outnumbered)
- Monsters: Bandit scouts (patrol, alert), Bandit main force (guard, leader_dead_routs), Wolves (pursue, territorial)
- Triggers: Ambush trigger on entering clearing, wolf howl on crossing river
- Quests: Rescue the traveler, Retrieve stolen cargo
- Design goal: Exercise combat morale (rout on leader death), multi-group encounters, environmental triggers

**File:** `scenarios/starters/merchant_quarter.yaml`

A social/investigation scenario (3-4 scenes):
- Focus: NPC interaction, trust mechanics, multiple solutions
- Scenes: Market square, Merchant's shop, Thieves' den, City watch post
- NPCs: Merchant Elara (grateful, quest giver), Fence Kel (untrustworthy, has information for a price), Watch Captain Holt (by-the-book, suspicious of adventurers)
- Items: Stolen necklace (quest item), Forged documents (deception tool), Gold coins (bribery)
- Quests: Find the stolen necklace (multiple paths: buy from fence, raid thieves' den, report to watch)
- Design goal: Exercise multiple solution paths, NPC trust/distrust interplay, faction relationships

### Task 2: Add more puzzle patterns and trigger types

**File:** `scenarios/schema.py` (extend if needed)

Add new trigger effect types to handle:

```
# New effect types for triggers (extend TriggerDefinition in schema.py):
# - "spawn_monster": effect_value = monster_id to activate
# - "reveal_exit": effect_value = exit_id to unhide
# - "modify_npc": effect_value = JSON with npc_id + field changes
# - "advance_quest": effect_value = quest_id + new status
# - "chain_trigger": effect_value = trigger_id to fire next
```

**File:** `scenarios/loader.py` (extend `_convert_trigger`)

Handle the new effect types in the trigger converter:
- `spawn_monster`: Add monster group to scene, set awareness to alert
- `reveal_exit`: Add exit to scene's visible exits dict, create KnowledgeFact
- `modify_npc`: Parse JSON, apply field changes to NPC entity
- `advance_quest`: Update QuestState status
- `chain_trigger`: Mark another trigger as ready to fire

**File:** `scenarios/puzzle_patterns.py` (new)

```
PuzzlePattern:
    """Reusable puzzle templates that can be instantiated in scenarios."""

    pattern_id: str
    name: str
    description: str
    required_components: list[str]     # what the scenario must provide
    solution_template: str             # parameterized solution description

# Pre-built patterns:
COMBINATION_LOCK:
    # N items/clues combine to open a lock
    # Components: lock_object_id, clue_item_ids (list), solution_sequence
    # Auto-generates: puzzle with max_attempts, solution_actions from sequence

LEVER_SEQUENCE:
    # N levers must be pulled in order
    # Components: lever_object_ids (list), correct_sequence
    # Auto-generates: puzzle with object state tracking, failure reset

KEY_AND_LOCK:
    # Simple key opens a lock
    # Components: key_item_id, locked_exit_id
    # Auto-generates: puzzle with "use {key} on {lock}" solution

RIDDLE_DOOR:
    # Answer a riddle to proceed
    # Components: riddle_text, answer_text, exit_id
    # Auto-generates: puzzle with text-match solution

MULTI_ROOM_ASSEMBLY:
    # Clues spread across multiple rooms combine to solve
    # Components: room_ids, clue_fact_ids, final_puzzle_id
    # Auto-generates: trigger chain that marks clues as discovered,
    #   puzzle that checks all clues are known
```

### Task 3: Add more NPC archetypes and monster templates

**File:** `scenarios/archetypes.py` (new)

```
NpcArchetype:
    """Reusable NPC personality template."""
    archetype_id: str
    personality_tags: list[str]
    default_goals: list[str]
    dialogue_hints: list[str]
    default_tells: list[NpcTellDefinition]

# Pre-built archetypes:
SUSPICIOUS_MERCHANT:
    personality_tags: [cautious, greedy, deceptive]
    goals: ["maximize profit", "avoid trouble"]
    dialogue_hints: ["speaks evasively", "quotes prices for everything"]
    tells: [trust_below(-20) → "glances at the exit",
            action_type("threaten") → "reaches under the counter"]

LOYAL_GUARD:
    personality_tags: [dutiful, brave, stubborn]
    goals: ["protect their charge", "follow orders"]
    dialogue_hints: ["speaks formally", "references duty and honor"]
    tells: [trust_above(30) → "relaxes stance slightly",
            trust_below(-40) → "hand moves to weapon"]

MYSTERIOUS_SAGE:
    personality_tags: [cryptic, knowledgeable, patient]
    goals: ["share wisdom selectively", "test the worthy"]
    dialogue_hints: ["speaks in metaphor", "asks questions instead of answering"]
    tells: [action_type("question") → "pauses thoughtfully before speaking"]

COWARDLY_MINION:
    personality_tags: [fearful, obedient, chatty_when_scared]
    goals: ["survive", "please the boss"]
    tells: [trust_below(-50) → "trembles and blurts information"]

MonsterTemplate:
    """Reusable monster group configuration."""
    template_id: str
    unit_type: str
    default_behavior_mode: str
    default_awareness_state: str
    default_stats: dict[str, int]
    default_special_rules: list[str]

# Pre-built templates:
GOBLIN_PATROL: {unit_type: goblin, behavior: patrol, awareness: alert, stats: {attack: 4, defense: 1, hp: 5}}
SKELETON_GUARD: {unit_type: skeleton, behavior: guard, awareness: unaware, stats: {attack: 5, defense: 3, hp: 8}, special: [immune_to_morale]}
WOLF_PACK: {unit_type: wolf, behavior: pursue, awareness: aware, stats: {attack: 6, defense: 1, hp: 6}, special: [pack_tactics]}
BANDIT_GROUP: {unit_type: bandit, behavior: ambush, awareness: alert, stats: {attack: 5, defense: 2, hp: 7}, special: [leader_dead_routs]}
SPIDER_SWARM: {unit_type: spider, behavior: ambush, awareness: unaware, stats: {attack: 3, defense: 0, hp: 3}, special: [poison_bite]}
```

### Task 4: Improve narration style guidance and pacing rules

**File:** `models/contracts/main_contracts.py` (extend)

Update the main-tier prompt contracts with improved style guidance:

```
# Add to scene_narration contract system prompt:
NARRATION_STYLE_GUIDE = """
Style rules:
- Use second-person plural ("you") for the party.
- Keep paragraphs to 2-3 sentences maximum.
- Lead with sensory details (sight, sound, smell) before exposition.
- End narration with an implicit prompt for player action.
- Never address players by real name — use character names only.
- Vary sentence structure. Avoid starting consecutive sentences the same way.
- For combat: lead with the most dramatic action, then resolve others concisely.
- For exploration: prioritize spatial orientation, then notable features.
- For social: lead with the NPC's most visible reaction, then dialogue.

Pacing rules:
- Exploration turns: 2-4 sentences of narration.
- Social turns: 1-2 sentences of NPC reaction + 1-3 sentences of dialogue.
- Combat turns: 3-5 sentences covering all combatant actions.
- Discovery moments: Allow 1 extra sentence for atmosphere.
"""

# Add to npc_dialogue contract system prompt:
DIALOGUE_STYLE_GUIDE = """
- Stay in character at all times.
- Reference specific personality tags in your tone and word choice.
- If trust is low, be evasive or hostile as appropriate.
- If trust is high, be more forthcoming but stay in character.
- Never break the fourth wall or reference game mechanics.
- Use dialogue tags sparingly ("says", "replies") — prefer action beats.
- Maximum 3 sentences of dialogue per response.
"""
```

### Task 5: Expand scenario validation coverage

**File:** `scenarios/validator.py` (extend)

Add new validation checks:

```
_check_quest_completability(manifest) -> list[str]
    # Warning if a quest's completion_condition references entities that
    # don't exist or can't be reached from the starting scene.

_check_item_accessibility(manifest) -> list[str]
    # Warning if an item is in a scene that's only reachable through a
    # locked exit, but the key item is also behind that exit.

_check_npc_tell_consistency(manifest) -> list[str]
    # Warning if an NPC has a tell with trigger_type "trust_above"
    # but no way for trust to reach that value (no social actions lead there).

_check_trigger_chain_validity(manifest) -> list[str]
    # Warning if a trigger references another trigger that doesn't exist
    # (for chain_trigger effect type).

_check_scene_connectivity(manifest) -> list[str]
    # Error if any scene is unreachable from starting_scene_id
    # (considering only non-hidden, non-locked exits for base reachability).
```

### Task 6: Add regression cases from long-session transcripts

**File:** `tests/unit/test_scenario_expanded.py`

```
# New scenario validation tests
test_haunted_manor_loads_successfully()
test_forest_ambush_loads_successfully()
test_merchant_quarter_loads_successfully()

test_haunted_manor_puzzle_chain_valid()
test_forest_ambush_combat_groups_valid()
test_merchant_quarter_multiple_quest_paths()

# Puzzle pattern tests
test_combination_lock_pattern()
test_lever_sequence_pattern()
test_key_and_lock_pattern()
test_multi_room_assembly_pattern()

# Archetype tests
test_suspicious_merchant_archetype_valid()
test_loyal_guard_archetype_valid()
test_all_archetypes_produce_valid_npcs()

# Monster template tests
test_goblin_patrol_template()
test_skeleton_guard_template()
test_all_templates_produce_valid_groups()

# Extended validation
test_quest_completability_check()
test_item_accessibility_check()
test_scene_connectivity_check()
test_trigger_chain_validity()

# Long-session regression
test_20_turn_exploration_sequence_state_consistent()
test_trust_accumulation_over_multiple_social_turns()
test_combat_morale_chain_across_encounters()
```

Target ~25 tests.

---

## Phase 20: Pre-Release Stabilization

**Goal:** Final stabilization pass before production use. Review all open bugs, freeze non-essential features, harden error messages, verify privacy/visibility safety, run extended campaign sessions, and patch release blockers.

**Package:** No new packages. Bug fixes and hardening across existing code.

### Task 1: Review open bugs and severity

Review `docs/playtest_findings.md` and any issues discovered during Phases 17-19.

**File:** `docs/release_readiness.md` (new)

```markdown
# Release Readiness Assessment

## Open Bugs

| ID | Severity | Category | Description | Status |
|---|---|---|---|---|
| (populated from findings) |

## Severity Definitions

- P0: Data loss, scope leakage, security issue → must fix before release
- P1: Gameplay-breaking bug → must fix before release
- P2: Quality/polish issue → fix if time permits
- P3: Enhancement → defer to post-release

## Release Criteria

- [ ] All P0 and P1 bugs resolved
- [ ] Full test suite passes (target: 1200+ tests)
- [ ] Lint clean (ruff check + ruff format)
- [ ] All 4 starter scenarios load and validate without errors
- [ ] 10-turn scripted session completes without crashes
- [ ] No scope leakage detected in extended session
- [ ] Admin diagnostics command works
- [ ] Mini App loads and displays data correctly
```

### Task 2: Freeze nonessential feature work

No new features. Only bug fixes and hardening from this point.

Create a freeze marker:

**File:** `docs/feature_freeze.md`

```markdown
# Feature Freeze Notice

**Effective:** [date]
**Scope:** All code in this repository

## Rules

1. No new features, endpoints, views, or data structures.
2. Bug fixes only — each fix must have a regression test.
3. Documentation updates are allowed.
4. Test additions are allowed and encouraged.
5. Performance improvements are allowed if they don't change behavior.

## Exceptions

Any exception requires explicit approval and a justification note here.
```

### Task 3: Harden onboarding, diagnostics, and failure messages

**File:** `bot/commands.py` (extend)

Improve user-facing error messages:

```
# Onboarding
- /start in group: Clear message directing user to DM the bot first
- /join without /start: Clear message explaining the prerequisite
- /join in DM: Clear message explaining /join must be in the group
- /join when already joined: Friendly acknowledgment, no error

# Game commands with no active game
- /scene with no campaign: "No active game. Ask the GM to start one with /newgame."
- /status with no character: "You haven't joined a game yet. Use /join in the campaign group."

# Admin commands
- /diagnostics from non-admin: "This command is admin-only."
- /forceresolve with no active turn: "No turn is currently in progress."

# Model failures
- When narration fallback is used: Smooth deterministic text, not an error message
- When fast model is unreachable: Graceful degradation, not stack traces
```

**File:** `bot/onboarding.py` (extend)

Improve the onboarding flow:

```
ONBOARDING_MESSAGES:
    welcome: "Welcome to the RPG! To join a game, go to the campaign group and type /join."
    already_joined: "You're already in the game! Your character is {name} in {scene}."
    join_success: "You've joined the campaign! Your character will be created shortly."
    dm_required: "Please start a private chat with me first by sending /start in DM."
    no_game: "No game is running in this group yet. Ask the GM to set one up."
```

### Task 4: Review privacy, visibility, and routing safety

**File:** `tests/unit/test_privacy_audit.py` (new)

Comprehensive privacy/visibility audit tests:

```
# Scope boundary tests
test_public_narration_never_contains_referee_facts()
test_public_narration_never_contains_private_player_facts()
test_private_dm_never_contains_other_player_facts()
test_side_channel_messages_only_reach_members()
test_npc_dialogue_prompt_excludes_other_npc_private_facts()

# Context assembly safety
test_context_assembler_strips_referee_facts_for_public()
test_context_assembler_strips_side_channel_facts_for_non_members()
test_leakage_guard_catches_referee_text_in_narration()
test_leakage_guard_catches_solution_hint_in_puzzle_description()

# API safety
test_api_inventory_only_returns_own_items()
test_api_inbox_only_returns_own_facts()
test_api_clues_only_returns_discoverable_facts()
test_api_scene_excludes_hidden_description()
test_api_map_excludes_undiscovered_hidden_exits()

# Routing safety
test_action_extraction_never_reveals_referee_facts()
test_model_prompt_scope_rules_enforced()
test_fallback_narration_contains_no_private_data()

# Edge cases
test_player_who_left_scene_cant_see_new_scene_facts()
test_dead_character_facts_still_scoped_correctly()
test_side_channel_closed_stops_message_delivery()
```

Target ~20 tests.

### Task 5: Run extended campaigns and full regression suite

**File:** `tests/integration/test_extended_session.py`

```
test_20_turn_goblin_caves_full_campaign()
    # Load goblin_caves scenario
    # Simulate 20 turns of play:
    #   Turns 1-3: Exploration (enter cave, explore entrance)
    #   Turns 4-5: Combat (fight goblin scouts)
    #   Turns 6-8: Exploration (navigate to main hall)
    #   Turns 9-10: Social (interact with Grix)
    #   Turns 11-12: Combat (fight goblin guards, or negotiate)
    #   Turns 13-14: Exploration (find prison cells, rescue Aldric)
    #   Turns 15-16: Social (question Aldric about treasury)
    #   Turns 17-18: Exploration (find hidden passage, enter treasury)
    #   Turns 19-20: Puzzle (open wooden box, recover ledger)
    # Assert: turn log has 20 entries
    # Assert: quest state updated correctly
    # Assert: no scope violations
    # Assert: all state consistent

test_10_turn_haunted_manor_puzzle_chain()
    # Similar structure for the haunted manor scenario

test_10_turn_forest_ambush_combat_heavy()
    # Similar structure for the forest ambush scenario

test_player_disconnect_and_rejoin()
    # Simulate a player going AFK for several turns
    # Assert: timeout fallbacks applied
    # Assert: player can resume without state corruption

test_split_party_across_extended_session()
    # Split the party at turn 5, rejoin at turn 15
    # Assert: independent scene state maintained
    # Assert: information propagation works when they rejoin
```

Target ~10 tests.

### Task 6: Patch release blockers

This is a reactive task. Fix any P0 or P1 bugs found during Tasks 1-5.

Common anticipated areas:
- **State consistency:** Entities getting out of sync between orchestrator dicts after 20+ turns. Fix: add state-consistency assertions in the orchestrator.
- **Memory growth:** Knowledge facts accumulating without bound over long sessions. Fix: add fact archival or summarization for very old facts.
- **Timer edge cases:** Race conditions between timer expiry and late action submission. Fix: stricter lock sequencing in the orchestrator.
- **Model prompt growth:** Prompts exceeding token limits in long campaigns. Fix: verify TruncationPolicy handles 20+ turn histories correctly.

For each fix, add a regression test.

### Task 7: Update STARTUP.md and core docs to match the actual system

**File:** `STARTUP.md` (update)

```
## Repo Layout (updated)

C:\Projects\rpg\
├── STARTUP.md
├── CLAUDE.md
├── docs/
│   ├── plan.md
│   ├── phase_status.md
│   ├── architecture.md          # Updated with orchestrator + API + Mini App layers
│   ├── miniapp_architecture.md  # Mini App design doc (Phase 17)
│   ├── model_routing.md
│   ├── repo_conventions.md
│   ├── testing.md               # Updated with integration + API test layers
│   ├── design.md
│   ├── pdr.md
│   ├── playtest_findings.md     # Phase 16 findings
│   ├── release_readiness.md     # Phase 20 readiness assessment
│   └── feature_freeze.md        # Phase 20 freeze notice
├── server/
│   ├── api/                     # REST API for Mini App (Phase 17)
│   ├── orchestrator/            # Top-level game loop (Phase 16)
│   ├── (existing packages)
├── bot/                         # Extended with new commands (Phases 16, 20)
├── models/                      # Extended contracts (Phase 19)
├── scenarios/
│   ├── starters/                # 4 scenarios (Phase 13 + Phase 19)
│   ├── archetypes.py            # NPC archetypes (Phase 19)
│   └── puzzle_patterns.py       # Puzzle templates (Phase 19)
├── webapp/                      # Mini App frontend (Phases 17-18)
│   ├── index.html
│   ├── css/style.css
│   └── js/
│       ├── app.js
│       └── views/               # sheet, inventory, recap, action, inbox, channels, quests, clues, map
└── tests/
    ├── integration/             # Playtest + extended session tests (Phases 16, 20)
    └── unit/                    # Expanded (all phases)
```

**File:** `docs/architecture.md` (update)

Add the orchestrator, API, and Mini App layers to the system diagram:

```
┌────────────────────────────────────────────────────────────┐
│                     Telegram Platform                       │
│  Supergroup + Topics + Private DMs + Inline Keyboards       │
│  Mini App (WebApp overlay)                                  │
└────────────┬───────────────────────────┬───────────────────┘
             │ Bot API                   │ WebApp API
┌────────────▼────────────┐  ┌───────────▼───────────────────┐
│   Telegram Bot Gateway  │  │   Mini App (HTML/JS/CSS)       │
│   bot/                  │  │   webapp/                      │
└────────────┬────────────┘  └───────────┬───────────────────┘
             │                           │ HTTP /api/
┌────────────▼───────────────────────────▼───────────────────┐
│                    Game Orchestrator                        │
│  server/orchestrator/game_loop.py                          │
│  Wires: turn engine, scope, timer, models, delivery        │
├────────────────────────────────────────────────────────────┤
│                      REST API                              │
│  server/api/ (FastAPI)                                     │
│  Endpoints: /player, /character, /scene, /recap, /action   │
└────────────┬───────────────────────────┬──────────────────┘
             │                           │
    ┌────────▼────────┐        ┌─────────▼────────────────┐
    │  Game Server     │        │  Model Adapters           │
    │  Domain engines  │        │  Fast (qwen2.5:1.5b)     │
    │  Scope, Timer    │        │  Main (Gemma 4 26B A4B)  │
    │  Reliability     │        │  Contracts + Repair       │
    └─────────────────┘        └──────────────────────────┘
```

---

## Verification

After each phase:
1. `pytest` — all tests pass.
2. `ruff check . && ruff format --check .` — lint clean.
3. Review test count growth:
   - Phase 16: expect ~1130 (1078 + ~55 integration + regression)
   - Phase 17: expect ~1150 (+ ~20 API tests)
   - Phase 18: expect ~1175 (+ ~25 API gameplay tests)
   - Phase 19: expect ~1200 (+ ~25 scenario + validation tests)
   - Phase 20: expect ~1230 (+ ~30 privacy + extended session tests)
4. One commit per phase, never push without explicit authorization.

## Dependencies to Add

| Phase | Package | Purpose | Version |
|-------|---------|---------|---------|
| 17 | `fastapi` | REST API + static file serving for Mini App | `>=0.100` |
| 17 | `uvicorn` | ASGI server for FastAPI | `>=0.20` |
| 17 | `httpx` | (already present) TestClient for FastAPI tests | `>=0.27` |

## Key Architectural Notes

1. **Phase 16 is the integration boundary.** Everything before it was unit-testable domain code. Phase 16 is the first time subsystems connect end-to-end. Expect wiring bugs.

2. **The Mini App is deliberately simple.** Vanilla HTML/JS/CSS with no build step. This keeps the deployment minimal and avoids frontend toolchain complexity. The Telegram WebApp SDK handles authentication and theming.

3. **The orchestrator is in-memory for now.** Phase 16's GameOrchestrator holds all state in dicts. This is fine for local playtest. Production persistence (loading/saving state to the database via server/storage/) is a post-Phase 20 concern.

4. **Phase 19 is content-only.** No structural changes — just more scenarios, patterns, and templates. This is where scenario authors can start working independently.

5. **Phase 20 is about confidence, not features.** The extended session tests (20+ turns) are the closest thing to a real playtest in the automated suite. If they pass with no scope leakage and consistent state, the system is ready.
