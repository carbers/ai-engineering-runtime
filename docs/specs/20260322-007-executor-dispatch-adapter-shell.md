# Implement Executor Dispatch Adapter Shell

## Metadata

### Source Plan / Request
Directly scoped task request in Codex chat on 2026-03-22 for a lightweight `executor-dispatch` adapter shell.

### Status
`done`

### Related Specs
- `20260322-004-task-spec-readiness-check.md`
- `20260322-005-validation-collect-foundation.md`
- `20260322-006-followup-suggester.md`

## Goal
Implement a lightweight `executor-dispatch` adapter shell that lets the runtime hand off a narrow, ready task spec to an external worker-plane executor without turning the runtime into a coding agent.

## In Scope
- define a minimal executor dispatch request and response model
- require a task spec that passes the shared `task-spec-readiness-check` gate before dispatch
- prepare a narrow handoff payload summary from the task spec rather than passing the whole repository context
- support exactly one safe shell-oriented adapter surface in this slice:
  - `preview` mode that shows the prepared handoff without executing anything
  - a minimal local shell echo path that proves dispatch plumbing without integrating Codex CLI or Claude Code
- return a structured dispatch result with:
  - executor target
  - dispatch status
  - handoff payload summary
  - execution mode metadata
- add a CLI path to exercise dispatch in a safe, non-heavy way
- add focused tests for readiness gating, request shaping, preview output, and minimal dispatch behavior
- update runtime docs only if dispatch boundary semantics become stable enough to describe

## Out of Scope
- deep Codex CLI integration
- deep Claude Code integration
- automatic code editing orchestration
- validation aggregation redesign
- write-back classification
- follow-up generation
- watcher, daemon, CI, or GitHub automation
- autonomy-platform behavior

## Affected Area
- `src/ai_engineering_runtime/artifacts.py`
- `src/ai_engineering_runtime/adapters.py`
- `src/ai_engineering_runtime/state.py`
- `src/ai_engineering_runtime/engine.py`
- `src/ai_engineering_runtime/nodes/*`
- `src/ai_engineering_runtime/cli.py`
- `tests/*`
- `docs/runtime/*`
- `README.md`

## Task Checklist
- [x] define a narrow executor dispatch request/response contract
- [x] gate dispatch on the shared task-spec readiness result instead of inventing a second eligibility check
- [x] implement a safe shell adapter with preview and minimal echo modes only
- [x] shape a narrow handoff payload from the task spec for external worker-plane use
- [x] add focused tests for non-ready rejection and ready dispatch behavior

## Done When
A contributor can exercise a minimal executor-dispatch command against a ready task spec, see the narrow handoff payload the control plane prepared, and optionally run a safe local echo dispatch path without the runtime trying to execute the task itself.

## Validation

### Black-box Checks
- reject dispatch for a non-ready task spec
- accept preview dispatch for a ready task spec
- accept the minimal local echo dispatch path for a ready task spec
- verify structured dispatch output is stable
- run unit tests successfully

### White-box Needed
Yes

### White-box Trigger
This slice introduces the first control-plane to worker-plane handoff boundary. Black-box checks alone will not reliably protect readiness gating, handoff shaping, or the rule that this runtime coordinates work instead of executing it.

### Internal Logic To Protect
- dispatch eligibility checks
- request shaping from task-spec fields
- stable dispatch result formatting
- preservation of control-plane vs worker-plane boundaries

## Write-back Needed
Yes, but keep it narrow by updating runtime docs only if the dispatch boundary semantics become stable. Do not add broad executor integration details into facts.

## Risks / Notes
- avoid turning this slice into full executor integration
- keep adapter behavior minimal and exercised
- preserve the principle that the runtime coordinates but does not replace external executors
- do not overbuild abstraction layers that are not used by this shell slice
- Black-box validation completed with `python -m unittest discover -s tests -v` and `$env:PYTHONPATH='src'; python -m ai_engineering_runtime executor-dispatch --spec docs/specs/20260322-007-executor-dispatch-adapter-shell.md --mode preview`
