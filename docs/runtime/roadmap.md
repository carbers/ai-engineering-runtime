# Runtime Roadmap

## Problem
This repository was initialized from the `ai-engineering-sop` starter and still mostly reflects starter identity. It does not yet provide a concrete runtime layer that can consume SOP artifacts and turn them into executable workflow steps.

## Goal
Establish a real Phase 0 / Phase 1 foundation for `ai-engineering-runtime`: align the repository with its runtime identity, land the minimum durable design package, and implement one narrow CLI slice that compiles a plan into a task spec.

## Non-goals
- redefine the SOP as a second methodology
- replace Claude Code, Codex CLI, or other coding agents
- build a dashboard, web UI, daemon service, or web product
- implement full autonomy, PR automation, or merge automation
- add broad abstractions that are not exercised by the first slice

## Constraints
- keep the copied SOP starter as the canonical development operating model
- keep the repository lightweight, CLI-first, and runtime-focused
- prefer runtime code that depends on artifact/protocol contracts rather than copied-starter implementation details
- make the first slice real and executable instead of landing empty scaffolding
- stay stdlib-only for the initial Python runtime implementation

## Proposed Approach
Add a small runtime design package under `docs/runtime/`, minimally refine starter files that are inaccurate for this project, and implement a stdlib-only Python CLI around a single real node, `plan-to-spec`. Dogfood the runtime by compiling this roadmap into the current implementation spec in `docs/specs/`.

## Risks
- the local environment may not yet have Python available for black-box validation
- the initial Markdown contract could become either too loose or too rigid if the slice is not exercised quickly
- a broader orchestration design could distract from landing a small coherent executable slice

## Phase Split
- Phase 0: align repository identity and establish runtime design artifacts
- Phase 1: implement `plan-to-spec`, run logging, and test scaffolding
- Phase 2: add readiness checks and executor dispatch adapters
- Phase 3: collect validation results and generate write-back or follow-up suggestions

## First Slice
The first reviewable slice is a runtime foundation centered on compiling a durable plan into a narrow task spec.

### Spec Title
Runtime Plan To Spec Foundation

### In Scope
- align the repository with its runtime identity while preserving the copied SOP operating model
- add runtime design artifacts for architecture, protocol, state machine, and roadmap
- add a stdlib-only Python package with protocol, state, engine, adapter, node, and CLI layers
- implement Markdown artifact discovery and plan parsing for the runtime contract
- implement the `plan-to-spec` node and JSON run logging
- add `unittest` coverage for the first implemented slice

### Out of Scope
- readiness-check, executor dispatch, validation collection, and write-back suggestion commands
- dashboards, web UI, daemon services, PR automation, or merge automation
- generalized plugin systems or abstractions not exercised by `plan-to-spec`

### Affected Area
- `README.md`
- `AGENTS.md`
- `docs/facts/project-scope.md`
- `docs/runtime/*`
- `docs/templates/plan-template.md`
- `skills/plan-to-spec.md`
- `pyproject.toml`
- `src/ai_engineering_runtime/*`
- `tests/*`

### Task Checklist
- align repository-facing docs with the runtime identity
- add runtime architecture, protocol, state-machine, and roadmap documents
- implement artifact discovery, Markdown parsing, and workflow-state models
- implement the `plan-to-spec` node, CLI entrypoint, and JSON run logging
- dogfood the roadmap into a real task spec in `docs/specs/`
- add black-box and white-box `unittest` coverage for the slice

### Done When
A contributor can use `ae-runtime plan-to-spec --plan docs/runtime/roadmap.md` to compile this roadmap into a draft task spec and JSON run log, and the repository clearly reads as a lightweight runtime layered on top of the copied SOP starter.

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

### Write-back Needed
Yes - keep `docs/facts/project-scope.md` aligned with the stable current phase and boundary language clarified by this slice.

### Risks / Notes
- keep the parser limited to the documented heading-based contract
- local black-box validation may need to wait until Python 3.11+ is available in the environment
