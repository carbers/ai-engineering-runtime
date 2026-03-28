# Implement Write-back Classifier

## Metadata

### Source Plan / Request
Directly scoped task request in Codex chat on 2026-03-22 for a first-class `writeback-classifier` capability.

### Status
`done`

### Related Specs
- `20260322-002-runtime-plan-readiness-check.md`
- `20260322-006-followup-suggester.md`

## Goal
Implement a first-class `writeback-classifier` capability that decides whether closeout information is stable enough to persist, and if so whether it belongs in facts, skills, or only a task-local change summary.

## In Scope
- define a small write-back classification result model with a destination, machine-usable reason codes, and a write-back eligibility flag
- support exactly these destinations in this slice:
  - `facts`
  - `skills`
  - `change_summary_only`
  - `ignore`
- classify a single candidate closeout item at a time from candidate text plus a small optional kind hint
- keep destination semantics aligned with the repository write-back policy in `AGENTS.md`
- add a CLI path for classifying one supplied candidate
- add focused tests for destination mapping, reason-code emission, and CLI output stability
- update runtime docs only if the classifier contract becomes stable enough to describe

## Out of Scope
- automatic file writing into `ai/doc/facts/*` or `ai/skill/*`
- follow-up task generation
- validation aggregation
- executor dispatch
- broad artifact-model redesign
- multi-candidate ranking or policy-engine behavior
- GitHub, watcher, or daemon automation

## Affected Area
- `src/ai_engineering_runtime/state.py`
- `src/ai_engineering_runtime/engine.py`
- `src/ai_engineering_runtime/nodes/*`
- `src/ai_engineering_runtime/cli.py`
- `tests/*`
- `ai/doc/runtime/*`
- `README.md`

## Task Checklist
- [x] define a narrow write-back result model with stable destinations and reason codes
- [x] implement a `writeback-classifier` node that classifies one candidate item without writing files
- [x] add a CLI command for classifying supplied candidate text
- [x] cover facts, skills, change-summary-only, and ignore outcomes with focused tests
- [x] update stable runtime docs only if the contract meaningfully changes

## Done When
A contributor can run a dedicated write-back classification against a supplied closeout candidate and receive a structured destination decision with stable reason codes, without the runtime writing facts or skills automatically.

## Validation

### Black-box Checks
- classify a stable project-wide decision as `facts`
- classify a reusable runtime-side workflow pattern as `skills`
- classify task-local delivery detail as `change_summary_only`
- classify one-off debugging or transient detail as `ignore`
- verify CLI output is stable and understandable
- run unit tests successfully

### White-box Needed
Yes

### White-box Trigger
This slice introduces a control-plane closeout decision with machine-usable outputs. Black-box checks alone will not reliably protect the boundary between durable write-back, task-local summaries, and transient noise.

### Internal Logic To Protect
- destination selection
- stable vs transient distinction
- reusable workflow vs project-context distinction
- stable reason-code emission
- result formatting for logs and CLI output

## Write-back Needed
Yes, but keep it narrow by updating runtime docs only if the write-back destination contract becomes stable. Do not write new facts or skills from this task by default.

## Risks / Notes
- avoid overfitting to one current closeout wording style
- avoid turning this slice into a large policy engine
- keep the result model small enough for later follow-up logic to consume directly
- preserve the lightweight CLI-first control-plane boundary
- Black-box validation completed with `python -m unittest discover -s tests -v` and `$env:PYTHONPATH='src'; python -m ai_engineering_runtime writeback-classifier --text "This repeatable workflow checklist should be reused later." --kind workflow_pattern`
