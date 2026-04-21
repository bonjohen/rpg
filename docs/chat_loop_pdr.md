# Physical Design Requirements: Chat-Driven Game Loop Integration

**Source document:** `docs/design.md` (Sections 4-8, 14), `docs/architecture.md`
**Project root:** `C:\Projects\rpg`
**Date:** 2026-04-20 10:00 PM (PST)
**Revised:** 2026-04-20 11:30 PM (PST) — incorporated Plan subagent review

## 1. System Context

The game server has a complete infrastructure stack — turn engine, scope enforcement, timer controller, two-tier model routing, database persistence, outbound message delivery, and 1479 passing tests. However, the Telegram bot's message handlers are stubs: player chat messages are logged and dropped. The only way to play is through slash commands (`/nextturn`, `/forceresolve`), which is nothing like the design doc's intended experience of players typing naturally in chat and the AI referee driving the game.

This PDR covers the integration wiring that connects "player types in Telegram" to "game responds with narration," making the core game loop described in `docs/design.md` Section 6 actually work.

### 1.1 Existing Infrastructure to Reuse

| Asset | Location | Reuse |
|---|---|---|
| `handle_player_message()` | `server/orchestrator/game_loop.py:691` | Async. Classifies intent via fast model, extracts action packets, submits to turn engine. Wire bot handlers to call this. |
| `open_turn()` | `server/orchestrator/game_loop.py:418` | Sync. Creates TurnWindow, starts timer. Needs to be called automatically, not just via `/nextturn`. |
| `submit_action()` | `server/orchestrator/game_loop.py:465` | Sync. Commits player action to turn window. Already called by `_handle_as_action()`. |
| `resolve_turn()` | `server/orchestrator/game_loop.py:528` | Sync. Locks, resolves, commits. Generates basic concatenated narration. Does NOT call main model. |
| `narrate_scene()` | `models/main/tasks.py` | Async. Calls main model (temp 0.7) for rich narration. Exists, tested, never called by orchestrator. |
| `generate_npc_dialogue()` | `models/main/tasks.py` | Async. NPC dialogue (temp 0.8). Exists, never called in game loop. |
| `summarize_combat()` | `models/main/tasks.py` | Async. Combat narration (temp 0.7). Exists, never called. |
| `propose_ruling()` | `models/main/tasks.py` | Async. Ruling on ambiguous actions (temp 0.3). Exists, never called from chat. |
| `send_public()` | `bot/outbound.py` | Async. Sends to group chat play topic. Production-ready. |
| `send_private()` / `send_private_by_player_id()` | `bot/outbound.py` | Async. Sends DM to player. Production-ready. |
| `route_message()` | `bot/routing.py` | Sync. Classifies messages to `RouteTarget` enum. Production-ready. |
| `parse_group_message()` / `parse_private_message()` | `bot/parsers.py` | Sync. Extracts user ID, text, thread info. Production-ready. |
| `classify_intent()` | `models/fast/tasks.py` | Async. Fast model intent classification. Returns action/question/chat/command/unknown. |
| `extract_action_packet()` | `models/fast/tasks.py` | Async. Fast model action parsing. Returns action_type, target, item_ids. |
| `suggest_scope()` | `models/fast/tasks.py` | Async. Suggests public/private/side-channel scope. |
| `generate_clarification()` | `models/fast/tasks.py` | Async. Produces clarification questions for ambiguous actions. |
| `TimerController` | `server/timer/controller.py` | Sync, poll-based. Has `check_expiry()`, NOT push callbacks. Timer expiry must be scheduled externally. |
| `BotRegistry` | `bot/mapping.py` | In-memory player ↔ Telegram ID mapping. |
| `ScopeEngine` / `LeakageGuard` | `server/scope/` | Scope filtering and leakage prevention. Tested. |
| `ContextAssembler` | `models/contracts/context_assembly.py` | Builds scoped prompts for model calls. Tested. |
| PTB `Application.job_queue` | python-telegram-bot built-in | APScheduler-backed job queue. Supports `run_once(callback, when)` for delayed execution within the bot's event loop. |

### 1.2 New Dependencies to Add

None. All required packages are already in `requirements.txt`. PTB's job queue uses APScheduler which ships with `python-telegram-bot`.

## 2. Replayability Principle

A core design goal: each playthrough of the same scenario should feel different. The scenario YAML defines structure (scenes, triggers, NPCs, puzzles, stat blocks), but the main model generates the *telling*. Different player choices route through different scene paths, interact with different NPCs, and trigger different events. Even the same mechanical outcome (trap triggers, 3 damage) gets narrated with different flavor each time because `narrate_scene()` and `generate_npc_dialogue()` use creative temperatures (0.7-0.8).

This only works if the main model is actually called during gameplay — which is exactly what this PDR wires up. The concatenated string fallback (`"In Cave Entrance: Player took 3 damage from fire pit."`) is the safety net, not the experience.

## 3. What Needs to Be Built

Seven gaps between existing infrastructure and a playable chat-driven game. Each gap is a well-bounded integration task — no new engines, models, or data structures required.

### Gap 1: Bot Message Handlers → Orchestrator Dispatch

**Current state:** `_handle_group_message()` and `_handle_private_message()` in `bot/handlers.py` log the message and return. Lines 87-95 and 112-120 are stubs with `# Game engine dispatch added in Phase 7+`.

**Required state:** Both handlers call `orchestrator.handle_player_message()` and route the `DispatchResult` to the appropriate outbound channel.

**Design:**

```
_handle_group_message(update, context):
    parsed = parse_group_message(message)
    routed = route_message(message, config)

    if routed.target == RouteTarget.play_action:
        player_id = registry.player_id_for(parsed.telegram_user_id)
        result = await orchestrator.handle_player_message(
            player_id, parsed.text, is_private=False
        )
        if result.response_text:
            await send_public(bot, config, result.response_text)
        if result.action_submitted:
            await _check_and_resolve(orchestrator, player_id, bot, config, registry, context)

_handle_private_message(update, context):
    parsed = parse_private_message(message)
    player_id = registry.player_id_for(parsed.telegram_user_id)
    result = await orchestrator.handle_player_message(
        player_id, parsed.text, is_private=True
    )
    if result.response_text:
        await send_private(bot, registry, parsed.telegram_user_id, result.response_text)
```

**Sync orchestrator calls from async handlers:** All sync orchestrator methods (`open_turn`, `submit_action`, `resolve_turn`) do SQLAlchemy I/O. For single-campaign single-server with SQLite, direct calls are acceptable. If latency under concurrent submissions becomes a problem, wrap in `asyncio.get_event_loop().run_in_executor(None, ...)`. Start without the executor; add it if testing reveals event loop blocking.

**Error handling:** If `player_id_for()` raises `UnknownUserError`, reply with the "not joined" onboarding message. If `handle_player_message()` raises, log the error and reply with a generic "something went wrong" message. Never crash the handler.

**Files modified:** `bot/handlers.py`

### Gap 2: Auto-Turn Management

**Current state:** Turns must be opened manually via `/nextturn` and resolved manually via `/forceresolve`. Players have no way to trigger turns through natural play.

**Required state:** The orchestrator auto-opens a turn when a player submits an action and no turn is active in their scene. The orchestrator auto-resolves when all players are ready or the timer expires.

**Design:**

**2a. Auto-open with scene introduction (INVARIANT: situation before timer).**

Add `ensure_turn_open(scene_id) -> TurnWindow` to the orchestrator. Called by `_handle_as_action()` before `submit_action()`.

**Critical ordering invariant from design doc Section 6:** No turn window may transition to `open` without the scene situation having been posted first. `ensure_turn_open` must:
1. Check if scene already has an active turn window → return it if found (idempotent)
2. If not, call `open_turn(scene_id)`
3. Return the turn window; the caller (bot handler) is responsible for posting the scene description and turn-control message (Gap 5, Gap 6) *before* acknowledging the player's action

**Race condition guard:** Two simultaneous messages could both see no active turn and both call `open_turn`. `open_turn` must check for an existing active turn window *inside its database session* and return it if found, rather than unconditionally creating a new one. This is a check-and-set within a single transaction.

**2b. Auto-resolve on all-ready.**

`submit_action()` already calls `TurnEngine.check_all_ready()` and may transition the window to `all_ready`. After `submit_action()` returns, the handler checks the turn window state. If `all_ready`, the handler calls `resolve_turn()` immediately, generates narration (Gap 3), and delivers results (Gap 4).

**2c. Auto-resolve on timer expiry.**

Use PTB's `job_queue.run_once()` to schedule resolution at `expires_at` time when the turn opens. The job callback receives `CallbackContext` which has `context.bot` and `context.application.bot_data` — no closure fragility. The callback:
1. Checks if the turn window is still open (it may have been resolved by all-ready)
2. If still open, calls `resolve_turn()` (which auto-synthesizes hold actions for missing players)
3. Generates narration, delivers results

The `/nextturn` and `/forceresolve` slash commands remain as admin overrides.

**Files modified:** `server/orchestrator/game_loop.py`, `bot/handlers.py`

### Gap 3: Rich Narration via Main Model

**Current state:** `resolve_turn()` generates narration by concatenating action effect strings: `"In {scene.name}: {effect1} {effect2} ..."`. The main model's `narrate_scene()`, `summarize_combat()`, and `generate_npc_dialogue()` functions exist but are never called.

**Required state:** After `resolve_turn()` produces the turn log entry with basic narration, an async narration step calls the main model to generate rich, varied narration. If the main model fails, the basic concatenated narration is used as fallback (already generated). The main model's creative temperature (0.7-0.8) ensures each playthrough feels different even for the same mechanical outcomes.

**Design:**

Add an async function `generate_narration(orchestrator, turn_log_entry, scene, committed_actions) -> str`. This function:
1. Takes the resolved turn data
2. Uses `ContextAssembler` to build a scoped prompt (public facts only — no referee-only leakage)
3. Calls `narrate_scene()` for exploration/social scenes, or `summarize_combat()` if the scene has active combat
4. If NPCs were involved in the turn's actions, also calls `generate_npc_dialogue()` and weaves NPC lines into the narration
5. Returns the rich narration text, or falls back to `turn_log_entry.narration` on failure

This lives in `bot/delivery.py` (not on the orchestrator) because it's async and the orchestrator is Telegram-agnostic.

**Files modified:** `bot/delivery.py`

### Gap 4: Result Delivery to Telegram

**Current state:** `resolve_turn()` returns a `TurnLogEntry` to its caller, but nobody sends it to Telegram. The `/forceresolve` command handler manually posts `log_entry.narration` to the chat, but that's a debug command, not the normal flow.

**Required state:** After resolution and narration, the bot posts:
1. Public narration to the group chat via `send_public()`
2. Private facts revealed during this turn to affected players via `send_private_by_player_id()`

**Design:**

Add an async function `deliver_turn_results(orchestrator, turn_log_entry, scene, bot, config, registry)` in `bot/delivery.py`. This function:
1. Calls `generate_narration()` (Gap 3) to get rich narration
2. Posts the narration to the public channel via `send_public()`
3. Queries newly revealed private-referee facts from this turn via the orchestrator's repos
4. Sends each private fact to the owning player via `send_private_by_player_id()`
5. Edits the turn-control message (Gap 6) to show "Turn N resolved" and remove the keyboard

**Error handling for partial delivery:** If public narration sends successfully but a private DM fails (user blocked bot, rate limit), log the failure and continue. Do not retry synchronously — the turn log has the authoritative record. The player can retrieve missed private facts via the Mini App inbox (`/api/player/{id}/inbox`) or a future `/inbox` command. This is an acceptable degradation: the game continues, and the data is not lost.

**The orchestrator stays Telegram-agnostic.** The handler calls `deliver_turn_results()` after resolution. This function lives in `bot/delivery.py` and uses the outbound functions from `bot/outbound.py`.

**Files created:** `bot/delivery.py`
**Files modified:** `bot/handlers.py`

### Gap 5: Scene Introduction on Join and Newgame

**Current state:** `/newgame` says "Scenario loaded! N scenes ready." `/join` says "Welcome, name! Your character has been created. You're in: Scene Name." Neither shows the scene description, the scenario premise, or any narrative immersion.

**Required state:**
- `/newgame` posts the scenario title, description, and starting scene teaser to the group chat
- `/join` posts the full starting scene description and announces the player's arrival

**Design:**

Enhance `ScenarioLoadResult` with `title: str` and `description: str` fields, populated from the scenario manifest during loading.

Enhance `cmd_newgame` to post a narrative introduction after loading:
```
--- The Goblin Caves ---

A party of adventurers investigates reports of goblin raids.

Starting location: Cave Entrance
A dark mouth in the hillside, flanked by dead bushes. Claw marks
score the stone around the opening. A faint smell of smoke drifts out.

Players: send /join to enter the game.
```

Enhance `cmd_join` to:
1. After `add_player()`, post the full scene description (reuse the `/scene` format)
2. Announce to the group: "{name} has entered {scene.name}."

**Files modified:** `scenarios/loader.py` (add title/description to ScenarioLoadResult), `bot/commands.py`

### Gap 6: Turn-Control Message with Inline Keyboard

**Current state:** No inline keyboard buttons. No turn-control message. Players have no UI feedback during a turn.

**Required state:** When a turn opens, the bot posts a turn-control message with inline keyboard buttons. This message shows the scene situation and updates as players submit. When the turn resolves, the message is edited to show the narration.

**Design:**

When a turn opens (either via `/nextturn` or auto-open from Gap 2), post a turn-control message:
- Text: scene description + "What do you do? (Type your action, or tap a button.)"
- InlineKeyboard: `[[Ready] [Pass]]`
- Store the `message_id` on the orchestrator's in-memory turn state (not on the TurnWindow entity — the message_id is Telegram-specific and ephemeral, not game state)

Add a `CallbackQueryHandler` in `bot/handlers.py` for button presses:
- **Ready:** Submit a hold action with ready state for this player
- **Pass:** Submit a hold action with pass state for this player
- Answer the callback query with confirmation text

When a player submits an action (via chat text or button), edit the turn-control message to show who has acted: "Waiting for: {remaining players}".

When the turn resolves, edit the control message to show the narration and remove the keyboard.

**Files modified:** `bot/handlers.py`, `bot/delivery.py`

### Gap 7: Question Intent Handling

**Current state:** `handle_player_message()` classifies "question" intent but returns a canned string: "Your question has been noted. The referee will respond." Nobody ever responds. This is a dead end that will confuse players immediately.

**Required state:** Questions from players (especially private DMs like "Can I tell if the merchant is lying?") get a meaningful response from the AI referee.

**Design:**

When intent is classified as "question":
1. Call `propose_ruling()` from `models/main/tasks.py` (temp 0.3, conservative) with the question text, player's character state, and scene context
2. If the ruling suggests a check is needed, the orchestrator can resolve it deterministically (dice roll, stat check) and return the result
3. If it's a pure information question, return the ruling's response text
4. Private questions (is_private=True) → response goes to DM only
5. Public questions → response goes to group chat

If the main model fails, fall back to: "The referee considers your question... (no ruling available, try rephrasing or take an action instead.)"

**Files modified:** `server/orchestrator/game_loop.py` (replace the canned question response)

## 4. Flow Diagram: Chat-Driven Turn

```
Player types "I search the fire pit" in group chat
    │
    ▼
_handle_group_message()                    [bot/handlers.py]
    │ parse + route → RouteTarget.play_action
    ▼
orchestrator.handle_player_message()       [game_loop.py]
    │ classify_intent() → "action"         [fast model]
    │ extract_action_packet() → search     [fast model]
    ▼
ensure_turn_open(scene_id)                 [game_loop.py]
    │ ├─ active turn exists? → return it
    │ └─ no active turn? → open_turn()
    │         │
    │         ├─ post scene description     [send_public]
    │         ├─ post turn-control message  [inline keyboard]
    │         └─ schedule timer job         [job_queue.run_once]
    ▼
submit_action(player_id, ...)              [turn engine + DB]
    │ check_all_ready()
    │
    ├─ [all_ready] ─────────────────────────┐
    │                                        │
    │   [else: wait for timer/others]        │
    │         │                              │
    │   [timer job fires] ──────────────────┤
    │                                        │
    │                                        ▼
    │                            resolve_turn()           [game_loop.py]
    │                                        │
    │                                        ▼
    │                            generate_narration()     [main model, temp 0.7]
    │                                        │
    │                                        ▼
    │                            deliver_turn_results()   [bot/delivery.py]
    │                                        │
    │                            ├─ send_public(): narration
    │                            ├─ send_private(): hidden facts
    │                            └─ edit turn-control msg: "resolved"
    ▼
Player sees narration in group chat.
Next action from any player auto-opens the next turn.
```

## 5. Idempotency Fix

The current idempotency key in `handle_player_message()` is `msg:{player_id}:{sha256(text)[:16]}`. This will cause false collisions: a player sending "I attack" in turn 1 and "I attack" in turn 2 would be deduped. The key must include temporal context.

**Fix:** Change the key to `msg:{player_id}:{turn_window_id or 'no_turn'}:{sha256(text)[:16]}`. If no turn is active, include `'no_turn'` so pre-turn messages are still deduped within a session but don't collide across turns.

**Files modified:** `server/orchestrator/game_loop.py`

## 6. Scope Safety

All narration and result delivery must pass through the scope system:
- `send_public()` content must contain only public-scope facts
- `send_private_by_player_id()` content must contain only facts scoped to that player
- `ContextAssembler` already enforces this for model prompts — use it for narration assembly
- `LeakageGuard` can validate outbound content before delivery as a safety check

No new scope infrastructure is needed. The existing system is sufficient.

## 7. Async/Sync Boundary

The orchestrator's turn lifecycle methods (`open_turn`, `submit_action`, `resolve_turn`) are **sync** (SQLAlchemy sync sessions). Model calls and bot outbound calls are **async**.

`handle_player_message()` is already async and bridges this by calling sync methods within its async body. For single-campaign single-server with SQLite, this is acceptable — SQLite I/O is sub-millisecond.

**Mitigation if needed:** If testing reveals event loop blocking under concurrent player submissions (4-6 players submitting near the timer deadline), wrap sync orchestrator calls in `asyncio.get_event_loop().run_in_executor(None, sync_fn)`. This is a mechanical change that doesn't affect the design. Start without it.

## 8. What This PDR Does NOT Cover

- **Inline keyboard for structured action drafting/revision** (Submit/Revise buttons that open a multi-field action builder). Players type actions in natural language; the fast model's `extract_action_packet()` handles interpretation. A structured builder is a UX refinement, not a blocker.
- **Side-channel relay via DM** (design doc Section 5). Side channels exist in the data model but DM relay adds complexity. Defer to post-integration.
- **Mini App integration** (character sheets, inventory, map). Separate concern.
- **Combat-specific narration selection.** The turn engine already handles combat actions. `summarize_combat()` vs `narrate_scene()` selection based on scene state is a refinement within Gap 3, not a separate gap.
- **Split-party auto-routing.** Existing `get_player_scene()` handles this. No new routing logic needed.

## 9. Verification Criteria

After implementation, these user stories from the design doc must work end-to-end **in a live Telegram session, not just in unit tests:**

1. **Scenario introduction (design doc Section 6 Step 1):** GM sends `/newgame scenarios/starters/goblin_caves.yaml`. The group chat shows the scenario title, description, and starting scene. Players know what the game is about.

2. **Player onboarding:** A player sends `/start` in a DM, then `/join` in the group. They see the full scene description of Cave Entrance, including exits. The group sees "{name} has entered Cave Entrance."

3. **Natural action submission (design doc Section 6 Steps 3-5):** A player types "I pick up the discarded torch" in the group chat. The bot classifies it as an action, auto-opens a turn if needed (posting the scene situation first), and submits the action. The player sees confirmation. Other players see the turn-control message with Ready/Pass buttons.

4. **Private question (design doc Use Case 2):** A player DMs the bot "Can I tell whether Grix is nervous?" The bot classifies it as a question, calls the main model for a ruling, and replies privately. The group chat sees nothing.

5. **All-ready early close (design doc Section 7):** All players in the scene submit actions or press Ready. The turn resolves immediately. The main model narrates the result. Players see rich narrative text in the group chat, not concatenated strings.

6. **Timeout fallback (design doc Section 7):** A turn opens, some players submit, one doesn't. The timer expires (PTB job fires). The absent player gets a default "hold" action. The turn resolves and narrates normally.

7. **Rich narration with replayability (design doc Section 6 Step 9):** The same mechanical outcome produces different narrative text on different playthroughs. The main model is called with creative temperature. If it fails, the deterministic fallback text appears instead.

8. **Private fact delivery:** After resolution, if any private facts were revealed (e.g., a player passed an awareness check), they arrive in that player's DM only. Other players do not see them.

9. **Consecutive turns:** After resolution, the next player action auto-opens a new turn. The game continues without needing `/nextturn`. Players can play multiple turns in sequence through natural chat.
