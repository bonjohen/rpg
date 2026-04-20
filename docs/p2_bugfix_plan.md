# P2 Bug-Fix — Implementation Plan

**Source document:** `docs/bugs.md` (42 open P2 bugs)

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

## Phase 1: Security & Bot Safety

**Goal:** API endpoints require authentication; action submission verifies caller; internal UUIDs masked.
**Depends on:** Nothing (first phase).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 1.1 | Completed | 2026-04-19 11:30 PM | 2026-04-19 11:35 PM | BUG-055: Add auth guard to data-returning endpoints in `server/api/routes.py` |
| 1.2 | Completed | 2026-04-19 11:30 PM | 2026-04-19 11:35 PM | BUG-056: Verify authenticated user matches action submitter in `server/api/routes.py` |
| 1.3 | Completed | 2026-04-19 11:35 PM | 2026-04-19 11:36 PM | BUG-065: Replace player UUID with display_name in /status output in `bot/commands.py` |
| 1.4 | Completed | 2026-04-19 11:36 PM | 2026-04-19 11:40 PM | Add tests for auth enforcement and UUID masking |
| 1.5 | Completed | 2026-04-19 11:40 PM | 2026-04-19 11:41 PM | Update BUG-055, 056, 065 status in `docs/bugs.md` |
| 1.6 | Completed | 2026-04-19 11:41 PM | 2026-04-19 11:44 PM | Run pytest + ruff, fix any failures |

### Phase 1 Summary

- **Changes:** Added `require_auth` FastAPI dependency (validates X-Init-Data header via HMAC-SHA256). Applied to all 16 data-returning endpoints. Added player ownership verification to submit_action (telegram_user_id must match). Replaced player UUID with display_name in /status bot command (3 code paths). Updated existing test helpers to pass auth headers. 12 new tests, 1408 total passing.
- **Commit:** `P2 bug-fix Phase 1: API auth guards and bot UUID masking`

## Phase 2: Timer, Orchestrator & Diagnostics

**Goal:** Timer arithmetic correct, orchestrator edge cases fixed, diagnostics accurate.
**Depends on:** Phase 1.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 2.1 | Completed | 2026-04-19 11:45 PM | 2026-04-19 11:47 PM | BUG-040: Use `round()` instead of `int()` for elapsed_before_pause in `server/timer/controller.py` |
| 2.2 | Completed | 2026-04-19 11:45 PM | 2026-04-19 11:47 PM | BUG-041: Use `max(0, remaining)` instead of `max(1, remaining)` in `server/timer/controller.py` |
| 2.3 | Completed | 2026-04-19 11:45 PM | 2026-04-19 11:47 PM | BUG-042: Use ActionState enum instead of raw strings in `server/timer/integration.py` |
| 2.4 | Completed | 2026-04-19 11:45 PM | 2026-04-19 11:47 PM | BUG-043: Remove `or None` coercion in `server/orchestrator/game_loop.py` |
| 2.5 | Completed | 2026-04-19 11:45 PM | 2026-04-19 11:47 PM | BUG-058/059/060: Verified DB migration resolved all 3 perf issues; closed |
| 2.6 | Completed | 2026-04-19 11:47 PM | 2026-04-19 11:50 PM | BUG-044: Filter pending players by submitted actions in `server/observability/diagnostics.py` |
| 2.7 | Completed | 2026-04-19 11:47 PM | 2026-04-19 11:50 PM | BUG-045: Tighten fast_model_responsive threshold in `server/observability/diagnostics.py` |
| 2.8 | Completed | 2026-04-19 11:50 PM | 2026-04-19 11:54 PM | Add tests for timer fixes, diagnostics accuracy |
| 2.9 | Completed | 2026-04-19 11:54 PM | 2026-04-19 11:55 PM | Update bug statuses in `docs/bugs.md` |
| 2.10 | Completed | 2026-04-19 11:55 PM | 2026-04-19 11:56 PM | Run pytest + ruff, fix any failures |

### Phase 2 Summary

- **Changes:** Timer pause uses round() for accurate elapsed time. Resume with 0 remaining expires immediately (max(0,...) not max(1,...)). Timer integration uses ActionState enum instead of raw strings. Removed `or None` coercion on empty timeout_players list. Diagnostics filters pending players by submitted actions. Model health threshold tightened to < 50% failure rate. BUG-058/059/060 verified fixed by DB migration. 8 new tests, 1416 total passing.
- **Commit:** `P2 bug-fix Phase 2: Timer arithmetic, orchestrator edge cases, diagnostics accuracy`

## Phase 3: Combat & Exploration

**Goal:** Combat damage scales, movement validated, exploration state transitions correct.
**Depends on:** Phase 2.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 3.1 | Completed | 2026-04-19 11:57 PM | 2026-04-20 12:10 AM | BUG-029: Set `item.is_hidden = False` on search discovery in `server/exploration/actions.py` |
| 3.2 | Completed | 2026-04-19 11:57 PM | 2026-04-20 12:10 AM | BUG-032: Add idempotency guard to clue discover() in `server/exploration/clues.py` |
| 3.3 | Completed | 2026-04-19 11:57 PM | 2026-04-20 12:10 AM | BUG-030: Add direction field to ExplorationContext for trigger disambiguation in `server/exploration/triggers.py` |
| 3.4 | Completed | 2026-04-19 11:57 PM | 2026-04-20 12:10 AM | BUG-031: Support per-fact scope_override in trigger _apply() in `server/exploration/triggers.py` |
| 3.5 | Completed | 2026-04-19 11:57 PM | 2026-04-20 12:10 AM | BUG-033: Scale unit kills by damage magnitude in `server/combat/resolution.py` |
| 3.6 | Completed | 2026-04-19 11:57 PM | 2026-04-20 12:10 AM | BUG-034: Validate direction in combat move in `server/combat/actions.py` |
| 3.7 | Completed | 2026-04-19 11:57 PM | 2026-04-20 12:10 AM | BUG-035: Cast heal amount to int in `server/combat/actions.py` |
| 3.8 | Completed | 2026-04-19 11:57 PM | 2026-04-20 12:10 AM | BUG-053: Copy overrides dict before pop() in `scenarios/puzzle_patterns.py` |
| 3.9 | Completed | 2026-04-20 12:10 AM | 2026-04-20 12:25 AM | Add tests for all 8 fixes |
| 3.10 | Completed | 2026-04-20 12:25 AM | 2026-04-20 12:25 AM | Update bug statuses in `docs/bugs.md` |
| 3.11 | Completed | 2026-04-20 12:10 AM | 2026-04-20 12:25 AM | Run pytest + ruff, fix any failures |

### Phase 3 Summary

- **Changes:** Fixed 8 bugs across combat, exploration, and scenario systems. BUG-029: search() now sets `item.is_hidden = False`. BUG-030: ExplorationContext gains `direction` field. BUG-031: Trigger `_apply()` supports per-fact scope_override via extended tuples. BUG-032: Clue `discover()` rejects already-discovered clues. BUG-033: Damage scaling kills `damage // hp_per_unit` units instead of flat 1. BUG-034: Combat move validates direction against scene exits. BUG-035: Heal amount cast to `int()`. BUG-053: `instantiate()` copies kwargs before pop. Updated 2 existing tests for new damage scaling behavior. 12 new tests, 1428 total passing.
- **Commit:** `P2 bug-fix Phase 3: Combat scaling, exploration state, puzzle safety`

## Phase 4: NPC/Social, Scene & Side Channels

**Goal:** NPC types safe, trust zones complete, scene membership correct, side channel IDs unique.
**Depends on:** Phase 3.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 4.1 | Completed | 2026-04-20 12:30 AM | 2026-04-20 12:40 AM | BUG-036: Convert SocialOutcome to str Enum in `server/npc/social.py` |
| 4.2 | Completed | 2026-04-20 12:30 AM | 2026-04-20 12:40 AM | BUG-037: Log warning on unknown action_key in `server/npc/trust.py` |
| 4.3 | Completed | 2026-04-20 12:30 AM | 2026-04-20 12:40 AM | BUG-038: Add "suspicious" zone to _derive_stance in `server/npc/trust.py` |
| 4.4 | Completed | 2026-04-20 12:30 AM | 2026-04-20 12:40 AM | BUG-039: Check for remaining characters before removing player_id in `server/scene/membership.py` |
| 4.5 | Completed | 2026-04-20 12:30 AM | 2026-04-20 12:40 AM | BUG-025: Use new_id() for fact_id in `server/scope/side_channel_audit.py` |
| 4.6 | Completed | 2026-04-20 12:30 AM | 2026-04-20 12:40 AM | BUG-026: Append UUID suffix to channel_id in `server/scope/side_channel_engine.py` |
| 4.7 | Completed | 2026-04-20 12:40 AM | 2026-04-20 12:45 AM | Add tests for all 6 fixes |
| 4.8 | Completed | 2026-04-20 12:45 AM | 2026-04-20 12:45 AM | Update bug statuses in `docs/bugs.md` |
| 4.9 | Completed | 2026-04-20 12:40 AM | 2026-04-20 12:45 AM | Run pytest + ruff, fix any failures |

### Phase 4 Summary

- **Changes:** Fixed 6 bugs. BUG-036: SocialOutcome converted to `str, Enum`. BUG-037: Unknown action_key logs warning. BUG-038: `_derive_stance` adds "suspicious" zone for mean_trust in [-60, -20). BUG-039: `remove_character` preserves player_id when other characters of same player remain. BUG-025: Audit fact_ids use `new_id()`. BUG-026: Channel IDs include UUID suffix. 11 new tests, 1439 total passing.
- **Commit:** `P2 bug-fix Phase 4: NPC type safety, scene membership, side channel uniqueness`

## Phase 5: Model Contracts & Error Handling

**Goal:** Model pipeline logs errors, type coercion correct, routing strict, templates fail visibly.
**Depends on:** Phase 4.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 5.1 | Completed | 2026-04-20 12:50 AM | 2026-04-20 1:00 AM | BUG-048: Check bool before int in `models/contracts/output_repair.py` |
| 5.2 | Completed | 2026-04-20 12:50 AM | 2026-04-20 1:00 AM | BUG-050: Reject unknown task types in `models/fast/router.py` |
| 5.3 | Completed | 2026-04-20 12:50 AM | 2026-04-20 1:00 AM | BUG-051: Use json.dumps() for inline schema in `models/contracts/context_assembly.py` |
| 5.4 | Completed | 2026-04-20 12:50 AM | 2026-04-20 1:00 AM | BUG-062: Log SchemaValidationError reason in `models/main/tasks.py` |
| 5.5 | Completed | 2026-04-20 12:50 AM | 2026-04-20 1:00 AM | BUG-063: Log warning on template rendering failure in `models/contracts/context_assembly.py` |
| 5.6 | Completed | 2026-04-20 12:50 AM | 2026-04-20 1:00 AM | BUG-064: Narrow except scope in `server/reliability/model_recovery.py` |
| 5.7 | Completed | 2026-04-20 12:50 AM | 2026-04-20 1:00 AM | BUG-061: Cap histogram list in `server/observability/metrics.py` |
| 5.8 | Completed | 2026-04-20 1:00 AM | 2026-04-20 1:10 AM | Add tests for all 7 fixes |
| 5.9 | Completed | 2026-04-20 1:10 AM | 2026-04-20 1:10 AM | Update bug statuses in `docs/bugs.md` |
| 5.10 | Completed | 2026-04-20 1:00 AM | 2026-04-20 1:10 AM | Run pytest + ruff, fix any failures |

### Phase 5 Summary

- **Changes:** Fixed 7 bugs. BUG-048: Boolean checked before integer in type validation. BUG-050: Unknown task types raise ValueError. BUG-051: `json.dumps()` for inline schema. BUG-062: SchemaValidationError logged with reason. BUG-063: Template rendering failures logged. BUG-064: Narrowed except to `(httpx.HTTPError, RuntimeError, ValueError, KeyError)`. BUG-061: Histogram capped with reservoir sampling. Updated 1 existing test. 12 new tests, 1451 total passing.
- **Commit:** `P2 bug-fix Phase 5: Model pipeline error handling, type safety, metrics cap`

## Phase 6: API Routes, Bot & Scenarios

**Goal:** API route correctness, bot output safety, scenario loading informative, connection reuse.
**Depends on:** Phase 5.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 6.1 | Open | | | BUG-046: Route leave_channel through SideChannelEngine in `server/api/routes.py` |
| 6.2 | Open | | | BUG-047: Fix map discovered adjacency logic in `server/api/routes.py` |
| 6.3 | Open | | | BUG-066: Truncate narration to 4096 chars in `bot/commands.py` |
| 6.4 | Open | | | BUG-052: Preserve YAML parse error context in `scenarios/loader.py` |
| 6.5 | Open | | | BUG-054: Replace unsafe casts in `scenarios/archetypes.py` |
| 6.6 | Open | | | BUG-057: Create shared httpx.AsyncClient per adapter in `models/fast/adapter.py` + `models/main/adapter.py` |
| 6.7 | Open | | | Add tests for all 6 fixes |
| 6.8 | Open | | | Update bug statuses in `docs/bugs.md` |
| 6.9 | Open | | | Run pytest + ruff, fix any failures |

### Phase 6 Summary

- **Changes:** TBD
- **Commit:** `P2 bug-fix Phase 6: API routes, bot safety, scenario errors, connection reuse`

## Phase 7: Datetime Hardening & Final Sweep

**Goal:** Datetime handling consistent. Replay warns on missing actions. Docs updated.
**Depends on:** Phase 6.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 7.1 | Open | | | BUG-027: Audit all `replace(tzinfo=None)` calls; use `utc_now()` from helpers consistently |
| 7.2 | Open | | | BUG-028: Log warning on missing action IDs in replay_turn in `server/engine/turn_engine.py` |
| 7.3 | Open | | | Add tests for datetime consistency and replay warning |
| 7.4 | Open | | | Update bug statuses in `docs/bugs.md` |
| 7.5 | Open | | | Update `docs/phase_status.md` and `STARTUP.md` with P2 bug-fix summary |
| 7.6 | Open | | | Run pytest + ruff, fix any failures |

### Phase 7 Summary

- **Changes:** TBD
- **Commit:** `P2 bug-fix Phase 7: Datetime hardening, replay warning, docs update`
