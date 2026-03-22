# Runtime Plan To Spec Foundation

## Metadata

### Source Plan / Request
`docs/runtime/roadmap.md`

### Status
`done`

### Related Specs
None.

## Goal
Establish a real Phase 0 / Phase 1 foundation for `ai-engineering-runtime`: align the repository with its runtime identity, land the minimum durable design package, and implement one narrow CLI slice that compiles a plan into a task spec.

## In Scope
- align the repository with its runtime identity while preserving the copied SOP operating model
- add runtime design artifacts for architecture, protocol, state machine, and roadmap
- add a stdlib-only Python package with protocol, state, engine, adapter, node, and CLI layers
- implement Markdown artifact discovery and plan parsing for the runtime contract
- implement the `plan-to-spec` node and JSON run logging
- add `unittest` coverage for the first implemented slice

## Out of Scope
- readiness-check, executor dispatch, validation collection, and write-back suggestion commands
- dashboards, web UI, daemon services, PR automation, or merge automation
- generalized plugin systems or abstractions not exercised by `plan-to-spec`

## Affected Area
- `README.md`
- `AGENTS.md`
- `docs/facts/project-scope.md`
- `docs/runtime/*`
- `docs/templates/plan-template.md`
- `skills/plan-to-spec.md`
- `pyproject.toml`
- `src/ai_engineering_runtime/*`
- `tests/*`

## Task Checklist
- [x] align the repository-facing docs and runtime design package with the runtime identity
- [x] implement the `plan-to-spec` slice across protocol, state, engine, adapter, node, and CLI layers
- [x] dogfood the roadmap into a real task spec and add focused `unittest` coverage for the slice
- [x] run the required black-box validation in a Python-enabled local environment

## Done When
A contributor can use `ae-runtime plan-to-spec --plan docs/runtime/roadmap.md` to compile this roadmap into a draft task spec and JSON run log, and the repository clearly reads as a lightweight runtime layered on top of the copied SOP starter.

## Validation

### Black-box Checks
- compile `docs/runtime/roadmap.md` into the next dated task-spec path
- run with `--dry-run` and confirm the rendered spec is printed without creating the spec file
- remove a required `First Slice` field and confirm the node fails without writing a spec
- confirm a successful run writes a JSON run log under `.runtime/runs/`

### White-box Needed
Yes

### White-box Trigger
The first slice introduces stateful parsing and transition logic. Black-box checks alone will not reliably protect section-boundary parsing, same-day spec numbering, or the `planning` to `spec-ready` gate.

### Internal Logic To Protect
- top-level and nested Markdown heading parsing
- extraction of the `First Slice` contract fields
- same-day task-spec sequence selection
- `planning` -> `spec-ready` only when validation issues are empty

## Write-back Needed
Yes - keep `docs/facts/project-scope.md` aligned with the stable current phase and boundary language clarified by this slice.

## Risks / Notes
- keep the parser limited to the documented heading-based contract
- Black-box validation completed with Python 3.12.10 via `python -m unittest discover -s tests -v`, `python -m ai_engineering_runtime plan-to-spec --plan docs/runtime/roadmap.md --dry-run`, and a successful explicit-output `plan-to-spec` run
