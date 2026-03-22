# Project Scope

## Current Phase Goal
Establish a Phase 0 / Phase 1 foundation for `ai-engineering-runtime` by aligning the copied SOP starter with the runtime identity, landing the minimum real design artifacts, and shipping one concrete CLI slice for `plan-to-spec`.

## In Scope
- lightweight repository alignment from SOP starter to runtime project
- runtime-specific design docs for architecture, protocol, state machine, and roadmap
- a stdlib-only Python CLI/runtime package
- artifact discovery and Markdown parsing for runtime-consumed artifacts
- state model definitions and run/result logging scaffolding
- one real executable node: `plan-to-spec`
- initial `unittest` coverage for the first runtime slice

## Out of Scope
- redefining the SOP itself as a new methodology
- replacing Claude Code, Codex CLI, or other coding agents
- readiness-check, executor dispatch, validation collection, or write-back suggestion commands beyond basic design documentation
- dashboards, web UI, daemon services, PR automation, or merge automation
- broad framework work that is not exercised by the first runtime slice

## Key Constraints
- the copied SOP starter remains the canonical operating model for this repository
- runtime code should depend on artifact/protocol contracts, not tightly on copied-starter implementation details
- this pass must stay lightweight, CLI-first, and runtime-focused
- design artifacts should be specific enough to guide implementation but narrow enough to avoid framework sprawl

## Current Assumptions
- Markdown artifacts in the repository are the source of truth for the first runtime slice
- a plan or roadmap can be compiled into a narrow task spec through a heading-based contract
- external executors and adapters remain outside the first implemented runtime slice
- Python 3.11+ is the intended implementation language when local tooling is available
- write-back should stay disciplined and limited to stable reusable context

## Open Risks
- the initial Markdown contract may be too loose or too rigid if not exercised quickly
- the local environment may not yet have Python available for black-box validation
- runtime docs and the executable contract could drift if the first slice is not kept narrow
