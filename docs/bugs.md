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
| BUG-003 | P3 | Enhancement | No persistent storage; all state is in-memory (by design for playtest) | — | **Closed** (DB Phases 1–7: all entity state persisted via SQLAlchemy repos, startup recovery, optimistic locking) |
| BUG20260419-001 | P0 | Security | Bot token accepted from client in /api/auth/validate — attacker can forge auth for any user | `server/api/routes.py:71` | **Fixed** |
| BUG20260419-002 | P0 | Security | Path traversal in /newgame — user-supplied path passed directly to file open | `bot/commands.py:158` | **Fixed** |
| BUG20260419-003 | P0 | Scope Leakage | Visibility grant check is overly permissive — any grant for a fact makes it visible to ALL players | `server/scope/engine.py:170` | **Fixed** |
| BUG20260419-004 | P1 | Correctness | HP not clamped to zero — negative HP causes inflated healing and negative display | `server/combat/resolution.py:33` | **Fixed** |
| BUG20260419-005 | P1 | Correctness | resolve_attack() does not apply damage to target — caller must separately apply, but coupling is implicit | `server/combat/actions.py:111` | **Fixed** |
| BUG20260419-006 | P1 | Correctness | Damage pipeline split across actions.py and resolution.py with inconsistent defense models | `server/combat/actions.py` + `server/combat/resolution.py` | **Fixed** |
| BUG20260419-007 | P1 | Correctness | "defended" status effect never removed at end of turn — permanent +3 armor | `server/combat/resolution.py:29` | **Fixed** |
| BUG20260419-008 | P1 | Correctness | NPC mutation in social engine has no rollback — failed outcomes still permanently reduce trust | `server/npc/social.py:106` | **Fixed** |
| BUG20260419-009 | P1 | Correctness | transfer_character claims atomicity but rollback can silently fail | `server/scene/membership.py:106` | **Fixed** |
| BUG20260419-010 | P1 | Correctness | Running timer with expires_at=None returns "not expired, 0 remaining" instead of error | `server/timer/controller.py:208` | **Fixed** |
| BUG20260419-011 | P1 | Correctness | trigger_early_close bypasses state machine — paused-to-early_closed not in transition table | `server/timer/controller.py:232` | **Fixed** |
| BUG20260419-012 | P1 | Correctness | Idempotency key uses hash() which is randomized per process — breaks across restarts | `server/orchestrator/game_loop.py:493` | **Fixed** |
| BUG20260419-013 | P1 | Correctness | All scenes share one public scope — multi-scene scope separation broken | `server/orchestrator/game_loop.py:638` | **Fixed** |
| BUG20260419-014 | P1 | Correctness | Scene.player_ids not maintained by orchestrator — turn recovery gets zero pending players | `server/reliability/turn_recovery.py:88` | **Fixed** (DB migration: recovery now gets players from CharacterRepo via `get_scene_players()`) |
| BUG20260419-015 | P1 | Correctness | model_recovery returns success=True with empty dict when async fallback silently discarded | `server/reliability/model_recovery.py:117` | **Fixed** |
| BUG20260419-016 | P1 | Correctness | Unguarded update.effective_user None access in all bot command handlers | `bot/commands.py:47` | **Fixed** |
| BUG20260419-017 | P1 | Correctness | Unguarded update.message None access in all bot command handlers | `bot/commands.py:48` | **Fixed** |
| BUG20260419-018 | P1 | Correctness | Fresh empty BotRegistry created on every fallback lookup — players never found | `bot/commands.py:39` | **Fixed** |
| BUG20260419-019 | P1 | Correctness | Unguarded message.from_user None access in handlers.py | `bot/handlers.py:107` | **Fixed** |
| BUG20260419-020 | P1 | Contract Drift | combat_summary contract requires "narration" but schemas.py expects "summary" | `models/contracts/main_contracts.py:196` | **Fixed** |
| BUG20260419-021 | P1 | Contract Drift | ruling_proposal contract fields mismatch schemas.py (reason vs reasoning, etc.) | `models/contracts/main_contracts.py:238` | **Fixed** |
| BUG20260419-022 | P1 | Contract Drift | npc_dialogue contract has internal_thought field that could leak NPC private state | `models/contracts/main_contracts.py:143` | **Fixed** |
| BUG20260419-023 | P1 | Correctness | OpenAI adapter returns success=True on empty choices array | `models/main/adapter.py:157` | **Fixed** |
| BUG20260419-024 | P1 | Correctness | Morale state raw strings — typo silently prevents combat from ending | `server/combat/conditions.py:74` | **Fixed** |
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
| BUG20260419-049 | P2 | Correctness | combat_summary contract fallback has invalid tone "medium" | `models/contracts/main_contracts.py:206` | **Fixed** |
| BUG20260419-050 | P2 | Correctness | is_fast_tier admits unknown tasks — typos route to fast tier silently | `models/fast/router.py:44` | Open |
| BUG20260419-051 | P2 | Correctness | Narration system prompt uses Python single quotes instead of JSON double quotes | `models/main/context.py:144` | Open |
| BUG20260419-052 | P2 | Correctness | ScenarioLoader YAML parse error context lost — user gets generic "Failed" | `scenarios/loader.py:199` | Open |
| BUG20260419-053 | P2 | Correctness | puzzle_patterns.create_puzzle mutates caller's overrides dict via pop() | `scenarios/puzzle_patterns.py:48` | Open |
| BUG20260419-054 | P2 | Correctness | scenarios/archetypes.py unsafe casts from object overrides with type: ignore | `scenarios/archetypes.py:38` | Open |
| BUG20260419-055 | P2 | Security | API endpoints return player data without authentication | `server/api/routes.py:88` | **Fixed** |
| BUG20260419-056 | P2 | Security | Action submission endpoint does not verify authenticated user | `server/api/routes.py:277` | **Fixed** |
| BUG20260419-057 | P2 | Performance | httpx.AsyncClient created per request in both adapters — connection overhead | `models/fast/adapter.py:90` + `models/main/adapter.py:117` | Open |
| BUG20260419-058 | P2 | Performance | Turn number computed by scanning entire turn_log — O(n) on every open_turn | `server/orchestrator/game_loop.py:268` | Open |
| BUG20260419-059 | P2 | Performance | Linear scan of committed_actions by turn_window_id — repeated O(n) | `server/orchestrator/game_loop.py:344` | Open |
| BUG20260419-060 | P2 | Performance | _get_player_character linear scan on every call — O(characters) | `server/orchestrator/game_loop.py:615` | Open |
| BUG20260419-061 | P2 | Performance | Histogram values unbounded list — percentile sort is O(n log n) per query | `server/observability/metrics.py:101` | Open |
| BUG20260419-062 | P2 | Error Handling | SchemaValidationError reason silently discarded in all task functions | `models/main/tasks.py:107` | Open |
| BUG20260419-063 | P2 | Error Handling | Silent template rendering failures in context_assembly — placeholders sent to LLM | `models/contracts/context_assembly.py:269` | Open |
| BUG20260419-064 | P2 | Error Handling | model_recovery broad except Exception catches programming errors as fallback | `server/reliability/model_recovery.py:97` | Open |
| BUG20260419-065 | P2 | Error Handling | Bot leaks internal player UUIDs to Telegram users | `bot/commands.py:124` | **Fixed** |
| BUG20260419-066 | P2 | Error Handling | AI-generated narration sent to Telegram without length check or sanitization | `bot/commands.py:221` | Open |
| BUG20260419-067 | P2 | Design | _now()/_new_id() helpers duplicated identically in 5+ files | Multiple files | Fixed |
| BUG20260419-068 | P2 | Design | Module-level singletons in timer/integration.py block testability | `server/timer/integration.py:36` | Fixed |
| BUG20260419-069 | P2 | Design | API routes access orchestrator private methods directly | `server/api/routes.py:95` | Fixed |
| BUG20260419-070 | P2 | Design | Orchestrator stored in module-level global — prevents DI and testing | `server/api/routes.py:51` | Fixed |
| BUG20260419-071 | P2 | Design | Scope engine fallback creates fake ConversationScope with empty IDs | `server/scope/engine.py:295` | Fixed |
| BUG20260419-072 | P2 | Design | bot/outbound.py accesses BotRegistry private _user_to_player dict | `bot/outbound.py:130` | Fixed |
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

### BUG20260419-025 — Side channel audit fact_id collision

**File:** `server/scope/side_channel_audit.py:56`
**Severity:** P2
**Category:** Correctness
**Description:** `record_message()` generates `fact_id` from only `side_channel_id` and `sender_player_id` (e.g. `f"fact-sc-msg-{channel.side_channel_id}-{sender_player_id}"`). When the same player sends multiple messages in the same channel, every message gets the same `fact_id`, causing a collision. Each message should include a unique component (timestamp, sequence number, or UUID).
**Suggested fix:** Include a UUID or monotonic counter in the `fact_id` construction: `f"fact-sc-msg-{channel.side_channel_id}-{sender_player_id}-{new_id()[:8]}"`.

### BUG20260419-026 — Side channel_id collision on duplicate labels

**File:** `server/scope/side_channel_engine.py:89`
**Severity:** P2
**Category:** Correctness
**Description:** `create_channel()` constructs `side_channel_id` as `f"sc-{campaign_id}-{label}"`. If two side channels with the same label are created in the same campaign, they receive identical IDs. No uniqueness check or UUID component is included.
**Suggested fix:** Append a UUID suffix: `f"sc-{campaign_id}-{label}-{new_id()[:8]}"`, or validate label uniqueness per campaign before creation.

### BUG20260419-027 — Naive datetime stripping

**File:** Multiple files
**Severity:** P2
**Category:** Correctness
**Description:** The pattern `datetime.now(timezone.utc).replace(tzinfo=None)` is used pervasively (now centralised in `server/domain/helpers.py:utc_now()`). It creates a UTC datetime then strips the timezone, losing UTC context. Naive datetimes are ambiguous on deserialisation, and comparisons between naive and aware datetimes raise `TypeError`. Additional instances remain in `server/scope/facts.py:95`, `server/scene/propagation.py:105`, `server/timer/controller.py:128`, and `server/scope/side_channel_audit.py:66`.
**Suggested fix:** Adopt timezone-aware datetimes throughout (`datetime.now(timezone.utc)` without `.replace(tzinfo=None)`), or document that all datetimes are naive-UTC by convention and enforce at storage boundaries.

### BUG20260419-028 — replay_turn() silently drops missing action IDs

**File:** `server/engine/turn_engine.py:480`
**Severity:** P2
**Category:** Correctness
**Description:** `replay_turn()` builds an action map from the provided list, then reconstructs committed actions via `[action_map[aid] for aid in log_entry.action_ids if aid in action_map]`. The `if aid in action_map` filter silently drops any action ID from the log entry that wasn't provided. Incomplete action data or corrupted IDs produce partial replays without warning.
**Suggested fix:** Log a warning or raise when `aid` is missing from `action_map`. At minimum, record which IDs were dropped.

### BUG20260419-029 — search() does not flip item.is_hidden=False

**File:** `server/exploration/actions.py:301`
**Severity:** P2
**Category:** Correctness
**Description:** `search()` finds hidden items in a scene and creates `KnowledgeFact` entries for them, but never sets `item.is_hidden = False` on the discovered items. On a subsequent search of the same scene, the same items are "found" again, producing duplicate facts.
**Suggested fix:** Add `item.is_hidden = False` for each discovered item inside the loop body.

### BUG20260419-030 — Trigger on_enter/on_exit ambiguity

**File:** `server/exploration/triggers.py:231`
**Severity:** P2
**Category:** Correctness
**Description:** Both `on_enter` and `on_exit` trigger kinds check identically that `ctx.action_type == ActionType.move`. The `ExplorationContext` has no `from_scene_id` or `to_scene_id` field, so the trigger engine cannot distinguish whether a move is entering or exiting a scene. Both fire on any move action.
**Suggested fix:** Add `from_scene_id` and `to_scene_id` to `ExplorationContext`, then check `ctx.to_scene_id == trigger.scene_id` for `on_enter` and `ctx.from_scene_id == trigger.scene_id` for `on_exit`.

### BUG20260419-031 — Trigger _apply() always scopes facts privately

**File:** `server/exploration/triggers.py:281`
**Severity:** P2
**Category:** Correctness
**Description:** `_apply()` selects scope via `trigger.private_scope_id if trigger.private_scope_id else trigger.public_scope_id`. Whenever a private scope is set (which is common), all facts go to the private scope regardless of whether the effect should be publicly visible. There is no per-fact visibility mechanism.
**Suggested fix:** Add a `scope_policy` field to `TriggerEffect` fact payloads (similar to `ClueDefinition.scope_policy`) to control per-fact visibility.

### BUG20260419-032 — Clue discover() allows double-discovery

**File:** `server/exploration/clues.py:282`
**Severity:** P2
**Category:** Correctness
**Description:** `discover()` sets `clue.has_been_discovered = True` and creates a new `KnowledgeFact`, but never checks `clue.has_been_discovered` before proceeding. Calling `discover()` twice on the same clue creates two facts with different IDs.
**Suggested fix:** Add an early return: `if clue.has_been_discovered: return ClueDiscovery(discovered=False, rejection_reason="Already discovered")`.

### BUG20260419-033 — Monster damage kills exactly 1 unit regardless of magnitude

**File:** `server/combat/resolution.py:51`
**Severity:** P2
**Category:** Correctness
**Description:** `apply_damage_to_group()` calculates `kills = 1 if damage >= 3 else 0`. A hit dealing 50 damage kills the same number of units as 3 damage. Damage magnitude is ignored.
**Suggested fix:** Scale kills with damage: `kills = damage // hp_per_unit` where `hp_per_unit` is the per-unit HP for the monster group (currently hardcoded as 3).

### BUG20260419-034 — Combat move validates destination but not direction

**File:** `server/combat/actions.py:239`
**Severity:** P2
**Category:** Correctness
**Description:** `resolve_combat_move()` checks that `destination.scene_id` is in `scene.exits.values()` but does not take or validate a direction parameter. A scene with multiple exits to the same destination cannot be disambiguated. The method signature lacks a `direction` argument.
**Suggested fix:** Add a `direction: str` parameter and validate `scene.exits.get(direction) == destination.scene_id`.

### BUG20260419-035 — resolve_use_item heal amount could be string

**File:** `server/combat/actions.py:192`
**Severity:** P2
**Category:** Correctness
**Description:** `amount = item.properties.get("amount", 0)` retrieves the heal amount from a dict that can contain any type. If stored as a string (e.g. `"25"` from JSON), `min(amount, max_hp - hp)` raises `TypeError` comparing string to int.
**Suggested fix:** Cast explicitly: `amount = int(item.properties.get("amount", 0))` with a try/except for malformed data.

### BUG20260419-036 — SocialOutcome is plain class, not Enum

**File:** `server/npc/social.py:60`
**Severity:** P2
**Category:** Correctness
**Description:** `SocialOutcome` is a plain class with string constants (`SUCCESS = "success"`, etc.) rather than a `str, Enum`. Typos in outcome comparisons pass silently, type checkers cannot validate usage, and serialisation is ambiguous.
**Suggested fix:** Redefine as `class SocialOutcome(str, Enum):` with the same members.

### BUG20260419-037 — apply_action_delta returns 0 for unknown action_key

**File:** `server/npc/trust.py:160`
**Severity:** P2
**Category:** Correctness
**Description:** `base = _BASE_DELTAS.get(action_key, 0)` silently returns 0 for unknown keys. A typo in `action_key` (e.g. `"persuad"` instead of `"persuade"`) results in zero trust change with no error or warning.
**Suggested fix:** Raise `KeyError` on unknown keys, or log a warning. The docstring already states `action_key` must be a key in `_BASE_DELTAS`.

### BUG20260419-038 — Trust _derive_stance missing "suspicious" zone

**File:** `server/npc/trust.py:189`
**Severity:** P2
**Category:** Correctness
**Description:** `_derive_stance()` maps mean trust to "hostile", "neutral", or "friendly" but has no "suspicious" or "wary" zone despite the docstring implying one. Trust values between `_HOSTILE_THRESHOLD` and 20 fall through to "neutral" or the default "hostile" with no intermediate stance. The condition logic also has a gap where both `mean_trust >= 20` and `mean_trust >= _HOSTILE_THRESHOLD` map to "neutral".
**Suggested fix:** Add a "suspicious" stance for the range between hostile and neutral thresholds, and verify condition ordering prevents dead branches.

### BUG20260419-039 — remove_character unconditionally removes player_id

**File:** `server/scene/membership.py:65`
**Severity:** P2
**Category:** Correctness
**Description:** `remove_character()` removes `character.player_id` from `scene.player_ids` without checking whether another character from the same player remains in the scene. If a player has multiple characters, removing one character incorrectly removes the player from the scene roster.
**Suggested fix:** Before removing `player_id`, check: `if not any(c.player_id == character.player_id for c in remaining_characters): scene.player_ids.remove(...)`.

### BUG20260419-040 — Timer pause truncation drift

**File:** `server/timer/controller.py:256`
**Severity:** P2
**Category:** Correctness
**Description:** `timer.elapsed_before_pause = timer.duration_seconds - int(remaining)` uses `int()` which truncates (floors) the fractional seconds. Each pause/resume cycle loses up to 1 second of precision, accumulating drift over multiple cycles.
**Suggested fix:** Use `round(remaining)` instead of `int(remaining)`.

### BUG20260419-041 — Timer resume with 0 remaining gets free extra second

**File:** `server/timer/controller.py:275`
**Severity:** P2
**Category:** Correctness
**Description:** `timer.expires_at = t + timedelta(seconds=max(1, remaining))` forces a minimum of 1 second on resume. A timer paused with 0.5 seconds remaining gets expanded to 1 full second, granting unintended extra time.
**Suggested fix:** Use `max(0, remaining)` or allow timers with 0 remaining to expire immediately on resume.

### BUG20260419-042 — Timer integration uses raw strings for ActionState

**File:** `server/timer/integration.py:77`
**Severity:** P2
**Category:** Correctness
**Description:** `a.state.value in {"submitted", "validated"}` compares enum `.value` strings against raw string literals. If `ActionState` enum values change, this comparison silently breaks.
**Suggested fix:** Use enum comparisons: `a.state in {ActionState.submitted, ActionState.validated}`.

### BUG20260419-043 — timeout_players empty list coerced to None

**File:** `server/orchestrator/game_loop.py:432`
**Severity:** P2
**Category:** Correctness
**Description:** `resolve_window(tw, actions, chars_by_player, timeout_players or None)` converts an empty list `[]` to `None` via the `or` operator. If `resolve_window` treats `None` differently from `[]`, this changes semantics silently.
**Suggested fix:** Pass `timeout_players` directly without `or None`. If the callee needs to distinguish "no timeouts" from "not specified", use a sentinel.

### BUG20260419-044 — Diagnostics always reports ALL players as pending

**File:** `server/observability/diagnostics.py:153`
**Severity:** P2
**Category:** Correctness
**Description:** Stuck-turn diagnostics sets `pending = list(scene_players)` without filtering out players who have already submitted actions. The comment acknowledges "we don't have actions here" but the method signature could accept action data. All players are reported as pending even when only a subset is actually blocking.
**Suggested fix:** Accept committed actions as a parameter and filter: `pending = [pid for pid in scene_players if pid not in submitted_ids]`.

### BUG20260419-045 — fast_model_responsive threshold too permissive

**File:** `server/observability/diagnostics.py:221`
**Severity:** P2
**Category:** Correctness
**Description:** `fast_model_responsive = bool(fast_latencies) and failures < len(model_call_log)` marks the model as responsive if there is at least one successful call and failures are less than total calls. One success out of 10 attempts (90% failure rate) still reports responsive. No latency threshold is checked.
**Suggested fix:** Use a minimum success rate (e.g. `failures / len(model_call_log) < 0.5`) and check latency against a threshold.

### BUG20260419-046 — leave_channel mutates entity directly

**File:** `server/api/routes.py:588`
**Severity:** P2
**Category:** Correctness
**Description:** The `/api/channel/{channel_id}/leave` endpoint directly mutates `ch.member_player_ids.remove(req.player_id)` and `ch.is_open = False` on the domain entity without going through the `SideChannelEngine`. This bypasses any validation, auditing, or side-effect logic that the engine provides.
**Suggested fix:** Route through `SideChannelEngine` with a `leave_channel()` or `remove_member()` method that handles validation and audit fact creation.

### BUG20260419-047 — Map discovered logic wrong

**File:** `server/api/routes.py:686`
**Severity:** P2
**Category:** Correctness
**Description:** The map endpoint marks the current scene plus all scenes directly connected via exits as "discovered". However, adjacent scenes the player has never visited are marked as discovered rather than as "visible but undiscovered". Without persistent visit records, the logic conflates "reachable" with "visited".
**Suggested fix:** Only mark the current scene as discovered. Mark adjacent scenes as "visible" with a separate flag. Or integrate with `MemoryEngine` visit records if available.

### BUG20260419-048 — output_repair bool/int type confusion

**File:** `models/contracts/output_repair.py:75`
**Severity:** P2
**Category:** Correctness
**Description:** The integer type check `isinstance(value, int)` passes for `bool` values because `bool` is a subclass of `int` in Python. A field marked as "integer" will accept `True`/`False`, and a field marked as "boolean" that passes the boolean check first may still pass the integer check in other code paths.
**Suggested fix:** Add `and not isinstance(value, bool)` to the integer type check: `isinstance(value, int) and not isinstance(value, bool)`.

### BUG20260419-049 — combat_summary contract fallback has invalid tone

**File:** `models/contracts/main_contracts.py:206`
**Severity:** P2
**Category:** Correctness
**Description:** The `fallback_output` dict specifies `"tone": "medium"`, but the contract schema's tone enum only allows `["neutral", "tense", "triumphant", "ominous", "comic"]`. The fallback output fails its own schema validation.
**Suggested fix:** Change `"medium"` to `"neutral"` in the fallback output.

### BUG20260419-050 — is_fast_tier admits unknown tasks

**File:** `models/fast/router.py:44`
**Severity:** P2
**Category:** Correctness
**Description:** `is_fast_tier()` returns `True` for any `task_type` not in `_MAIN_TIER_ONLY`. Unknown task types (typos, new unregistered types) silently route to the fast tier instead of raising an error. The `_FAST_TIER_TASKS` frozenset is defined but never checked.
**Suggested fix:** Validate membership first: `return task_type in _FAST_TIER_TASKS and task_type not in _MAIN_TIER_ONLY`.

### BUG20260419-051 — Narration system prompt uses Python single quotes

**File:** `models/main/context.py:144`
**Severity:** P2
**Category:** Correctness
**Description:** The system prompt embeds a JSON schema using Python single quotes: `"Schema: {'narration': 'string', ...}"`. JSON requires double quotes. The LLM receives an invalid JSON schema specification, which may cause it to produce malformed output.
**Suggested fix:** Use escaped double quotes or a `json.dumps()` call to produce valid JSON in the prompt.

### BUG20260419-052 — ScenarioLoader YAML parse error context lost

**File:** `scenarios/loader.py:199`
**Severity:** P2
**Category:** Correctness
**Description:** `_parse_yaml()` catches `OSError` and `yaml.YAMLError` and returns `None`, discarding all error context. The caller receives a generic "Failed to load scenario" with no indication of whether the file is missing, unreadable, or has invalid YAML syntax.
**Suggested fix:** Re-raise as a custom `ScenarioLoadError` with the original exception chained, or log the exception details before returning None.

### BUG20260419-053 — create_puzzle mutates caller's overrides dict

**File:** `scenarios/puzzle_patterns.py:48`
**Severity:** P2
**Category:** Correctness
**Description:** `create_puzzle()` calls `.pop()` on the caller's `overrides` dict multiple times to extract `puzzle_id`, `description`, `success_text`, and `failure_text`. This mutates the caller's dict, causing side effects if the dict is reused.
**Suggested fix:** Use `.get()` instead of `.pop()`, or copy the dict at entry: `overrides = dict(overrides)`.

### BUG20260419-054 — Archetypes unsafe casts with type: ignore

**File:** `scenarios/archetypes.py:38`
**Severity:** P2
**Category:** Correctness
**Description:** `instantiate()` retrieves values from `**overrides: object` without validation and passes them to `list()` with four `# type: ignore[arg-type]` annotations. If an override provides a non-iterable (string, int, dict), the code fails at runtime. The type suppressions hide the unsafe casting.
**Suggested fix:** Validate that override values are sequences before casting, or type `overrides` more precisely.

### BUG20260419-055 — API endpoints return player data without authentication

**File:** `server/api/routes.py:88`
**Severity:** P2
**Category:** Security
**Description:** The `GET /api/player/{player_id}` endpoint returns full player data (character, scene, stats) without verifying that the requesting client is authenticated or authorised to view that player's data. Any caller with a valid player_id can retrieve complete player information.
**Suggested fix:** Add authentication middleware and verify the authenticated user matches the requested player_id, or restrict the endpoint to admin access.

### BUG20260419-056 — Action submission lacks user verification

**File:** `server/api/routes.py:277`
**Severity:** P2
**Category:** Security
**Description:** `POST /api/action/submit` accepts a `player_id` in the request body but does not verify that the authenticated user matches that player_id. Any authenticated user could submit actions on behalf of any other player.
**Suggested fix:** Extract the authenticated user's player_id from the session/token and reject requests where `req.player_id != authenticated_player_id`.

### BUG20260419-057 — httpx.AsyncClient created per request

**File:** `models/fast/adapter.py:90` + `models/main/adapter.py:117`
**Severity:** P2
**Category:** Performance
**Description:** Both the fast and main model adapters create a new `httpx.AsyncClient` inside an `async with` block for every single inference request. This incurs connection setup overhead, TLS handshake, and connection pool initialisation on every call. For high-throughput scenarios, this is a significant bottleneck.
**Suggested fix:** Create the `AsyncClient` once at adapter initialisation (in `__init__`) and reuse it across requests. Provide an `async close()` method for cleanup.

### BUG20260419-058 — Turn number computed by scanning entire turn_log

**File:** `server/orchestrator/game_loop.py:268`
**Severity:** P2
**Category:** Performance
**Description:** Turn number is computed as `len([e for e in self.turn_log if e.scene_id == scene_id]) + 1`, scanning the entire turn log on every `open_turn()` call. As `turn_log` grows over a session, this O(n) scan becomes increasingly expensive.
**Suggested fix:** Maintain a per-scene turn counter (`dict[str, int]`) that increments atomically on each `open_turn()`.

### BUG20260419-059 — Linear scan of committed_actions by turn_window_id

**File:** `server/orchestrator/game_loop.py:344`
**Severity:** P2
**Category:** Performance
**Description:** Actions for a turn window are found by scanning all `committed_actions.values()` and filtering by `turn_window_id`. This O(n) scan is performed twice in the same function. As committed actions accumulate, this becomes increasingly expensive.
**Suggested fix:** Maintain a secondary index: `dict[str, list[str]]` mapping `turn_window_id` → action IDs.

### BUG20260419-060 — get_player_character linear scan

**File:** `server/orchestrator/game_loop.py:615`
**Severity:** P2
**Category:** Performance
**Description:** `get_player_character()` scans all `characters.values()` to find a character by `player_id`. This is O(n) per call and is invoked from API endpoints on every request.
**Suggested fix:** Maintain a reverse index: `dict[str, str]` mapping `player_id` → `character_id`.

### BUG20260419-061 — Histogram values unbounded list

**File:** `server/observability/metrics.py:101`
**Severity:** P2
**Category:** Performance
**Description:** `MetricsCollector.record()` appends every histogram value to an unbounded Python list. Over time, histogram storage grows without limit, consuming unbounded memory. Percentile queries on large lists require O(n log n) sorting.
**Suggested fix:** Use a bounded data structure (fixed-size ring buffer, reservoir sampling, or histogram buckets) and periodically flush/reset.

### BUG20260419-062 — SchemaValidationError reason silently discarded

**File:** `models/main/tasks.py:107`
**Severity:** P2
**Category:** Error Handling
**Description:** When `validate_narration()` raises `SchemaValidationError`, the exception is caught with a bare `except SchemaValidationError: pass`, discarding the error reason entirely. The code falls through to the fallback path with no log or diagnostic.
**Suggested fix:** Log the exception: `except SchemaValidationError as exc: logger.warning("Narration validation failed: %s", exc)`.

### BUG20260419-063 — Silent template rendering failures

**File:** `models/contracts/context_assembly.py:269`
**Severity:** P2
**Category:** Error Handling
**Description:** When `format_map()` fails on system or user prompt templates, the code catches `KeyError`/`ValueError` and falls back to the raw unrendered template string. The LLM receives unexpanded `{placeholder}` tags instead of actual data, producing nonsensical output. No warning is logged.
**Suggested fix:** Log which fields were missing and which template failed. Consider raising if critical fields are absent.

### BUG20260419-064 — model_recovery broad except Exception

**File:** `server/reliability/model_recovery.py:97`
**Severity:** P2
**Category:** Error Handling
**Description:** `except Exception as exc` catches all exceptions — including programming errors like `AttributeError`, `TypeError`, `KeyError` — and treats them as graceful fallbacks with `success=True`. Real bugs are silently swallowed and masked by fallback data.
**Suggested fix:** Catch specific expected exceptions (e.g. `httpx.HTTPError`, `TimeoutError`). Let programming errors propagate.

### BUG20260419-065 — Bot leaks internal player UUIDs

**File:** `bot/commands.py:124`
**Severity:** P2
**Category:** Error Handling
**Description:** The `/status` command handler sends `f"Player ID: {player_id}"` directly to the Telegram user in three places. The `player_id` is an internal UUID that should not be exposed to end users.
**Suggested fix:** Display human-readable identifiers (character name, Telegram username) instead of internal UUIDs.

### BUG20260419-066 — AI narration sent without length check or sanitization

**File:** `bot/commands.py:221`
**Severity:** P2
**Category:** Error Handling
**Description:** `log_entry.narration` (AI-generated text) is sent directly to Telegram without length checking or sanitisation. Telegram messages have a 4096-character limit; oversized messages will fail. The narration could also contain formatting attacks or control characters.
**Suggested fix:** Truncate to 4000 characters with an ellipsis, and sanitise HTML/Markdown entities before sending.

### BUG20260419-067 — _now()/_new_id() helpers duplicated (FIXED)

**Status:** Fixed in Phase 22. Centralised in `server/domain/helpers.py`.

### BUG20260419-068 — Timer integration module-level singletons (FIXED)

**Status:** Fixed in Phase 23. Made injectable via function parameters.

### BUG20260419-069 — API routes access orchestrator private methods (FIXED)

**Status:** Fixed in Phase 21. Renamed `_get_player_character` → `get_player_character`.

### BUG20260419-070 — Orchestrator module-level global (FIXED)

**Status:** Fixed in Phase 24. Documented startup-injection pattern.

### BUG20260419-071 — Scope engine fake ConversationScope fallback (FIXED)

**Status:** Fixed in Phase 24. Replaced with explicit missing-scope warning.

### BUG20260419-072 — bot/outbound.py private dict access (FIXED)

**Status:** Fixed in Phase 24. Added `get_user_id_for_player()` to BotRegistry.

### BUG20260419-073 — NPC/MonsterGroup raw string state fields

**File:** `server/domain/entities.py:271`
**Severity:** P3
**Category:** Data Model
**Description:** `NPC.health_state` (line 271: `"healthy"`, `"injured"`, `"incapacitated"`, `"dead"`), `NPC.stance_to_party` (line 277: `"friendly"`, `"neutral"`, `"hostile"`, `"fearful"`), and `MonsterGroup.morale_state` are all plain `str` fields with valid values documented only in comments. Typos pass silently, type checkers cannot validate usage, and there is no discoverability.
**Suggested fix:** Define `HealthState`, `StanceToParty`, and `MoraleState` enums in `server/domain/enums.py` and use throughout.

### BUG20260419-074 — InventoryItem dual-owner invariant not enforced

**File:** `server/domain/entities.py:335`
**Severity:** P3
**Category:** Data Model
**Description:** `InventoryItem` has `owner_character_id` and `owner_scene_id` with a comment stating "exactly one should be set", but no `__post_init__` enforces the XOR constraint. Items can have both owners (data corruption) or no owner.
**Suggested fix:** Add `__post_init__` validating `(owner_character_id is None) != (owner_scene_id is None)`.

### BUG20260419-075 — create_channel created_at typed as object

**File:** `server/scope/side_channel_engine.py:60`
**Severity:** P3
**Category:** Data Model
**Description:** `created_at: object = None` should be `created_at: datetime | None = None`. The `object` type accepts anything, provides no type-checker guidance, and makes the API contract unclear.
**Suggested fix:** Change to `created_at: datetime | None = None` and add `from datetime import datetime` (already imported).

### BUG20260419-076 — validate_fact_creation None check on non-Optional

**File:** `server/scope/facts.py:70`
**Severity:** P3
**Category:** Data Model
**Description:** `scope: ConversationScope` is typed as non-Optional but line 70 checks `if scope is None: raise ...`. Type checkers won't warn callers about None, creating a false sense of safety.
**Suggested fix:** Either change to `scope: ConversationScope | None` and let callers handle None, or remove the None check and trust the type annotation.

### BUG20260419-077 — SocialActionInput.extra dead field

**File:** `server/npc/social.py:91`
**Severity:** P3
**Category:** Data Model
**Description:** `SocialActionInput.extra: dict` (line 77) is defined with `field(default_factory=dict)` but no code in the codebase reads it. It accumulates unused data and creates confusion about feature completeness.
**Suggested fix:** Remove the field, or implement reading it in the relevant social action handlers.

### BUG20260419-078 — Memory recall_description off-by-one

**File:** `server/exploration/memory.py:209`
**Severity:** P3
**Category:** Correctness
**Description:** When `visit_count == 1`, `recall_description()` returns "You have been here once before." But `visit_count` includes the current visit, so `1` means this is the first visit — not that the player has been here "once before". The message should say "first time" for count 1 and "once before" for count 2.
**Suggested fix:** Adjust: `if count <= 1: return "first visit" text; elif count == 2: "once before"; else: f"{count - 1} times before"`.

### BUG20260419-079 — Monster ambush flag is dead code

**File:** `server/combat/monsters.py:109`
**Severity:** P3
**Category:** Correctness
**Description:** Lines 109–111 check `group.behavior_mode == BehaviorMode.ambush` and append `"ambush_used"` to `group.special_rules`, but this flag is never read anywhere. No bonus (damage, initiative, etc.) is applied for ambush. The code sets a flag with no consumer.
**Suggested fix:** Either implement the ambush bonus logic, or remove the dead code.

### BUG20260419-080 — /api/player/{id}/inbox `since` parameter ignored

**File:** `server/api/routes.py:397`
**Severity:** P3
**Category:** Correctness
**Description:** The inbox endpoint declares `since: str = ""` as a query parameter but never uses it in the function body. The API contract promises time-based filtering that isn't implemented.
**Suggested fix:** Implement filtering (parse `since` as a datetime, filter facts by `revealed_at >= since`), or remove the parameter.

### BUG20260419-081 — Quest title displays quest_id (UUID)

**File:** `server/api/routes.py:613`
**Severity:** P3
**Category:** Correctness
**Description:** `QuestInfo(title=quest.quest_id, ...)` uses the internal UUID as the quest title shown to players. The inline comment confirms this: `"quest_id is used as title"`. Should use `quest.name` or `quest.title`.
**Suggested fix:** Change to `title=quest.name` (or whichever field holds the human-readable quest name).

### BUG20260419-082 — Scene scoped_prompts O(n*m) membership checks

**File:** `server/scene/scoped_prompts.py:57`
**Severity:** P3
**Category:** Performance
**Description:** List comprehensions use `in` membership checks against `scene.character_ids`, `scene.npc_ids`, and `scene.monster_group_ids`. If these are lists, each `in` check is O(m), making overall complexity O(n*m).
**Suggested fix:** Convert scene membership lists to sets at the start of the method: `char_ids = set(scene.character_ids)`.

### BUG20260419-083 — BFS uses list.pop(0) — O(n^2)

**File:** `scenarios/validator.py:376`
**Severity:** P3
**Category:** Performance
**Description:** The reachability BFS uses `queue.pop(0)` which is O(n) per call on a Python list (shifts all elements). For a BFS with m nodes, total time is O(m^2).
**Suggested fix:** Use `collections.deque` with `popleft()` for O(1) dequeue.

### BUG20260419-084 — Scope violation detection O(n*m) substring search

**File:** `models/contracts/context_assembly.py:219`
**Severity:** P3
**Category:** Performance
**Description:** `excluded_facts` is built with `[f for f in all_available if f not in permitted_facts]` where `permitted_facts` is a list. The `not in` check on a list is O(m), making the total O(n*m).
**Suggested fix:** Convert to set: `permitted_set = set(permitted_facts); excluded = [f for f in all_available if f not in permitted_set]`.

### BUG20260419-085 — Leakage guard module-level singletons (FIXED)

**Status:** Fixed in Phase 23. Made injectable via constructor parameters.

### BUG20260419-086 — Deferred stdlib imports (FIXED)

**Status:** Fixed in Phase 21. Moved to module top level.

---

## Review Summary — 20260419

- **Files reviewed:** ~65 Python files across 17 directories
- **Findings:** 86 total — 3 P0, 21 P1, 48 P2, 14 P3
- **Top concerns:**
  1. **Security (P0):** Bot token from client defeats auth; path traversal in /newgame; scope grant leakage exposes private facts to all players.
  2. **Combat system (P1):** Damage pipeline split across two modules with inconsistent models; HP not clamped; permanent defense buff; attack results not applied to targets.
  3. **Bot handlers (P1):** Every command handler lacks None guards for effective_user, message, and from_user — any non-standard Telegram update causes crashes.
  4. **Contract drift (P1):** Three of six main-tier prompt contracts have field names that don't match the schema validation code.
