# Implement Writeback Package Builder

## Metadata

### Source Plan / Request
Directly scoped phase request in Codex chat on 2026-03-23 to continue the post-summary control-plane chain with artifact refs, node contracts, gate evaluation, validation rollups, and package builders.

### Status
`done`

### Related Specs
- `20260322-003-writeback-classifier.md`
- `20260322-013-artifact-reference-resolution.md`
- `20260322-016-validation-rollup-policy.md`
- `20260322-018-followup-package-builder.md`

## Goal
Implement one stable write-back package artifact that packages the current write-back classification, rationale, supporting refs, and suggested next action for control-plane review.

## In Scope
- define a compact `WritebackPackage` contract with:
  - destination / classification
  - rationale
  - actionable flag
  - suggested next action
  - supporting artifact refs
  - related summary ref
  - related validation-rollup ref when present
- build one package at a time from:
  - `writeback-classifier` result or replayable log
  - current run summary
  - validation rollup artifact when available
- materialize packages under a dedicated runtime package directory
- add one thin CLI command `writeback-package`
- add focused tests for facts, skills, change-summary-only, and ignore scenarios

## Out of Scope
- automatic write-back execution
- patch generation
- GitHub, PR, or issue automation
- dashboards or reporting systems
- generalized remediation workflows

## Affected Area
- `src/ai_engineering_runtime/writeback_package.py`
- `src/ai_engineering_runtime/artifact_refs.py`
- `src/ai_engineering_runtime/adapters.py`
- `src/ai_engineering_runtime/nodes/writeback_package.py`
- `src/ai_engineering_runtime/cli.py`
- `tests/test_writeback_package.py`
- `tests/test_cli.py`

## Task Checklist
- [ ] define the stable write-back package model and storage convention
- [ ] build packages from classifier output plus supporting summary and optional rollup refs
- [ ] expose a thin `writeback-package` CLI for explicit log, run-id, and latest queries
- [ ] add focused unit and CLI coverage for actionable and non-actionable package cases

## Done When
A contributor can run `python -m ai_engineering_runtime writeback-package --log .runtime/runs/<timestamp>-writeback-classifier.json` and receive one stable write-back package artifact that points to the relevant summary and supporting refs without auto-writing anything back.

## Validation

### Black-box Checks
- build a package for a `facts` classification with an actionable suggested next step
- build a package for a `skills` classification with the expected rationale
- build non-actionable packages for `change_summary_only` and `ignore`
- materialize and reload a package by run id
- run `python -m unittest tests.test_writeback_package tests.test_cli -v`

### White-box Needed
Yes

### White-box Trigger
This slice creates a new durable suggestion artifact. Black-box checks alone will not reliably protect package field derivation, supporting-ref construction, or actionable-flag mapping.

### Internal Logic To Protect
- write-back result to package field mapping
- suggested-next-action mapping by destination
- supporting artifact-ref construction
- package materialization and reload behavior

## Write-back Needed
Yes - update `ai/doc/runtime/protocol.md` and `README.md` only if the package artifact and CLI semantics stabilize during implementation.

## Risks / Notes
### Implementation Shape
Keep this as a suggestion artifact builder only. Do not auto-edit repo files or generate patches.

### Package / Data Contract Impact
This slice adds a stable write-back package artifact with summary and rollup linkage via artifact refs.

### CLI Impact
Add one thin `writeback-package` query command for one classifier result at a time.

### Split / Defer
Create a follow-on spec before implementation if work expands to auto-writeback execution, patch generation, or GitHub automation.
