# Bug-Fix P0 + P1 — Implementation Plan

**Source document:** `docs/bugfix_pdr.md`

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

## Phase 1: Security & Scope (P0)

**Goal:** All 3 P0 bugs closed. No auth bypass, path traversal, or scope leakage.
**Depends on:** Nothing (first phase).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 1.1 | Completed | 2026-04-19 10:45 PM | 2026-04-19 10:50 PM | BUG-001: Remove `bot_token` from `ValidateAuthRequest` in `server/api/routes.py`; read token from env/config server-side |
| 1.2 | Completed | 2026-04-19 10:50 PM | 2026-04-19 10:52 PM | BUG-002: Sanitize scenario path in `bot/commands.py` cmd_newgame — resolve against `scenarios/` root, reject `..` |
| 1.3 | Completed | 2026-04-19 10:52 PM | 2026-04-19 10:58 PM | BUG-003: Fix `can_player_see_fact` in `server/scope/engine.py` — check `granted_to_scope_id` matches player's scope |
| 1.4 | Completed | 2026-04-19 10:58 PM | 2026-04-19 11:05 PM | Add tests for all 3 P0 fixes |
| 1.5 | Completed | 2026-04-19 11:05 PM | 2026-04-19 11:06 PM | Update BUG-001, 002, 003 status in `docs/bugs.md` |
| 1.6 | Completed | 2026-04-19 11:06 PM | 2026-04-19 11:08 PM | Run pytest + ruff, fix any failures |

### Phase 1 Summary

- **Changes:** Removed `bot_token` from `ValidateAuthRequest`, added `set_bot_token()` injection and env fallback. Sanitized `/newgame` path against `scenarios/` root. Fixed `can_player_see_fact` to check `granted_to_scope_id` against player's scopes. 9 new tests, 1338 total passing.
- **Commit:** `Bug-fix Phase 1: Close P0 security bugs (auth bypass, path traversal, scope leakage)`

## Phase 2: Bot Handler None Guards

**Goal:** All bot handlers safely handle None `effective_user`, `message`, `from_user`.
**Depends on:** Phase 1.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 2.1 | Completed | 2026-04-19 11:10 PM | 2026-04-19 11:15 PM | BUG-016/017: Add None guards for `effective_user` and `message` at top of all 10 cmd_* handlers in `bot/commands.py` |
| 2.2 | Completed | 2026-04-19 11:10 PM | 2026-04-19 11:11 PM | BUG-018: Fix `_registry()` in `bot/commands.py` — don't create empty BotRegistry on fallback |
| 2.3 | Completed | 2026-04-19 11:15 PM | 2026-04-19 11:16 PM | BUG-019: Add `from_user` None guard in `bot/handlers.py` message handler |
| 2.4 | Completed | 2026-04-19 11:16 PM | 2026-04-19 11:18 PM | Add tests for None guard behavior |
| 2.5 | Completed | 2026-04-19 11:18 PM | 2026-04-19 11:19 PM | Update BUG-016, 017, 018, 019 status in `docs/bugs.md` |
| 2.6 | Completed | 2026-04-19 11:19 PM | 2026-04-19 11:20 PM | Run pytest + ruff, fix any failures |

### Phase 2 Summary

- **Changes:** Added None guards for `effective_user`, `message`, and `from_user` to all 10 bot command handlers and the private message handler. Fixed `_registry()` to raise RuntimeError instead of creating empty BotRegistry. 20 new tests, 1358 total passing.
- **Commit:** `Bug-fix Phase 2: Bot handler None guards and registry fallback`

## Phase 3: Combat Pipeline

**Goal:** Damage pipeline consistent, HP clamped, status effects expire, morale enum.
**Depends on:** Phase 2.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 3.1 | Open | | | BUG-004: Clamp HP to zero in `server/combat/resolution.py` apply_damage_to_character |
| 3.2 | Open | | | BUG-005/006: Refactor `server/combat/actions.py` resolve_attack to delegate damage to CombatResolutionEngine |
| 3.3 | Open | | | BUG-007: Add `clear_turn_effects` method to resolution.py; remove "defended" status at turn boundary |
| 3.4 | Open | | | BUG-024: Add `MoraleState` enum to `server/domain/enums.py`; update `conditions.py` and `entities.py` |
| 3.5 | Open | | | Add tests for HP clamp, damage delegation, status cleanup, morale enum |
| 3.6 | Open | | | Update BUG-004, 005, 006, 007, 024 status in `docs/bugs.md` |
| 3.7 | Open | | | Run pytest + ruff, fix any failures |

### Phase 3 Summary

- **Changes:** TBD
- **Commit:** `Bug-fix Phase 3: Combat pipeline — HP clamp, damage delegation, status cleanup, morale enum`

## Phase 4: Contract Drift

**Goal:** All prompt contracts match schema validators. No NPC state leakage.
**Depends on:** Phase 3.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 4.1 | Open | | | BUG-020: Align combat_summary contract in `models/contracts/main_contracts.py` — "narration"→"summary", "tone"→"tension" |
| 4.2 | Open | | | BUG-021: Align ruling_proposal contract — remove "success"/"confidence", use "ruling"/"reason" per schemas.py |
| 4.3 | Open | | | BUG-022: Align npc_dialogue contract — remove "internal_thought"/"trust_shift_suggestion", use "dialogue"/"action_beat"/"mood" |
| 4.4 | Open | | | Add tests verifying contract output_schema keys match validate_* expectations |
| 4.5 | Open | | | Update BUG-020, 021, 022 status in `docs/bugs.md` |
| 4.6 | Open | | | Run pytest + ruff, fix any failures |

### Phase 4 Summary

- **Changes:** TBD
- **Commit:** `Bug-fix Phase 4: Align prompt contracts with schema validators`

## Phase 5: Timer + Orchestrator

**Goal:** Timer state machine correct. Idempotency deterministic. Per-scene public scope.
**Depends on:** Phase 4.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 5.1 | Open | | | BUG-010: Raise ValueError on None expires_at in `server/timer/controller.py` check_expiry |
| 5.2 | Open | | | BUG-011: Add paused→early_closed to transition table in `server/timer/controller.py` |
| 5.3 | Open | | | BUG-012: Replace `hash(text)` with `hashlib.sha256` in `server/orchestrator/game_loop.py` |
| 5.4 | Open | | | BUG-013: Include scene_id in public scope lookup in `server/orchestrator/game_loop.py` and extend `ConversationScopeRepo` |
| 5.5 | Open | | | Add tests for timer ValueError, transition, deterministic idem keys, per-scene scope |
| 5.6 | Open | | | Update BUG-010, 011, 012, 013 status in `docs/bugs.md` |
| 5.7 | Open | | | Run pytest + ruff, fix any failures |

### Phase 5 Summary

- **Changes:** TBD
- **Commit:** `Bug-fix Phase 5: Timer state machine, deterministic idempotency, per-scene scope`

## Phase 6: NPC/Social + Scene

**Goal:** NPC trust rollback on failure. Scene transfer atomicity verified.
**Depends on:** Phase 5.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 6.1 | Open | | | BUG-008: Add trust snapshot + restore on failure in `server/npc/social.py` |
| 6.2 | Open | | | BUG-009: Verify transfer_character rollback in `server/scene/membership.py`; add warning log on rollback |
| 6.3 | Open | | | Add tests for trust rollback, transfer rollback logging |
| 6.4 | Open | | | Update BUG-008, 009 status in `docs/bugs.md` |
| 6.5 | Open | | | Run pytest + ruff, fix any failures |

### Phase 6 Summary

- **Changes:** TBD
- **Commit:** `Bug-fix Phase 6: NPC trust rollback and scene transfer atomicity`

## Phase 7: Reliability + Model

**Goal:** Model adapters report failures honestly. Recovery pipeline verified.
**Depends on:** Phase 6.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 7.1 | Open | | | BUG-014: Verify turn_recovery DB fix is complete; close if so |
| 7.2 | Open | | | BUG-015: Fix `_invoke_fallback` in `server/reliability/model_recovery.py` — return success=False + log warning on async discard |
| 7.3 | Open | | | BUG-023: Fix `models/main/adapter.py` — return success=False on empty choices |
| 7.4 | Open | | | Add tests for async fallback failure, empty choices failure |
| 7.5 | Open | | | Update BUG-014, 015, 023 status in `docs/bugs.md` |
| 7.6 | Open | | | Run pytest + ruff, fix any failures |
| 7.7 | Open | | | Update `docs/phase_status.md` and `STARTUP.md` with bug-fix summary |

### Phase 7 Summary

- **Changes:** TBD
- **Commit:** `Bug-fix Phase 7: Model adapter failure reporting and recovery verification`
