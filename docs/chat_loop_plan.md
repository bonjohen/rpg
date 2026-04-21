# Chat-Driven Game Loop — Implementation Plan

**Source documents:** `docs/chat_loop_pdr.md`, `docs/chat_loop_test_plan.md`

## Work Queue Instructions

### State Transitions

Open  ──>  Started  ──>  Completed
              │
              └──>  Blocked  ──>  Started  ──>  Completed

- **Open**: Not yet begun.
- **Started**: Actively in progress. Record the start datetime (PST).
- **Completed**: Done and verified. Record the completion datetime (PST).
- **Blocked**: Cannot proceed; note the blocker in the description.

### Commit Protocol

1. Work through all tasks in a phase.
2. When every task reaches Completed, write the Phase Summary.
3. Stage and commit all changes for the phase. Do not push.
4. Proceed immediately to the next phase.

## Technology Stack (Additive)

| Concern | Choice |
|---|---|
| Timer scheduling | PTB `job_queue.run_once()` (replaces poll-based timer for turn expiry) |
| Turn-control UI | PTB `InlineKeyboardMarkup` + `CallbackQueryHandler` |
| Result delivery | New `bot/delivery.py` module using existing `bot/outbound.py` functions |

---

## Phase 1: Scene Introduction and Scenario Metadata

**Goal:** `/newgame` and `/join` produce immersive narrative output instead of dry status messages. Players understand what the game is about and where they are.
**Depends on:** Nothing (first phase).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 1.1 | Completed | 2026-04-20 04:15 PM | 2026-04-20 04:17 PM | Add `title: str = ""` and `description: str = ""` fields to `ScenarioLoadResult` in `scenarios/loader.py`. Populate from manifest in `load_from_manifest()`. |
| 1.2 | Completed | 2026-04-20 04:17 PM | 2026-04-20 04:22 PM | Return `ScenarioLoadResult` from `orchestrator.load_scenario()` (currently returns `bool`). Store title/description on orchestrator or pass back to caller. |
| 1.3 | Completed | 2026-04-20 04:22 PM | 2026-04-20 04:26 PM | Rewrite `cmd_newgame` in `bot/commands.py`: post scenario title, description, starting scene description+exits. End with "Players: send /join to enter the game." |
| 1.4 | Completed | 2026-04-20 04:26 PM | 2026-04-20 04:32 PM | Rewrite `cmd_join` in `bot/commands.py`: after `add_player()`, post full scene description (reuse `/scene` format). Announce "{name} has entered {scene.name}." to group via `send_public()`. |
| 1.5 | Completed | 2026-04-20 04:32 PM | 2026-04-20 04:40 PM | Write tests in `tests/unit/test_scene_introduction.py`: 5 tests per test plan §3.6 (newgame shows title/description/scene, join shows scene, join announces arrival, load result carries metadata). |
| 1.6 | Completed | 2026-04-20 04:40 PM | 2026-04-20 04:48 PM | Run `pytest`, `ruff check .`, `ruff format --check .`. All green. |
| 1.7 | Completed | 2026-04-20 04:48 PM | 2026-04-20 04:50 PM | Stage and commit: "Phase 1: Scene introduction on /newgame and /join" |

### Phase 1 Summary

- **Changes:** Added `title`/`description` fields to `ScenarioLoadResult`. Changed `orchestrator.load_scenario()` to return `ScenarioLoadResult | None`. Rewrote `cmd_newgame` to post narrative intro (title, description, starting scene, exits). Rewrote `cmd_join` to show full scene description and announce arrival via `send_public()`. 6 new tests in `tests/unit/test_scene_introduction.py`. Fixed existing test in `test_bugfix_p0.py` for new return type. 1485 tests pass, lint clean.
- **Changes hosted at:** local commit `2ff19e1`
- **Commit:** `Phase 1: Scene introduction on /newgame and /join`

---

## Phase 2: Bot Handler Dispatch and Orchestrator Wiring

**Goal:** Player messages in the group chat and DMs are dispatched to the orchestrator instead of being dropped. The core design doc Section 6 flow begins to work.
**Depends on:** Phase 1 (join must work for handler tests to have registered players).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 2.1 | Completed | 2026-04-20 04:52 PM | 2026-04-20 04:56 PM | Wire `_handle_group_message` in `bot/handlers.py`: parse, route, if `play_action` → look up player_id → call `orchestrator.handle_player_message()` → route `DispatchResult` to `send_public()`. Handle `UnknownUserError` gracefully. |
| 2.2 | Completed | 2026-04-20 04:56 PM | 2026-04-20 05:00 PM | Wire `_handle_private_message` in `bot/handlers.py`: look up player_id → call `orchestrator.handle_player_message(is_private=True)` → route response to `send_private()`. Handle onboarding and unknown user. |
| 2.3 | Completed | 2026-04-20 05:00 PM | 2026-04-20 05:03 PM | Fix idempotency key in `handle_player_message` (`game_loop.py`): include `turn_window_id` (or `'no_turn'`) in hash key to prevent cross-turn collisions. |
| 2.4 | Completed | 2026-04-20 05:03 PM | 2026-04-20 05:12 PM | Write tests in `tests/unit/test_bot_handlers.py`: 9 tests per test plan §3.1 (dispatch to orchestrator, response routing, error handling, unknown user). |
| 2.5 | Completed | 2026-04-20 05:03 PM | 2026-04-20 05:15 PM | Write tests in `tests/unit/test_orchestrator_message.py`: 9 tests per test plan §3.2 (action/question/chat intent, dedup, cross-turn dedup, fallback). |
| 2.6 | Completed | 2026-04-20 05:15 PM | 2026-04-20 05:18 PM | Run `pytest`, `ruff check .`, `ruff format --check .`. All green. |
| 2.7 | Completed | 2026-04-20 05:18 PM | 2026-04-20 05:20 PM | Stage and commit: "Phase 2: Bot handler dispatch and orchestrator wiring" |

### Phase 2 Summary

- **Changes:** Wired `_handle_group_message` and `_handle_private_message` in `bot/handlers.py` to dispatch to `orchestrator.handle_player_message()`. Fixed idempotency key in `game_loop.py` to include `turn_window_id` (PDR §5). Added graceful error handling for `UnknownUserError` and orchestrator exceptions. 18 new tests across `test_bot_handlers.py` and `test_orchestrator_message.py`. 1503 tests pass.
- **Changes hosted at:** local commit `f5e010a`
- **Commit:** `Phase 2: Bot handler dispatch and orchestrator wiring`

---

## Phase 3: Auto-Turn Management

**Goal:** Turns open automatically when a player acts and no turn is active. Turns resolve automatically when all players are ready. No more `/nextturn` required for normal play.
**Depends on:** Phase 2 (handler dispatch must work).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 3.1 | Completed | 2026-04-20 05:22 PM | 2026-04-20 05:28 PM | Add `ensure_turn_open(scene_id) -> TurnWindow` to orchestrator. Check for existing active turn inside DB session (race condition guard). If none, call `open_turn()`. Return the turn window. |
| 3.2 | Completed | 2026-04-20 05:22 PM | 2026-04-20 05:28 PM | Add race condition guard inside `open_turn()`: within the session, check if `scene.active_turn_window_id` already set → return existing TurnWindow if found. |
| 3.3 | Completed | 2026-04-20 05:28 PM | 2026-04-20 05:34 PM | Wire `ensure_turn_open` into `_handle_as_action()`: call before `submit_action()`. |
| 3.4 | Completed | 2026-04-20 05:28 PM | 2026-04-20 05:34 PM | Enforce ordering invariant: when auto-opening, the handler must post scene description + turn-control message BEFORE acknowledging the action. Update handler in `bot/handlers.py` to post scene context when `ensure_turn_open` creates a new turn. |
| 3.5 | Completed | 2026-04-20 05:28 PM | 2026-04-20 05:36 PM | Add auto-resolve on all-ready: after `submit_action()` returns, check turn window state. If `all_ready`, trigger resolution pipeline (resolve → narrate → deliver). Wire in handler. |
| 3.6 | Completed | 2026-04-20 05:36 PM | 2026-04-20 05:42 PM | Write tests in `tests/unit/test_auto_turn.py`: 7 tests per test plan §3.3 (create when none, return existing, race guard, auto-resolve, scene posted first, nextturn still works). |
| 3.7 | Completed | 2026-04-20 05:42 PM | 2026-04-20 05:48 PM | Run `pytest`, `ruff check .`, `ruff format --check .`. All green. |
| 3.8 | Completed | 2026-04-20 05:48 PM | 2026-04-20 05:50 PM | Stage and commit: "Phase 3: Auto-turn management with ordering invariant" |

### Phase 3 Summary

- **Changes:** Added `ensure_turn_open()` with race condition guard. Added race guard inside `open_turn()`. Wired auto-open into `_handle_as_action()`. Added auto-resolve on all-ready with `turn_resolved`/`turn_log_entry` fields on `DispatchResult`. 7 new tests. 1510 total passing.
- **Changes hosted at:** local commit `440eed9`
- **Commit:** `Phase 3: Auto-turn management with ordering invariant`

---

## Phase 4: Rich Narration and Result Delivery

**Goal:** After turn resolution, the main model generates rich narrative text (not concatenated strings), and results are delivered to Telegram — public narration to the group, private facts to individual DMs.
**Depends on:** Phase 3 (auto-resolve triggers the delivery pipeline).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 4.1 | Completed | 2026-04-20 05:52 PM | 2026-04-20 05:58 PM | Create `bot/delivery.py` with `generate_narration(orchestrator, turn_log_entry, scene, committed_actions) -> str`. Uses `ContextAssembler` for scoped prompts, calls `narrate_scene()` or `summarize_combat()` based on scene state, calls `generate_npc_dialogue()` if NPCs involved. Falls back to `turn_log_entry.narration` on failure. |
| 4.2 | Completed | 2026-04-20 05:52 PM | 2026-04-20 05:58 PM | Add `deliver_turn_results(orchestrator, turn_log_entry, scene, bot, config, registry)` to `bot/delivery.py`. Posts narration via `send_public()`. Queries private-referee facts for this turn. Sends each to owning player via `send_private_by_player_id()`. Logs and continues on partial DM failure. |
| 4.3 | Completed | 2026-04-20 05:58 PM | 2026-04-20 06:02 PM | Wire `deliver_turn_results` into the auto-resolve path in `bot/handlers.py` (called after `resolve_turn()` in both the all-ready path and the timer-expiry path). |
| 4.4 | Completed | 2026-04-20 05:58 PM | 2026-04-20 06:10 PM | Write tests in `tests/unit/test_narration_pipeline.py`: 7 tests per test plan §3.4 (main model called, context assembler used, no referee facts, fallback on failure/timeout, combat uses summarize_combat, NPC dialogue). |
| 4.5 | Completed | 2026-04-20 05:58 PM | 2026-04-20 06:10 PM | Write tests in `tests/unit/test_delivery.py`: 7 tests per test plan §3.5 (public sent, private facts to owner only, partial failure continues, control message edited, empty turn no DMs). |
| 4.6 | Completed | 2026-04-20 06:10 PM | 2026-04-20 06:14 PM | Run `pytest`, `ruff check .`, `ruff format --check .`. All green. |
| 4.7 | Started | 2026-04-20 06:14 PM | | Stage and commit: "Phase 4: Rich narration via main model and result delivery" |

### Phase 4 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Phase 4: Rich narration via main model and result delivery`

---

## Phase 5: Inline Keyboard and Callback Queries

**Goal:** Turn-control messages appear with Ready/Pass buttons. Players get visual feedback on turn state. Buttons trigger action submission.
**Depends on:** Phase 4 (delivery pipeline must exist to edit control messages on resolution).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 5.1 | Open | | | Add turn-control message posting when a turn opens: scene description + "What do you do?" + InlineKeyboard [[Ready][Pass]]. Store `message_id` in orchestrator's in-memory state (not on TurnWindow entity — it's Telegram-specific). Post via `send_public()` or `bot.send_message()` with `reply_markup`. |
| 5.2 | Open | | | Add `CallbackQueryHandler` in `bot/handlers.py` for Ready/Pass button presses. Look up player, submit hold action with appropriate state, answer callback query. Reject presses from non-players or after turn resolved. |
| 5.3 | Open | | | Update control message on each action submission: edit text to show "Waiting for: {remaining players}". |
| 5.4 | Open | | | On turn resolution, edit control message to show "Turn N resolved." and remove keyboard. Wire into `deliver_turn_results`. |
| 5.5 | Open | | | Add `make_callback_query()` to `tests/fixtures/telegram_builders.py`. |
| 5.6 | Open | | | Write tests in `tests/unit/test_callback_queries.py`: 7 tests per test plan §3.7 (control message posted, ready/pass submit actions, non-player rejected, post-resolve rejected, message updates, callback answered). |
| 5.7 | Open | | | Run `pytest`, `ruff check .`, `ruff format --check .`. All green. |
| 5.8 | Open | | | Stage and commit: "Phase 5: Inline keyboard turn controls" |

### Phase 5 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Phase 5: Inline keyboard turn controls`

---

## Phase 6: Timer Expiry via Job Queue

**Goal:** Turn timer fires automatically via PTB's job_queue, triggering resolution and delivery without manual `/forceresolve`.
**Depends on:** Phase 4 (delivery pipeline), Phase 5 (control message editing).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 6.1 | Open | | | When a turn opens (in handler, after `ensure_turn_open` creates a new turn), schedule a job via `context.job_queue.run_once(callback, when=duration_seconds)`. Pass `turn_window_id` in `job.data`. |
| 6.2 | Open | | | Implement timer job callback: load turn window, check if still open (skip if already resolved), call `resolve_turn()`, call `generate_narration()`, call `deliver_turn_results()`. The callback receives `CallbackContext` with `.bot` and `.application.bot_data`. |
| 6.3 | Open | | | Cancel the scheduled job when a turn resolves early (all-ready path). Store the `Job` reference and call `job.schedule_removal()`. |
| 6.4 | Open | | | Write tests in `tests/unit/test_timer_job.py`: 5 tests per test plan §3.8 (job scheduled, expired turn resolved, already-resolved skipped, fallback actions generated, bot context available). |
| 6.5 | Open | | | Run `pytest`, `ruff check .`, `ruff format --check .`. All green. |
| 6.6 | Open | | | Stage and commit: "Phase 6: Timer expiry auto-resolve via PTB job queue" |

### Phase 6 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Phase 6: Timer expiry auto-resolve via PTB job queue`

---

## Phase 7: Question Intent Handling

**Goal:** Player questions (especially private DMs) get meaningful AI responses instead of a canned string.
**Depends on:** Phase 2 (handler dispatch), Phase 4 (main model calling pattern).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 7.1 | Open | | | Replace canned "question" response in `handle_player_message` (`game_loop.py`). Call `propose_ruling()` with the question text, player's character state, and scene context. Return the ruling's response text. |
| 7.2 | Open | | | Ensure private questions stay private: if `is_private=True`, set `scope="private"` on `DispatchResult`. Handler routes to `send_private()`. |
| 7.3 | Open | | | Add fallback: if `propose_ruling()` fails, return "The referee considers your question... Try rephrasing or take an action instead." |
| 7.4 | Open | | | Tests already specified in §3.2 of test plan (`test_question_intent_calls_ruling`, `test_question_private_stays_private`). Verify they pass. |
| 7.5 | Open | | | Run `pytest`, `ruff check .`, `ruff format --check .`. All green. |
| 7.6 | Open | | | Stage and commit: "Phase 7: Question intent handling via propose_ruling" |

### Phase 7 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Phase 7: Question intent handling via propose_ruling`

---

## Phase 8: End-to-End Integration Tests and Scenario Playthrough

**Goal:** Prove all PDR §9 verification criteria work end-to-end. Validate with a scripted goblin_caves playthrough.
**Depends on:** All prior phases.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 8.1 | Open | | | Write `tests/integration/test_chat_turn_e2e.py`: 6 tests per test plan §4.1 (full turn via chat, multi-player, private question, timeout fallback, consecutive turns, private fact delivery). |
| 8.2 | Open | | | Write `tests/integration/test_goblin_caves_playthrough.py`: 6 tests per test plan §4.2 (newgame intro, join cave entrance, pick up torch, enter cave triggers lookout, talk to Grix, private awareness check). |
| 8.3 | Open | | | Add any needed fixture builders per test plan §6 (`make_mock_orchestrator_with_scenario`, `make_mock_fast_adapter`, `make_mock_main_adapter`, `make_mock_job_queue`). |
| 8.4 | Open | | | Run full suite: `pytest`. Verify all 1,479 existing tests still pass plus ~73 new tests. |
| 8.5 | Open | | | Run `ruff check .`, `ruff format --check .`. All green. |
| 8.6 | Open | | | **Critical review: walk through every PDR §9 verification criterion against the test traceability matrix (test plan §9). Confirm each criterion has a passing test.** |
| 8.7 | Open | | | Update `docs/release_readiness.md`: check off "10-turn scripted session" and "No scope leakage in extended session" criteria if applicable. |
| 8.8 | Open | | | Update `STARTUP.md` with current phase status and test count. |
| 8.9 | Open | | | Stage and commit: "Phase 8: E2E integration tests and goblin caves playthrough" |

### Phase 8 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Phase 8: E2E integration tests and goblin caves playthrough`

---

## Phase 9: Documentation and Cleanup

**Goal:** All docs reflect the new chat-driven game loop. No stale references to slash-command-only play.
**Depends on:** Phase 8.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 9.1 | Open | | | Update `README.md`: describe chat-driven gameplay, not slash-command-driven. Add "How to Play" section. |
| 9.2 | Open | | | Update `docs/architecture.md`: mark bot handler stubs as resolved. Update flow diagram. |
| 9.3 | Open | | | Update `STARTUP.md`: current phase status, test count, known defects. |
| 9.4 | Open | | | Update `docs/testing.md`: add new test file descriptions to fixture/layer lists. |
| 9.5 | Open | | | Update `docs/release_readiness.md` with final test count and criteria status. |
| 9.6 | Open | | | Remove or update stub comments in `bot/handlers.py` ("Phase 7+" comments). |
| 9.7 | Open | | | Run full suite one final time: `pytest`, `ruff check .`, `ruff format --check .`. |
| 9.8 | Open | | | Stage and commit: "Phase 9: Documentation update for chat-driven game loop" |

### Phase 9 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Phase 9: Documentation update for chat-driven game loop`
