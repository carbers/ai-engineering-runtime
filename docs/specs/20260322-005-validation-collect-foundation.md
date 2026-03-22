# Implement Validation Collect Foundation

## Metadata

### Source Plan / Request
Directly scoped task request in Codex chat on 2026-03-22 for a first-class `validation-collect` capability.

### Status
`done`

### Related Specs
- `20260322-004-task-spec-readiness-check.md`
- `20260322-006-followup-suggester.md`

## Goal
Implement a first-class `validation-collect` capability that aggregates supplied validation evidence into a structured control-plane result suitable for task closeout and later follow-up decisions.

## In Scope
- define a structured validation collection result model with:
  - overall status
  - evidence entries
  - gap / failure reason codes
- support evidence entries for at least:
  - command execution outcome
  - black-box validation outcome
  - white-box validation outcome
  - optional manual note
- allow the collector to consider task-spec metadata when deciding whether missing white-box evidence is a failure or an incomplete gap
- derive exactly these overall statuses in this slice:
  - `passed`
  - `failed`
  - `incomplete`
- add a CLI path that collects validation from explicit supplied evidence inputs rather than orchestrating an external test runner
- add focused tests for status derivation, evidence shaping, and CLI output stability
- update runtime docs only if the validation result contract becomes stable enough to describe

## Out of Scope
- test-runner-specific parsing
- automatic command or test execution orchestration beyond a minimal manual input surface
- write-back classification
- follow-up suggestion generation
- CI, dashboard, watcher, or daemon behavior
- broad workflow graph redesign

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
- [x] define a narrow validation evidence and aggregated result model
- [x] implement a `validation-collect` node that derives `passed`, `failed`, or `incomplete`
- [x] use task-spec validation requirements when deciding whether missing evidence is a gap
- [x] add a CLI command that accepts explicit evidence inputs without becoming a test runner
- [x] add focused tests for passing, failing, and incomplete aggregation paths

## Done When
A contributor can supply task validation evidence to a dedicated runtime node and receive a structured aggregated validation result that distinguishes passing, failing, and incomplete closeout states without the runtime becoming a CI orchestration layer.

## Validation

### Black-box Checks
- aggregate a fully passing validation case as `passed`
- aggregate a failing command or failing validation case as `failed`
- aggregate a missing-required-evidence case as `incomplete`
- verify CLI output is stable and understandable
- run unit tests successfully

### White-box Needed
Yes

### White-box Trigger
This slice introduces control-plane aggregation logic. Black-box checks alone will not reliably protect the difference between failed evidence and missing evidence, or the effect of task-spec white-box requirements on the final status.

### Internal Logic To Protect
- overall status derivation
- evidence entry shaping
- failed vs incomplete distinction
- required-white-box gap detection
- stable reason-code emission

## Write-back Needed
Yes, but keep it narrow by updating runtime docs only if the validation aggregation contract becomes stable. Do not add facts or skills by default from this slice.

## Risks / Notes
- avoid coupling the collector to a single test runner format
- avoid turning this slice into a full CI orchestration engine
- keep evidence inputs simple enough for later follow-up logic to consume directly
- preserve the CLI-first control-plane position
- Black-box validation completed with `python -m unittest discover -s tests -v` and `$env:PYTHONPATH='src'; python -m ai_engineering_runtime validation-collect --spec docs/specs/20260322-005-validation-collect-foundation.md --command-status passed --black-box-status passed --white-box-status passed`
