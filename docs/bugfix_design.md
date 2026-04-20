# Bug-Fix Design Document: P0 + P1 Bugs

## 1. Purpose

Close all 3 P0 (security) and 21 P1 (gameplay-breaking) bugs before release. These bugs span security (auth bypass, path traversal, scope leakage), combat pipeline (damage not applied, HP not clamped, permanent status effects), bot reliability (None guards), contract drift (field mismatches between prompt contracts and schema validators), timer state machine (invalid transitions), orchestrator correctness (non-deterministic idempotency, shared public scope), NPC trust rollback, and model adapter failure reporting.

## 2. Scope

24 bugs total across 7 fix clusters. Each cluster is independently shippable. No new features — only correctness and security fixes.

## 3. Core Design Principles

- **Fix at the source.** Don't add workarounds downstream; fix the root cause in the owning module.
- **One defense model.** Consolidate duplicated armor/defense logic into `resolution.py`. `actions.py` delegates all damage math.
- **Fail loud.** Model adapters, recovery functions, and timer operations must report failures honestly — never return success with empty data.
- **Contracts match schemas.** The prompt contract output_schema must exactly match what `validate_*` functions in `schemas.py` expect.
- **Guards at boundaries.** Bot handlers guard against None at entry. API endpoints read secrets server-side.

## 4. Primary User Stories

- As a player, I cannot forge authentication or access another player's private data (P0 security).
- As a player, combat damage is applied correctly and status effects expire (P1 combat).
- As a player, the bot does not crash when Telegram sends unexpected None fields (P1 bot).
- As a developer, prompt contracts and schema validators agree on field names (P1 contracts).
- As the server, timer transitions follow the state machine, idempotency keys survive restarts, and each scene has its own public scope (P1 orchestrator).

## 5. Functional Requirements

### 5.1 Security (P0)

BUG-001: Remove `bot_token` from `ValidateAuthRequest`. Read from server config or environment. BUG-002: Sanitize `/newgame` path against `scenarios/` root. BUG-003: Check `granted_to_scope_id` against requesting player's scopes in `can_player_see_fact`.

### 5.2 Bot Handlers (P1)

BUG-016/017/018/019: Add None guards for `effective_user`, `message`, `from_user` at top of every handler. Fix `_registry()` to not create empty fallback.

### 5.3 Combat Pipeline (P1)

BUG-004: Clamp HP to zero. BUG-005/006: `resolve_attack` delegates to resolution engine for damage application and defense calculation. BUG-007: Add `clear_turn_effects` to remove "defended" at turn boundaries. BUG-024: Add `MoraleState` enum to `enums.py`; use in conditions.py and entities.py.

### 5.4 Contract Drift (P1)

BUG-020: Align combat_summary to use "summary"/"tension" (matching schemas.py). BUG-021: Align ruling_proposal to use "ruling"/"reason" (matching schemas.py). BUG-022: Remove "internal_thought" from npc_dialogue contract; align to "dialogue"/"action_beat"/"mood".

### 5.5 Timer + Orchestrator (P1)

BUG-010: Raise ValueError on None expires_at in check_expiry. BUG-011: Either add paused→early_closed to transition table or reject with error. BUG-012: Replace `hash()` with `hashlib.sha256`. BUG-013: Include scene_id in public scope lookup/creation.

### 5.6 NPC/Social + Scene (P1)

BUG-008: Snapshot trust before resolution; restore on failure. BUG-009: transfer_character rollback is already implemented in-memory; verify DB-level safety.

### 5.7 Reliability + Model (P1)

BUG-014: Verify DB migration fix is complete. BUG-015: Return success=False with error on async fallback discard. BUG-023: Return success=False on empty choices array.
