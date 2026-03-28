# Product Control Plane Upgrade

## Metadata

### Source Plan / Request
`2026-03-28 productization upgrade request`

### Status
`done`

### Related Specs
- 20260327-002-executor-run-poll-resume-lifecycle

## Goal
Upgrade the runtime from a node-oriented kernel into a product-oriented control plane that can consume chat/prompt/handoff input directly, compile normalized handoffs, evaluate structured next-step decisions, route executors by workflow node, and run a minimal review-repair-closeout loop.

## In Scope
- add a validated handoff schema and compiler
- add workflow definitions for `repo-coding-task` and `chat-to-execution`
- add lane, artifact, gate, readiness, and advance-decision models
- add product CLI commands for run, compile-handoff, validate-handoff, inspect, resume, retry, and close
- add minimal retry, fallback, and review-repair loop logic
- add acceptance-oriented tests including the JX3 case

## Out of Scope
- distributed orchestration
- remote queueing or dashboard UI
- live Codex backend integration beyond the existing adapter seam

## Affected Area
- `src/ai_engineering_runtime/cli.py`
- `src/ai_engineering_runtime/handoffs.py`
- `src/ai_engineering_runtime/product_runtime.py`
- `src/ai_engineering_runtime/state.py`
- `src/ai_engineering_runtime/adapters.py`
- `tests/test_product_cli.py`

## Task Checklist
- [x] compile natural-language input into a validated handoff artifact
- [x] materialize workflow, lane, gate, readiness, and next-step models
- [x] route node execution through capability-matched executors with fallback
- [x] hold instead of auto-advancing when approval or review is required
- [x] close the minimal review-repair loop with retry and closeout commands
- [x] cover the new path with CLI-level tests

## Done When
The runtime can start from chat/prompt/handoff without a handwritten handoff, emit an explicit hold-or-dispatch next-step decision, keep parked lanes out of default advancement, and drive a minimal review finding into retry/repair/closeout through the product CLI.

## Validation

### Black-box Checks
- `python -m unittest tests.test_product_cli -v`
- `python -m unittest tests.test_cli tests.test_executor_dispatch tests.test_executor_run_lifecycle tests.test_integration_workflows -v`

### White-box Needed
Yes

### White-box Trigger
The new control-plane layer encodes workflow policy, artifact categorization, gate semantics, retry selection, and lane-aware next-step behavior.

### Internal Logic To Protect
- handoff normalization and validation
- execution readiness and auto-advance refusal
- review finding to repair-dispatch transition

## Write-back Needed
Yes. Update the root README and record a task-local change summary.

## Risks / Notes
- the product run layer is intentionally local and file-backed; it is not a distributed scheduler
- the coding and review executors are still mockable adapter paths, not live worker integrations
