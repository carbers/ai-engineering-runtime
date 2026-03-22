# Implement Node IO Contract And Dependency Declarations

## Metadata

### Source Plan / Request
Directly scoped phase request in Codex chat on 2026-03-23 to continue the post-summary control-plane chain with artifact refs, node contracts, gate evaluation, validation rollups, and package builders.

### Status
`done`

### Related Specs
- `20260322-013-artifact-reference-resolution.md`
- `20260322-015-eligibility-gate-evaluator.md`
- `20260322-016-validation-rollup-policy.md`
- `20260322-017-writeback-package-builder.md`
- `20260322-018-followup-package-builder.md`

## Goal
Implement one explicit declaration layer for node inputs, outputs, dependencies, and produced signals so orchestration-oriented code can inspect stable node contracts instead of relying on scattered implicit knowledge.

## In Scope
- define a small static `NodeContract` model that declares:
  - required artifact-ref kinds
  - required signals
  - optional any-of signal groups
  - produced artifact-ref kinds
  - produced signals
  - applicable terminal statuses when needed
- add a lightweight registry for the current implemented node set:
  - `plan-readiness-check`
  - `plan-to-spec`
  - `task-spec-readiness-check`
  - `validation-collect`
  - `writeback-classifier`
  - `followup-suggester`
  - `executor-dispatch`
  - `result-log-replay`
  - `run-history-select`
  - `run-summary`
  - `validation-rollup`
  - `writeback-package`
  - `followup-package`
- keep contracts as static Python declarations rather than decorators, reflection, or plugin registration
- expose lookup helpers for later gate-evaluation logic
- add focused tests for registry coverage and selected contract fields

## Out of Scope
- dynamic DAG execution
- plugin systems
- scheduler or watcher behavior
- rewriting existing node implementations around a new base class
- deep executor integration
- a dedicated node-contract inspection CLI

## Affected Area
- `src/ai_engineering_runtime/node_contracts.py`
- `src/ai_engineering_runtime/artifact_refs.py`
- `src/ai_engineering_runtime/gate_evaluator.py`
- `tests/test_node_contracts.py`

## Task Checklist
- [ ] define the lightweight node-contract and dependency-declaration model
- [ ] register the current implemented node set with explicit input/output and signal declarations
- [ ] expose lookup helpers for later gate evaluation without changing node execution behavior
- [ ] add focused unit coverage for registry shape and contract lookup

## Done When
Runtime code can look up a stable contract declaration for the current implemented node set and inspect required artifacts, required signals, produced artifacts, and produced signals without reading node bodies.

## Validation

### Black-box Checks
- retrieve a declared contract for core nodes such as `validation-collect`, `run-summary`, and `writeback-package`
- verify contract declarations cover the expected current node set
- run `python -m unittest tests.test_node_contracts -v`

### White-box Needed
Yes

### White-box Trigger
This slice creates a new static contract layer used by later gate logic. Black-box checks alone will not reliably protect contract-field shape, registry completeness, or required-signal semantics.

### Internal Logic To Protect
- node-contract registry coverage
- contract field normalization
- required-all versus required-any signal declaration shape
- produced artifact and signal declarations

## Write-back Needed
Yes - update `docs/runtime/protocol.md` only if the declaration layer becomes stable enough to describe.

## Risks / Notes
### Implementation Shape
Keep declarations static and narrow. Do not build a reflective registration framework or require every node to subclass a new contract-aware base type.

### Node / Data Contract Impact
This slice adds inspectable node metadata for current nodes only. It should not change existing node IO behavior directly.

### CLI Impact
No dedicated CLI command in this slice.

### Split / Defer
Create a follow-on spec before implementation if work expands to runtime plugin registration, dynamic DAG planning, or node-class rewrites.
