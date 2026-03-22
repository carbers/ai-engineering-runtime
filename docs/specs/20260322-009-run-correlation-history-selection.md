# Implement Run Correlation History Selection

## Metadata

### Source Plan / Request
Directly scoped phase request in Codex chat on 2026-03-22 to normalize and implement the 009-012 history, terminal-state, and summary chain on top of the existing replay foundation.

### Status
`done`

### Related Specs
- `20260322-008-result-log-ingestion-replay.md`
- `20260322-010-replay-signal-projection.md`
- `20260322-011-terminal-state-resolution.md`
- `20260322-012-run-summary-materialization.md`

## Goal
Implement a narrow history-selection capability that lets the runtime choose replayable prior runs relevant to one explicit artifact target instead of scanning all run history indiscriminately.

## In Scope
- define one exact-match selector contract rooted in an explicit artifact target:
  - `spec`
  - `plan`
  - `output`
- support optional narrowing by replayed node name and replay signal kind
- select replayable prior run logs by reusing the 008 replay normalization layer instead of introducing a second raw-log contract
- order matches by existing filename-derived run-log timestamps, newest first
- return a compact structured selection result with:
  - selection status
  - ordered matches
  - applied selector basis
  - stable no-match reason codes
- add one focused history-selection service/module outside `engine.py`, `state.py`, and `cli.py`
- add a thin CLI query surface for exact selector-based history inspection
- add focused tests for selector matching, ordering, replay-only filtering, and no-match behavior

## Out of Scope
- fuzzy matching or similarity scoring
- implicit "current run context" inference without an explicit selector
- lineage graphs or event sourcing
- database-backed indexing
- replay-driven resume or recovery
- analytics, dashboards, or trend reporting
- AI-generated correlation decisions
- turning history into a new authoritative state source

## Affected Area
- `src/ai_engineering_runtime/run_logs.py`
- `src/ai_engineering_runtime/history_selection.py`
- `src/ai_engineering_runtime/nodes/run_history_select.py`
- `src/ai_engineering_runtime/engine.py`
- `src/ai_engineering_runtime/cli.py`
- `tests/test_history_selection.py`
- `tests/test_cli.py`
- `tests/fixtures/run_logs/*`
- `docs/runtime/protocol.md`
- `README.md`

## Task Checklist
- [x] add a narrow exact-selector history-selection contract centered on artifact target matching
- [x] implement replay-backed selection that reuses 008 normalized replay results
- [x] expose a thin `run-history-select` CLI path with explicit selectors and stable no-match handling
- [x] add targeted unit and CLI coverage for selection, ordering, filtering, and no-match results
- [x] document the selector boundary only if the CLI and contract stabilize during implementation

## Done When
A contributor can run `python -m ai_engineering_runtime run-history-select --spec docs/specs/20260322-005-validation-collect-foundation.md --node validation-collect --limit 3` and receive the newest relevant replayable runs for that exact artifact target, or a stable no-match result, without the runtime introducing fuzzy correlation or a separate history store.

## Validation

### Black-box Checks
- select the newest replayable run for an exact `--spec` selector
- narrow the result set further with `--node` and `--signal-kind`
- preserve newest-first ordering from filename timestamps
- return a stable no-match result when no replayable history matches the selector
- run `python -m unittest tests.test_history_selection tests.test_cli -v`

### White-box Needed
Yes

### White-box Trigger
This slice introduces deterministic selector matching and replay-backed ordering rules. Black-box checks alone will not reliably protect exact artifact-target normalization, replay-only filtering, or newest-first selection semantics.

### Internal Logic To Protect
- artifact-target normalization to the repo-relative contract already used by run logs
- replayable-only filtering on top of 008
- newest-first ordering from filename timestamps
- stable selector-basis reporting and no-match reason codes

## Write-back Needed
Yes - update `docs/runtime/protocol.md` and `README.md` only if the selector contract and CLI surface stabilize during implementation.

## Risks / Notes
### Implementation Shape
Implement this slice as one exact-match history-selection service plus one thin CLI node. Do not introduce an implicit current-run correlator, a second raw-log API, or a separate persistent index.

### Data Contract Impact
Add a narrow `HistorySelectionResult` contract that exposes selection status, ordered replay matches, and applied selector basis. Treat multiple exact matches as an ordered result set rather than an ambiguity engine in this slice.

### CLI Impact
Add one thin `run-history-select` command with explicit selector flags and no analytics-style output.

### Split / Defer
Create a follow-on spec before implementation if work expands to fuzzy matching, selector ambiguity taxonomies beyond exact selectors, implicit session correlation, or non-replayable history analysis.
