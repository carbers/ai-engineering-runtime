# Implement Executor Adapter Contract And Codex Adapter V1

## Metadata

### Source Plan / Request
Directly scoped task request in Copilot chat on 2026-03-27 for a control-plane executor adapter evolution that remains compatible with the existing runtime workflow.

### Status
`done`

### Related Specs
- `20260322-007-executor-dispatch-adapter-shell.md`
- `20260322-006-followup-suggester.md`
- `20260322-018-followup-package-builder.md`

## Goal
Evolve the runtime from a preview-oriented executor-dispatch shell into a worker-plane-capable control plane with a vendor-neutral executor adapter contract, a minimal Codex adapter v1, capability gating, and normalized execution outputs that can feed later review-repair-validation loops.

## In Scope
- define a vendor-neutral executor adapter contract for prepare, dispatch, poll, collect, and normalize/materialize stages
- define a stable executor capability model and a minimal compatibility gate between task requirements and adapter capabilities
- add a standardized execution-result model that records executor metadata, dispatch summary, final outcome, output references, validation claims, caveats, and follow-up hints
- evolve the existing `executor-dispatch` node to select and invoke adapters instead of hard-coding a shell echo path
- keep preview mode as a first-class control-plane path
- implement a minimal Codex adapter v1 with a mockable backend and a real-backend extension seam
- preserve the existing shell adapter as a lightweight local adapter
- add structured finding normalization and follow-up derivation inputs so execution output can be consumed by later review/follow-up logic
- update runtime docs and tests for the new dispatch contract

## Out of Scope
- full autonomous review-repair-validate orchestration
- multi-executor scheduling or queueing
- mandatory live Codex CLI execution in every environment
- write-back automation
- automatic git commit or branch management
- distributed execution infrastructure

## Affected Area
- `src/ai_engineering_runtime/adapters.py`
- `src/ai_engineering_runtime/state.py`
- `src/ai_engineering_runtime/engine.py`
- `src/ai_engineering_runtime/nodes/executor_dispatch.py`
- `src/ai_engineering_runtime/cli.py`
- `src/ai_engineering_runtime/followup_package.py`
- `src/ai_engineering_runtime/artifact_refs.py`
- `tests/test_executor_dispatch.py`
- `tests/test_cli.py`
- `tests/test_followup_package.py`
- `docs/runtime/protocol.md`
- `docs/runtime/architecture.md`
- `docs/runtime/state-machine.md`
- `README.md`

## Task Checklist
- [x] add the executor adapter contract and capability model
- [x] add a standardized execution-result and finding-normalization model
- [x] wire `executor-dispatch` through adapter selection and compatibility gating
- [x] implement shell adapter compatibility through the new contract
- [x] implement Codex adapter v1 with a mockable backend and normalized execution result
- [x] expose the new dispatch path through the CLI without breaking preview mode
- [x] connect execution-result follow-up inputs to at least one later review artifact path
- [x] add focused unit and CLI tests
- [x] update runtime docs and repository entrypoint text

## Done When
The runtime can prepare and dispatch a ready task spec through a vendor-neutral adapter contract, reject incompatible tasks with structured capability reasons, run a minimal Codex adapter v1 path with normalized execution output, and persist enough structured execution detail for later follow-up and review packaging.

## Validation

### Black-box Checks
- preview dispatch still works for a ready task spec
- incompatible capability requirements are rejected with stable reason codes
- the shell adapter still supports the existing safe local dispatch proof path
- the Codex adapter v1 can run through a mock backend and return a normalized execution result
- CLI output and run logs include the new executor/execution information
- targeted unit tests pass

### White-box Needed
Yes

### White-box Trigger
This slice adds a cross-layer contract between runtime dispatch, adapter capability gating, normalized execution output, and later follow-up consumption. These boundaries are regression-sensitive and not fully protected by black-box assertions alone.

### Internal Logic To Protect
- adapter selection and capability gating
- task requirement parsing and normalization
- dispatch payload shaping and execution-result normalization
- preservation of the control-plane versus worker-plane boundary
- follow-up signal derivation from normalized execution findings

## Write-back Needed
Yes. Update the runtime architecture, protocol, state-machine, and README docs when the contract names and behavior stabilize in code. Avoid adding transient backend details to facts.

## Risks / Notes
- keep Codex-specific details behind the adapter boundary
- avoid introducing a large registry or plugin framework that only one adapter uses
- preserve existing run-log and summary compatibility where practical
- make the mock path realistic enough that later real-backend hookup does not require redesigning the contract
- Black-box validation completed with `python -m unittest tests.test_executor_dispatch tests.test_cli tests.test_followup_package -v`, `python -m unittest discover -s tests -v`, and `$env:PYTHONPATH='src'; python -m ai_engineering_runtime executor-dispatch --spec docs/specs/20260327-001-executor-adapter-codex-v1.md --executor codex --mode submit`