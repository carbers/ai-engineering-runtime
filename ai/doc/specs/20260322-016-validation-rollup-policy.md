# Implement Validation Rollup Policy

## Metadata

### Source Plan / Request
Directly scoped phase request in Codex chat on 2026-03-23 to continue the post-summary control-plane chain with artifact refs, node contracts, gate evaluation, validation rollups, and package builders.

### Status
`done`

### Related Specs
- `20260322-005-validation-collect-foundation.md`
- `20260322-011-terminal-state-resolution.md`
- `20260322-012-run-summary-materialization.md`
- `20260322-017-writeback-package-builder.md`
- `20260322-018-followup-package-builder.md`

## Goal
Implement one decision-facing validation rollup layer that summarizes validation-collect findings into a stable blocking or advisory conclusion for downstream control-plane use.

## In Scope
- define a compact `ValidationRollup` contract with:
  - rollup status
  - finding severity
  - blocking versus advisory classification
  - normalized findings
- keep severity taxonomy minimal:
  - `blocking`
  - `advisory`
  - `info`
- build rollups from existing `validation-collect` results without redesigning validation collection
- support rollup materialization and query for one validation run at a time
- add one thin CLI command `validation-rollup`
- add focused tests for blocking, advisory, and clean rollups plus CLI output

## Out of Scope
- redesigning `validation-collect`
- analytics or quality dashboards
- long-term trend statistics
- a generalized rules engine
- automatic remediation or retry logic

## Affected Area
- `src/ai_engineering_runtime/validation_rollup.py`
- `src/ai_engineering_runtime/run_logs.py`
- `src/ai_engineering_runtime/adapters.py`
- `src/ai_engineering_runtime/nodes/validation_rollup.py`
- `src/ai_engineering_runtime/cli.py`
- `tests/test_validation_rollup.py`
- `tests/test_cli.py`

## Task Checklist
- [ ] define the minimal validation-rollup and normalized-finding model
- [ ] derive rollups from existing validation-collect run logs and current validation results
- [ ] materialize and query one validation rollup artifact at a time
- [ ] add focused unit and CLI coverage for blocking, advisory, and clean rollups

## Done When
A contributor can run `python -m ai_engineering_runtime validation-rollup --log .runtime/runs/<timestamp>-validation-collect.json` and receive one stable validation rollup that marks findings as blocking, advisory, or informational without reinterpreting validation evidence in each downstream consumer.

## Validation

### Black-box Checks
- roll up a failed or incomplete validation result as `blocking`
- roll up a passed validation result with manual notes as `info` or clean non-blocking output
- materialize and reload one validation rollup artifact by run id
- run `python -m unittest tests.test_validation_rollup tests.test_cli -v`

### White-box Needed
Yes

### White-box Trigger
This slice adds a new decision-facing normalization layer over validation results. Black-box checks alone will not reliably protect severity mapping or blocking-versus-advisory classification.

### Internal Logic To Protect
- validation-status to rollup-status mapping
- reason-code to severity mapping
- normalized-finding derivation from validation reasons and notes
- artifact materialization and reload behavior

## Write-back Needed
Yes - update `ai/doc/runtime/protocol.md` and `README.md` only if the rollup artifact and CLI semantics stabilize during implementation.

## Risks / Notes
### Implementation Shape
Keep the rollup layer downstream of `validation-collect`. Do not turn it into a second validation engine or broad policy system.

### Validation / Data Contract Impact
This slice adds a stable rollup artifact that downstream summary and package builders can reference instead of re-reading raw validation findings.

### CLI Impact
Add one thin `validation-rollup` query command for one validation run at a time.

### Split / Defer
Create a follow-on spec before implementation if work expands to long-window trends, comparative reporting, or executor-facing remediation advice.
