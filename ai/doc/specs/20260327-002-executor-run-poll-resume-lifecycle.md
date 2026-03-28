# Implement Executor Run Poll And Resume Lifecycle

## Metadata

### Source Plan / Request
Directly scoped follow-up request in Copilot chat on 2026-03-27 to continue under the repository SPEC workflow after local-review fixes and a product-shape review.

### Status
`done`

### Related Specs
- `20260327-001-executor-adapter-codex-v1.md`
- `20260322-008-result-log-ingestion-replay.md`
- `20260322-012-run-summary-materialization.md`
- `20260322-005-validation-collect-foundation.md`

## Goal
Add a narrow control-plane lifecycle step for previously submitted executor runs so the runtime can revisit one in-flight run, poll or resume it through the adapter contract, capture a terminal normalized execution result when available, and make the path from `executing` to later validation reviewable instead of one-shot.

## In Scope
- define the smallest stable way to identify and revisit one previously submitted executor run from runtime artifacts
- add one narrow node/CLI path that can poll or resume a prior executor run without redispatching the original task
- reuse the existing executor adapter contract for run-status polling, collection, and normalization rather than inventing a second execution model
- preserve explicit separation between `running`, `succeeded`, `failed`, and `blocked` execution outcomes
- emit concrete structured reasons when the selected run cannot be resumed, is missing required handle data, or uses an adapter that does not support the requested lifecycle operation
- persist updated execution-state information in run logs strongly enough that summary/history consumers can read it safely
- add focused unit and CLI tests for running and terminal lifecycle paths

## Out of Scope
- wiring Codex v1 to a mandatory live backend in every environment
- background daemons, queues, schedulers, or automatic repeated polling loops
- automatic transition into `validation-collect` without an explicit operator action
- multi-run orchestration, fleet management, or cross-run dashboards
- broad redesign of run-summary, history-selection, or follow-up packaging beyond what this lifecycle slice strictly needs

## Affected Area
- `src/ai_engineering_runtime/adapters.py`
- `src/ai_engineering_runtime/state.py`
- `src/ai_engineering_runtime/cli.py`
- `src/ai_engineering_runtime/run_logs.py`
- `src/ai_engineering_runtime/run_summary.py`
- `src/ai_engineering_runtime/history_selection.py`
- `src/ai_engineering_runtime/nodes/executor_dispatch.py`
- `src/ai_engineering_runtime/nodes/*` for the new executor-run lifecycle node
- `tests/test_executor_dispatch.py`
- `tests/test_cli.py`
- `tests/test_result_log_replay.py`
- `tests/test_run_summary.py`

## Task Checklist
- [ ] define the artifact/query contract for selecting one previously dispatched executor run
- [ ] implement a narrow executor-run lifecycle node and CLI entrypoint for poll or resume behavior
- [ ] preserve normalized execution-state updates for both non-terminal and terminal outcomes
- [ ] surface stable rejection reasons for missing handle data and unsupported resume capabilities
- [ ] add focused tests for running, terminal-success, terminal-failure, and invalid-selection paths
- [ ] update protocol and state-machine docs only where the lifecycle behavior becomes stable in code

## Done When
An operator can explicitly revisit one previously dispatched executor run through the runtime, receive a normalized `running` or terminal execution result without redispatching the original task, and inspect run logs/CLI output that make the post-submit lifecycle reviewable and safe for later validation handling.

## Validation

### Black-box Checks
- a previously dispatched executor run can be selected and polled without creating a second dispatch
- a still-running executor run remains `executing` and reports a normalized running execution result
- a terminal executor run produces a normalized terminal execution result through the lifecycle path
- missing or invalid executor run selection is rejected with stable reason codes
- CLI output and persisted run logs expose the updated lifecycle result clearly
- targeted unit tests pass

### White-box Needed
Yes

### White-box Trigger
This slice crosses adapter contracts, run-log identity, lifecycle-state transitions, and replay/summary consumers. The main risk is not UI behavior alone but silently corrupting the execution lifecycle record or allowing redispatch where only revisit/poll should happen.

### Internal Logic To Protect
- prior-run selection and handle recovery
- adapter lifecycle branching between `poll`, `collect`, `normalize`, and any resume-specific path
- transition behavior from `executing` to later terminal outcomes
- preservation of execution schema compatibility for replay/history/summary consumers

## Write-back Needed
Yes. Update runtime protocol and state-machine docs if the lifecycle command name, status semantics, and artifact contract stabilize. Avoid writing speculative backend details into facts.

## Risks / Notes
- keep the lifecycle path explicit and operator-invoked; do not smuggle in autonomous polling
- avoid overloading `executor-dispatch` if a separate lifecycle node produces a clearer contract
- make sure running-state revisits do not fabricate validation readiness before terminal evidence exists
- preserve compatibility with existing mock-backed adapter tests while leaving room for later real backend hookup
- Black-box validation completed with `python -m unittest tests.test_executor_run_lifecycle tests.test_executor_dispatch tests.test_cli`, `python -m unittest tests.test_result_log_replay tests.test_history_selection tests.test_run_summary`, and `python -m unittest discover -s tests`
