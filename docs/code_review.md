# Code Review Instructions

## Purpose

Systematic review of the RPG codebase to surface bugs, inferior design patterns, poor coding practices, inefficiencies, and better implementation choices. The output is a list of findings written to `docs/bugs.md`.

## Bug ID Format

Each finding gets an ID: **`BUG[YYYYMMDD]-[NNN]`**

- `YYYYMMDD` is today's date in **PST** (Pacific Standard Time).
- `NNN` is a zero-padded three-digit sequence starting at `001`.
- Example: `BUG20260419-001`, `BUG20260419-002`, etc.
- IDs are assigned in discovery order. Do not reuse or skip numbers within a session.

## Severity Levels

| Level | Meaning | Action |
|---|---|---|
| P0 | Data loss, scope leakage, security vulnerability | Must fix before release |
| P1 | Gameplay-breaking bug, crash, data corruption | Must fix before release |
| P2 | Quality/polish issue, design smell, inefficiency | Fix if time permits |
| P3 | Enhancement, minor style issue, nice-to-have | Defer to post-release |

## Output Format

Append each finding to the **Open Bugs** table in `docs/bugs.md`:

```markdown
| BUG20260419-001 | P2 | Category | One-line description | File path:line | Open |
```

After the table, add a **Details** section for each finding:

```markdown
### BUG20260419-001 — Short Title

**File:** `path/to/file.py:42`
**Severity:** P2
**Category:** [from checklist below]
**Description:** What is wrong and why it matters.
**Suggested fix:** Concrete recommendation (code sketch if helpful).
```

---

## Review Scope

Review every `.py` file under these directories, in this order:

1. `server/domain/` — entities, enums (pure data layer)
2. `server/scope/` — scope engine, leakage guard, side channels
3. `server/engine/` — turn engine
4. `server/combat/` — combat loop, conditions, dice
5. `server/exploration/` — movement, triggers, actions, clues, objects
6. `server/npc/` — NPC social engine, trust, memory
7. `server/scene/` — scene membership
8. `server/timer/` — timer controller
9. `server/orchestrator/` — game loop
10. `server/reliability/` — idempotency, retry, recovery
11. `server/observability/` — diagnostics, metrics
12. `server/api/` — FastAPI REST endpoints
13. `models/fast/` — fast model adapter, router, tasks
14. `models/main/` — main model adapter, router, tasks, context, fallback
15. `models/contracts/` — prompt contracts
16. `bot/` — Telegram bot gateway, commands, parsers, onboarding, outbound
17. `scenarios/` — scenario loader, validator, YAML files

Skip `__pycache__/`, `tests/`, `webapp/`, and `docs/`.

---

## Checklist

Work through each category below for every file in scope. Not every category applies to every file — skip categories that are irrelevant to the file under review.

### 1. Correctness Bugs

- **Off-by-one errors** in loops, slicing, range bounds, indexing.
- **Wrong comparison operators**: `is` vs `==` for value comparison; `is None` is correct, `is True/False` usually is not.
- **Mutable default arguments**: function signatures with `def f(x=[])` or `def f(x={})` instead of `None` + factory. Dataclass fields using `field(default_factory=...)` are correct — flag any that don't.
- **Missing `await`** on async calls. Look for coroutine objects being silently discarded.
- **Unchecked `.get()` or `[]` access** on dicts that may lack the key.
- **Silent swallowing of exceptions**: bare `except:` or `except Exception: pass` that hide real errors.
- **Integer vs float division** where the wrong one is used (`/` vs `//`).
- **String formatting bugs**: f-strings referencing undefined names, `.format()` with wrong arg count.

### 2. Scope and Visibility Invariants

This project's core safety property is that private information never leaks to unauthorized players.

- **Scope field assignment**: every piece of game content must have an explicit `ScopeType`. Flag any content creation that omits scope or defaults to `public` without justification.
- **Context assembly leakage**: when building LLM prompt context, verify that `referee_only` and `private_referee` facts are excluded from player-visible prompts. Check that the leakage guard is invoked before any prompt is sent.
- **Delivery target filtering**: outbound messages must filter recipients by scope. Flag any `send_message` path that skips the scope engine.
- **Side channel isolation**: DM content for player A must never appear in player B's context. Trace data flow from side channel creation to delivery.
- **Logging of private data**: check that log statements (especially at DEBUG/INFO level) don't dump private facts, hidden rolls, or referee-only content to a shared log sink.

### 3. Async and Concurrency

- **Blocking calls in async context**: `time.sleep()`, synchronous file I/O, synchronous HTTP requests inside `async def` functions. These block the event loop.
- **Missing error handling on `await`**: async calls to external services (Ollama, Telegram API) should handle `TimeoutError`, `ConnectionError`, `httpx.HTTPStatusError`.
- **Race conditions**: shared mutable state accessed from multiple async tasks without synchronization. In-memory game state is single-writer by design — flag any code path that violates this.
- **Unclosed async resources**: `httpx.AsyncClient` or similar opened without `async with` or explicit `.aclose()`.
- **Fire-and-forget coroutines**: `asyncio.create_task()` without storing the reference (exceptions are silently dropped).

### 4. Data Model and Type Safety

- **Dataclass mutability where immutability is expected**: entities that should be value objects but allow mutation after creation.
- **Enum misuse**: raw strings where an enum value should be used; comparisons like `scope == "public"` instead of `scope == ScopeType.PUBLIC`.
- **Optional fields accessed without None checks**: `player.character.name` when `character` could be `None`.
- **Type narrowing gaps**: after an `isinstance` or `is not None` check, code outside the narrowed branch using the variable unsafely.
- **UUID/ID type confusion**: comparing IDs of different entity types (player ID vs character ID) that happen to both be strings.

### 5. Error Handling

- **Overly broad exception handlers**: `except Exception` where a specific exception type is known.
- **Lost error context**: `raise NewError("msg")` without `from original` when wrapping exceptions.
- **Missing rollback on partial failure**: multi-step operations (commit action → update state → send message) where a failure midway leaves state inconsistent.
- **Retry without idempotency**: operations retried on failure that aren't safe to repeat (double-applying damage, double-sending messages).
- **Error messages that leak internals**: exceptions or error responses that expose file paths, stack traces, or internal IDs to players.

### 6. Design Patterns and Architecture

- **God objects**: classes with too many responsibilities (>5 public methods that span different concerns).
- **Inappropriate coupling**: modules importing from layers they shouldn't (e.g., `domain/` importing from `bot/`, `models/` importing from `server/`).
- **Circular dependencies**: A imports B, B imports A (even if Python allows it at module level, it's a design smell).
- **Violation of the "server is referee authority" rule**: any code path where the LLM's output is applied to game state without server-side validation.
- **Contract drift**: prompt contracts in `models/contracts/` that don't match the actual expected output schema used by the calling code.
- **Duplicated logic**: the same validation, transformation, or decision appearing in multiple places instead of being factored to one location.
- **Feature envy**: a function that mostly accesses data from another object rather than the object it lives on.

### 7. Performance and Efficiency

- **Repeated expensive computation**: recalculating the same value in a loop when it could be computed once.
- **O(n²) patterns**: nested loops over collections that could use sets, dicts, or indexes.
- **Unnecessary copies**: `list(some_list)` or dict unpacking where a view or iterator suffices.
- **Excessive string concatenation** in loops (use `"".join()` or f-strings).
- **Unused imports and dead code**: imports that are never referenced; functions that are never called.
- **Large prompt assembly**: context assembly that includes more text than the model's context window can use, wasting tokens.
- **Redundant validation**: the same input validated multiple times along a single call path.

### 8. API and Interface Quality

- **FastAPI endpoint issues**: missing response models, missing status codes, missing validation on path/query params, synchronous handlers where async is needed.
- **Telegram bot handler issues**: missing error handlers, commands that don't reply on failure, handlers that assume message structure without checking.
- **Missing input validation at system boundaries**: player input, scenario YAML, API request bodies accepted without validation.
- **Inconsistent return types**: functions that return `None` on error in some paths and raise in others.

### 9. Testing Gaps (Informational Only)

Flag as P3 — these are not code bugs but coverage risks:

- **Untested branches**: complex `if/elif/else` chains where only the happy path is tested.
- **Missing edge-case tests**: empty collections, None inputs, boundary values, concurrent access.
- **Mock-heavy tests that don't test real behavior**: tests that mock so aggressively they only test the mock wiring.

---

## Procedure

1. **Set up**: note today's PST date for the bug ID prefix. Start the sequence at `001`.
2. **For each directory** in the Review Scope list (in order):
   a. Read every `.py` file in the directory.
   b. Work through each applicable checklist category.
   c. For each finding, assign the next bug ID, determine severity, and record it.
3. **Write output**: append all findings to `docs/bugs.md` in the format described above.
4. **Summary**: after completing all directories, add a summary section at the bottom of `docs/bugs.md`:

```markdown
## Review Summary — [YYYYMMDD]

- **Files reviewed:** [count]
- **Findings:** [count by severity: P0/P1/P2/P3]
- **Top concerns:** [1-3 sentences on the most important findings]
```

## Notes

- Be specific. Every finding must include an exact file path and line number.
- Prefer actionable findings over style nitpicks. "This could crash" beats "this could be prettier."
- Do not flag patterns that are intentional project conventions (e.g., `GenerateResult.success` flag instead of exceptions for model failures — that is by design).
- Do not flag the disabled Gemma adapter (BUG-001) or in-memory storage (BUG-003) — these are known and tracked.
- When uncertain whether something is a bug or an intentional choice, still record it as P3 with a note asking for clarification.
