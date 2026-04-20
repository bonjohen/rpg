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
| 1.11 | Started | 2026-04-19 11:12 AM | | Phase End: update `docs/phase_status.md`, `STARTUP.md`, commit locally |

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
| 2.1 | Open | | | Add `session_factory: sessionmaker | None = None` parameter to `GameOrchestrator.__init__()` in `server/orchestrator/game_loop.py` |
| 2.2 | Open | | | Implement `_session_scope()` context manager on `GameOrchestrator` that yields a `Session`, commits on clean exit, rolls back on exception |
| 2.3 | Open | | | Implement `_run_in_session(fn)` helper that wraps a sync callable in `asyncio.get_event_loop().run_in_executor(None, fn)` for use from async methods |
| 2.4 | Open | | | Update `server/api/app.py` `create_api_app()` to optionally accept and store a `session_factory` on the orchestrator |
| 2.5 | Open | | | Update all test files that construct `GameOrchestrator()` (7 files in `tests/`) to pass `session_factory=create_test_session_factory()` where needed, or `None` to preserve existing behavior |
| 2.6 | Open | | | Add unit tests for `_session_scope()` commit/rollback behavior |
| 2.7 | Open | | | Run full test suite and lint, fix any failures |
| 2.8 | Open | | | Phase End: update `docs/phase_status.md`, `STARTUP.md`, commit locally |

### Phase 2 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Database Phase 2: Session scope and orchestrator constructor`

---

## Phase 3: Migrate Scenario Loading and Player Management

**Goal:** `load_scenario()` and `add_player()` write to the database through repositories. The in-memory dicts for campaigns, scenes, players, characters, NPCs, monster groups, items, puzzles, quests, knowledge facts, scopes, and side channels are removed. All reads go through repos. Query helpers (`get_player_character`, `get_player_scene`, `get_scene_players`, etc.) use repos.

**Depends on:** Phase 2.

| # | Status | Started (PST) | Completed (PST) | Description |
|---|--------|---------------|------------------|-------------|
| 3.1 | Open | | | Rewrite `load_scenario()` to open a session, save all entities via repos (CampaignRepo, SceneRepo, NPCRepo, MonsterGroupRepo, InventoryItemRepo, PuzzleStateRepo, QuestStateRepo, KnowledgeFactRepo, ConversationScopeRepo), and commit atomically |
| 3.2 | Open | | | Rewrite `add_player()` to open a session, save Player + Character + private ConversationScope + updated Scene via repos, and commit atomically |
| 3.3 | Open | | | Rewrite `get_player_character()` to use `CharacterRepo.get_for_player()` |
| 3.4 | Open | | | Rewrite `get_player_scene()` to use `CharacterRepo.get_for_player()` + `SceneRepo.get()` |
| 3.5 | Open | | | Rewrite `get_scene_players()` to use `CharacterRepo.list_for_scene()` + `PlayerRepo.get()` |
| 3.6 | Open | | | Rewrite `_find_starting_scene_id()` to use `SceneRepo.list_for_campaign()` |
| 3.7 | Open | | | Rewrite `_get_private_scope_id()` to use `ConversationScopeRepo.get_private_scope_for_player()` |
| 3.8 | Open | | | Rewrite `_get_or_create_public_scope()` to use `ConversationScopeRepo.get_public_scope()` with fallback create+save |
| 3.9 | Open | | | Remove the in-memory dicts: `self.campaign`, `self.scenes`, `self.characters`, `self.players`, `self.npcs`, `self.monster_groups`, `self.items`, `self.puzzles`, `self.quests`, `self.knowledge_facts`, `self.scopes`, `self.side_channels`. Keep `self.triggers` (loaded from scenario, not persisted), `self.drafts`, `self.inbox_read`, `self.channel_messages`, `self.timers` |
| 3.10 | Open | | | Store `self.campaign_id: str | None` instead of `self.campaign: Campaign | None` — the orchestrator holds only the ID; the full entity is loaded from the repo when needed |
| 3.11 | Open | | | Update all orchestrator tests (`tests/integration/test_playtest_setup.py`, `test_playtest_session.py`, `test_playtest_logging.py`, `test_defect_categories.py`, `test_extended_session.py`) to use `create_test_session_factory()` and verify scenario loads persist to DB |
| 3.12 | Open | | | Run full test suite and lint, fix any failures |
| 3.13 | Open | | | Phase End: update `docs/phase_status.md`, `STARTUP.md`, commit locally |

### Phase 3 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Database Phase 3: Migrate scenario loading and player management to repos`

---

## Phase 4: Migrate Turn Lifecycle (Open, Submit, Resolve)

**Goal:** `open_turn()`, `submit_action()`, and `resolve_turn()` use database sessions with proper transaction boundaries. `resolve_turn()` uses the split-session pattern (load → compute → version-checked commit). The turn log is append-only via `TurnLogRepo`.

**Depends on:** Phase 3.

| # | Status | Started (PST) | Completed (PST) | Description |
|---|--------|---------------|------------------|-------------|
| 4.1 | Open | | | Rewrite `open_turn()`: open session, create TurnWindow, update Scene state, save both via repos, commit. Remove `self.turn_windows` dict usage |
| 4.2 | Open | | | Rewrite `submit_action()`: open session, load TurnWindow + existing actions from repos, validate via TurnEngine, save CommittedAction + updated TurnWindow, commit. Remove `self.committed_actions` dict usage |
| 4.3 | Open | | | Rewrite `resolve_turn()` with split-session pattern: Session 1 loads TurnWindow (with version), actions, scene, characters, NPCs, items into a working set dict. Compute phase runs engine logic and builds narration on the working set (no session). Session 2 calls `TurnWindowRepo.save_with_version_check()`, saves all mutated entities from working set, appends TurnLogEntry, commits. Catch `StaleStateError` and retry from load |
| 4.4 | Open | | | Rewrite `_apply_action_effects()` and sub-methods (`_apply_move`, `_apply_attack`, `_apply_social`) to operate on a working set dict instead of `self.scenes`, `self.characters`, etc. |
| 4.5 | Open | | | Remove `self.turn_windows`, `self.committed_actions`, `self.turn_log` dicts/lists — all three now go through repos |
| 4.6 | Open | | | Rewrite `get_turn_log_for_scene()` to use `TurnLogRepo` |
| 4.7 | Open | | | Update `handle_player_message()` and `_handle_as_action()` to load state from repos within a session |
| 4.8 | Open | | | Update all turn-lifecycle tests in `tests/integration/` to verify database persistence: actions survive session boundary, turn log entries are queryable, version increments on TurnWindow saves |
| 4.9 | Open | | | Add test for optimistic locking: simulate concurrent TurnWindow modification, verify `StaleStateError` raised and retry succeeds |
| 4.10 | Open | | | Run full test suite and lint, fix any failures |
| 4.11 | Open | | | Phase End: update `docs/phase_status.md`, `STARTUP.md`, commit locally |

### Phase 4 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Database Phase 4: Migrate turn lifecycle with split-session and optimistic locking`

---

## Phase 5: Migrate Bot Commands and API Routes

**Goal:** Bot commands and API routes no longer access orchestrator dicts (which no longer exist). Display-data API routes use repos directly. Decision-relevant routes and write operations go through the orchestrator.

**Depends on:** Phase 4.

| # | Status | Started (PST) | Completed (PST) | Description |
|---|--------|---------------|------------------|-------------|
| 5.1 | Open | | | Update `server/api/app.py` to inject a `SessionFactory` into the API routes module (alongside the orchestrator) |
| 5.2 | Open | | | Update display-data API routes to use repos directly: `GET /api/player/{id}`, `GET /api/character/{id}`, `GET /api/character/{id}/inventory`, `GET /api/scene/{id}`, `GET /api/campaign/{id}/recap`, `GET /api/campaign/{id}/quests`, `GET /api/player/{id}/clues`, `GET /api/campaign/{id}/map` |
| 5.3 | Open | | | Keep decision-relevant API routes going through orchestrator: `POST /api/action/submit`, `GET /api/scene/{id}/context` (turn state), `POST /api/channel/create`, `POST /api/channel/{id}/send`, `POST /api/channel/{id}/leave` |
| 5.4 | Open | | | Update inbox route `GET /api/player/{id}/inbox` to use `KnowledgeFactRepo` for facts (DB) + `self.inbox_read` for read status (in-memory) |
| 5.5 | Open | | | Update channel routes `GET /api/player/{id}/channels`, `GET /api/channel/{id}/messages` — channels from `SideChannelRepo` (DB), messages from `self.channel_messages` (in-memory) |
| 5.6 | Open | | | Update draft route `GET /api/action/draft/{id}` — drafts remain in `self.drafts` (in-memory) |
| 5.7 | Open | | | Update bot commands in `bot/commands.py`: replace `orchestrator.scenes`, `orchestrator.players`, `orchestrator.campaign` with calls through orchestrator query methods or direct repo reads |
| 5.8 | Open | | | Update `/diagnostics` command to query campaigns and turn windows from repos |
| 5.9 | Open | | | Update `/scene` and `/who` commands to use repo-backed query methods |
| 5.10 | Open | | | Update all API tests (`tests/unit/test_api_routes.py`, `tests/unit/test_api_gameplay.py`) to use `create_test_session_factory()` |
| 5.11 | Open | | | Run full test suite and lint, fix any failures |
| 5.12 | Open | | | Phase End: update `docs/phase_status.md`, `STARTUP.md`, commit locally |

### Phase 5 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Database Phase 5: Migrate bot commands and API routes to database-backed reads`

---

## Phase 6: Startup Recovery and Multi-Campaign Support

**Goal:** On startup, the orchestrator loads active campaigns from the database, reconstructs timer state for open turn windows, and resumes interrupted turns. The orchestrator supports multiple campaigns by routing on `campaign_id` rather than holding a single `self.campaign`.

**Depends on:** Phase 5.

| # | Status | Started (PST) | Completed (PST) | Description |
|---|--------|---------------|------------------|-------------|
| 6.1 | Open | | | Add `startup()` method to `GameOrchestrator` that: creates tables via `create_all_tables(engine)`, queries `CampaignRepo.list_active()`, and for each campaign queries open TurnWindows via `TurnWindowRepo` |
| 6.2 | Open | | | Implement timer reconstruction: for each open TurnWindow, compute remaining time from `expires_at - utc_now()` and create a TimerRecord via `TimerController` |
| 6.3 | Open | | | Integrate `TurnRecoveryEngine`: on startup, call `find_stuck_turns()` for each active campaign, then `recover()` for any stuck turns (within a database transaction) |
| 6.4 | Open | | | Update `load_scenario()` to accept a `telegram_group_id` parameter so new campaigns map to their Telegram group |
| 6.5 | Open | | | Update bot commands to derive `campaign_id` from `BotRegistry.get_campaign_for_chat()` and pass it through to orchestrator methods |
| 6.6 | Open | | | Add startup recovery tests: create a campaign with an open turn window, simulate crash (discard orchestrator), create new orchestrator, call `startup()`, verify timer reconstructed and turn recoverable |
| 6.7 | Open | | | Add multi-campaign test: load two scenarios with different `campaign_id`s, verify each campaign's state is isolated |
| 6.8 | Open | | | Run full test suite and lint, fix any failures |
| 6.9 | Open | | | Phase End: update `docs/phase_status.md`, `STARTUP.md`, commit locally |

### Phase 6 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Database Phase 6: Startup recovery and multi-campaign support`

---

## Phase 7: Documentation, Cleanup, and Verification

**Goal:** All documentation reflects the database-backed architecture. BUG-003 is closed. The full test suite passes with database persistence active. No in-memory entity dicts remain in the orchestrator.

**Depends on:** Phase 6.

| # | Status | Started (PST) | Completed (PST) | Description |
|---|--------|---------------|------------------|-------------|
| 7.1 | Open | | | Update `docs/architecture.md`: replace "In-memory state for playtest" with database-backed storage description, add storage layer to system diagram |
| 7.2 | Open | | | Update `STARTUP.md`: note database persistence is active, document `DATABASE_URL` env var, document startup recovery behavior |
| 7.3 | Open | | | Update `docs/repo_conventions.md`: add `DATABASE_URL` to environment variables table, note `*.db` in `.gitignore` |
| 7.4 | Open | | | Update `docs/bugs.md`: close BUG-003 ("No persistent storage"), note improvements to BUG20260419-014 (scene.player_ids) |
| 7.5 | Open | | | Verify no orchestrator code references `self.scenes`, `self.characters`, `self.players`, `self.npcs`, `self.monster_groups`, `self.items`, `self.puzzles`, `self.quests`, `self.knowledge_facts`, `self.scopes`, `self.turn_windows`, `self.committed_actions`, `self.turn_log`, `self.side_channels`, `self.campaign` as dicts — grep for all, confirm zero hits |
| 7.6 | Open | | | Run full test suite (`pytest`), verify all 1292+ tests pass |
| 7.7 | Open | | | Run lint (`ruff check . && ruff format --check .`), verify clean |
| 7.8 | Open | | | Phase End: update `docs/phase_status.md`, `STARTUP.md`, commit locally |

### Phase 7 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Database Phase 7: Documentation, cleanup, BUG-003 closed`
