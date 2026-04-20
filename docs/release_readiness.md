# Release Readiness Assessment

## Open Bugs

See `docs/bugs.md` for the full bug tracker.

| Severity | Count | Status |
|---|---|---|
| P0 | 3 | Open — must fix before release |
| P1 | 21 | Open — must fix before release |
| P2 | 48 | Open — fix if time permits |
| P3 | 14 | Open — defer to post-release |

## Severity Definitions

- P0: Data loss, scope leakage, security issue -- must fix before release
- P1: Gameplay-breaking bug -- must fix before release
- P2: Quality/polish issue -- fix if time permits
- P3: Enhancement -- defer to post-release

## Release Criteria

- [ ] All P0 and P1 bugs resolved (3 P0 + 21 P1 = 24 remaining)
- [x] Full test suite passes (target: 1200+ tests) -- currently 1292
- [x] Lint clean (ruff check + ruff format)
- [x] All 4 starter scenarios load and validate without errors
- [ ] 10-turn scripted session completes without crashes
- [ ] No scope leakage detected in extended session
- [x] Admin diagnostics command works
- [x] Mini App loads and displays data correctly

## Notes

- Bug audit on 2026-04-19 found 86 bugs across ~65 files. See `docs/bugs.md` for full details.
- Top priorities: 3 P0 security bugs (auth bypass, path traversal, scope leakage), then 21 P1 correctness bugs (combat pipeline, bot handlers, contract drift, timer, recovery).
- The OpenAI adapter (BUG-001) requires a live API key; Gemma adapter (`models/gemma/`) provides a local-network alternative via `GEMMA_BASE_URL`.
- Mock adapters provide full test coverage for both main-tier backends.
