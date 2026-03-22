# Implement Task-Spec Readiness Check

## Metadata

### Source Plan / Request
Directly scoped task request in Codex chat on 2026-03-22 for a first-class `task-spec-readiness-check` capability.

### Status
`done`

### Related Specs
- `20260322-002-runtime-plan-readiness-check.md`
- `20260322-007-executor-dispatch-adapter-shell.md`

## Goal
Implement a first-class `task-spec-readiness-check` capability that determines whether a task spec using the current repository contract is ready to move into implementation or dispatch, and returns a structured readiness result with machine-usable reasons.

## In Scope
- define or extend task-spec parsing for the current spec contract in `docs/templates/task-spec-template.md`
- reuse the shared readiness result model shape and status taxonomy where it still fits
- implement readiness checking for `task spec -> implementation` eligibility
- return structured readiness outcomes for `ready`, `needs_clarification`, and `blocked`
- validate at least:
  - metadata source presence
  - allowed spec status for implementation eligibility
  - goal presence
  - list-shaped scope sections
  - deliverable / `Done When` presence
  - validation section presence
  - `Write-back Needed` presence or explicit `No`
- treat missing required structure or invalid choice fields as `blocked`
- treat placeholder or ambiguous required content as `needs_clarification`
- add a CLI path to run readiness checks on a task-spec artifact
- add focused tests for ready, clarification, blocked, and parser/contract failures
- update runtime docs/state docs only if the task-spec contract becomes more explicit

## Out of Scope
- executor dispatch itself
- validation aggregation
- write-back classification
- automatic follow-up generation
- broad task-spec template redesign
- replacing plan-readiness logic
- autonomy enforcement or worker behavior
- GitHub, watcher, or daemon automation

## Affected Area
- `src/ai_engineering_runtime/artifacts.py`
- `src/ai_engineering_runtime/state.py`
- `src/ai_engineering_runtime/engine.py`
- `src/ai_engineering_runtime/nodes/*`
- `src/ai_engineering_runtime/cli.py`
- `tests/*`
- `docs/runtime/*`
- `README.md`

## Task Checklist
- [x] add task-spec parsing helpers for the current Markdown spec contract
- [x] implement a dedicated `task-spec-readiness-check` node and CLI command
- [x] classify `ready`, `needs_clarification`, and `blocked` with stable reason codes
- [x] protect the distinction between missing contract structure and ambiguous content with focused tests
- [x] update stable runtime docs only if the task-spec readiness contract needs to be documented

## Done When
A contributor can run a dedicated readiness check against a task spec and receive a structured readiness result with stable reason codes, and later slices can rely on that result before dispatch or implementation.

## Validation

### Black-box Checks
- run readiness check against a known ready task spec and get `ready`
- run readiness check against a clarification-needed task spec and get `needs_clarification`
- run readiness check against a blocked task spec and get `blocked`
- verify CLI output is stable and understandable
- run unit tests successfully

### White-box Needed
Yes

### White-box Trigger
This slice introduces a second workflow gate and the first executable parser for task-spec contracts. Black-box checks alone will not reliably protect contract parsing, eligibility rules, or the distinction between blocked and clarification-needed specs.

### Internal Logic To Protect
- task-spec section and metadata parsing
- readiness result classification
- distinction between `blocked` and `needs_clarification`
- required execution-contract checks
- stable reason-code emission

## Write-back Needed
Yes, but keep it narrow by updating runtime protocol/state docs only if the task-spec readiness semantics become stable. Do not write facts unless project-wide behavior changes.

## Risks / Notes
- avoid overfitting the checker to incidental prose in the current spec files
- avoid turning readiness logic into a large rule engine
- keep the result model aligned with the existing plan-readiness contract where possible
- preserve the lightweight control-plane direction so later dispatch uses this gate instead of inventing a second one
- Black-box validation completed with `python -m unittest discover -s tests -v` and `$env:PYTHONPATH='src'; python -m ai_engineering_runtime task-spec-readiness-check --spec docs/specs/20260322-004-task-spec-readiness-check.md`
