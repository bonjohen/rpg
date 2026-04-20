# Central Database Integration Design Document

## 1. Purpose

The game server currently holds all canonical state in-memory inside `GameOrchestrator` as Python dicts. This works for single-session playtesting but has three hard limits that prevent real use: a server restart loses all campaign state, only one process can serve the game (no horizontal scaling or hot-restart), and crash recovery cannot resume a campaign mid-turn. This document designs the integration of a central relational database to replace the in-memory dicts as the authoritative state store, enabling persistent campaigns, crash-safe turn resolution, and a foundation for future multi-instance operation.

## 2. Scope

This design covers the transition from in-memory state to database-backed state for the existing game server. It does not redesign the domain model, change the turn engine's resolution logic, or introduce a new ORM. The existing SQLAlchemy ORM models (`server/storage/models.py`), repository classes (`server/storage/repository.py`), and database factory (`server/storage/db.py`) were built in Phase 1 specifically for this purpose and have never been connected to the orchestrator. The primary work is wiring them in, defining transaction boundaries, handling the runtime-only state that should not be persisted, and updating tests.

Out of scope: read replicas, connection pooling tuning for high concurrency, multi-tenant isolation, schema versioning tooling (Alembic), and cloud-managed database deployment. These are follow-on concerns once the basic integration is proven.

## 3. Core Design Principles

3.1. **The database is the single source of truth.** After integration, the orchestrator must not hold long-lived entity dicts. Every read goes through a repository; every write is flushed to the database within a session. The in-memory dicts are removed, not dual-written alongside the database.

3.2. **Turn commit is the critical transaction boundary.** The append-only turn log contract requires that a turn's resolved actions, state changes, narration, and log entry are committed atomically. If any part fails, the entire turn commit rolls back. This is the one place where transactional integrity directly affects gameplay correctness.

3.3. **Stateless engines stay stateless.** The domain engines (TurnEngine, ScopeEngine, MovementEngine, CombatActionEngine, SocialEngine, etc.) are already stateless — they accept entities as arguments and return results. This design does not change that. The orchestrator remains the coordinator that loads entities from repositories, passes them to engines, and saves the results.

3.4. **Runtime-only state stays in memory.** Some state is ephemeral by design and should not be persisted: action drafts being composed, inbox read-tracking, the timer tick loop, the idempotency dedup cache, and the metrics collector. These remain in-memory. The database stores only canonical game state that must survive a restart.

3.5. **SQLite for development and single-server production; PostgreSQL as an upgrade path.** SQLite is already wired in `server/storage/db.py` and is sufficient for the current single-process, single-campaign architecture. The ORM and repository layers use standard SQLAlchemy — switching to PostgreSQL later requires only changing `DATABASE_URL`. The design should not use SQLite-specific features.

## 4. Primary User Stories

4.1. **Campaign persistence.** A GM starts a campaign on Monday. Players join over the week. The server restarts on Wednesday for a code update. When it comes back, the campaign, all players, characters, scenes, NPCs, items, quests, and the full turn log are intact. Play resumes from the last committed turn.

4.2. **Crash recovery mid-turn.** The server crashes while a turn window is open (state = `open` or `all_ready`). On restart, the recovery engine finds the interrupted turn window in the database, applies timeout fallbacks for players who hadn't submitted, and resolves the turn. No manual intervention needed.

4.3. **Campaign history and replay.** A player asks for a recap of turns 5-15. The Mini App API queries the turn log from the database, filtered by campaign and turn number range. This works identically whether the campaign is active or archived.

4.4. **Multiple campaigns.** Two different Telegram groups each run their own campaign on the same server. Each campaign's state is isolated by `campaign_id` foreign keys throughout the schema. The orchestrator loads the relevant campaign's state on demand rather than holding everything in memory.

4.5. **Admin diagnostics.** The diagnostics engine queries the database for stuck turn windows (state not `committed` or `aborted` and `opened_at` older than a threshold), failed deliveries, and player status across all active campaigns. This replaces the current approach of scanning in-memory dicts.

## 5. Functional Requirements

### 5.1 Orchestrator State Migration

The `GameOrchestrator` currently holds 15 entity dicts plus a turn log list:

```
self.campaign, self.scenes, self.characters, self.players,
self.npcs, self.monster_groups, self.items, self.puzzles,
self.quests, self.knowledge_facts, self.scopes,
self.turn_windows, self.committed_actions, self.turn_log,
self.side_channels
```

Each of these has a corresponding repository class already built. The migration replaces each dict with repository calls:

| Current pattern | New pattern |
|---|---|
| `self.scenes[scene_id] = scene` | `self.scene_repo.save(scene)` |
| `scene = self.scenes.get(scene_id)` | `scene = self.scene_repo.get(scene_id)` |
| `[s for s in self.scenes.values() if s.campaign_id == cid]` | `self.scene_repo.list_for_campaign(cid)` |
| `self.turn_log.append(entry)` | `self.turn_log_repo.append(entry)` |

The orchestrator receives a `SessionFactory` (SQLAlchemy `sessionmaker`) at construction time. Each public method (e.g., `open_turn`, `submit_action`, `resolve_turn`) opens a session, performs repository operations within it, and commits or rolls back.

### 5.2 Transaction Boundaries

Not every orchestrator method needs a long-running transaction. The boundaries should match the game's consistency requirements:

| Operation | Transaction scope | Rationale |
|---|---|---|
| `load_scenario()` | Single transaction | All scenario entities (scenes, NPCs, items, triggers, quests, puzzles, scopes, facts) are created atomically. Partial load is worse than no load. |
| `add_player()` | Single transaction | Player + Character + private scope created together. |
| `open_turn()` | Single transaction | TurnWindow + scene state update. |
| `submit_action()` | Single transaction | CommittedAction creation + TurnWindow state check. |
| `resolve_turn()` | Single transaction | This is the critical path. All state mutations from resolution (character HP, NPC trust, item transfers, monster morale, scene transitions, quest progress, new knowledge facts, visibility grants), plus the TurnLogEntry append, plus the TurnWindow state transition to `committed`, must commit atomically. |
| `handle_player_message()` | Read-only or short write | Intent classification and action extraction are read-heavy. If a side effect occurs (e.g., scope suggestion creates a fact), that's a small write transaction. |

### 5.3 Session Management Pattern

The orchestrator should use a **session-per-request** pattern. Each public method:

1. Creates a session from the factory.
2. Instantiates the repositories it needs, passing the session.
3. Performs reads, engine calls, and writes.
4. Commits on success; rolls back on exception.
5. Closes the session.

A context manager or decorator can standardize this. Example shape:

```python
def resolve_turn(self, turn_window_id: str) -> ResolveResult:
    with self._session_scope() as session:
        tw_repo = TurnWindowRepo(session)
        action_repo = CommittedActionRepo(session)
        # ... load entities, call engines, save results ...
        # session.commit() happens at context manager exit
```

This keeps transaction lifetime explicit and prevents long-lived sessions that hold database locks across async I/O (model inference, Telegram delivery).

**Split-session pattern for `resolve_turn`.** Turn resolution includes a model inference call (500ms-10s) that must not hold a database transaction open. The actual flow is:

1. **Load phase** (session 1): Open session, load TurnWindow + committed actions + scene + characters + NPCs + all relevant entities. Close session. Build a local working set of domain dataclasses.
2. **Compute phase** (no session): Run engine logic (damage, movement, trust changes, etc.) on the working set. Call the main model for narration. All mutations happen on the in-memory working set objects.
3. **Commit phase** (session 2): Open session, verify the TurnWindow's `version` matches what was loaded (optimistic locking — see 5.3.1), save all mutated entities from the working set, append the TurnLogEntry, commit.

If the version check fails in step 3, the resolution is retried from step 1. This is rare — it only happens if a concurrent operation modifies the TurnWindow between load and commit (e.g., a late action submission racing with timer expiry).

### 5.3.1 Optimistic Locking

The split-session pattern for `resolve_turn` creates a window where concurrent writes could interfere (e.g., `handle_player_message` triggers a side-effect write, or a timer fires `trigger_early_close` while resolution is computing). To prevent write-write races:

- Add a `version` integer column to `TurnWindowRow` (and the `TurnWindow` domain entity), starting at 1.
- Every `TurnWindowRepo.save()` increments `version` and includes `WHERE version = :expected_version` in the update. If zero rows are affected, raise a `StaleStateError`.
- The orchestrator catches `StaleStateError` in the commit phase and retries from the load phase.

This is the standard optimistic concurrency control pattern. It works with SQLite (no `SELECT ... FOR UPDATE` needed) and PostgreSQL alike.

### 5.3.2 Working Set Pattern

Within a single turn resolution, entities must be loaded once into a local working set. Engines mutate these working set objects. The working set is then saved in bulk during the commit phase. This avoids the bug where re-fetching a mutated entity from the repo returns the pre-mutation version (repos return new dataclass copies on every `get()`).

The working set is a plain dict-of-dicts scoped to the resolution call, not a long-lived cache. It is discarded after commit.

### 5.4 Runtime-Only State (Not Persisted)

The following state remains in-memory because it is ephemeral, reconstructable, or not worth the write overhead:

| State | Reason to keep in memory |
|---|---|
| `drafts` (action drafts) | Ephemeral; discarded on submit or timeout. Losing drafts on restart is acceptable — the player resubmits. |
| `inbox_read` (read-tracking) | Convenience state. Can be rebuilt (mark all as unread on restart) or moved to a lightweight table later. |
| `channel_messages` (side channel history) | Could be persisted, but side channel audit facts already capture the important content as KnowledgeFacts. Full message history is a future enhancement. |
| `timers` (TimerRecord instances) | Timer state is derived from `TurnWindow.opened_at`, `expires_at`, and `state`. The timer controller reconstructs active timers from open turn windows on startup. |
| `IdempotencyStore` | In-memory dedup cache with TTL. Acceptable to lose on restart — the worst case is a duplicate Telegram update being processed, which the turn engine's action-per-player rule already guards against. |
| `MetricsCollector` | Counters and histograms. Losing them on restart is fine; they're for live monitoring, not historical analysis. |

### 5.5 Orchestrator Initialization Changes

On startup, the orchestrator must:

1. Accept `database_url` or a `SessionFactory` as a constructor parameter.
2. Call `create_all_tables(engine)` to ensure the schema exists (idempotent).
3. Load active campaigns from the database (query `CampaignRepo.list_active()`).
4. For each active campaign with open turn windows, reconstruct timer state.
5. Resume any interrupted turns via `TurnRecoveryEngine`.

This replaces the current pattern where the orchestrator starts empty and waits for `/newgame` to load a scenario.

### 5.6 Scenario Loading

`load_scenario()` currently populates in-memory dicts from YAML. After integration, it creates a database session, builds all entities via the scenario loader (unchanged), saves each entity through its repository, and commits. The scenario loader itself does not change — it produces domain dataclasses. Only the orchestrator's persistence of those dataclasses changes.

### 5.7 API Layer Changes

The Mini App API routes (`server/api/routes.py`) currently access `orchestrator.scenes`, `orchestrator.characters`, etc. directly. After integration, these routes should either:

- (A) Call orchestrator methods that internally use repositories, or
- (B) Receive their own `SessionFactory` and use repositories directly for read-only queries.

Option (B) is better for read-heavy API endpoints because it avoids routing simple lookups through the orchestrator's game logic. The API routes would open a read-only session, query the relevant repository, and return the response. Write operations (action submission, channel creation) still go through the orchestrator.

**Important distinction: display data vs. decision-relevant data.** Not all reads are safe for Option B. The split is not "reads vs. writes" but "display data vs. decision-relevant data":

- **Safe for direct repo reads (Option B):** Character sheet, inventory, quest log, turn log/recap, scene descriptions, clue journal. These are display-only and tolerate brief staleness.
- **Must go through orchestrator (Option A):** Turn window state, action submission status, "is it my turn" checks, timer remaining. These inform the player's next action and must reflect the orchestrator's in-flight state. Reading stale turn state from the database could show a turn as open when the orchestrator has already locked it.

### 5.8 Bot Command Changes

Bot commands (`bot/commands.py`) currently access `orchestrator.players`, `orchestrator.campaign`, etc. The same pattern applies: read operations can use repositories directly; write operations go through the orchestrator.

### 5.9 Database File Location

The SQLite database file defaults to `rpg.db` at the repo root (per `server/storage/db.py`). This is acceptable for development. For production, `DATABASE_URL` should point to a dedicated location outside the repo. The `.gitignore` should include `*.db` to prevent accidental commits of database files.

### 5.10 Schema Creation and Migration

For the initial integration, `create_all_tables()` (SQLAlchemy `Base.metadata.create_all`) is sufficient. It creates tables if they don't exist and is idempotent. No migration tool is needed yet because there is no existing production data to migrate — the schema is being used for the first time.

When the schema needs to evolve later (adding columns, changing types), Alembic should be introduced. That is a follow-on task, not part of this integration.

### 5.11 Concurrent Access and Locking

SQLite supports concurrent reads but serializes writes. For a single-campaign, single-process server, this is adequate. The turn engine's design already serializes resolution (one turn resolves at a time per scene), so database write contention is minimal.

If the server later needs to handle multiple concurrent campaigns with high write throughput, switching to PostgreSQL (via `DATABASE_URL`) provides proper row-level locking and concurrent writes without code changes to the repository layer.

### 5.12 Impact on Existing Tests

The test suite (1292 tests) currently operates entirely against in-memory state. The integration should not break existing tests. Strategy:

- **Unit tests for stateless engines** (turn engine, scope engine, combat, exploration, social, etc.) are unaffected. They don't touch persistence.
- **Orchestrator tests and integration tests** need to be updated. These currently construct a `GameOrchestrator` with no database. After integration, they should use an in-memory SQLite database (`sqlite:///:memory:`) for speed, with `create_all_tables` in the test fixture setup.
- **API route tests** may need similar fixture updates if they directly access orchestrator state.
- A test fixture helper (e.g., `create_test_session()`) should be added to `tests/fixtures/` to standardize database setup for tests.

### 5.13 Performance Considerations

The current in-memory approach has O(1) dict lookups. Database queries add I/O overhead. Mitigations:

- SQLite with WAL mode reduces read-write contention.
- The most frequent operations during a turn (checking turn window state, validating action submission) are single-row lookups by primary key — fast in any database.
- The largest query patterns (listing all facts for a scope, listing all actions for a turn window) are already indexed by foreign key in the ORM models.
- If hot-path latency becomes an issue, a lightweight read cache (e.g., caching the active turn window and its scene for the duration of a turn) can be added without architectural changes. This is an optimization, not a design requirement.

### 5.14 Crash Recovery Improvements

With database persistence, the existing `TurnRecoveryEngine` (`server/reliability/turn_recovery.py`) becomes fully functional:

- `find_stuck_turns()` queries the database for turn windows in non-terminal states older than a threshold.
- `diagnose()` and `recover()` load the turn window and its committed actions from the database.
- Recovery synthesizes timeout fallback actions for missing players, resolves the turn, and commits — all within a single database transaction.
- This resolves BUG-003 and improves the crash-recovery path described in BUG20260419-014 (scene.player_ids not maintained) because the database is the source of truth for scene membership.

### 5.15 Multi-Campaign Support

The current orchestrator holds a single `self.campaign`. With database backing, the orchestrator can serve multiple campaigns:

- Each bot command and API request includes a `campaign_id` (derived from the Telegram group ID via `BotRegistry`).
- The orchestrator loads campaign-scoped state on demand rather than holding a global reference.
- This is a natural consequence of the repository pattern — all repos already filter by `campaign_id`.

## 6. Risks and Mitigations

6.1. **Risk: Performance regression on hot paths.** The turn submission and resolution paths currently do zero I/O. Adding database queries will increase latency. **Mitigation:** SQLite with WAL mode on a local SSD is sub-millisecond for single-row lookups. The model inference calls (500ms-10s) dominate turn resolution time. Database I/O is negligible by comparison.

6.2. **Risk: Test suite disruption.** Changing the orchestrator's constructor and internal state access will break orchestrator and integration tests. **Mitigation:** Use `sqlite:///:memory:` in test fixtures. Add a helper that creates an engine, runs `create_all_tables`, and returns a session factory. Existing test entity builders produce domain dataclasses (unchanged); only the orchestrator wiring changes.

6.3. **Risk: Transaction scope too broad.** Wrapping entire methods in transactions could hold locks during async operations (model inference, Telegram delivery). **Mitigation:** The split-session pattern (section 5.3) explicitly separates load, compute, and commit into distinct session lifetimes. The model inference call happens outside any database session.

6.4. **Risk: Incomplete migration leaves dual state.** If some paths read from dicts and others from the database, state diverges silently. **Mitigation:** Remove the in-memory dicts entirely. Dual state is a correctness hazard that gets more expensive to fix over time. Any access to a removed dict immediately raises an `AttributeError`, making incomplete migration obvious during testing.

6.5. **Risk: SQLite file corruption on unclean shutdown.** SQLite is robust against this with WAL mode and proper `PRAGMA journal_mode=WAL`. See section 5.17 for the full pragma configuration.

6.6. **Risk: Write-write race on `resolve_turn`.** The split-session pattern creates a window where concurrent writes could modify the TurnWindow between load and commit. **Mitigation:** Optimistic locking via a `version` column (section 5.3.1). The commit phase checks the version; if it has changed, the resolution retries from the load phase. This works with both SQLite and PostgreSQL.

## 5.16 Async/Sync Decision

The bot gateway and API server are async (FastAPI + python-telegram-bot). SQLAlchemy sessions are synchronous by default. This decision cannot be deferred to the PDR because it shapes every session context manager and repository call in the orchestrator.

**Decision: Use synchronous SQLAlchemy with `run_in_executor` for now.** Rationale:

- The existing repository layer is synchronous. Rewriting it for `AsyncSession` is a large refactor with no gameplay benefit.
- SQLite does not benefit from async drivers — its I/O is local disk, not network.
- `run_in_executor(None, ...)` offloads blocking database calls to the default thread pool, keeping the async event loop responsive.
- The orchestrator's public methods become `async` (most already are, since they call async model adapters). Database operations within them are wrapped: `await loop.run_in_executor(None, self._resolve_turn_sync, turn_window_id)`.
- If PostgreSQL becomes the backend, `sqlalchemy[asyncio]` with `AsyncSession` can replace the executor pattern. The repository interface (accept session, return domain dataclasses) stays the same.

### 5.17 SQLite Pragmas

The `get_engine()` function in `db.py` must set these pragmas on every connection via a `@event.listens_for(engine, "connect")` handler:

- `PRAGMA journal_mode=WAL` — Write-ahead logging. Allows concurrent reads during writes. Critical for the split-session pattern.
- `PRAGMA foreign_keys=ON` — SQLite ignores foreign key constraints by default. The schema has FK constraints; without this pragma they are decorative.
- `PRAGMA busy_timeout=5000` — Wait up to 5 seconds for a write lock instead of immediately returning SQLITE_BUSY. Prevents spurious failures under light contention.
- `PRAGMA synchronous=NORMAL` — Balances durability and performance with WAL mode. `FULL` is unnecessary for a game server (not a financial system).

### 5.18 Bulk Save Performance

After turn resolution, the orchestrator saves multiple mutated entities (characters, NPCs, items, quest states, etc.). Each `repo.save()` does a `session.get()` + field-by-field copy + `session.flush()`. Within a single session, SQLAlchemy batches these flushes into a single transaction commit, so the per-entity overhead is the Python-side ORM work, not individual disk writes.

If bulk saves become a measurable bottleneck (unlikely for 4-6 players and a handful of NPCs per turn), a `save_many()` method can be added to repositories that uses `session.bulk_save_objects()` or `session.execute(insert(...).values([...]))`. This is an optimization to defer, not a design requirement.

## 7. Decision Points for PDR

The following decisions should be resolved in the PDR before implementation:

7.1. **Read-path caching.** Should the orchestrator cache recently-read entities (e.g., the active campaign and its scenes) to reduce database round-trips during a turn? The design allows this but does not require it. The PDR should decide whether to implement a cache layer or defer it.

7.2. **Side channel message persistence.** The design keeps `channel_messages` in-memory. If side channel message history should survive restarts, a new `SideChannelMessage` entity and table should be added. This is a scope decision for the PDR.

7.3. **Draft persistence.** Action drafts are currently ephemeral. If players should be able to resume drafts after a server restart, a `DraftAction` table is needed. This is low priority but worth deciding.

7.4. **TurnWindow version column.** The optimistic locking scheme (section 5.3.1) requires adding a `version` integer to both the `TurnWindow` domain entity and `TurnWindowRow` ORM model. The PDR should specify the exact column definition and default.
