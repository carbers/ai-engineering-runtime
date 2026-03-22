# Implement Run Summary Materialization

## Metadata

### Source Plan / Request
Directly scoped phase request in Codex chat on 2026-03-22 to normalize and implement the 009-012 history, terminal-state, and summary chain on top of the existing replay foundation.

### Status
`done`

### Related Specs
- `20260322-008-result-log-ingestion-replay.md`
- `20260322-009-run-correlation-history-selection.md`
- `20260322-010-replay-signal-projection.md`
- `20260322-011-terminal-state-resolution.md`

## Goal
Implement one stable per-run summary artifact and query surface that materializes canonical run review data for current and historical runs without exposing raw run logs as the public control-plane interface.

## In Scope
- define a minimal materialized run-summary contract that includes:
  - summary schema version
  - run id
  - node identity
  - source log path
  - ordered timestamp
  - success flag
  - artifact target when present
  - canonical terminal state
  - compact projected history signals when relevant history exists
- materialize a summary JSON artifact for each new run under a dedicated `.runtime/summaries/` directory
- load a historical summary by:
  - explicit run-log path
  - run id
  - latest run-log selection with optional node filter
- fall back to replay-backed materialization from the source run log when a summary artifact does not yet exist
- keep summary generation in a dedicated service so `engine.py` only needs a thin post-run hook
- add one thin `run-summary` CLI command with:
  - human-readable default output
  - optional `--json` output
- add focused tests for automatic materialization, fallback loading, latest selection, and human-readable CLI output

## Out of Scope
- dashboards or reporting platforms
- long-form narrative report generation
- issue or task creation automation
- GitHub or CI integrations
- trend analytics across many runs
- event sourcing or schema-migration frameworks
- exposing all raw run-log payloads as the summary contract

## Affected Area
- `src/ai_engineering_runtime/adapters.py`
- `src/ai_engineering_runtime/engine.py`
- `src/ai_engineering_runtime/run_logs.py`
- `src/ai_engineering_runtime/history_selection.py`
- `src/ai_engineering_runtime/history_projection.py`
- `src/ai_engineering_runtime/terminal_state.py`
- `src/ai_engineering_runtime/run_summary.py`
- `src/ai_engineering_runtime/nodes/run_summary.py`
- `src/ai_engineering_runtime/cli.py`
- `tests/test_run_summary.py`
- `tests/test_cli.py`
- `docs/runtime/protocol.md`
- `README.md`

## Task Checklist
- [x] define the materialized run-summary schema and storage path convention
- [x] materialize a summary artifact automatically after each successful or failed node run
- [x] support replay-backed summary loading for existing historical run logs without summaries
- [x] expose a thin `run-summary` CLI for explicit log, run-id, and latest queries
- [x] add targeted unit and CLI coverage for materialization, fallback loading, and summary output
- [x] document the summary contract only if the artifact shape and CLI semantics stabilize during implementation

## Done When
A contributor can run any runtime node and find a matching summary artifact under `.runtime/summaries/`, then query that summary with `python -m ai_engineering_runtime run-summary --latest` or `python -m ai_engineering_runtime run-summary --run-id <timestamp-node>`, receiving one stable control-plane summary view backed by canonical terminal state and compact history signals rather than raw run-log assembly.

## Validation

### Black-box Checks
- running a node writes both a run log and a matching summary artifact
- `run-summary --log <path>` loads or materializes the expected summary for an existing historical run log
- `run-summary --run-id <timestamp-node>` resolves the expected summary artifact
- `run-summary --latest --node validation-collect` selects the latest matching run and prints a thin human-readable summary
- `run-summary --latest --json` emits the materialized summary JSON view
- run `python -m unittest tests.test_run_summary tests.test_cli -v`

### White-box Needed
Yes

### White-box Trigger
This slice introduces the first durable run-summary artifact and a new engine-level post-run hook. Black-box checks alone will not reliably protect summary path mapping, fallback materialization, or the rule that summary reuses normalized services instead of reassembling raw logic independently.

### Internal Logic To Protect
- run-id and summary-path derivation from run-log filenames
- automatic summary materialization after node execution
- fallback summary materialization from historical run logs
- reuse of history selection, signal projection, and terminal-state services
- stable JSON summary schema rendering

## Write-back Needed
Yes - update `docs/runtime/protocol.md` and `README.md` if the summary artifact shape and query semantics stabilize during implementation.

## Risks / Notes
### Implementation Shape
Materialize summaries through one dedicated summary service plus a thin engine hook. Keep `engine.py` limited to calling the service after node execution rather than embedding summary logic directly.

### Summary / Data Contract Impact
Add one stable per-run summary artifact under `.runtime/summaries/` with canonical terminal state and compact history context. Keep the schema narrow and versioned from day one with a minimal integer version field.

### CLI Impact
Add one thin `run-summary` query command. Use it as the only user-facing inspection surface for terminal state and projected history in this slice.

### Split / Defer
Create a follow-on spec before implementation if work expands to dashboards, trend analytics, narrative report generation, or automated issue creation.
