# Implement Follow-up Suggester

## Metadata

### Source Plan / Request
Directly scoped task request in Codex chat on 2026-03-22 for a first-class `followup-suggester` capability.

### Status
`done`

### Related Specs
- `20260322-003-writeback-classifier.md`
- `20260322-004-task-spec-readiness-check.md`
- `20260322-005-validation-collect-foundation.md`

## Goal
Implement a first-class `followup-suggester` capability that recommends the next narrow control-plane action based on earlier readiness, validation, and write-back results.

## In Scope
- define a structured follow-up suggestion result model with a suggestion category, machine-usable reason codes, and a concise explanation
- consume structured signals from earlier runtime nodes rather than re-deriving readiness, validation, or write-back decisions
- support exactly these suggestion outcomes in this slice:
  - `implement_next_task`
  - `clarify_plan`
  - `fix_validation_failure`
  - `write_back_stable_context`
  - `promote_skill_candidate`
  - `no_followup_needed`
- apply a small explicit priority order when multiple signals are present
- allow an optional closeout hint so `no_followup_needed` is only returned when the inputs actually support a clean stop
- add a CLI path to generate follow-up suggestions from supplied structured statuses
- add focused tests for category selection, reason-code emission, and priority handling
- update runtime docs only if the follow-up contract becomes stable enough to describe

## Out of Scope
- automatic creation of new spec files
- automatic file writing into facts or skills
- executor dispatch
- autonomy enforcement
- broad planning-engine behavior
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
- [x] define a narrow follow-up suggestion model with stable categories and reason codes
- [x] implement a `followup-suggester` node that consumes prior node results instead of recomputing them
- [x] establish and test a small priority order across readiness, validation, and write-back signals
- [x] add a CLI command for generating follow-up suggestions from supplied statuses
- [x] update stable runtime docs only if the contract needs to be documented

## Done When
A contributor can supply earlier runtime outputs to a dedicated follow-up node and receive one clear next-step suggestion with stable reason codes, without the runtime turning into a planner or automation engine.

## Validation

### Black-box Checks
- suggest `clarify_plan` for a clarification-needed readiness result
- suggest `fix_validation_failure` for a failed validation result
- suggest `write_back_stable_context` for a facts-worthy write-back result
- suggest `promote_skill_candidate` for a skills-worthy write-back result
- suggest `implement_next_task` for a clean ready/passed path with no closer stop signal
- suggest `no_followup_needed` only when the supplied closeout hint explicitly supports a clean stop
- run unit tests successfully

### White-box Needed
Yes

### White-box Trigger
This slice introduces a control-plane decision node with competing upstream signals. Black-box checks alone will not reliably protect the priority order and boundary between â€œcontinueâ€? â€œfixâ€? â€œclarifyâ€? and â€œclose outâ€?

### Internal Logic To Protect
- suggestion category selection
- signal priority ordering
- stable reason-code emission
- mapping from readiness, validation, and write-back signals to next-step categories
- guarded `no_followup_needed` handling

## Write-back Needed
Yes, but keep it narrow by updating runtime docs only if the follow-up contract becomes stable. Do not auto-create downstream artifacts in this slice.

## Risks / Notes
- avoid turning the suggester into a large planning engine
- keep the suggestion taxonomy small and composable
- avoid duplicating readiness, validation, or write-back logic inside this node
- preserve the control-plane boundary by recommending actions instead of taking them
- Black-box validation completed with `python -m unittest discover -s tests -v` and `$env:PYTHONPATH='src'; python -m ai_engineering_runtime followup-suggester --validation-status failed`
