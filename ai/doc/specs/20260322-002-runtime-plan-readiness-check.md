# Implement Plan Readiness Check

## Metadata

### Source Plan / Request
Directly scoped task request in Codex chat on 2026-03-22 for a first-class `plan-readiness-check` capability.

### Status
`done`

### Related Specs
- `20260322-001-runtime-plan-to-spec-foundation.md`

## Goal
Implement a first-class `plan-readiness-check` capability that determines whether a plan is ready to be compiled into task specs, and returns a structured readiness result with machine-usable reasons.

## In Scope
- define a runtime-facing readiness result model
- implement readiness checking for `plan` -> `task-spec` compilation readiness
- return structured readiness outcomes for `ready`, `blocked`, and `needs_clarification`
- return machine-usable reason codes and messages for non-ready outcomes
- add a CLI path to run readiness checks on a plan artifact
- add focused tests for readiness outcomes, reason codes, and failure cases
- align runtime docs and state docs where the readiness semantics become stable

## Out of Scope
- draft task spec -> implementation readiness
- executor dispatch
- validation ingestion
- write-back classification
- automatic follow-up generation
- autonomy level enforcement
- GitHub, watcher, or daemon automation
- broad artifact model redesign
- replacing the existing `plan-to-spec` node

## Affected Area
- `src/ai_engineering_runtime/state.py`
- `src/ai_engineering_runtime/engine.py`
- `src/ai_engineering_runtime/nodes/*`
- `src/ai_engineering_runtime/cli.py`
- `tests/*`
- `ai/doc/runtime/*`
- `README.md`

## Task Checklist
- [x] define and wire a reusable readiness result model
- [x] add a first-class readiness-check node and CLI command
- [x] route `plan-to-spec` through the shared readiness gate
- [x] add focused ready, clarification, blocked, and failure-path tests
- [x] update runtime docs for the stable readiness semantics

## Done When
A contributor can run a dedicated readiness check against a plan artifact and receive a structured readiness result with stable reason codes, while `plan-to-spec` only proceeds when that readiness result is `ready`.

## Validation

### Black-box Checks
- run `python -m unittest discover -s tests -v`
- run a readiness check against a known ready plan fixture and get `ready`
- run a readiness check against a clarification-needed plan fixture and get `needs_clarification`
- run a readiness check against a blocked plan fixture and get `blocked`
- verify the readiness CLI output is stable and understandable

### White-box Needed
Yes

### White-box Trigger
This slice introduces a core workflow gate and affects internal decision logic, state transitions, and non-ready path handling.

### Internal Logic To Protect
- readiness result classification
- distinction between `blocked` and `needs_clarification`
- required field and contract checks
- stable reason-code emission
- state transition eligibility checks

## Write-back Needed
Yes, but keep it narrow by updating runtime design and state docs only where the readiness semantics become stable.

## Risks / Notes
- avoid overfitting the checker to only the current roadmap markdown shape
- avoid turning readiness logic into a large rule engine in this slice
- keep the result model small but extensible
- preserve the current lightweight CLI-first direction
