# Project Scope

Use this fact for relatively stable scope, boundary, and assumption context.
Do not update it for routine task progress or every active-slice change.
Use `project/CURRENT.md` for live operating state when the repository uses a control surface.

## Project Target
Provide a lightweight execution and orchestration runtime that consumes SOP artifacts, determines workflow readiness, dispatches narrow executor work through explicit adapters, aggregates validation outcomes, and suggests write-back or follow-up actions without replacing the external executor.

## Stable Current Target
Keep the runtime as a narrow CLI-first control plane that can read plans and task specs, hand work to external executors through explicit boundaries, and materialize reviewable run, validation, write-back, and follow-up artifacts.

## Stable Phase Goal
Establish the lightweight CLI-first runtime foundation, ship concrete executable control-plane slices, and evolve executor dispatch from preview plumbing into an adapter-backed handoff boundary that can integrate with external worker-plane executors.

## In Scope
- lightweight repository alignment from SOP starter to runtime project
- runtime-specific design docs for architecture, protocol, state machine, and roadmap
- a stdlib-only Python CLI/runtime package
- artifact discovery and Markdown parsing for runtime-consumed artifacts
- state model definitions and run/result logging scaffolding
- executor adapter contracts, capability gating, and normalized execution results
- concrete executable nodes across readiness, dispatch, validation, write-back, follow-up, replay, and packaging slices
- `unittest` coverage for the current implemented runtime slice

## Out of Scope
- redefining the SOP itself as a new methodology
- replacing Claude Code, Codex CLI, or other coding agents
- turning the runtime into a replacement coding agent or full autonomy platform
- dashboards, web UI, daemon services, PR automation, or merge automation
- broad framework work that is not exercised by the first runtime slice

## Key Constraints
- the copied SOP starter remains the canonical operating model for this repository
- runtime code should depend on artifact/protocol contracts, not tightly on copied-starter implementation details

- this pass must stay lightweight, CLI-first, and runtime-focused
- design artifacts should be specific enough to guide implementation but narrow enough to avoid framework sprawl

## Current Assumptions
- Markdown artifacts in the repository remain the source of truth for runtime-consumed plans and task specs
- a plan or roadmap can be compiled into a narrow task spec through a heading-based contract
- external executors should sit behind narrow adapter contracts so the runtime remains the control plane
- Python 3.11+ is the intended implementation language when local tooling is available
- write-back should stay disciplined and limited to stable reusable context

## Open Risks
- the initial Markdown contract may be too loose or too rigid if not exercised quickly
- the local environment may not yet have Python available for black-box validation
- runtime docs and the executable contract could drift if the first slice is not kept narrow
