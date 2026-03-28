# CURRENT

## Current phase
Operate and extend the lightweight CLI-first runtime while keeping the copied SOP layer and recovery surface current.

## Current target
Preserve the `runtime = control plane` boundary, keep external executor handoff explicit, and maintain the copied SOP assets as the canonical working model for this repository.

## Active slice
Operate the CLI-first runtime while keeping the copied SOP layer aligned under `ai/*` and the human recovery surface current.

## In scope now
- keep runtime-specific design docs under `ai/doc/runtime/*`
- keep copied SOP guides, templates, specs, facts, and skills aligned under `ai/*` with the latest stable starter guidance
- use `project/CURRENT.md` and `project/DOC_MAP.md` as the human recovery entrypoints
- keep release sensitivity, escalation, and closeout guidance lightweight and reviewable

## Out of scope now
- dashboards, web UI, or broad reporting systems
- turning `project/*` into a project board or task log
- replacing external executors with local full-autonomy behavior
- broad framework work outside the current runtime slice

## Current source of truth
- `project/DOC_MAP.md`
- `README.md`
- `AGENTS.md`
- `ai/README.md`
- `ai/doc/runtime/roadmap.md`
- `ai/doc/facts/project-scope.md`
- the current active task spec in `ai/doc/specs/*`, if implementation work is underway

## Frozen decisions
- this repository remains a lightweight, CLI-first runtime rather than a dashboard or broad automation platform
- the copied SOP layer remains the canonical operating model for how the runtime repo is planned, specified, implemented, validated, and written back
- `project/*` is the default human-facing control surface when current state or durable decisions need quick recovery
- runtime-specific design artifacts stay under `ai/doc/runtime/*`

## Latest experiment
None yet.

## Next 3 actions
1. Keep `project/CURRENT.md` and `project/DOC_MAP.md` short as later runtime slices land.
2. Use `ai/skill/session-closeout.md` when future slices may affect current state, decisions, experiments, facts, or skills.
3. Extend runtime behavior through narrow specs without weakening the control-plane boundary.

## Risks to watch
- `project/CURRENT.md` could drift into task-by-task reporting instead of staying recovery-focused
- copied SOP docs could drift from runtime-specific usage if the `ai/*` namespace boundary is not kept current
- release sensitivity or escalation fields could become boilerplate instead of being used only when they add clarity
