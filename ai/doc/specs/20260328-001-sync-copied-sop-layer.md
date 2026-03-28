# Task Spec

Keep this document narrow. Reference the parent context when needed instead of restating it.
Store task specs in `ai/doc/specs/` and name them `YYYYMMDD-NNN-task-slug.md`.

## Summary

### Source Context
User request to sync the latest copied SOP guidance from `D:\github\ai-engineering-sop` back into this runtime repository while preserving runtime-specific docs and implementation layers.

### Parent Phase
Documentation and workflow alignment for the copied SOP layer inside the runtime repository.

### Parent Plan
None. This is a directly scoped documentation and workflow sync slice.

### Status
`done`

### Related Specs
Optional. Link sibling, prerequisite, or follow-up specs when that helps navigation.

### Goal
Update the copied SOP assets in this repository so they reflect the latest stable workflow guidance from the source SOP starter without overwriting runtime-specific architecture, protocol, roadmap, or implementation docs.

## Scope

### In Scope
- sync reusable SOP guides, templates, cursor rules, and skills that are still applicable in this repo
- add any missing control-surface assets that now belong in copied projects
- update repository entrypoint guidance so it reflects the current SOP model and the runtime repo's adapted structure

### Out of Scope
- rewriting runtime-specific docs under `ai/doc/runtime/*`
- changing runtime implementation code under `src/ai_engineering_runtime/*`
- copying task-local or source-repo-specific change specs from `ai-engineering-sop`

## Phase-Aware Contract

## Inputs
- current runtime repository guidance and copied SOP assets
- latest stable SOP assets from `D:\github\ai-engineering-sop`

## Expected Outputs
- synced SOP-facing docs and skills under `ai/doc/*`, `ai/skill/*`, and `.cursor/rules/*`
- a minimal root `project/*` control surface adapted to this runtime repo if still applicable
- updated repository entrypoint guidance that keeps runtime-specific boundaries intact

## Constraints
- keep changes narrow and reviewable
- preserve runtime-specific repo purpose and runtime-layer boundaries
- adapt source paths from `ai/doc/*` and `ai/skill/*` to this repo's `ai/doc/*` and `ai/skill/*` layout

## Validation

### Black-box Checks
- repo guidance files exist at the expected adapted paths
- synced docs reference `ai/doc/*`, `ai/skill/*`, and `project/*` consistently instead of `ai/doc/*` or `ai/skill/*`
- runtime-specific files under `ai/doc/runtime/*` remain unchanged

### White-box Needed
No

### Write-back Needed
No additional fact write-back beyond the synced SOP layer itself.

## Risks / Notes
- the source SOP repo includes starter-internal artifacts that should not be copied verbatim into this runtime repo
- newer SOP control-surface guidance must be adapted to this repo's existing `ai/doc/*` layout rather than forcing the `ai/*` namespace model
