# Implement Replay Signal Projection

## Metadata

### Source Plan / Request
Directly scoped phase request in Codex chat on 2026-03-22 to normalize and implement the 009-012 history, terminal-state, and summary chain on top of the existing replay foundation.

### Status
`done`

### Related Specs
- `20260322-008-result-log-ingestion-replay.md`
- `20260322-009-run-correlation-history-selection.md`
- `20260322-011-terminal-state-resolution.md`
- `20260322-012-run-summary-materialization.md`

## Goal
Implement a compact replay-signal projection layer that converts selected replay history into stable downstream-facing control-plane signals without exposing raw replay structures.

## In Scope
- define a minimal compact signal contract derived from existing replayable signal kinds:
  - latest readiness status
  - latest validation status
  - latest write-back destination
  - latest follow-up action
  - latest dispatch status
- include minimal provenance for each projected signal:
  - source log path
  - ordered timestamp
  - replayed node
- consume the 009 history-selection output rather than rescanning raw run logs
- make absence explicit by omitting a signal entry instead of inventing inferred values
- keep projection deterministic by selecting the newest matching value per compact signal key
- add focused tests for newest-wins projection, sparse history, and mixed-signal history sets

## Out of Scope
- re-running upstream node logic
- conflict scoring or contradiction analysis across long histories
- analytics or trend summaries
- AI-generated inferred signals
- policy engines or automated decision systems
- a dedicated standalone CLI command in this slice

## Affected Area
- `src/ai_engineering_runtime/history_projection.py`
- `src/ai_engineering_runtime/history_selection.py`
- `src/ai_engineering_runtime/run_summary.py`
- `tests/test_history_projection.py`
- `tests/test_run_summary.py`

## Task Checklist
- [x] define the compact projected-signal contract and newest-wins mapping from replay signal kinds
- [x] project selected history into deterministic latest-known signal entries with provenance
- [x] make missing signals explicit without inventing partial or inferred values
- [x] add focused unit coverage for sparse, mixed, and newest-wins projection behavior

## Done When
Downstream runtime code can consume one compact projected-signal result built from selected replay history, with explicit provenance and newest-wins semantics, without depending on raw replay payload shape or re-running upstream node logic.

## Validation

### Black-box Checks
- project the newest validation signal from a mixed selected history set
- retain multiple compact keys when selected history contains different replay signal kinds
- omit absent keys cleanly when selected history is sparse
- run `python -m unittest tests.test_history_projection tests.test_run_summary -v`

### White-box Needed
Yes

### White-box Trigger
This slice adds a new normalization layer that downstream code will rely on. Black-box checks alone will not reliably protect newest-wins mapping, signal-key naming, or provenance retention.

### Internal Logic To Protect
- replay-signal-kind to compact-key mapping
- newest-wins projection ordering
- omission of absent signals instead of inferred defaults
- provenance attachment to each projected signal

## Write-back Needed
No

## Risks / Notes
### Implementation Shape
Keep this slice as one internal projection service consumed by terminal-state and summary code. Do not add a standalone CLI unless a later task proves one is necessary.

### Signal / Data Contract Impact
Add one compact projected-signal contract with stable key names and source provenance. Keep the signal set aligned with existing replayable node outputs instead of inventing broader analytics-style fields.

### CLI Impact
No dedicated CLI command in this slice. Surface projection results only through higher-level summary output.

### Split / Defer
Create a follow-on spec before implementation if work expands to contradiction handling, long-window trend analysis, or automatic policy decisions from projected history.
