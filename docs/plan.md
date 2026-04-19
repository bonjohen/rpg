# AI-Refereed Multiplayer Text Game on Telegram: Phased Release Tracker

Use this file one phase at a time and one task at a time. When a task begins, change its status from [ ] to [X] and fill in Started (PST). When the task is finished, change its status from [X] to [#] and fill in Completed (PST). Keep status and datelines accurate at all times. Treat [!] as a disabled task that is not currently being worked.

Status legend: [ ] Unstarted, [X] Started, [#] Completed, [!] Disabled

Follow this progression pattern with the statuses of each task:
[ ]  ──>  [X] ──>  [#] 
        │
        └──> [!] ──>  [X] ──>  [#]
Update Started and Completed datetimes when starting or completing a task.

At the beginning of each phase perform the following:
Phase Startup
* Sync repo and review branch status
* Read STARTUP.md and restore working context
* Review previous phase notes, known defects, and current priorities

At the end of each phase perform the following:
Phase End
* Run all tests and repair failures
* Update phase_status.md, STARTUP.md, and record Phase completion
* Commit Phase work locally without pushing
* Spawn a subagent via the Agent tool to execute the next phase. The subagent
  starts with a clean context window (equivalent to /clear). Pass it the plan
  file path and instruct it to read STARTUP.md, find the next Open phase, and
  execute end-to-end. Do not continue in the current context after committing.

On 3, 6, 9, 12, etc (phases evenly divisible by 3) do the additional step.
* Provide a few paragraphs about what was accomplished this phase, also lauch
  any necessary servers and services, indicate their paths, and explain how to
  use the sites, in context with the design document. Pause work on the plan.

## Phase 0: Repository Foundation and Startup Context

[#] Phase Startup | Started (PST): 2026-04-18 09:00 AM | Completed (PST): 2026-04-18 09:02 AM
[#] Create or refine STARTUP.md as the authoritative startup file | Started (PST): 2026-04-18 09:02 AM | Completed (PST): 2026-04-18 09:04 AM
[#] Create or refine docs/architecture.md | Started (PST): 2026-04-18 09:04 AM | Completed (PST): 2026-04-18 09:07 AM
[#] Create or refine docs/testing.md | Started (PST): 2026-04-18 09:07 AM | Completed (PST): 2026-04-18 09:09 AM
[#] Create or refine docs/phase_status.md | Started (PST): 2026-04-18 09:09 AM | Completed (PST): 2026-04-18 09:10 AM
[#] Create or refine docs/model_routing.md | Started (PST): 2026-04-18 09:10 AM | Completed (PST): 2026-04-18 09:12 AM
[#] Create or refine docs/repo_conventions.md | Started (PST): 2026-04-18 09:12 AM | Completed (PST): 2026-04-18 09:15 AM
[#] Define local workflow rules for branch, commit, and no-push behavior | Started (PST): 2026-04-18 09:12 AM | Completed (PST): 2026-04-18 09:15 AM
[#] Define environment, secrets, logging, and debug conventions | Started (PST): 2026-04-18 09:12 AM | Completed (PST): 2026-04-18 09:15 AM
[#] Define the repo layout for server, bot, models, scenarios, and docs | Started (PST): 2026-04-18 09:12 AM | Completed (PST): 2026-04-18 09:15 AM
[#] Define where prompt contracts and scenario notes will live | Started (PST): 2026-04-18 09:12 AM | Completed (PST): 2026-04-18 09:15 AM
[#] Phase End | Started (PST): 2026-04-18 09:15 AM | Completed (PST): 2026-04-18 09:16 AM

## Phase 1: Core Domain Model and Persistence

[#] Phase Startup | Started (PST): 2026-04-18 09:20 AM | Completed (PST): 2026-04-18 09:21 AM
[#] Define Campaign entity and persistence fields | Started (PST): 2026-04-18 09:21 AM | Completed (PST): 2026-04-18 09:25 AM
[#] Define Player entity and persistence fields | Started (PST): 2026-04-18 09:21 AM | Completed (PST): 2026-04-18 09:25 AM
[#] Define Character entity and persistence fields | Started (PST): 2026-04-18 09:21 AM | Completed (PST): 2026-04-18 09:25 AM
[#] Define Scene entity and persistence fields | Started (PST): 2026-04-18 09:21 AM | Completed (PST): 2026-04-18 09:25 AM
[#] Define ConversationScope and SideChannel entities | Started (PST): 2026-04-18 09:21 AM | Completed (PST): 2026-04-18 09:25 AM
[#] Define TurnWindow, CommittedAction, and TurnLogEntry entities | Started (PST): 2026-04-18 09:21 AM | Completed (PST): 2026-04-18 09:25 AM
[#] Define NPC and MonsterGroup entities | Started (PST): 2026-04-18 09:21 AM | Completed (PST): 2026-04-18 09:25 AM
[#] Define InventoryItem, QuestState, PuzzleState, and KnowledgeFact entities | Started (PST): 2026-04-18 09:21 AM | Completed (PST): 2026-04-18 09:25 AM
[#] Define state-machine enums for scene, turn, and action lifecycles | Started (PST): 2026-04-18 09:21 AM | Completed (PST): 2026-04-18 09:25 AM
[#] Implement schema or ORM models | Started (PST): 2026-04-18 09:25 AM | Completed (PST): 2026-04-18 09:40 AM
[#] Implement migrations or schema creation flow | Started (PST): 2026-04-18 09:25 AM | Completed (PST): 2026-04-18 09:40 AM
[#] Add fixture builders for core entities | Started (PST): 2026-04-18 09:40 AM | Completed (PST): 2026-04-18 09:50 AM
[#] Add persistence tests for create, load, update, and replayability | Started (PST): 2026-04-18 09:40 AM | Completed (PST): 2026-04-18 09:50 AM
[#] Phase End | Started (PST): 2026-04-18 09:50 AM | Completed (PST): 2026-04-18 09:52 AM

## Phase 2: Canonical Turn Engine

[#] Phase Startup | Started (PST): 2026-04-18 10:43 PM | Completed (PST): 2026-04-18 10:44 PM
[#] Implement TurnWindow lifecycle states and transitions | Started (PST): 2026-04-18 10:44 PM | Completed (PST): 2026-04-18 10:45 PM
[#] Implement one authoritative committed action per player per turn | Started (PST): 2026-04-18 10:45 PM | Completed (PST): 2026-04-18 10:46 PM
[#] Implement action validation and rejection flow | Started (PST): 2026-04-18 10:46 PM | Completed (PST): 2026-04-18 10:47 PM
[#] Implement late-submission rejection after turn lock | Started (PST): 2026-04-18 10:47 PM | Completed (PST): 2026-04-18 10:48 PM
[#] Implement all-ready early-close behavior | Started (PST): 2026-04-18 10:48 PM | Completed (PST): 2026-04-18 10:49 PM
[#] Implement timeout fallback behavior hooks | Started (PST): 2026-04-18 10:49 PM | Completed (PST): 2026-04-18 10:50 PM
[#] Implement append-only turn log writing | Started (PST): 2026-04-18 10:50 PM | Completed (PST): 2026-04-18 10:51 PM
[#] Implement deterministic turn commit ordering | Started (PST): 2026-04-18 10:51 PM | Completed (PST): 2026-04-18 10:52 PM
[#] Implement turn replay support from committed records | Started (PST): 2026-04-18 10:52 PM | Completed (PST): 2026-04-18 10:53 PM
[#] Add unit tests for open, lock, resolve, commit, abort, and replay | Started (PST): 2026-04-18 10:53 PM | Completed (PST): 2026-04-18 10:54 PM
[#] Phase End | Started (PST): 2026-04-18 10:54 PM | Completed (PST): 2026-04-18 10:55 PM

### Phase 2 Summary

- **Changes:** Created `server/engine/turn_engine.py` (TurnEngine class: lifecycle transitions, submit/validate/reject actions, timeout fallback synthesis, deterministic ordering, append-only log entry production, replay) and `tests/unit/test_turn_engine.py` (54 unit tests covering all lifecycle paths). Also `server/engine/__init__.py`.
- **Changes hosted at:** local only
- **Commit:** `Phase 2: Canonical Turn Engine`

## Phase 3: Telegram Bot Integration Skeleton

[#] Phase Startup | Started (PST): 2026-04-18 10:56 PM | Completed (PST): 2026-04-18 10:57 PM
[#] Implement Telegram bot gateway entry point | Started (PST): 2026-04-18 10:57 PM | Completed (PST): 2026-04-18 10:59 PM
[#] Implement webhook or polling handler | Started (PST): 2026-04-18 10:59 PM | Completed (PST): 2026-04-18 11:01 PM
[#] Implement public group message parsing | Started (PST): 2026-04-18 11:01 PM | Completed (PST): 2026-04-18 11:03 PM
[#] Implement private DM message parsing | Started (PST): 2026-04-18 11:03 PM | Completed (PST): 2026-04-18 11:04 PM
[#] Implement user-to-player and chat-to-campaign mapping | Started (PST): 2026-04-18 11:04 PM | Completed (PST): 2026-04-18 11:06 PM
[#] Implement player onboarding requirement for private DM initiation | Started (PST): 2026-04-18 11:06 PM | Completed (PST): 2026-04-18 11:08 PM
[#] Implement topic-aware routing for the main play topic | Started (PST): 2026-04-18 11:08 PM | Completed (PST): 2026-04-18 11:10 PM
[#] Implement minimal command handling for /start, /join, /help, /status | Started (PST): 2026-04-18 11:10 PM | Completed (PST): 2026-04-18 11:14 PM
[#] Implement outbound public message sending | Started (PST): 2026-04-18 11:14 PM | Completed (PST): 2026-04-18 11:16 PM
[#] Implement outbound private DM sending | Started (PST): 2026-04-18 11:16 PM | Completed (PST): 2026-04-18 11:17 PM
[#] Add Telegram payload fixtures and integration tests | Started (PST): 2026-04-18 11:17 PM | Completed (PST): 2026-04-18 11:26 PM
[#] Phase End | Started (PST): 2026-04-18 11:26 PM | Completed (PST): 2026-04-18 11:27 PM

### Phase 3 Summary

- **Changes:** Created `bot/` package: `config.py` (BotConfig), `gateway.py` (build_app, run_polling, run_webhook), `__main__.py` (env-driven entry point), `handlers.py` (PTB handler registration), `parsers.py` (classify/parse group and private messages), `mapping.py` (BotRegistry: user↔player, chat↔campaign), `onboarding.py` (onboarding gate), `routing.py` (topic-aware RouteTarget dispatch), `commands.py` (/start, /join, /help, /status), `outbound.py` (send_public, send_private, send_private_by_player_id). Added `tests/fixtures/telegram_builders.py` and 40 unit tests across 5 test files. Added `pytest.ini` (asyncio_mode=auto) and updated `requirements.txt`.
- **Changes hosted at:** local only
- **Commit:** `Phase 3: Telegram Bot Integration Skeleton`

## Phase 4: Scope and Visibility Enforcement

[#] Phase Startup | Started (PST): 2026-04-18 11:28 PM | Completed (PST): 2026-04-18 11:30 PM
[#] Implement public scope delivery rules | Started (PST): 2026-04-18 11:31 PM | Completed (PST): 2026-04-18 11:35 PM
[#] Implement private-referee scope delivery rules | Started (PST): 2026-04-18 11:35 PM | Completed (PST): 2026-04-18 11:36 PM
[#] Implement side-channel scope model and permissions | Started (PST): 2026-04-18 11:36 PM | Completed (PST): 2026-04-18 11:39 PM
[#] Implement referee-only storage rules | Started (PST): 2026-04-18 11:39 PM | Completed (PST): 2026-04-18 11:41 PM
[#] Implement KnowledgeFact ownership by scope | Started (PST): 2026-04-18 11:41 PM | Completed (PST): 2026-04-18 11:44 PM
[#] Implement scope-safe retrieval for prompts and message generation | Started (PST): 2026-04-18 11:44 PM | Completed (PST): 2026-04-18 11:46 PM
[#] Implement guardrails against accidental public leakage | Started (PST): 2026-04-18 11:46 PM | Completed (PST): 2026-04-18 11:49 PM
[#] Add tests for awareness checks, hidden clues, stealth, and secret objectives | Started (PST): 2026-04-18 11:49 PM | Completed (PST): 2026-04-18 11:57 PM
[#] Phase End | Started (PST): 2026-04-18 11:57 PM | Completed (PST): 2026-04-18 11:58 PM

### Phase 4 Summary

- **Changes:** Created `server/scope/` package: `engine.py` (ScopeEngine: delivery targets, visibility checks, fact filtering, scope-safe context assembly), `side_channel.py` (SideChannelPolicy: membership, lifecycle, recipient rules), `referee.py` (RefereeGuard: strip/assert referee-only content), `facts.py` (FactOwnershipPolicy: fact creation and VisibilityGrant creation with scope enforcement), `leakage_guard.py` (LeakageGuard: pre-flight checks before any player-visible or LLM operation). Added `tests/unit/test_scope_engine.py` (46 tests covering all scope types, awareness, hidden clues, stealth, secret objectives, leakage prevention).
- **Changes hosted at:** local only
- **Commit:** `Phase 4: Scope and Visibility Enforcement`

## Phase 5: Countdown Timer and Readiness Control

[#] Phase Startup | Started (PST): 2026-04-18 11:59 PM | Completed (PST): 2026-04-19 12:00 AM
[#] Implement timer creation for each turn | Started (PST): 2026-04-19 12:00 AM | Completed (PST): 2026-04-19 12:05 AM
[#] Implement timer expiration handling | Started (PST): 2026-04-19 12:05 AM | Completed (PST): 2026-04-19 12:09 AM
[#] Implement all-ready early completion | Started (PST): 2026-04-19 12:05 AM | Completed (PST): 2026-04-19 12:09 AM
[#] Implement timeout fallback action application | Started (PST): 2026-04-19 12:05 AM | Completed (PST): 2026-04-19 12:09 AM
[#] Implement pause and admin-stop controls | Started (PST): 2026-04-19 12:09 AM | Completed (PST): 2026-04-19 12:10 AM
[#] Implement a single public turn-control message | Started (PST): 2026-04-19 12:10 AM | Completed (PST): 2026-04-19 12:13 AM
[#] Implement inline controls for Ready, Pass, Ask Ref, Revise, and Submit | Started (PST): 2026-04-19 12:10 AM | Completed (PST): 2026-04-19 12:13 AM
[#] Implement timer message update logic | Started (PST): 2026-04-19 12:13 AM | Completed (PST): 2026-04-19 12:15 AM
[#] Add tests for expiry, early close, pause, and late submission | Started (PST): 2026-04-19 12:15 AM | Completed (PST): 2026-04-19 12:21 AM
[#] Phase End | Started (PST): 2026-04-19 12:21 AM | Completed (PST): 2026-04-19 12:22 AM

### Phase 5 Summary

- **Changes:** Created `server/timer/` package: `controller.py` (TimerController: create, start, check_expiry, trigger_early_close, pause, resume, stop; TimerRecord entity; TimerState machine), `integration.py` (process_tick: expiry→lock→fallback; process_early_close: all-ready→lock→resolve), `control_message.py` (ControlMessageBuilder: turn-control message text + inline keyboard with Ready/Pass/Ask Ref/Revise/Submit), `update_policy.py` (UpdatePolicy: interval + state-change edit throttle). Added `tests/unit/test_timer.py` (37 tests).
- **Changes hosted at:** local only
- **Commit:** `Phase 5: Countdown Timer and Readiness Control`

## Phase 6: Fast Local Model Routing Layer

[#] Phase Startup | Started (PST): 2026-04-19 12:23 AM | Completed (PST): 2026-04-19 12:24 AM
[#] Implement fast-model inference adapter | Started (PST): 2026-04-18 11:21 PM | Completed (PST): 2026-04-18 11:22 PM
[#] Define routing rules for simple and low-risk requests | Started (PST): 2026-04-18 11:22 PM | Completed (PST): 2026-04-18 11:22 PM
[#] Implement intent classification | Started (PST): 2026-04-18 11:22 PM | Completed (PST): 2026-04-18 11:23 PM
[#] Implement command normalization | Started (PST): 2026-04-18 11:22 PM | Completed (PST): 2026-04-18 11:23 PM
[#] Implement action packet extraction from raw player text | Started (PST): 2026-04-18 11:22 PM | Completed (PST): 2026-04-18 11:23 PM
[#] Implement likely-scope suggestion from message content | Started (PST): 2026-04-18 11:22 PM | Completed (PST): 2026-04-18 11:23 PM
[#] Implement short clarification-question generation | Started (PST): 2026-04-18 11:22 PM | Completed (PST): 2026-04-18 11:23 PM
[#] Implement recent-turn context summarization | Started (PST): 2026-04-18 11:22 PM | Completed (PST): 2026-04-18 11:23 PM
[#] Implement structured output validation and repair | Started (PST): 2026-04-18 11:22 PM | Completed (PST): 2026-04-18 11:23 PM
[#] Add latency, usage, and failure instrumentation | Started (PST): 2026-04-18 11:22 PM | Completed (PST): 2026-04-18 11:23 PM
[#] Add tests for extraction, repair, and fallback behavior | Started (PST): 2026-04-18 11:23 PM | Completed (PST): 2026-04-18 11:26 PM
[#] Phase End | Started (PST): 2026-04-18 11:26 PM | Completed (PST): 2026-04-18 11:26 PM

### Phase 6 Summary

- **Changes:** Created `models/fast/` package: `adapter.py` (OllamaFastAdapter: async Ollama HTTP wrapper, failure-safe, never raises), `instrumentation.py` (ModelCallLog dataclass), `router.py` (TaskType enum, is_fast_tier, is_main_tier_only, assert_fast_tier), `tasks.py` (classify_intent, normalize_command, extract_action_packet, suggest_scope, summarize_context, generate_clarification, repair_schema — all with structured JSON output, deterministic fallbacks, and per-call ModelCallLog). Added `tests/unit/test_fast_model.py` (35 tests). Added `httpx>=0.27` to `requirements.txt`.
- **Changes hosted at:** local only
- **Commit:** `Phase 6: Fast Local Model Routing Layer`

## Phase 7: Main Gameplay Model Integration

[#] Phase Startup | Started (PST): 2026-04-18 11:38 PM | Completed (PST): 2026-04-18 11:39 PM
[!] Implement Gemma 4 26B A4B inference adapter | Started (PST): | Completed (PST):
[#] Define prompt contract for narration | Started (PST): 2026-04-18 11:39 PM | Completed (PST): 2026-04-18 11:42 PM
[#] Define prompt contract for NPC dialogue | Started (PST): 2026-04-18 11:39 PM | Completed (PST): 2026-04-18 11:42 PM
[#] Define prompt contract for structured arbitration proposals | Started (PST): 2026-04-18 11:39 PM | Completed (PST): 2026-04-18 11:42 PM
[#] Implement scoped context assembly from canonical state | Started (PST): 2026-04-18 11:39 PM | Completed (PST): 2026-04-18 11:42 PM
[#] Implement schema validation and repair for model output | Started (PST): 2026-04-18 11:39 PM | Completed (PST): 2026-04-18 11:42 PM
[#] Implement fallback behavior for model timeout or invalid output | Started (PST): 2026-04-18 11:39 PM | Completed (PST): 2026-04-18 11:42 PM
[#] Add regression fixtures for representative game states | Started (PST): 2026-04-18 11:42 PM | Completed (PST): 2026-04-18 11:46 PM
[#] Add tests for prompt assembly, schema validation, and fallback behavior | Started (PST): 2026-04-18 11:42 PM | Completed (PST): 2026-04-18 11:46 PM
[#] Phase End | Started (PST): 2026-04-18 11:46 PM | Completed (PST): 2026-04-18 11:47 PM

### Phase 7 Summary

- **Changes:** Created `models/main/` package: `adapter.py` (OllamaMainAdapter: async Ollama HTTP wrapper for configurable main gameplay model, default "gemma3:27b", failure-safe, never raises), `router.py` (MainTaskType enum: scene_narration, npc_dialogue, combat_summary, ruling_proposal, social_arbitration, puzzle_flavor, unusual_action_interpretation; is_main_tier, assert_main_tier), `schemas.py` (output dataclasses + validate_* functions for all 6 structured task types, SchemaValidationError, SCHEMA_DESCRIPTIONS registry for fast-tier repair), `context.py` (SceneContext, PlayerContext, NpcContext, ActionContext, RecentHistory input containers; assemble_* prompt assembly functions for all task types; token budget helpers and history truncation), `fallback.py` (deterministic fallbacks for all task types, get_fallback() registry), `tasks.py` (narrate_scene, generate_npc_dialogue, summarize_combat, propose_ruling, arbitrate_social, generate_puzzle_flavor — each with 3-step failure pipeline: validate → fast-tier repair → deterministic fallback; full ModelCallLog instrumentation). Added `tests/fixtures/main_model_fixtures.py` (representative game state fixtures: tavern, dungeon, puzzle room scenes; Bram NPC; valid and invalid JSON responses for all task types) and `tests/unit/test_main_model.py` (103 tests). Also fixed pre-existing `F841` lint issue in `server/timer/controller.py`. The [!] OllamaMainAdapter requires a live gemma3:27b instance; all contracts, assembly, validation, and fallback logic is fully testable with mocks.
- **Changes hosted at:** local only
- **Commit:** `Phase 7: Main Gameplay Model Integration`

## Phase 8: Exploration Loop

[#] Phase Startup | Started (PST): 2026-04-18 11:48 PM | Completed (PST): 2026-04-18 11:49 PM
[#] Implement room and scene transition rules | Started (PST): 2026-04-18 11:49 PM | Completed (PST): 2026-04-18 11:50 PM
[#] Implement move, inspect, search, and interact actions | Started (PST): 2026-04-18 11:50 PM | Completed (PST): 2026-04-18 11:52 PM
[#] Implement environmental triggers and simple traps | Started (PST): 2026-04-18 11:52 PM | Completed (PST): 2026-04-18 11:54 PM
[#] Implement hidden clue discovery and scoped delivery | Started (PST): 2026-04-18 11:54 PM | Completed (PST): 2026-04-18 11:56 PM
[#] Implement object-state change handling | Started (PST): 2026-04-18 11:56 PM | Completed (PST): 2026-04-18 11:58 PM
[#] Implement revisit memory and scene recall behavior | Started (PST): 2026-04-18 11:58 PM | Completed (PST): 2026-04-19 12:00 AM
[#] Add a small connected-room scenario slice | Started (PST): 2026-04-19 12:00 AM | Completed (PST): 2026-04-19 12:02 AM
[#] Add tests for movement, interaction, trigger resolution, and clue delivery | Started (PST): 2026-04-19 12:02 AM | Completed (PST): 2026-04-19 12:02 AM
[#] Phase End | Started (PST): 2026-04-19 12:02 AM | Completed (PST): 2026-04-19 12:02 AM

### Phase 8 Summary

- **Changes:** Created `server/exploration/` package: `movement.py` (MovementEngine: check_move, move_character, list_exits — blocked exit support, character membership management), `actions.py` (ExplorationEngine: inspect, search, interact — KnowledgeFact creation, ObjectState model), `triggers.py` (TriggerEngine: evaluate, TriggerDefinition/TriggerKind/TriggerCondition/TriggerEffect dataclasses — on_enter, on_exit, on_search, on_inspect, on_interact, trap, on_any_action kinds), `clues.py` (ClueEngine: discover, share_clue, filter_discoverable — private/public/referee scope policies, discovery method gating), `objects.py` (ObjectStateEngine: apply_change, apply_batch, is_blocked_exit, derive_blocked_exits — predefined DOOR/CHEST/LEVER/PORTCULLIS_TRANSITIONS tables), `memory.py` (MemoryEngine: record_visit, recall_description, add_discovered_fact, has_character_visited, scenes_visited_by_character). Added `tests/fixtures/exploration_scenario.py` (three-room dungeon: Entrance Hall → Guard Room → Treasure Vault; fixed IDs for scenes, characters, items, objects, clues, triggers, scopes). Added `tests/unit/test_exploration.py` (97 tests across MovementEngine, ExplorationEngine, ObjectStateEngine, TriggerEngine, ClueEngine, MemoryEngine, and integration scenario). Total suite: 435 tests, all green.
- **Changes hosted at:** local only
- **Commit:** `Phase 8: Exploration Loop`

## Phase 9: NPC Social Loop

[#] Phase Startup | Started (PST): 2026-04-19 12:04 AM (PST) | Completed (PST): 2026-04-19 12:04 AM (PST)
[#] Implement NPC hard-state usage in scene resolution | Started (PST): 2026-04-19 12:04 AM (PST) | Completed (PST): 2026-04-19 12:07 AM (PST)
[#] Implement trust-by-player and party-stance fields in logic | Started (PST): 2026-04-19 12:04 AM (PST) | Completed (PST): 2026-04-19 12:07 AM (PST)
[#] Implement NPC memory-tag updates after interactions | Started (PST): 2026-04-19 12:04 AM (PST) | Completed (PST): 2026-04-19 12:07 AM (PST)
[#] Implement social action types for question, persuade, threaten, lie, and bargain | Started (PST): 2026-04-19 12:04 AM (PST) | Completed (PST): 2026-04-19 12:07 AM (PST)
[#] Implement secret NPC tells and private reactions | Started (PST): 2026-04-19 12:04 AM (PST) | Completed (PST): 2026-04-19 12:07 AM (PST)
[#] Implement NPC dialogue generation tied to structured state | Started (PST): 2026-04-19 12:04 AM (PST) | Completed (PST): 2026-04-19 12:07 AM (PST)
[#] Add at least two meaningful NPC interactions to starter content | Started (PST): 2026-04-19 12:07 AM (PST) | Completed (PST): 2026-04-19 12:12 AM (PST)
[#] Add tests for trust change, stance change, and memory persistence | Started (PST): 2026-04-19 12:07 AM (PST) | Completed (PST): 2026-04-19 12:12 AM (PST)
[#] Phase End | Started (PST): 2026-04-19 12:12 AM (PST) | Completed (PST): 2026-04-19 12:12 AM (PST)

### Phase 9 Summary

- **Changes:** Created `server/npc/` package: `trust.py` (TrustEngine: per-player trust deltas in -100..100, party stance derivation from mean trust, cooperative/hostile/fearful helpers, personality-modifier scaling), `tells.py` (NpcTellEngine: behavioral tell evaluation against tag/stance/action triggers, referee-only KnowledgeFact generation for trust status and private reactions), `dialogue.py` (DialogueContextBuilder: assembles DialogueContext from NPC state + action details including will_resist/is_evasive/can_be_threatened flags; public vs. referee dict split for scope-safe context delivery), `social.py` (SocialEngine: stateless resolution of question/persuade/threaten/lie/bargain; server-authoritative outcomes; delegates to TrustEngine + NpcTellEngine; produces trust deltas, memory tag updates, referee facts, and dialogue context for main model narration). Added `tests/fixtures/npc_social_scenario.py` (two NPC interaction scenarios: Mira the Innkeeper with secrecy/deception tells, Theron the Gate Guard with bribe/escalation tells). Added `tests/unit/test_npc_social.py` (90 tests covering all engines, all five action types, memory persistence, stance transitions, tell firing, dialogue context, and two full scenario integration sequences). Total suite: 525 tests, all green.
- **Changes hosted at:** local only
- **Commit:** `Phase 9: NPC Social Loop`

## Phase 10: Combat Loop

[#] Phase Startup | Started (PST): 2026-04-18 01:00 AM | Completed (PST): 2026-04-18 01:05 AM
[#] Define combat entry and exit conditions | Started (PST): 2026-04-18 01:05 AM | Completed (PST): 2026-04-18 01:10 AM
[#] Implement attack, move, defend, assist, use item, and ability actions | Started (PST): 2026-04-18 01:10 AM | Completed (PST): 2026-04-18 01:18 AM
[#] Implement grouped monster encounter behavior | Started (PST): 2026-04-18 01:18 AM | Completed (PST): 2026-04-18 01:25 AM
[#] Implement damage, armor, status effects, and defeat states | Started (PST): 2026-04-18 01:25 AM | Completed (PST): 2026-04-18 01:32 AM
[#] Implement morale and flee behavior | Started (PST): 2026-04-18 01:32 AM | Completed (PST): 2026-04-18 01:36 AM
[#] Implement combat visibility and awareness rules | Started (PST): 2026-04-18 01:36 AM | Completed (PST): 2026-04-18 01:42 AM
[#] Implement battlefield summaries for public turn posts | Started (PST): 2026-04-18 01:42 AM | Completed (PST): 2026-04-18 01:46 AM
[#] Add at least one combat encounter to starter content | Started (PST): 2026-04-18 01:46 AM | Completed (PST): 2026-04-18 01:50 AM
[#] Add tests for hit resolution, morale, grouped enemies, and end conditions | Started (PST): 2026-04-18 01:50 AM | Completed (PST): 2026-04-18 01:55 AM
[#] Phase End | Started (PST): 2026-04-18 01:55 AM | Completed (PST): 2026-04-18 02:00 AM

### Phase 10 Summary

- **Changes:** Created `server/combat/` package: `conditions.py` (CombatConditionEngine: entry/exit evaluation — engaged groups trigger combat; victory/annihilation/flee exit types), `actions.py` (CombatActionEngine: resolve_attack, resolve_defend, resolve_assist, resolve_use_item, resolve_use_ability, resolve_combat_move — all deterministic, status-effect-aware), `monsters.py` (MonsterBehaviorEngine: AI decision-making by behavior_mode with threat-table targeting; MoraleEngine: steady→shaken→routed transitions with leader_dead override, flee application), `resolution.py` (CombatResolutionEngine: character/group damage with armor, status effect management, poison ticks, defeat checks), `visibility.py` (CombatVisibilityEngine: awareness state machine with 8 transitions, visibility derived from awareness), `summaries.py` (BattlefieldSummaryBuilder: text assembly for public turn posts). Added `tests/fixtures/combat_scenario.py` (forest clearing: Kira + Dain vs goblin patrol + wolf pack). Added `tests/unit/test_combat.py` (89 tests covering all engines, full scenario integration). Total suite: 614 tests, all green.
- **Changes hosted at:** local only
- **Commit:** `Phase 10: Combat Loop`

## Phase 11: Side-Channels and Private Coordination

[#] Phase Startup | Started (PST): 2026-04-18 02:05 AM | Completed (PST): 2026-04-18 02:06 AM
[#] Define side-channel lifecycle and membership rules | Started (PST): 2026-04-18 02:06 AM | Completed (PST): 2026-04-18 02:10 AM
[#] Implement side-channel creation and closure | Started (PST): 2026-04-18 02:10 AM | Completed (PST): 2026-04-18 02:14 AM
[#] Implement DM-relay delivery for side-channel messages | Started (PST): 2026-04-18 02:14 AM | Completed (PST): 2026-04-18 02:17 AM
[#] Implement visibility isolation for side-channel content | Started (PST): 2026-04-18 02:17 AM | Completed (PST): 2026-04-18 02:20 AM
[#] Implement audit entries for side-channel activity | Started (PST): 2026-04-18 02:20 AM | Completed (PST): 2026-04-18 02:23 AM
[#] Add tests for side-channel secrecy and public prompt isolation | Started (PST): 2026-04-18 02:23 AM | Completed (PST): 2026-04-18 02:30 AM
[#] Phase End | Started (PST): 2026-04-18 02:30 AM | Completed (PST): 2026-04-18 02:35 AM

### Phase 11 Summary

- **Changes:** Extended `server/scope/side_channel.py` (SideChannelPolicy: add_member, remove_member with auto-close below MIN_MEMBERS, can_create with per-player active channel limit). Created `server/scope/side_channel_engine.py` (SideChannelEngine: create_channel with validation + entity production, close_channel with referee-only audit fact). Created `server/scope/side_channel_audit.py` (SideChannelAuditor: record_creation, record_message, record_closure — all producing referee-only KnowledgeFacts with [side_channel_audit] prefix). Extended `bot/outbound.py` (send_side_channel: DM relay to all members except sender, formatted with channel label). Extended `server/scope/engine.py` (ScopeEngine: assert_no_side_channel_leakage pre-flight check for non-member fact delivery). Added `tests/fixtures/side_channel_scenario.py` (three-player campaign with fixed IDs: Alice+Bob channel, Carol as outsider). Added `tests/unit/test_side_channels.py` (58 tests covering policy lifecycle, engine creation/closure, DM relay, visibility isolation, audit facts, and full lifecycle integration). Total suite: 672 tests, all green.
- **Changes hosted at:** local only
- **Commit:** `Phase 11: Side-Channels and Private Coordination`

## Phase 12: Split Party and Multi-Scene Handling

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Implement explicit scene membership for players and NPCs | Started (PST): | Completed (PST):
[ ] Implement multiple active scene contexts in a campaign | Started (PST): | Completed (PST):
[ ] Implement scoped prompts by subgroup | Started (PST): | Completed (PST):
[ ] Implement coordinated timing policy for split-party play | Started (PST): | Completed (PST):
[ ] Implement delayed information propagation between subgroups | Started (PST): | Completed (PST):
[ ] Add split-party scenario cases and tests | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 13: Scenario Authoring Format

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Define scenario file structure and schema | Started (PST): | Completed (PST):
[ ] Define scene, exit, item, NPC, monster, puzzle, and trigger formats | Started (PST): | Completed (PST):
[ ] Define public versus hidden content authoring rules | Started (PST): | Completed (PST):
[ ] Implement scenario validation tools | Started (PST): | Completed (PST):
[ ] Implement scenario import and load flow | Started (PST): | Completed (PST):
[ ] Create starter scenario package in the new format | Started (PST): | Completed (PST):
[ ] Add validation tests and content fixtures | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 14: Prompt Contracts and Context Assembly

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Define fast-model prompt contracts | Started (PST): | Completed (PST):
[ ] Define Gemma gameplay prompt contracts | Started (PST): | Completed (PST):
[ ] Define context assembly rules for narration, arbitration, dialogue, and summaries | Started (PST): | Completed (PST):
[ ] Define prompt size limits and truncation policies | Started (PST): | Completed (PST):
[ ] Define schema validation and output-repair rules | Started (PST): | Completed (PST):
[ ] Add prompt-assembly regression fixtures | Started (PST): | Completed (PST):
[ ] Add tests for scope-safe context assembly and leakage prevention | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 15: Reliability, Recovery, and Observability

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Implement structured logging and trace IDs | Started (PST): | Completed (PST):
[ ] Implement retry handling for Telegram delivery failures | Started (PST): | Completed (PST):
[ ] Implement duplicate-delivery and replay protection | Started (PST): | Completed (PST):
[ ] Implement model timeout and recovery behavior | Started (PST): | Completed (PST):
[ ] Implement crash-safe turn recovery | Started (PST): | Completed (PST):
[ ] Implement admin diagnostics for stuck turns and failed deliveries | Started (PST): | Completed (PST):
[ ] Implement metrics for latency, routing, and failures | Started (PST): | Completed (PST):
[ ] Add failure-path tests for retries, duplicates, and restart recovery | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 16: Internal Playtest Release

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Prepare internal playtest build locally | Started (PST): | Completed (PST):
[ ] Select and stage starter scenario for playtest | Started (PST): | Completed (PST):
[ ] Run structured multiplayer playtest session | Started (PST): | Completed (PST):
[ ] Capture logs, transcripts, and issues | Started (PST): | Completed (PST):
[ ] Categorize defects by timing, clarity, leakage, routing, and rules | Started (PST): | Completed (PST):
[ ] Patch highest-severity issues found in playtest | Started (PST): | Completed (PST):
[ ] Add regression tests for discovered failures | Started (PST): | Completed (PST):
[ ] Update architecture, prompts, and phase notes from findings | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 17: Mini App Foundation

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Define Mini App architecture and launch flow | Started (PST): | Completed (PST):
[ ] Implement Telegram-linked Mini App shell | Started (PST): | Completed (PST):
[ ] Implement read-only character sheet view | Started (PST): | Completed (PST):
[ ] Implement read-only inventory view | Started (PST): | Completed (PST):
[ ] Implement read-only turn recap view | Started (PST): | Completed (PST):
[ ] Add Mini App state-hydration tests | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 18: Mini App Gameplay Utilities

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Implement draft action builder | Started (PST): | Completed (PST):
[ ] Implement private inbox view | Started (PST): | Completed (PST):
[ ] Implement side-channel management UI | Started (PST): | Completed (PST):
[ ] Implement quest log and clue journal views | Started (PST): | Completed (PST):
[ ] Implement optional map or scene view | Started (PST): | Completed (PST):
[ ] Add Mini App submission-flow tests | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 19: Content Expansion and Quality Pass

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Add additional starter scenarios | Started (PST): | Completed (PST):
[ ] Add more puzzle patterns and trigger types | Started (PST): | Completed (PST):
[ ] Add more NPC archetypes and monster templates | Started (PST): | Completed (PST):
[ ] Improve narration style guidance and pacing rules | Started (PST): | Completed (PST):
[ ] Expand scenario validation coverage | Started (PST): | Completed (PST):
[ ] Add regression cases from long-session transcripts | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 20: Pre-Release Stabilization

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Review open bugs and severity | Started (PST): | Completed (PST):
[ ] Freeze nonessential feature work | Started (PST): | Completed (PST):
[ ] Harden onboarding, diagnostics, and failure messages | Started (PST): | Completed (PST):
[ ] Review privacy, visibility, and routing safety | Started (PST): | Completed (PST):
[ ] Run extended campaigns and full regression suite | Started (PST): | Completed (PST):
[ ] Patch release blockers | Started (PST): | Completed (PST):
[ ] Update STARTUP.md and core docs to match the actual system | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):
