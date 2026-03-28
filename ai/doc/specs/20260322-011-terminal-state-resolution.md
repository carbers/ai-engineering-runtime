# Implement Terminal State Resolution

## Metadata

### Source Plan / Request
Directly scoped phase request in Codex chat on 2026-03-22 to normalize and implement the 009-012 history, terminal-state, and summary chain on top of the existing replay foundation.

### Status
`done`

### Related Specs
- `20260322-008-result-log-ingestion-replay.md`
- `20260322-009-run-correlation-history-selection.md`
- `20260322-010-replay-signal-projection.md`
- `20260322-012-run-summary-materialization.md`

## Goal
Implement one canonical terminal-state resolver that turns current or historical normalized run outcomes into a stable control-plane terminal state and stop reason for downstream summary and review use.

## In Scope
- define a minimal terminal-state taxonomy grounded in existing workflow outcomes:
  - `planning`
  - `ready`
  - `executing`
  - `review`
  - `complete`
  - `blocked`
  - `unknown`
- resolve terminal state from:
  - current `RunResult`
  - historical run-log records loaded from existing run logs
- resolve one stop reason from the best available normalized evidence in priority order:
  - top-level run issues
  - signal-specific reasons
  - normalized signal kind and value
  - workflow-state fallback
- use projected history signals only as a fallback input when current normalized signal evidence is absent
- add focused tests for current-run resolution, historical-log resolution, and stop-reason priority

## Out of Scope
- changing node execution semantics
- automatic retry, resume, or recovery behavior
- schedulers or workflow engines
- deep policy engines
- AI-generated state decisions
- a dedicated standalone CLI command in this slice

## Affected Area
- `src/ai_engineering_runtime/run_logs.py`
- `src/ai_engineering_runtime/terminal_state.py`
- `src/ai_engineering_runtime/run_summary.py`
- `tests/test_terminal_state.py`
- `tests/test_run_summary.py`

## Task Checklist
- [x] define the canonical terminal-state taxonomy and stop-reason contract
- [x] resolve terminal state from current `RunResult` without re-running node logic
- [x] resolve terminal state from historical run-log records for replay-backed summary queries
- [x] add focused unit coverage for state mapping and stop-reason priority

## Done When
Runtime code can ask for one canonical terminal state and stop reason for a current run result or a historical run log and receive a stable control-plane answer without reinterpreting raw logs in each downstream consumer.

## Validation

### Black-box Checks
- resolve `blocked` from a failed replay or validation outcome with the expected stop reason
- resolve `ready` or `review` from successful control-plane states without inventing broader workflow semantics
- resolve a historical run log to the same terminal state contract used for current runs
- run `python -m unittest tests.test_terminal_state tests.test_run_summary -v`

### White-box Needed
Yes

### White-box Trigger
This slice defines a stable downstream contract over branch-heavy outcome mapping. Black-box checks alone will not reliably protect workflow-state normalization or stop-reason priority.

### Internal Logic To Protect
- workflow-state to terminal-state mapping
- stop-reason priority across issues, signal reasons, normalized signal values, and workflow fallback
- parity between current-run and historical-log resolution

## Write-back Needed
No

## Risks / Notes
### Implementation Shape
Keep this slice as one focused resolver module consumed by summary materialization. Do not turn it into a scheduler, policy engine, or retry coordinator.

### State / Data Contract Impact
Add one canonical terminal-state contract that hides raw run-log details while staying closely aligned with existing workflow-state semantics.

### CLI Impact
No dedicated CLI command in this slice. Surface terminal state through the run-summary query path.

### Split / Defer
Create a follow-on spec before implementation if work expands to retry policy, workflow orchestration, or automated decision logic on top of terminal states.
