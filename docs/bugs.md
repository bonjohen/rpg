# Bug Tracker

## Severity Definitions

- **P0:** Data loss, scope leakage, security issue — must fix before release
- **P1:** Gameplay-breaking bug — must fix before release
- **P2:** Quality/polish issue — fix if time permits
- **P3:** Enhancement — defer to post-release

## Open Bugs

| ID | Severity | Category | Description | Status |
|---|---|---|---|---|
| BUG-001 | P2 | Routing | OpenAI inference adapter requires live API key; all narration uses deterministic fallback without it | Deferred (requires OPENAI_API_KEY) |
| BUG-002 | P3 | Clarity | Narration fallback text is functional but repetitive across turns | Open |
| BUG-003 | P3 | Enhancement | No persistent storage; all state is in-memory (by design for playtest) | Deferred (post-Phase 20) |

## Resolved Bugs

None yet.
