# ai-engineering-runtime

`ai-engineering-runtime` is a lightweight, CLI-first workflow runtime built on top of the copied `ai-engineering-sop` starter in this repository.

The copied SOP remains the operating model for how this repository is planned, specified, implemented, validated, and written back. The runtime exists to consume those artifacts and turn them into narrow executable workflow steps.

## What this repository is for

This repository establishes a practical runtime layer that can:

1. discover SOP artifacts such as plans, task specs, facts, skills, and summaries
2. determine workflow readiness and state
3. compile plans into narrow executable task specs
4. dispatch work to external executors or adapters
5. collect validation results
6. suggest write-back and follow-up work

The current implementation is intentionally smaller than that full direction: one stdlib-only Python CLI, two real nodes, and one documented contract for checking plan readiness and compiling a plan into a narrow draft task spec.

## What stays the same

The copied SOP starter is still the canonical development model for this repo:

1. start from a plan or phase slice
2. derive or refine one or more narrow task specs
3. implement narrowly
4. validate explicitly
5. write back only stable facts
6. promote repeated workflows into skills when they stabilize

See `AGENTS.md` for the full repository rules.

## Repository layout

- `AGENTS.md`
  Canonical repository guidance. The copied SOP still governs how this repo is developed.

- `docs/runtime/*`
  Runtime-specific design artifacts: architecture, protocol, state machine, and roadmap.

- `docs/specs/*`
  Narrow execution contracts, including specs produced by the runtime.

- `docs/facts/*`
  Stable reusable project context.

- `docs/guides/*`, `docs/templates/*`, `skills/*`
  The copied SOP starter materials that this runtime consumes and dogfoods.

- `src/ai_engineering_runtime/*`
  The runtime CLI and internal layers.

- `tests/*`
  `unittest` coverage for the implemented runtime slice.

## Implemented commands

The current executable slice is:

```text
ae-runtime plan-readiness-check --plan docs/runtime/roadmap.md
ae-runtime plan-to-spec --plan docs/runtime/roadmap.md
```

Use `plan-readiness-check` to inspect a plan artifact and return a structured readiness outcome with stable reason codes.

Use `plan-to-spec --dry-run` to preview the generated spec and readiness outcome without writing a spec file.
Omit `--dry-run` to write the next dated spec under `docs/specs/`.

These commands currently:

- parse a roadmap or plan artifact from Markdown
- classify plan readiness as `ready`, `needs_clarification`, or `blocked`
- return stable reason codes and messages for non-ready outcomes
- render a narrow draft task spec only when readiness is `ready`
- write a JSON run log under `.runtime/runs/`

## What this repository is not

This repository is not:

- a replacement for the SOP itself
- a replacement for Claude Code or Codex CLI
- a dashboard or web product
- a full autonomy, PR automation, or merge automation platform

## Where to look next

1. read `AGENTS.md`
2. read `docs/runtime/architecture.md`
3. read `docs/runtime/roadmap.md`
4. read `docs/specs/20260322-002-runtime-plan-readiness-check.md`
5. run `ae-runtime plan-readiness-check --plan docs/runtime/roadmap.md` once Python 3.11+ is available locally
