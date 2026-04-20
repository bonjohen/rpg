# Bug Tracker

## Severity Definitions

- **P0:** Data loss, scope leakage, security issue — must fix before release
- **P1:** Gameplay-breaking bug — must fix before release
- **P2:** Quality/polish issue — fix if time permits
- **P3:** Enhancement — defer to post-release

## Open Bugs

| ID | Severity | Category | Description | File | Status |
|---|---|---|---|---|---|
| BUG-001 | P2 | Routing | OpenAI inference adapter requires live API key; all narration uses deterministic fallback without it | `models/main/adapter.py` | Deferred (requires OPENAI_API_KEY) |
| BUG-002 | P3 | Clarity | Narration fallback text is functional but repetitive across turns | `models/main/fallback.py` | Open |
| BUG-003 | P3 | Enhancement | No persistent storage; all state is in-memory (by design for playtest) | — | Deferred (post-Phase 20) |
| BUG20260419-001 | P0 | Security | Bot token accepted from client in /api/auth/validate — attacker can forge auth for any user | `server/api/routes.py:71` | Open |
| BUG20260419-002 | P0 | Security | Path traversal in /newgame — user-supplied path passed directly to file open | `bot/commands.py:158` | Open |
| BUG20260419-003 | P0 | Scope Leakage | Visibility grant check is overly permissive — any grant for a fact makes it visible to ALL players | `server/scope/engine.py:170` | Open |
| BUG20260419-004 | P1 | Correctness | HP not clamped to zero — negative HP causes inflated healing and negative display | `server/combat/resolution.py:33` | Open |
| BUG20260419-005 | P1 | Correctness | resolve_attack() does not apply damage to target — caller must separately apply, but coupling is implicit | `server/combat/actions.py:111` | Open |
| BUG20260419-006 | P1 | Correctness | Damage pipeline split across actions.py and resolution.py with inconsistent defense models | `server/combat/actions.py` + `server/combat/resolution.py` | Open |
| BUG20260419-007 | P1 | Correctness | "defended" status effect never removed at end of turn — permanent +3 armor | `server/combat/resolution.py:29` | Open |
| BUG20260419-008 | P1 | Correctness | NPC mutation in social engine has no rollback — failed outcomes still permanently reduce trust | `server/npc/social.py:106` | Open |
| BUG20260419-009 | P1 | Correctness | transfer_character claims atomicity but rollback can silently fail | `server/scene/membership.py:106` | Open |
| BUG20260419-010 | P1 | Correctness | Running timer with expires_at=None returns "not expired, 0 remaining" instead of error | `server/timer/controller.py:208` | Open |
| BUG20260419-011 | P1 | Correctness | trigger_early_close bypasses state machine — paused-to-early_closed not in transition table | `server/timer/controller.py:232` | Open |
| BUG20260419-012 | P1 | Correctness | Idempotency key uses hash() which is randomized per process — breaks across restarts | `server/orchestrator/game_loop.py:493` | Open |
| BUG20260419-013 | P1 | Correctness | All scenes share one public scope — multi-scene scope separation broken | `server/orchestrator/game_loop.py:638` | Open |
| BUG20260419-014 | P1 | Correctness | Scene.player_ids not maintained by orchestrator — turn recovery gets zero pending players | `server/reliability/turn_recovery.py:88` | Open |
| BUG20260419-015 | P1 | Correctness | model_recovery returns success=True with empty dict when async fallback silently discarded | `server/reliability/model_recovery.py:117` | Open |
| BUG20260419-016 | P1 | Correctness | Unguarded update.effective_user None access in all bot command handlers | `bot/commands.py:47` | Open |
| BUG20260419-017 | P1 | Correctness | Unguarded update.message None access in all bot command handlers | `bot/commands.py:48` | Open |
| BUG20260419-018 | P1 | Correctness | Fresh empty BotRegistry created on every fallback lookup — players never found | `bot/commands.py:39` | Open |
| BUG20260419-019 | P1 | Correctness | Unguarded message.from_user None access in handlers.py | `bot/handlers.py:107` | Open |
| BUG20260419-020 | P1 | Contract Drift | combat_summary contract requires "narration" but schemas.py expects "summary" | `models/contracts/main_contracts.py:196` | Open |
| BUG20260419-021 | P1 | Contract Drift | ruling_proposal contract fields mismatch schemas.py (reason vs reasoning, etc.) | `models/contracts/main_contracts.py:238` | Open |
| BUG20260419-022 | P1 | Contract Drift | npc_dialogue contract has internal_thought field that could leak NPC private state | `models/contracts/main_contracts.py:143` | Open |
| BUG20260419-023 | P1 | Correctness | OpenAI adapter returns success=True on empty choices array | `models/main/adapter.py:157` | Open |
| BUG20260419-024 | P1 | Correctness | Morale state raw strings — typo silently prevents combat from ending | `server/combat/conditions.py:74` | Open |
| BUG20260419-025 | P2 | Correctness | Side channel audit fact_id collision — same player, same channel, multiple messages | `server/scope/side_channel_audit.py:56` | Open |
| BUG20260419-026 | P2 | Correctness | Side channel_id collision on duplicate labels within campaign | `server/scope/side_channel_engine.py:89` | Open |
| BUG20260419-027 | P2 | Correctness | Naive datetime stripping (replace(tzinfo=None)) used in 10+ files — fragile | Multiple files | Open |
| BUG20260419-028 | P2 | Correctness | replay_turn() silently drops missing action IDs | `server/engine/turn_engine.py:486` | Open |
| BUG20260419-029 | P2 | Correctness | search() does not flip item.is_hidden=False — items rediscovered every search | `server/exploration/actions.py:301` | Open |
| BUG20260419-030 | P2 | Correctness | Trigger on_enter/on_exit ambiguity — caller must split evaluation correctly | `server/exploration/triggers.py:231` | Open |
| BUG20260419-031 | P2 | Correctness | Trigger _apply() always scopes facts privately regardless of fact content | `server/exploration/triggers.py:281` | Open |
| BUG20260419-032 | P2 | Correctness | Clue discover() allows double-discovery — no idempotency guard | `server/exploration/clues.py:282` | Open |
| BUG20260419-033 | P2 | Correctness | Monster damage: damage=3+ kills exactly 1 unit regardless of magnitude | `server/combat/resolution.py:51` | Open |
| BUG20260419-034 | P2 | Correctness | Combat move validates destination but not direction | `server/combat/actions.py:239` | Open |
| BUG20260419-035 | P2 | Correctness | resolve_use_item heal amount from dict could be string — TypeError | `server/combat/actions.py:192` | Open |
| BUG20260419-036 | P2 | Correctness | SocialOutcome is plain class, not Enum — typos pass silently | `server/npc/social.py:60` | Open |
| BUG20260419-037 | P2 | Correctness | apply_action_delta returns 0 for unknown action_key — typos silently ignored | `server/npc/trust.py:160` | Open |
| BUG20260419-038 | P2 | Correctness | Trust _derive_stance has no "suspicious" zone despite docstring claiming it | `server/npc/trust.py:189` | Open |
| BUG20260419-039 | P2 | Correctness | remove_character unconditionally removes player_id even if other chars remain | `server/scene/membership.py:65` | Open |
| BUG20260419-040 | P2 | Correctness | Timer pause truncation drift — int() instead of round() loses up to 1s per cycle | `server/timer/controller.py:256` | Open |
| BUG20260419-041 | P2 | Correctness | Timer resume with 0 remaining gets free extra second — can never truly expire | `server/timer/controller.py:275` | Open |
| BUG20260419-042 | P2 | Correctness | timer integration uses raw strings for ActionState comparison | `server/timer/integration.py:77` | Open |
| BUG20260419-043 | P2 | Correctness | timeout_players empty list coerced to None via `or None` | `server/orchestrator/game_loop.py:432` | Open |
| BUG20260419-044 | P2 | Correctness | Diagnostics always reports ALL players as pending in stuck turns | `server/observability/diagnostics.py:153` | Open |
| BUG20260419-045 | P2 | Correctness | fast_model_responsive threshold too permissive — 1 success masks 9 failures | `server/observability/diagnostics.py:221` | Open |
| BUG20260419-046 | P2 | Correctness | leave_channel mutates entity directly, bypassing SideChannelEngine | `server/api/routes.py:588` | Open |
| BUG20260419-047 | P2 | Correctness | Map discovered logic wrong — adjacent scenes shown as undiscovered | `server/api/routes.py:686` | Open |
| BUG20260419-048 | P2 | Correctness | output_repair bool/int type confusion — isinstance(True, int) passes | `models/contracts/output_repair.py:75` | Open |
| BUG20260419-049 | P2 | Correctness | combat_summary contract fallback has invalid tone "medium" | `models/contracts/main_contracts.py:206` | Open |
| BUG20260419-050 | P2 | Correctness | is_fast_tier admits unknown tasks — typos route to fast tier silently | `models/fast/router.py:44` | Open |
| BUG20260419-051 | P2 | Correctness | Narration system prompt uses Python single quotes instead of JSON double quotes | `models/main/context.py:144` | Open |
| BUG20260419-052 | P2 | Correctness | ScenarioLoader YAML parse error context lost — user gets generic "Failed" | `scenarios/loader.py:199` | Open |
| BUG20260419-053 | P2 | Correctness | puzzle_patterns.create_puzzle mutates caller's overrides dict via pop() | `scenarios/puzzle_patterns.py:48` | Open |
| BUG20260419-054 | P2 | Correctness | scenarios/archetypes.py unsafe casts from object overrides with type: ignore | `scenarios/archetypes.py:38` | Open |
| BUG20260419-055 | P2 | Security | API endpoints return player data without authentication | `server/api/routes.py:88` | Open |
| BUG20260419-056 | P2 | Security | Action submission endpoint does not verify authenticated user | `server/api/routes.py:277` | Open |
| BUG20260419-057 | P2 | Performance | httpx.AsyncClient created per request in both adapters — connection overhead | `models/fast/adapter.py:90` + `models/main/adapter.py:117` | Open |
| BUG20260419-058 | P2 | Performance | Turn number computed by scanning entire turn_log — O(n) on every open_turn | `server/orchestrator/game_loop.py:268` | Open |
| BUG20260419-059 | P2 | Performance | Linear scan of committed_actions by turn_window_id — repeated O(n) | `server/orchestrator/game_loop.py:344` | Open |
| BUG20260419-060 | P2 | Performance | _get_player_character linear scan on every call — O(characters) | `server/orchestrator/game_loop.py:615` | Open |
| BUG20260419-061 | P2 | Performance | Histogram values unbounded list — percentile sort is O(n log n) per query | `server/observability/metrics.py:101` | Open |
| BUG20260419-062 | P2 | Error Handling | SchemaValidationError reason silently discarded in all task functions | `models/main/tasks.py:107` | Open |
| BUG20260419-063 | P2 | Error Handling | Silent template rendering failures in context_assembly — placeholders sent to LLM | `models/contracts/context_assembly.py:269` | Open |
| BUG20260419-064 | P2 | Error Handling | model_recovery broad except Exception catches programming errors as fallback | `server/reliability/model_recovery.py:97` | Open |
| BUG20260419-065 | P2 | Error Handling | Bot leaks internal player UUIDs to Telegram users | `bot/commands.py:124` | Open |
| BUG20260419-066 | P2 | Error Handling | AI-generated narration sent to Telegram without length check or sanitization | `bot/commands.py:221` | Open |
| BUG20260419-067 | P2 | Design | _now()/_new_id() helpers duplicated identically in 5+ files | Multiple files | Fixed |
| BUG20260419-068 | P2 | Design | Module-level singletons in timer/integration.py block testability | `server/timer/integration.py:36` | Fixed |
| BUG20260419-069 | P2 | Design | API routes access orchestrator private methods directly | `server/api/routes.py:95` | Fixed |
| BUG20260419-070 | P2 | Design | Orchestrator stored in module-level global — prevents DI and testing | `server/api/routes.py:51` | Open |
| BUG20260419-071 | P2 | Design | Scope engine fallback creates fake ConversationScope with empty IDs | `server/scope/engine.py:295` | Open |
| BUG20260419-072 | P2 | Design | bot/outbound.py accesses BotRegistry private _user_to_player dict | `bot/outbound.py:130` | Open |
| BUG20260419-073 | P3 | Data Model | NPC.health_state, stance_to_party, MonsterGroup.morale_state are raw strings not enums | `server/domain/entities.py:271` | Open |
| BUG20260419-074 | P3 | Data Model | InventoryItem dual-owner fields (character + scene) not enforced by __post_init__ | `server/domain/entities.py:335` | Open |
| BUG20260419-075 | P3 | Data Model | SideChannelEngine.create_channel created_at typed as object not datetime | `server/scope/side_channel_engine.py:60` | Open |
| BUG20260419-076 | P3 | Data Model | facts.py validate_fact_creation None check on non-Optional parameter | `server/scope/facts.py:70` | Open |
| BUG20260419-077 | P3 | Data Model | SocialActionInput.extra dead field — never read anywhere | `server/npc/social.py:91` | Open |
| BUG20260419-078 | P3 | Correctness | Memory recall_description off-by-one: visit_count=1 says "once before" | `server/exploration/memory.py:209` | Open |
| BUG20260419-079 | P3 | Correctness | Monster ambush code sets flag but applies no bonus — dead code | `server/combat/monsters.py:109` | Open |
| BUG20260419-080 | P3 | Correctness | /api/player/{id}/inbox `since` parameter accepted but ignored | `server/api/routes.py:397` | Open |
| BUG20260419-081 | P3 | Correctness | Quest title displays quest_id (UUID) instead of human-readable name | `server/api/routes.py:613` | Open |
| BUG20260419-082 | P3 | Performance | Scene scoped_prompts O(n*m) ID membership checks on lists | `server/scene/scoped_prompts.py:57` | Open |
| BUG20260419-083 | P3 | Performance | BFS in scenario validator uses list.pop(0) — O(n^2) | `scenarios/validator.py:376` | Open |
| BUG20260419-084 | P3 | Performance | Scope violation detection is O(n*m) substring search | `models/contracts/context_assembly.py:219` | Open |
| BUG20260419-085 | P3 | Design | Leakage guard module-level singletons couple import to instantiation | `server/scope/leakage_guard.py:30` | Fixed |
| BUG20260419-086 | P3 | Design | Deferred stdlib imports in side_channel_engine (datetime) | `server/scope/side_channel_engine.py:77` | Fixed |

## Resolved Bugs

None yet.

---

## Details

### BUG20260419-001 — Bot token accepted from client

**File:** `server/api/routes.py:71`
**Severity:** P0
**Category:** Security
**Description:** The `/api/auth/validate` endpoint accepts `bot_token` as a request body field from the client. Any caller can supply an arbitrary bot token and forge valid Telegram WebApp initData for any user_id, completely defeating authentication.
**Suggested fix:** Store the bot_token in server configuration (BotConfig) and read it server-side. The endpoint should only accept `init_data` from the client.

### BUG20260419-002 — Path traversal in /newgame

**File:** `bot/commands.py:158` -> `scenarios/loader.py:93`
**Severity:** P0
**Category:** Security
**Description:** `cmd_newgame` passes user-supplied text from Telegram directly to `ScenarioLoader.load_from_yaml()` which calls `open(yaml_path)`. No validation that the path is within the allowed scenarios directory. A malicious user could read arbitrary server files.
**Suggested fix:** Use `pathlib.Path.resolve()` and verify the resolved path starts with the allowed scenarios base directory. Restrict `/newgame` to admin users.

### BUG20260419-003 — Visibility grant overly permissive

**File:** `server/scope/engine.py:170`
**Severity:** P0
**Category:** Scope Leakage
**Description:** In `can_player_see_fact()`, the grant check returns True for any matching VisibilityGrant regardless of who the grant targets. If Player A has a private fact with a grant to Player B, Player C also sees it because the grant loop doesn't verify the granted_to_scope covers the requesting player.
**Suggested fix:** Verify that `grant.granted_to_scope_id` corresponds to a public scope, the requesting player's own private scope, or a side channel the requesting player belongs to.

### BUG20260419-004 — HP not clamped to zero

**File:** `server/combat/resolution.py:33`
**Severity:** P1
**Category:** Correctness
**Description:** `apply_damage_to_character()` allows HP to go negative. Negative HP persists in `character.stats["hp"]`, causing inflated healing calculations (`max_hp - hp` with negative hp) and negative HP displayed to players.
**Suggested fix:** Clamp: `new_hp = max(0, hp - final_damage)`.

### BUG20260419-005 — resolve_attack does not apply damage

**File:** `server/combat/actions.py:111`
**Severity:** P1
**Category:** Correctness
**Description:** `resolve_attack()` computes damage against a monster group but does not mutate `group.count`. Returns the computed damage but the caller must separately call `apply_damage_to_group()`, and the two systems have different defense calculations.
**Suggested fix:** Unify the damage pipeline. Either `resolve_attack` should call through to `apply_damage_to_group`, or the pipeline should be clearly documented with a single source of truth for defense math.

### BUG20260419-006 — Split damage pipeline

**File:** `server/combat/actions.py` + `server/combat/resolution.py`
**Severity:** P1
**Category:** Correctness
**Description:** Damage calculation is split across two modules with inconsistent defense models. The "defended" +3 armor is duplicated in both. If the defense bonus changes, it must be updated in two places.
**Suggested fix:** Centralize the damage pipeline in one module.

### BUG20260419-007 — Permanent "defended" status

**File:** `server/combat/resolution.py:29`
**Severity:** P1
**Category:** Correctness
**Description:** The "defended" status effect grants +3 armor but is never removed at end of turn. `resolve_defend()` adds it, but nothing expires it. Defense becomes a permanent buff.
**Suggested fix:** Add a round-end cleanup step that removes transient effects like "defended" and "assisted".

### BUG20260419-008 — NPC trust mutation without rollback

**File:** `server/npc/social.py:106`
**Severity:** P1
**Category:** Correctness
**Description:** Social engine mutates NPC trust/stance/memory in place before checking outcomes. Failed outcomes (e.g., ESCALATION from threaten) still permanently reduce trust. No rollback path exists.
**Suggested fix:** Snapshot NPC state before dispatch and restore on failure, or document that all outcomes (including failures) intentionally persist trust changes.

### BUG20260419-009 — transfer_character non-atomic

**File:** `server/scene/membership.py:106`
**Severity:** P1
**Category:** Correctness
**Description:** Claims atomicity but if `add_character` to destination fails, the rollback `add_character` back to source can itself fail silently, leaving the character in neither scene.
**Suggested fix:** Check rollback result and raise/log if rollback also fails. Document single-threaded assumption.

### BUG20260419-010 — Timer running with None expires_at

**File:** `server/timer/controller.py:208`
**Severity:** P1
**Category:** Correctness
**Description:** A running timer with `expires_at=None` (invalid state) returns `has_expired=False, seconds_remaining=0`. The tick loop will never expire this timer.
**Suggested fix:** Guard: if state==running and expires_at is None, raise TimerError or return an error result.

### BUG20260419-011 — Early close bypasses state machine

**File:** `server/timer/controller.py:232`
**Severity:** P1
**Category:** Correctness
**Description:** `trigger_early_close` accepts paused timers but doesn't use `_assert_timer_transition`. The transition table only allows paused -> {running, stopped}, not paused -> early_closed.
**Suggested fix:** Add `TimerState.early_closed` to allowed transitions from paused, or enforce the transition table in trigger_early_close.

### BUG20260419-012 — Randomized idempotency key

**File:** `server/orchestrator/game_loop.py:493`
**Severity:** P1
**Category:** Correctness
**Description:** Idempotency key uses Python's `hash()` which is randomized per process (PYTHONHASHSEED). Keys differ across restarts, so duplicate messages after restart are not detected. Also, hash collisions can silently drop distinct messages.
**Suggested fix:** Use `hashlib.sha256(text.encode()).hexdigest()[:16]`.

### BUG20260419-013 — All scenes share one public scope

**File:** `server/orchestrator/game_loop.py:638`
**Severity:** P1
**Category:** Correctness
**Description:** `_get_or_create_public_scope` returns the first public scope found regardless of scene_id. In a multi-scene campaign, all scenes share one scope, breaking per-scene visibility.
**Suggested fix:** Create one public scope per scene; filter by scene_id.

### BUG20260419-014 — Scene.player_ids not maintained

**File:** `server/reliability/turn_recovery.py:88`
**Severity:** P1
**Category:** Correctness
**Description:** Recovery engine reads `scene.player_ids` but the orchestrator never maintains this field. Default empty list means recovery synthesizes zero fallback actions.
**Suggested fix:** Keep `Scene.player_ids` in sync in add_player/transfer_character, or change recovery to accept player_ids from the character index.

### BUG20260419-015 — Silent async fallback discard

**File:** `server/reliability/model_recovery.py:117`
**Severity:** P1
**Category:** Correctness
**Description:** `_invoke_fallback` detects an async fallback function, closes the coroutine, and returns empty dict. Caller reports `success=True` with empty data, masking the failure entirely.
**Suggested fix:** Log a warning when closing a coroutine. Consider making _invoke_fallback async, or raise if fallback is async.

### BUG20260419-016 — Unguarded effective_user

**File:** `bot/commands.py:47`
**Severity:** P1
**Category:** Correctness
**Description:** `update.effective_user` can be None (channel posts). Every command handler accesses `.id` without a None guard, causing AttributeError.
**Suggested fix:** Add `if user is None: return` after `user = update.effective_user` in each handler.

### BUG20260419-017 — Unguarded update.message

**File:** `bot/commands.py:48`
**Severity:** P1
**Category:** Correctness
**Description:** `update.message` can be None (edited messages, callback queries). Every handler calls `.reply_text()` on it, causing AttributeError.
**Suggested fix:** Add `message = update.effective_message` with a `if message is None: return` guard.

### BUG20260419-018 — Fresh empty BotRegistry on fallback

**File:** `bot/commands.py:39` + `bot/handlers.py:106`
**Severity:** P1
**Category:** Correctness
**Description:** `bot_data.get("registry", BotRegistry())` creates a new empty registry on every call if the key is missing. Player lookups always fail, potentially trapping users in onboarding loops.
**Suggested fix:** Use `bot_data["registry"]` (let it raise KeyError on startup bug), or store a single fallback instance.

### BUG20260419-019 — Unguarded from_user in handlers

**File:** `bot/handlers.py:107`
**Severity:** P1
**Category:** Correctness
**Description:** `message.from_user` can be None. Accessing `.id` raises AttributeError.
**Suggested fix:** Add `if message.from_user is None: return`.

### BUG20260419-020 — combat_summary contract drift

**File:** `models/contracts/main_contracts.py:196`
**Severity:** P1
**Category:** Contract Drift
**Description:** Contract requires field "narration" but `schemas.py` expects "summary". Contract also lacks "outcomes" array. RepairPipeline and validate_combat_summary disagree on field names.
**Suggested fix:** Align contract output_schema with schemas.py.

### BUG20260419-021 — ruling_proposal contract drift

**File:** `models/contracts/main_contracts.py:238`
**Severity:** P1
**Category:** Contract Drift
**Description:** Contract requires [ruling, success, confidence, reasoning] but schemas.py expects [ruling, reason, condition, suggested_action_type, difficulty_class]. Incompatible field sets.
**Suggested fix:** Align contract with schemas.py.

### BUG20260419-022 — npc_dialogue contract internal_thought leak

**File:** `models/contracts/main_contracts.py:143`
**Severity:** P1
**Category:** Contract Drift / Scope
**Description:** Contract has "internal_thought" field that could contain NPC-private reasoning. No equivalent in the validation pipeline to filter it from player-visible output.
**Suggested fix:** Remove internal_thought from contract or ensure downstream filters it.

### BUG20260419-023 — Empty response marked success

**File:** `models/main/adapter.py:157`
**Severity:** P1
**Category:** Correctness
**Description:** When OpenAI API returns 200 with empty choices array (content filtering), adapter returns `GenerateResult(text="", success=True)`. This wastes a fast-tier repair call on empty input.
**Suggested fix:** If `not choices or not text`, return `GenerateResult(success=False, failure_reason="empty_response")`.

### BUG20260419-024 — Morale state raw strings

**File:** `server/combat/conditions.py:74`
**Severity:** P1
**Category:** Data Model
**Description:** morale_state compared as raw string "routed" without enum backing. A typo like "routeed" would silently prevent combat from ending when all monsters have fled.
**Suggested fix:** Define MoraleState enum in `server/domain/enums.py` and use throughout combat code.

### BUG20260419-025 through BUG20260419-086

See table above for one-line descriptions. Detailed descriptions available on request for any specific bug.

---

## Review Summary — 20260419

- **Files reviewed:** ~65 Python files across 17 directories
- **Findings:** 86 total — 3 P0, 21 P1, 48 P2, 14 P3
- **Top concerns:**
  1. **Security (P0):** Bot token from client defeats auth; path traversal in /newgame; scope grant leakage exposes private facts to all players.
  2. **Combat system (P1):** Damage pipeline split across two modules with inconsistent models; HP not clamped; permanent defense buff; attack results not applied to targets.
  3. **Bot handlers (P1):** Every command handler lacks None guards for effective_user, message, and from_user — any non-standard Telegram update causes crashes.
  4. **Contract drift (P1):** Three of six main-tier prompt contracts have field names that don't match the schema validation code.
