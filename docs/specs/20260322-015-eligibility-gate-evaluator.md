# Implement Eligibility Gate Evaluator

## Metadata

### Source Plan / Request
Directly scoped phase request in Codex chat on 2026-03-23 to continue the post-summary control-plane chain with artifact refs, node contracts, gate evaluation, validation rollups, and package builders.

### Status
`done`

### Related Specs
- `20260322-013-artifact-reference-resolution.md`
- `20260322-014-node-io-contract-and-dependency-declarations.md`
- `20260322-016-validation-rollup-policy.md`
- `20260322-017-writeback-package-builder.md`
- `20260322-018-followup-package-builder.md`

## Goal
Implement one explicit gate-evaluation service that decides whether a declared node is eligible, blocked, skipped, not-applicable, or unknown for one current run context without turning the runtime into a workflow engine.

## In Scope
- define a small `GateResult` contract with:
  - gate status
  - blocking reasons
  - advisory reasons
  - evaluated node name
- evaluate one node at a time from:
  - declared node contract
  - available artifact refs
  - available produced signals
  - current terminal status when present
- support skip detection when the node's primary produced artifact already exists for the same run context
- keep node-specific logic out of the evaluator by relying on contract declarations and simple generic rules
- add one thin CLI command `node-gate` for inspection by run id or latest run summary
- add focused tests for eligible, blocked, skipped, not-applicable, and unknown outcomes

## Out of Scope
- scheduling or DAG execution
- automatic retries
- autonomy or policy engines
- executor orchestration
- batch workflow planning across many nodes

## Affected Area
- `src/ai_engineering_runtime/gate_evaluator.py`
- `src/ai_engineering_runtime/node_contracts.py`
- `src/ai_engineering_runtime/run_summary.py`
- `src/ai_engineering_runtime/nodes/node_gate.py`
- `src/ai_engineering_runtime/cli.py`
- `tests/test_gate_evaluator.py`
- `tests/test_cli.py`

## Task Checklist
- [ ] define the gate-result model and generic evaluation rules over contracts, signals, refs, and terminal status
- [ ] support artifact-produced skip detection for package and summary builders
- [ ] expose a thin `node-gate` CLI query by run id or latest node summary
- [ ] add focused unit and CLI coverage for all supported gate outcomes

## Done When
A contributor can run `python -m ai_engineering_runtime node-gate --node writeback-package --run-id <timestamp-node>` and receive one stable gate result that explains whether the node is eligible, blocked, skipped, not-applicable, or unknown for that current run context.

## Validation

### Black-box Checks
- report `eligible` when declared required refs and signals are present
- report `blocked` when required refs or signals are missing
- report `skipped` when the node's produced package or summary already exists
- report `not_applicable` when terminal status is outside the contract's applicable set
- report `unknown` for undeclared nodes
- run `python -m unittest tests.test_gate_evaluator tests.test_cli -v`

### White-box Needed
Yes

### White-box Trigger
This slice adds decision logic over multiple normalized inputs. Black-box checks alone will not reliably protect required-ref checks, any-of signal handling, or skip detection.

### Internal Logic To Protect
- required-all and required-any dependency checks
- terminal-status applicability checks
- produced-artifact skip detection
- separation of blocking versus advisory reasons

## Write-back Needed
Yes - update `docs/runtime/protocol.md` and `README.md` only if the gate query surface stabilizes during implementation.

## Risks / Notes
### Implementation Shape
Keep this evaluator generic and contract-driven. Do not encode node business logic or execution branching tables directly in the evaluator.

### State / Data Contract Impact
This slice adds one generic gate result contract for single-node evaluation against current normalized run context.

### CLI Impact
Add one thin `node-gate` inspection command. Do not expand it into a multi-node planning interface.

### Split / Defer
Create a follow-on spec before implementation if work expands to DAG planning, scheduling, or automatic next-node selection across the whole runtime.
