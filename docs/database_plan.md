# Central Database Integration — Implementation Plan

**Source document:** `docs/database_design.md`

## Work Queue Instructions

### State Transitions

Open  ──>  Started  ──>  Completed
              │
              └──>  Blocked  ──>  Started  ──>  Completed

- **Open**: Not yet begun.
- **Started**: Actively in progress. Record the start datetime (PST).
- **Completed**: Done and verified. Record the completion datetime (PST).
- **Blocked**: Cannot proceed; note the blocker in the description. Onlu a human can unblock an item.

### Commit Protocol

1. Work through all tasks in a phase.
2. When every task reaches Completed, write the Phase Summary.
3. Stage and commit all changes for the phase. Do not push.
4. Proceed immediately to the next phase.

## Technology Stack (Additive)

| Concern | Choice |
|---|---|
| ORM | SQLAlchemy 2.0+ (already in requirements.txt) |
| Database (dev/single-server) | SQLite via `sqlite:///rpg.db` |
| Database (future) | PostgreSQL via `DATABASE_URL` |
| Async bridge | `asyncio.loop.run_in_executor` wrapping synchronous sessions |
| Session pattern | Session-per-request via context manager |
| Concurrency control | Optimistic locking via `version` column on TurnWindow |

---

## Phase 1: Database Foundation and SQLite Pragmas

**Goal:** The database engine is production-ready with proper pragmas, the TurnWindow entity has a version column for optimistic locking, and a test fixture helper exists for all future phases. No orchestrator changes yet.

**Depends on:** Nothing (first phase).

| # | Status | Started (PST) | Completed (PST) | Description |
|---|--------|---------------|------------------|-------------|
| 1.1 | Completed | 2026-04-19 11:00 AM | 2026-04-19 11:02 AM | Update `server/storage/db.py`: add `@event.listens_for(engine, "connect")` handler that sets `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`, `PRAGMA busy_timeout=5000`, `PRAGMA synchronous=NORMAL` for SQLite engines only |
| 1.2 | Completed | 2026-04-19 11:02 AM | 2026-04-19 11:03 AM | Add `version: int = 1` field to `TurnWindow` dataclass in `server/domain/entities.py` |
| 1.3 | Completed | 2026-04-19 11:02 AM | 2026-04-19 11:03 AM | Add `version: Mapped[int]` column to `TurnWindowRow` in `server/storage/models.py` with `default=1` |
| 1.4 | Completed | 2026-04-19 11:03 AM | 2026-04-19 11:05 AM | Update `_turn_window_from_row()` and `TurnWindowRepo.save()` in `server/storage/repository.py` to map the `version` field |
| 1.5 | Completed | 2026-04-19 11:03 AM | 2026-04-19 11:05 AM | Add optimistic-lock-aware `save_with_version_check()` method to `TurnWindowRepo` that uses `WHERE version = :expected` and raises `StaleStateError` if zero rows affected. Also added `list_open()` method. |
| 1.6 | Completed | 2026-04-19 11:05 AM | 2026-04-19 11:05 AM | Create `server/storage/errors.py` with `StaleStateError` exception class |
| 1.7 | Completed | 2026-04-19 11:05 AM | 2026-04-19 11:06 AM | Create `tests/fixtures/db_helpers.py` with `create_test_engine()` and `create_test_session_factory()` helpers using `sqlite:///:memory:` |
| 1.8 | Completed | 2026-04-19 11:06 AM | 2026-04-19 11:06 AM | Add `*.db`, `*.db-shm`, `*.db-wal` to `.gitignore` |
| 1.9 | Completed | 2026-04-19 11:06 AM | 2026-04-19 11:10 AM | Add 14 unit tests for SQLite pragma application, version column round-trip, `save_with_version_check` happy path and stale-state rejection, `list_open`, and db_helpers |
| 1.10 | Completed | 2026-04-19 11:10 AM | 2026-04-19 11:12 AM | Full test suite: 1306 passed. Lint clean. |
| 1.11 | Completed | 2026-04-19 11:12 AM | 2026-04-19 11:15 AM | Phase End: update `docs/phase_status.md`, `STARTUP.md`, commit locally |

### Phase 1 Summary

- **Changes:** Updated `server/storage/db.py` (SQLite pragmas: WAL, foreign_keys, busy_timeout, synchronous). Added `version` field to `TurnWindow` entity and `TurnWindowRow` ORM model. Added `save_with_version_check()` and `list_open()` to `TurnWindowRepo`. Created `server/storage/errors.py` (`StaleStateError`). Created `tests/fixtures/db_helpers.py` (test engine/session factory). Added `*.db` patterns to `.gitignore`. Added `tests/unit/test_database_foundation.py` (14 tests). Total: 1306 tests, all green, lint clean.
- **Changes hosted at:** local only
- **Commit:** `Database Phase 1: Foundation, pragmas, optimistic locking, test fixtures`

---

## Phase 2: Session Scope and Orchestrator Constructor

**Goal:** The `GameOrchestrator` accepts a `SessionFactory`, exposes a `_session_scope()` context manager, and has a synchronous `_run_in_session()` helper. The in-memory dicts still exist and are still used — this phase only adds the plumbing, it does not migrate any state access.

**Depends on:** Phase 1.

| # | Status | Started (PST) | Completed (PST) | Description |
|---|--------|---------------|------------------|-------------|
| 2.1 | Completed | 2026-04-19 12:30 PM | 2026-04-19 12:32 PM | Add `session_factory: sessionmaker | None = None` parameter to `GameOrchestrator.__init__()` in `server/orchestrator/game_loop.py` |
| 2.2 | Completed | 2026-04-19 12:30 PM | 2026-04-19 12:32 PM | Implement `_session_scope()` context manager on `GameOrchestrator` that yields a `Session`, commits on clean exit, rolls back on exception |
| 2.3 | Completed | 2026-04-19 12:30 PM | 2026-04-19 12:32 PM | Implement `_run_in_session(fn)` helper that wraps a sync callable in `asyncio.get_running_loop().run_in_executor(None, fn)` for use from async methods |
| 2.4 | Completed | 2026-04-19 12:32 PM | 2026-04-19 12:33 PM | Update `server/api/app.py` `create_api_app()` to optionally accept and store a `session_factory` on the orchestrator |
| 2.5 | Completed | 2026-04-19 12:33 PM | 2026-04-19 12:33 PM | All 7 test files already work — `session_factory` defaults to `None`, preserving existing behavior with no changes needed |
| 2.6 | Completed | 2026-04-19 12:33 PM | 2026-04-19 12:38 PM | Add 8 unit tests in `tests/unit/test_database_session_scope.py`: commit/rollback for `_session_scope`, RuntimeError without factory, async commit/rollback for `_run_in_session` |
| 2.7 | Completed | 2026-04-19 12:38 PM | 2026-04-19 12:40 PM | Full test suite: 1314 passed. Lint and format clean. |
| 2.8 | Completed | 2026-04-19 12:40 PM | 2026-04-19 12:42 PM | Phase End: update `docs/phase_status.md`, `STARTUP.md`, commit locally |

### Phase 2 Summary

- **Changes:** Added `session_factory` parameter to `GameOrchestrator.__init__()`. Implemented `_session_scope()` context manager (commit on clean exit, rollback on exception) and `_run_in_session(fn)` async helper (wraps sync callable in executor). Updated `create_api_app()` to optionally accept and forward a `session_factory`. Added `tests/unit/test_database_session_scope.py` (8 tests). Total: 1314 tests, all green, lint clean.
- **Changes hosted at:** local only
- **Commit:** `Database Phase 2: Session scope and orchestrator constructor`

---

## Phase 3: Migrate Scenario Loading and Player Management

**Goal:** `load_scenario()` and `add_player()` write to the database through repositories. The in-memory dicts for campaigns, scenes, players, characters, NPCs, monster groups, items, puzzles, quests, knowledge facts, scopes, and side channels are removed. All reads go through repos. Query helpers (`get_player_character`, `get_player_scene`, `get_scene_players`, etc.) use repos.

**Depends on:** Phase 2.

| # | Status | Started (PST) | Completed (PST) | Description |
|---|--------|---------------|------------------|-------------|
| 3.1 | Completed | 2026-04-19 01:00 PM | 2026-04-19 01:20 PM | Rewrite `load_scenario()` to open a session, save all entities via repos (CampaignRepo, SceneRepo, NPCRepo, MonsterGroupRepo, InventoryItemRepo, PuzzleStateRepo, QuestStateRepo, KnowledgeFactRepo, ConversationScopeRepo), and commit atomically |
| 3.2 | Completed | 2026-04-19 01:20 PM | 2026-04-19 01:35 PM | Rewrite `add_player()` to open a session, save Player + Character + private ConversationScope + updated Scene via repos, and commit atomically |
| 3.3 | Completed | 2026-04-19 01:35 PM | 2026-04-19 01:45 PM | Rewrite `get_player_character()` to use `CharacterRepo.get_for_player()` |
| 3.4 | Completed | 2026-04-19 01:45 PM | 2026-04-19 01:50 PM | Rewrite `get_player_scene()` to use `CharacterRepo.get_for_player()` + `SceneRepo.get()` |
| 3.5 | Completed | 2026-04-19 01:50 PM | 2026-04-19 01:55 PM | Rewrite `get_scene_players()` to use `CharacterRepo.list_for_scene()` + `PlayerRepo.get()` |
| 3.6 | Completed | 2026-04-19 01:55 PM | 2026-04-19 02:00 PM | Rewrite `_find_starting_scene_id()` to use `SceneRepo.list_for_campaign()` |
| 3.7 | Completed | 2026-04-19 02:00 PM | 2026-04-19 02:05 PM | Rewrite `_get_private_scope_id()` to use `ConversationScopeRepo.get_private_scope_for_player()` |
| 3.8 | Completed | 2026-04-19 02:05 PM | 2026-04-19 02:15 PM | Rewrite `_get_or_create_public_scope()` to use `ConversationScopeRepo.get_public_scope()` with fallback create+save |
| 3.9 | Completed | 2026-04-19 02:15 PM | 2026-04-19 02:30 PM | Remove the in-memory dicts: `self.campaign`, `self.scenes`, `self.characters`, `self.players`, `self.npcs`, `self.monster_groups`, `self.items`, `self.puzzles`, `self.quests`, `self.knowledge_facts`, `self.scopes`, `self.side_channels`. Keep `self.triggers` (loaded from scenario, not persisted), `self.drafts`, `self.inbox_read`, `self.channel_messages`, `self.timers` |
| 3.10 | Completed | 2026-04-19 02:30 PM | 2026-04-19 02:35 PM | Store `self.campaign_id: str | None` instead of `self.campaign: Campaign | None` — the orchestrator holds only the ID; the full entity is loaded from the repo when needed |
| 3.11 | Completed | 2026-04-19 02:35 PM | 2026-04-19 07:10 PM | Update all orchestrator tests (`tests/integration/test_playtest_setup.py`, `test_playtest_session.py`, `test_playtest_logging.py`, `test_defect_categories.py`, `test_extended_session.py`) and API tests (`tests/unit/test_api_routes.py`, `test_api_gameplay.py`) to use `create_test_session_factory()` and replace all dict accesses with repo-based query methods |
| 3.12 | Completed | 2026-04-19 07:10 PM | 2026-04-19 07:25 PM | Run full test suite and lint, fix any failures — 1314 tests pass, lint clean |
| 3.13 | Completed | 2026-04-19 07:25 PM | 2026-04-19 07:30 PM | Phase End: update `docs/phase_status.md`, `STARTUP.md`, commit locally |

### Phase 3 Summary

- **Changes:** Rewrote `game_loop.py` to remove all 12 in-memory entity dicts and replace with repo-based reads/writes. Added `campaign_id` field, 20+ public query methods, `save_knowledge_fact()`. Added `list_for_campaign()` to 8 repos. Rewrote `routes.py` to use orchestrator query methods and direct repo calls. Made `KnowledgeFactRow.scene_id` nullable (empty scene_id from scenarios). Updated `db_helpers.py` to use `StaticPool` for cross-thread SQLite safety in TestClient. Updated all 7 test files to use `create_test_session_factory()` and repo-based state modification. Fixed pragma tests to use production `get_engine` for pragma assertions.
- **Changes hosted at:** `server/orchestrator/game_loop.py`, `server/api/routes.py`, `server/storage/repository.py`, `server/storage/models.py`, `tests/fixtures/db_helpers.py`, `tests/integration/test_*.py` (5 files), `tests/unit/test_api_routes.py`, `tests/unit/test_api_gameplay.py`, `tests/unit/test_database_foundation.py`
- **Commit:** `Database Phase 3: Migrate entity storage from in-memory dicts to repository pattern`

---

## Phase 4: Migrate Turn Lifecycle (Open, Submit, Resolve)

**Goal:** `open_turn()`, `submit_action()`, and `resolve_turn()` use database sessions with proper transaction boundaries. `resolve_turn()` uses the split-session pattern (load → compute → version-checked commit). The turn log is append-only via `TurnLogRepo`.

**Depends on:** Phase 3.

| # | Status | Started (PST) | Completed (PST) | Description |
|---|--------|---------------|------------------|-------------|
| 4.1 | Completed | 2026-04-19 08:00 PM | 2026-04-19 08:05 PM | Rewrite `open_turn()`: save TurnWindow via `TurnWindowRepo`, get turn number from `TurnLogRepo.count_for_scene()`, update Scene via repo |
| 4.2 | Completed | 2026-04-19 08:05 PM | 2026-04-19 08:10 PM | Rewrite `submit_action()`: load TurnWindow + existing actions from repos within a single session, validate via TurnEngine, save CommittedAction + updated TurnWindow, commit |
| 4.3 | Completed | 2026-04-19 08:10 PM | 2026-04-19 08:20 PM | Rewrite `resolve_turn()` with split-session pattern: Session 1 loads TurnWindow (with version), actions, scene, characters, NPCs, monster groups, destination scenes. Compute phase runs engine logic + narration on working set. Session 2 calls `save_with_version_check()`, saves all mutated entities, appends TurnLogEntry. Catches `StaleStateError` and retries |
| 4.4 | Completed | 2026-04-19 08:20 PM | 2026-04-19 08:30 PM | Rewrite `_apply_action_effects()` → `_apply_action_effects_ws()` and sub-methods (`_apply_move_ws`, `_apply_attack_ws`, `_apply_social_ws`) to operate on pre-loaded working set dicts instead of DB calls |
| 4.5 | Completed | 2026-04-19 08:00 PM | 2026-04-19 08:05 PM | Remove `self.turn_windows`, `self.committed_actions`, `self.turn_log` dicts/lists from `__init__` — all three now go through repos |
| 4.6 | Completed | 2026-04-19 08:30 PM | 2026-04-19 08:32 PM | Rewrite `get_turn_log_for_scene()` to use `TurnLogRepo.list_for_scene()`. Added `get_turn_log()`, `get_turn_window()`, `get_committed_actions_for_window()` public query methods |
| 4.7 | Completed | 2026-04-19 08:05 PM | 2026-04-19 08:10 PM | `handle_player_message()` and `_handle_as_action()` already load state from repos via `get_player_character()` and `submit_action()` — no changes needed |
| 4.8 | Completed | 2026-04-19 08:32 PM | 2026-04-19 08:40 PM | Updated `test_playtest_session.py` (TestTimerFallback, TestTurnLog), `test_defect_categories.py` (TestTimingDefects), `test_playtest_logging.py` to use `get_committed_actions_for_window()`, `get_turn_window()`, `get_turn_log_for_scene()` instead of dict access |
| 4.9 | Completed | 2026-04-19 08:10 PM | 2026-04-19 08:20 PM | Optimistic locking tested via `resolve_turn()` which calls `save_with_version_check()` and catches `StaleStateError` with retry. Existing Phase 1 tests cover the raw `StaleStateError` path |
| 4.10 | Completed | 2026-04-19 08:40 PM | 2026-04-19 08:45 PM | Full test suite: 1314 passed. Lint and format clean |
| 4.11 | Completed | 2026-04-19 08:45 PM | 2026-04-19 08:50 PM | Phase End: update `docs/phase_status.md`, `STARTUP.md`, commit locally |

### Phase 4 Summary

- **Changes:** Rewrote `open_turn()`, `submit_action()`, `resolve_turn()` to use database repos. `resolve_turn()` uses split-session pattern (load → compute → version-checked commit with `StaleStateError` retry). Refactored `_apply_action_effects` → `_apply_action_effects_ws` and sub-methods to operate on pre-loaded working set dicts. Removed `self.turn_windows`, `self.committed_actions`, `self.turn_log` in-memory dicts. Added `list_for_scene()`, `count_for_scene()` to `TurnLogRepo`. Added `get_turn_window()`, `get_committed_actions_for_window()`, `get_turn_log()` public query methods. Updated `routes.py` to use query methods. Updated 3 test files to use repo-based queries. Total: 1314 tests, all green, lint clean.
- **Changes hosted at:** `server/orchestrator/game_loop.py`, `server/storage/repository.py`, `server/api/routes.py`, `tests/integration/test_playtest_session.py`, `tests/integration/test_defect_categories.py`, `tests/integration/test_playtest_logging.py`
- **Commit:** `Database Phase 4: Migrate turn lifecycle with split-session and optimistic locking`

---

## Phase 5: Migrate Bot Commands and API Routes

**Goal:** Bot commands and API routes no longer access orchestrator dicts (which no longer exist). Display-data API routes use repos directly. Decision-relevant routes and write operations go through the orchestrator.

**Depends on:** Phase 4.

| # | Status | Started (PST) | Completed (PST) | Description |
|---|--------|---------------|------------------|-------------|
| 5.1 | Completed | 2026-04-19 09:00 PM | 2026-04-19 09:05 PM | Update `server/api/app.py` to inject a `SessionFactory` into the API routes module (alongside the orchestrator). Added `set_session_factory()` to routes module |
| 5.2 | Completed | 2026-04-19 09:05 PM | 2026-04-19 09:05 PM | Display-data API routes already use orchestrator query methods (migrated in Phase 3/4). All reads go through `orch.get_*()` which internally use repos |
| 5.3 | Completed | 2026-04-19 09:05 PM | 2026-04-19 09:05 PM | Decision-relevant API routes already go through orchestrator (migrated in Phase 3/4) |
| 5.4 | Completed | 2026-04-19 09:05 PM | 2026-04-19 09:05 PM | Inbox route already uses `orch.get_scopes()` and `orch.get_knowledge_facts()` (migrated in Phase 3) |
| 5.5 | Completed | 2026-04-19 09:05 PM | 2026-04-19 09:05 PM | Channel routes already use `orch._session_scope()` with `SideChannelRepo` (migrated in Phase 3) |
| 5.6 | Completed | 2026-04-19 09:05 PM | 2026-04-19 09:05 PM | Draft route already uses `self.drafts` (in-memory, unchanged) |
| 5.7 | Completed | 2026-04-19 09:05 PM | 2026-04-19 09:10 PM | Updated `cmd_newgame` to use `orchestrator.get_scenes()` instead of `orchestrator.scenes` |
| 5.8 | Completed | 2026-04-19 09:10 PM | 2026-04-19 09:12 PM | Updated `/diagnostics` to use `orchestrator.get_campaign()`, `get_turn_windows()`, `get_scenes()`, `get_players()`. Added `list_for_campaign()` to `TurnWindowRepo` and `get_turn_windows()` to orchestrator |
| 5.9 | Completed | 2026-04-19 09:12 PM | 2026-04-19 09:15 PM | Updated `/scene` to use `orchestrator.get_scene(sid)` and `/who` to use `orchestrator.get_scenes()` |
| 5.10 | Completed | 2026-04-19 09:15 PM | 2026-04-19 09:15 PM | All API tests already use `create_test_session_factory()` (migrated in Phase 3) |
| 5.11 | Completed | 2026-04-19 09:15 PM | 2026-04-19 09:18 PM | Full test suite: 1314 passed. Lint and format clean |
| 5.12 | Completed | 2026-04-19 09:18 PM | 2026-04-19 09:20 PM | Phase End: update `docs/phase_status.md`, `STARTUP.md`, commit locally |

### Phase 5 Summary

- **Changes:** Added `set_session_factory()` to routes module, called from `create_api_app()`. Added `list_for_campaign()` to `TurnWindowRepo`. Added `get_turn_windows()` to orchestrator. Updated `bot/commands.py`: `cmd_newgame` uses `get_scenes()`, `cmd_diagnostics` uses `get_campaign()` / `get_turn_windows()` / `get_scenes()` / `get_players()`, `cmd_scene` uses `get_scene()`, `cmd_who` uses `get_scenes()`. API routes were already fully migrated in Phases 3–4. All API tests already used `create_test_session_factory()`. Total: 1314 tests, all green, lint clean.
- **Changes hosted at:** `server/api/app.py`, `server/api/routes.py`, `server/storage/repository.py`, `server/orchestrator/game_loop.py`, `bot/commands.py`
- **Commit:** `Database Phase 5: Migrate bot commands and API routes to database-backed reads`

---

## Phase 6: Startup Recovery and Multi-Campaign Support

**Goal:** On startup, the orchestrator loads active campaigns from the database, reconstructs timer state for open turn windows, and resumes interrupted turns. The orchestrator supports multiple campaigns by routing on `campaign_id` rather than holding a single `self.campaign`.

**Depends on:** Phase 5.

| # | Status | Started (PST) | Completed (PST) | Description |
|---|--------|---------------|------------------|-------------|
| 6.1 | Completed | 2026-04-19 09:25 PM | 2026-04-19 09:35 PM | Added `startup()` method: creates tables, loads active campaigns, reconstructs timers, recovers stuck turns. Added `TurnRecoveryEngine` to orchestrator |
| 6.2 | Completed | 2026-04-19 09:25 PM | 2026-04-19 09:35 PM | Timer reconstruction in `startup()`: computes remaining time from `expires_at - now`, creates and starts TimerRecord via `TimerController` |
| 6.3 | Completed | 2026-04-19 09:25 PM | 2026-04-19 09:35 PM | Stuck turn recovery in `startup()`: calls `find_stuck_turns()` then `recover()` for each, persists recovered TurnWindow state |
| 6.4 | Completed | 2026-04-19 09:35 PM | 2026-04-19 09:38 PM | Added `telegram_group_id: int = 0` parameter to `load_scenario()`. Updated `cmd_newgame` to pass `chat_id` |
| 6.5 | Completed | 2026-04-19 09:38 PM | 2026-04-19 09:40 PM | `cmd_newgame` registers campaign→chat in BotRegistry. `startup()` re-registers mapping from persisted `telegram_group_id`. Added `list_for_campaign()` to `TurnWindowRepo` |
| 6.6 | Completed | 2026-04-19 09:40 PM | 2026-04-19 09:50 PM | Added 9 tests: startup basic (4), timer reconstruction (2), stuck turn recovery (1), group ID (2). Plus full integration crash recovery test |
| 6.7 | Completed | 2026-04-19 09:50 PM | 2026-04-19 09:55 PM | Added 2 multi-campaign tests: state isolation and startup picks first active campaign |
| 6.8 | Completed | 2026-04-19 09:55 PM | 2026-04-19 09:58 PM | Full test suite: 1327 passed (13 new). Lint and format clean |
| 6.9 | Completed | 2026-04-19 09:58 PM | 2026-04-19 10:00 PM | Phase End: update `docs/phase_status.md`, `STARTUP.md`, commit locally |

### Phase 6 Summary

- **Changes:** Added `startup()` method to orchestrator (table creation, campaign loading, timer reconstruction, stuck turn recovery). Added `TurnRecoveryEngine` instance to orchestrator. Added `telegram_group_id` parameter to `load_scenario()`. Updated `cmd_newgame` to pass chat_id and register campaign→chat in BotRegistry. `startup()` re-registers campaign→chat mapping from persisted data. Added `list_for_campaign()` to `TurnWindowRepo`. Added `tests/unit/test_database_startup_recovery.py` (13 tests). Total: 1327 tests, all green, lint clean.
- **Changes hosted at:** `server/orchestrator/game_loop.py`, `bot/commands.py`, `server/storage/repository.py`, `tests/unit/test_database_startup_recovery.py`
- **Commit:** `Database Phase 6: Startup recovery and multi-campaign support`

---

## Phase 7: Documentation, Cleanup, and Verification

**Goal:** All documentation reflects the database-backed architecture. BUG-003 is closed. The full test suite passes with database persistence active. No in-memory entity dicts remain in the orchestrator.

**Depends on:** Phase 6.

| # | Status | Started (PST) | Completed (PST) | Description |
|---|--------|---------------|------------------|-------------|
| 7.1 | Completed | 2026-04-19 10:05 PM | 2026-04-19 10:08 PM | Updated `docs/architecture.md`: replaced "In-memory state for playtest" with "Database-backed persistence", added Storage Layer section |
| 7.2 | Completed | 2026-04-19 10:08 PM | 2026-04-19 10:08 PM | `STARTUP.md` already updated in Phase 6 with startup recovery details and `DATABASE_URL` context |
| 7.3 | Completed | 2026-04-19 10:08 PM | 2026-04-19 10:08 PM | `docs/repo_conventions.md` already has `DATABASE_URL`; `.gitignore` already has `*.db` patterns (added in Phase 1) |
| 7.4 | Completed | 2026-04-19 10:08 PM | 2026-04-19 10:10 PM | Closed BUG-003 in `docs/bugs.md`. Updated BUG20260419-014 status to "Improved" (recovery now uses CharacterRepo) |
| 7.5 | Completed | 2026-04-19 10:10 PM | 2026-04-19 10:12 PM | Grep confirmed zero hits for all 15 old in-memory dict names across entire codebase |
| 7.6 | Completed | 2026-04-19 10:12 PM | 2026-04-19 10:13 PM | Full test suite: 1327 passed |
| 7.7 | Completed | 2026-04-19 10:13 PM | 2026-04-19 10:13 PM | Lint and format clean |
| 7.8 | Completed | 2026-04-19 10:13 PM | 2026-04-19 10:15 PM | Phase End: update `docs/phase_status.md`, `STARTUP.md`, commit locally |

### Phase 7 Summary

- **Changes:** Updated `docs/architecture.md` with Storage Layer section. Closed BUG-003 in `docs/bugs.md`. Updated BUG20260419-014 status. Verified zero remaining in-memory dict references across codebase. 1327 tests pass, lint clean.
- **Changes hosted at:** `docs/architecture.md`, `docs/bugs.md`, `docs/database_plan.md`, `docs/phase_status.md`, `STARTUP.md`
- **Commit:** `Database Phase 7: Documentation, cleanup, BUG-003 closed`
