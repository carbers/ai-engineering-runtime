# Implement Followup Package Builder

## Metadata

### Source Plan / Request
Directly scoped phase request in Codex chat on 2026-03-23 to continue the post-summary control-plane chain with artifact refs, node contracts, gate evaluation, validation rollups, and package builders.

### Status
`done`

### Related Specs
- `20260322-006-followup-suggester.md`
- `20260322-013-artifact-reference-resolution.md`
- `20260322-016-validation-rollup-policy.md`
- `20260322-017-writeback-package-builder.md`

## Goal
Implement one stable follow-up package artifact that packages the current suggested next action, blockers or preconditions, supporting refs, and summary linkage for control-plane review.

## In Scope
- define a compact `FollowupPackage` contract with:
  - follow-up action
  - rationale
  - suggested next step
  - blockers or preconditions
  - supporting artifact refs
  - related summary ref
  - related validation-rollup ref when present
- build one package at a time from:
  - `followup-suggester` result or replayable log
  - current run summary
  - validation rollup artifact when available
- materialize packages under a dedicated runtime package directory
- add one thin CLI command `followup-package`
- add focused tests for clarify, fix-validation, write-back, promote-skill, and no-followup scenarios

## Out of Scope
- automatic task creation
- automatic dispatch or execution
- GitHub or CI automation
- dashboards
- generalized workflow orchestration

## Affected Area
- `src/ai_engineering_runtime/followup_package.py`
- `src/ai_engineering_runtime/artifact_refs.py`
- `src/ai_engineering_runtime/adapters.py`
- `src/ai_engineering_runtime/nodes/followup_package.py`
- `src/ai_engineering_runtime/cli.py`
- `tests/test_followup_package.py`
- `tests/test_cli.py`

## Task Checklist
- [ ] define the stable follow-up package model and storage convention
- [ ] build packages from follow-up output plus supporting summary and optional rollup refs
- [ ] expose a thin `followup-package` CLI for explicit log, run-id, and latest queries
- [ ] add focused unit and CLI coverage for the current follow-up action set

## Done When
A contributor can run `python -m ai_engineering_runtime followup-package --log .runtime/runs/<timestamp>-followup-suggester.json` and receive one stable follow-up package artifact that captures rationale, blockers, and the suggested next step without turning the runtime into an execution planner.

## Validation

### Black-box Checks
- build a package for `clarify_plan` with the expected blocker rationale
- build a package for `fix_validation_failure` with the expected suggested next step
- build a package for `no_followup_needed` with a non-actionable clean-closeout package
- materialize and reload a package by run id
- run `python -m unittest tests.test_followup_package tests.test_cli -v`

### White-box Needed
Yes

### White-box Trigger
This slice creates a second durable suggestion artifact with structured blockers and next-step mapping. Black-box checks alone will not reliably protect package field mapping or blocker extraction.

### Internal Logic To Protect
- follow-up result to package field mapping
- blocker and precondition extraction from follow-up reasons
- suggested-next-step mapping by follow-up action
- supporting artifact-ref construction

## Write-back Needed
Yes - update `docs/runtime/protocol.md` and `README.md` only if the package artifact and CLI semantics stabilize during implementation.

## Risks / Notes
### Implementation Shape
Keep this as a suggestion package builder only. Do not create tasks, dispatch work, or orchestrate execution automatically.

### Package / Data Contract Impact
This slice adds a stable follow-up package artifact with summary and rollup linkage via artifact refs.

### CLI Impact
Add one thin `followup-package` query command for one follow-up result at a time.

### Split / Defer
Create a follow-on spec before implementation if work expands to task creation, dispatch automation, or full workflow orchestration.
