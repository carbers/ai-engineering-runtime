# Change Summary

## What Changed
Synchronized the copied SOP layer in this repository with the latest stable starter guidance while preserving runtime-specific docs under `ai/doc/runtime/*`.
Added the missing phase-aware guides, example specs, control-surface assets, closeout skill, and updated templates, rules, and entrypoint docs to the current SOP model.

## Scope Completed
- updated repository entrypoint guidance in `AGENTS.md`, `README.md`, and `CLAUDE.md`
- added `ai/README.md` as the docs-layer namespace map
- added `project/*` as the minimal human-facing control surface
- synced reusable SOP guides, templates, specs guidance, skills, and Cursor rules
- aligned `ai/doc/facts/project-scope.md` and `ai/doc/facts/facts-index.md` with the newer scope/control-surface model

## Validation Run

### Black-box
- `python -m unittest discover -s tests -v`
- `$env:PYTHONPATH='src'; python -m ai_engineering_runtime plan-readiness-check --plan ai/doc/runtime/roadmap.md`
- `rg -n "ai/|ai\\|`ai|ai\\*" AGENTS.md README.md CLAUDE.md docs skills project .cursor`

### White-box
Not needed. This slice updated repository guidance and workflow artifacts rather than internal runtime logic.

## Regression Path Protected
The copied SOP layer now carries explicit guidance for phase-aware planning, escalation, release sensitivity, control-surface closeout, and index/registry maintenance without changing the runtime execution code path.

## Release-Sensitive Notes
None. This was a documentation and workflow-layer sync only.

## Facts / Skills Updated
- updated `ai/doc/facts/project-scope.md`
- updated `ai/doc/facts/facts-index.md`
- added `ai/skill/session-closeout.md`
- updated `ai/skill/skill-registry.md`

## Remaining Gaps
- runtime-specific docs may still mention older copied-starter terminology where that wording is historical rather than normative
- future SOP starter changes will still need deliberate path adaptation because this repo uses `ai/doc/*` and `ai/skill/*` instead of the starter's `ai/*` layout
