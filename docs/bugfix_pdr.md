# Physical Design Requirements: Bug-Fix P0 + P1

**Source document:** `docs/bugfix_design.md`
**Project root:** `C:\Projects\rpg`
**Date:** 2026-04-19 10:30 PM (PST)

## 1. System Context

### 1.1 Existing Infrastructure to Reuse

| Asset | Location | Reuse |
|---|---|---|
| VisibilityGrant.granted_to_scope_id | `server/domain/entities.py` | Already exists on grant entity — just need to check it |
| ConversationScopeRepo.get_public_scope | `server/storage/repository.py` | Extend to accept scene_id filter |
| CombatResolutionEngine | `server/combat/resolution.py` | Already has apply_damage_to_character — wire actions.py to use it |
| remove_status_effect | `server/combat/resolution.py:84` | Already exists — use for "defended" cleanup |
| validate_* functions | `models/main/schemas.py` | Authoritative field names — contracts must match these |
| hashlib | stdlib | Replace hash() for idempotency |
| pathlib.Path.resolve | stdlib | Path traversal prevention |

### 1.2 New Dependencies to Add

None. All fixes use existing dependencies.

## 2. Files to Modify

| File | Bugs | Changes |
|---|---|---|
| `server/api/routes.py` | BUG-001 | Remove bot_token from ValidateAuthRequest; read from config/env |
| `bot/commands.py` | BUG-002, 016, 017, 018 | Path sanitization; None guards; fix _registry() |
| `bot/handlers.py` | BUG-019 | None guard for from_user |
| `server/scope/engine.py` | BUG-003 | Check granted_to_scope_id in can_player_see_fact |
| `server/combat/resolution.py` | BUG-004, 007 | Clamp HP; add clear_turn_effects |
| `server/combat/actions.py` | BUG-005, 006 | Delegate damage to resolution engine |
| `server/combat/conditions.py` | BUG-024 | Use MoraleState enum |
| `server/domain/enums.py` | BUG-024 | Add MoraleState enum |
| `server/domain/entities.py` | BUG-024 | Type morale_state field with enum |
| `models/contracts/main_contracts.py` | BUG-020, 021, 022 | Align all contract output_schemas to match schemas.py |
| `server/timer/controller.py` | BUG-010, 011 | ValueError on None expires_at; fix early_close transition |
| `server/orchestrator/game_loop.py` | BUG-012, 013 | hashlib for idem keys; scene_id in public scope |
| `server/npc/social.py` | BUG-008 | Trust snapshot + restore on failure |
| `server/scene/membership.py` | BUG-009 | Verify rollback; add logging |
| `server/reliability/model_recovery.py` | BUG-015 | Return success=False on async fallback |
| `models/main/adapter.py` | BUG-023 | Return success=False on empty choices |
| `server/reliability/turn_recovery.py` | BUG-014 | Verify fix; close bug |
| `server/storage/repository.py` | BUG-013 | Add scene_id param to get_public_scope |
| `docs/bugs.md` | All | Update status for each fixed bug |

## 3. Test Strategy

Each phase adds targeted tests for the specific bugs fixed. Existing 1327 tests must continue passing. Key test patterns:
- Security: test that forged tokens fail, traversal paths are rejected, grants are scope-checked
- Combat: test HP clamp, damage application, status effect cleanup, morale enum
- Contracts: test that contract output_schema fields match validate_* expectations
- Timer: test ValueError on None, transition rejection from paused
- Orchestrator: test deterministic idem keys, per-scene public scope

## 4. Verification Criteria

1. All existing 1327 tests pass
2. New tests cover each bug fix
3. `ruff check . && ruff format --check .` clean
4. Each bug status updated in `docs/bugs.md`
5. No `hash()` calls for idempotency
6. No `bot_token` in request models
7. No unguarded `update.effective_user` access
