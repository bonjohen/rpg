# Test Code Evaluation Criteria

**Purpose:** A rubric for evaluating the quality, completeness, and maintainability of test code. Use this to audit existing tests or review new test additions.

---

## 1. Naming and Organization

| Criterion | What to look for | Red flag |
|---|---|---|
| **Descriptive test names** | Name says what behavior is being verified: `test_entry_with_engaged_group`, `test_no_entry_without_engaged` | Generic names: `test_1`, `test_it_works`, `test_basic` |
| **One assertion concept per test** | Each test verifies one logical behavior. Multiple asserts are fine if they verify facets of the same behavior | A single test that verifies creation, update, deletion, and error handling |
| **Logical grouping** | Related tests grouped in classes or sections with clear headers | Flat file with 50 unrelated functions in random order |
| **Module-per-concern** | Test file maps to a specific module, feature, or behavior area | One mega-file testing everything; or test files that import from 10+ unrelated modules |
| **Docstrings on test modules** | Module-level docstring states what area is covered and what plan/spec it traces to | No context for why tests exist or what they validate |

## 2. Arrangement: Setup and Fixtures

| Criterion | What to look for | Red flag |
|---|---|---|
| **Builder functions** | Reusable `make_*()` or `build_*()` helpers that construct test entities with sensible defaults | Raw constructors with 15 positional args copy-pasted across tests |
| **Fixture isolation** | Each test starts from a clean state; no shared mutable state between tests | Class-level state that bleeds across test methods; tests that fail when run in isolation but pass in suite order |
| **Minimal setup** | Test only constructs what it needs; doesn't build an entire world when testing one function | Every test loads a full scenario + 5 players + 3 NPCs to test a single scope check |
| **Centralized fixture modules** | Common builders in `tests/fixtures/`; not duplicated per test file | Same 20-line setup function copy-pasted in 8 files |
| **Clear test-specific overrides** | When a test needs non-default state, the deviation is visible in the test body, not buried in a fixture | Test asserts on a value that was set 200 lines away in a base class `setUp` |

## 3. Assertions and Verification

| Criterion | What to look for | Red flag |
|---|---|---|
| **Specific assertions** | `assert result.state == TurnWindowState.open`, not `assert result is not None` | Tests that only check truthiness or existence, never the actual value |
| **Negative assertions** | Tests for what should NOT happen: rejected access, prevented leakage, blocked invalid input | Only happy-path tests; no verification of invariants or constraints |
| **Error path coverage** | Tests for expected exceptions, fallback behaviors, and graceful degradation | No tests for what happens when the model times out, the DB is down, or input is malformed |
| **Assertion messages** | When a bare `assert` could be cryptic on failure, a message or more specific assertion is used | `assert x` that produces `AssertionError` with no context |
| **No logic in assertions** | Assertions compare against known expected values, not re-derived values | `assert compute(x) == compute(x)` — tautological; `assert len(results) == len(input_list)` when the relationship isn't obvious |

## 4. Mocking and Test Doubles

| Criterion | What to look for | Red flag |
|---|---|---|
| **Mock at boundaries** | Mocks replace external systems (Telegram API, model inference, network I/O), not internal logic | Mocking internal methods of the class under test; mocking 6 layers deep to avoid building real state |
| **Narrow mock scope** | `patch` applied to the smallest scope needed (function or `with` block), not module-wide | `@patch` on every method of a class, making the test verify mock wiring rather than behavior |
| **Fake over mock when stateful** | For subsystems with state (DB, in-memory stores), use real in-memory implementations rather than `MagicMock` | `MagicMock` for a repository where the test needs to verify that writes persist across calls |
| **Verify mock interactions sparingly** | Mock call assertions only when the interaction IS the behavior (e.g., "message was sent to Telegram") | Every test ending with 10 `assert_called_with` lines that mirror the implementation |
| **Canned responses are realistic** | Mock return values match real API shapes; not empty dicts or bare strings | `MagicMock()` returned where the code expects a dataclass with 5 fields |

## 5. Coverage and Completeness

| Criterion | What to look for | Red flag |
|---|---|---|
| **Boundary conditions** | Tests for empty collections, zero counts, max values, first/last elements | Only tests with 2-3 items in a list; no edge cases |
| **State transitions** | Each valid transition tested; invalid transitions rejected | State machine with 6 states but only 2 transitions tested |
| **Concurrency / race conditions** | Tests for re-entrant calls, duplicate submissions, cross-turn collisions | System has dedup/idempotency logic but no test exercises the duplicate path |
| **Failure and recovery paths** | Tests for timeout, retry, crash-recovery, partial failure | Only sunny-day tests; the `except` branches have zero coverage |
| **Security-sensitive paths** | Scope enforcement, auth checks, input validation, path traversal prevention tested explicitly | Security logic exists but is only exercised incidentally by other tests |
| **Regression tests for bugs** | Each fixed bug has a targeted test that would catch a re-introduction | Bugs fixed without corresponding tests; fix could silently regress |

## 6. Test Independence and Determinism

| Criterion | What to look for | Red flag |
|---|---|---|
| **No test ordering dependency** | Tests pass when run in any order; `pytest --randomly` would work | Tests that pass only when run after another test set up state |
| **No wall-clock dependence** | Time-sensitive tests use injected clocks or frozen time, not `datetime.now()` | Flaky tests that fail around midnight or on slow CI machines |
| **No network calls** | Unit tests never hit real endpoints; integration tests use local/in-memory DBs | Tests that fail without internet or when Ollama isn't running |
| **No filesystem side effects** | Tests don't write to real paths; use `tmp_path` or in-memory alternatives | Tests that create files in the working directory and don't clean up |
| **Deterministic randomness** | Tests that involve dice rolls, shuffles, or randomization seed the RNG or mock it | Flaky combat tests that pass 95% of the time due to random damage rolls |

## 7. Readability and Maintainability

| Criterion | What to look for | Red flag |
|---|---|---|
| **Arrange-Act-Assert structure** | Each test has a clear setup, a single action, and focused assertions — visually separated | Setup, action, and assertions interleaved in a 40-line block |
| **Self-documenting tests** | The test body tells a story a new developer can follow without reading the implementation | Test that requires reading 3 fixture files and 2 helper modules to understand what it does |
| **No magic numbers/strings** | Constants have names or are explained; IDs like `"player-1"` are traceable to the fixture that created them | `assert result.count == 7` with no indication of where 7 comes from |
| **DRY without obscuring** | Shared setup extracted to helpers, but the test-specific parts stay in the test | So much abstraction that adding a new test requires understanding 4 layers of base classes |
| **Proportional complexity** | Test complexity is proportional to the feature complexity; simple features have simple tests | A 200-line test for a 5-line utility function |

## 8. Performance

| Criterion | What to look for | Red flag |
|---|---|---|
| **Fast unit tests** | Unit tests complete in < 1 second each; full unit suite in < 30 seconds | Unit tests that each take 2+ seconds due to unnecessary setup |
| **Lazy expensive setup** | Expensive fixtures (DB creation, scenario loading) are session or module-scoped, not per-test | Every test function creates and tears down a database |
| **No sleep in tests** | Timing is controlled via mocks/fakes, not `time.sleep()` | `sleep(2)` to "wait for the timer to fire" |
| **Parallelizable** | Tests don't share global state that prevents `pytest-xdist` | Singleton registries or module-level state that causes conflicts under parallel execution |

## 9. Traceability

| Criterion | What to look for | Red flag |
|---|---|---|
| **Spec references** | Test modules or classes reference the spec/plan section they verify (e.g., "per test plan section 3.3") | Tests exist but nobody knows which requirements they cover |
| **PDR/design coverage** | Each verification criterion in the PDR has at least one test that exercises it | Design doc lists 9 acceptance criteria; tests cover 5 of them |
| **Bug-fix traceability** | Regression tests reference the bug ID or description they prevent | `test_fix_42` with no indication of what bug 42 was |

## 10. Anti-Patterns to Flag

| Anti-pattern | Description |
|---|---|
| **Test the mock** | Test verifies that a mock returns what it was configured to return, not that the system does the right thing with it |
| **Ice cream cone** | Many slow integration/E2E tests, few fast unit tests (pyramid is inverted) |
| **Flickering tests** | Tests that sometimes pass, sometimes fail without code changes (timing, ordering, randomness) |
| **Commented-out tests** | Tests that were "temporarily" disabled and never re-enabled |
| **Assert True** | `assert True` or `assert 1 == 1` — placeholder tests that provide false confidence |
| **Copy-paste tests** | 10 nearly-identical tests that differ by one parameter but aren't parametrized |
| **God fixture** | One fixture that builds the entire universe and is used by every test |
| **Test confirms implementation, not behavior** | Test breaks when implementation changes even though behavior is unchanged (fragile mocking) |

---

## How to Use This Document

1. **Per-file audit:** Walk through each test file and score it against sections 1-9. Note specific findings.
2. **Suite-level audit:** Evaluate sections 5 (coverage), 6 (determinism), 8 (performance), and 9 (traceability) across the whole suite.
3. **Anti-pattern scan:** Check section 10 against the full suite; flag instances for remediation.
4. **Prioritize fixes:** Security gaps (5.5) and flaky tests (6) are highest priority. Naming (1) and readability (7) are lower priority but compound over time.
