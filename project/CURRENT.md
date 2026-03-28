# CURRENT

## Current phase
Phase 4 complete — the product-oriented runtime is now hardened for local daily dogfood with stronger intake preview, review-repair-closeout closure, and richer CLI observability.

## Current target
Use the runtime as a day-to-day control-plane workflow tool: compile chat and prompt intake predictably, route implementation and repair to Codex by default, route review through a review executor path, and close runs from the CLI without opening raw JSON.

## Active slice
No active implementation slice. The runtime is ready for daily local dogfood and for narrow extension through new specs.

## Implemented capability (as of 2026-03-28)

All 15 core control-plane nodes are complete and covered by `unittest`:

| Node | CLI command | Purpose |
|---|---|---|
| `plan-readiness-check` | `ae-runtime plan-readiness-check --plan <file>` | Classify a plan as ready / needs_clarification / blocked |
| `plan-to-spec` | `ae-runtime plan-to-spec --plan <file>` | Compile a ready plan into a dated draft task spec |
| `task-spec-readiness-check` | `ae-runtime task-spec-readiness-check --spec <file>` | Gate a task spec before executor handoff |
| `executor-dispatch` | `ae-runtime executor-dispatch --spec <file> --executor <shell\|codex> --mode <preview\|echo\|submit>` | Dispatch a ready spec to an executor adapter |
| `executor-run-lifecycle` | `ae-runtime executor-run-lifecycle --run-id <id> --action <poll\|resume>` | Poll or resume a previously submitted executor run |
| `validation-collect` | `ae-runtime validation-collect --spec <file> --command-status passed --black-box-status passed` | Aggregate validation evidence for a closeout |
| `writeback-classifier` | `ae-runtime writeback-classifier --text "..." --kind <workflow_pattern\|...>` | Classify a closeout item into facts/skills/summary/ignore |
| `followup-suggester` | `ae-runtime followup-suggester --validation-status passed` | Suggest next control-plane action from current signals |
| `result-log-replay` | `ae-runtime result-log-replay --latest --node <node>` | Normalize one prior run log for replay-oriented use |
| `run-history-select` | `ae-runtime run-history-select --spec <file> --node <node>` | Select replayable runs relevant to one artifact target |
| `run-summary` | `ae-runtime run-summary --latest --node <node>` | Materialize a stable summary from projected run history |
| `node-gate` | `ae-runtime node-gate --node <node> --run-id <id>` | Evaluate downstream node eligibility against the current state |
| `validation-rollup` | `ae-runtime validation-rollup --latest` | Roll up validation outcomes and write to `.runtime/rollups/` |
| `writeback-package` | `ae-runtime writeback-package --latest` | Build a write-back review package under `.runtime/packages/` |
| `followup-package` | `ae-runtime followup-package --latest` | Build a follow-up review package under `.runtime/packages/` |

Executor adapters: `shell` (preview + echo), `codex` (mock-backed submit; real backend seam present but not wired to live CLI), plus a product-runtime review executor route used for normalized review findings and repair-loop closure.

## In scope now
- operating the runtime as the CLI-first control plane for day-to-day SOP workflow work
- previewing handoff compilation and candidate actions before dispatch
- using inspect / retry / resume / close as the primary run-management surface
- creating narrow task specs for new extension slices under `ai/doc/specs/`
- keeping `ai/*` SOP docs aligned as the upstream starter evolves
- wiring the Codex adapter backend seam to a live Codex CLI when that need arises

## Out of scope now
- dashboards, web UI, or broad reporting systems
- replacing external executors with local full-autonomy behavior
- broad framework work not justified by a current execution need

## Current source of truth
- `project/DOC_MAP.md`
- `README.md`
- `AGENTS.md`
- `ai/README.md`
- `ai/doc/runtime/roadmap.md`
- `ai/doc/facts/project-scope.md`

## Frozen decisions
- this repository remains a lightweight, CLI-first runtime rather than a dashboard or broad automation platform
- the copied SOP layer remains the canonical operating model for how the runtime repo is planned, specified, implemented, validated, and written back
- `project/*` is the default human-facing control surface when current state or durable decisions need quick recovery
- runtime-specific design artifacts stay under `ai/doc/runtime/*`
- executor adapters sit behind a narrow vendor-neutral contract; the runtime never executes coding work directly

## Latest experiment
None. All recent slices were standard plan → spec → implement → validate → closeout cycles.

## Next 3 actions
1. Use `ae compile-handoff --preview` or `ae run --preview-handoff` before dispatching real work.
2. Wire the Codex adapter backend seam to a live Codex CLI when that integration need surfaces.
3. Open a new spec only for genuine extension needs; do not add speculative nodes.

## Risks to watch
- the Codex adapter backend remains mock-backed; live integration will require an explicit new spec
- the review executor route is runtime-native and mockable today; a live external review backend would still require an explicit new spec
- `project/CURRENT.md` could drift into task-by-task reporting instead of staying recovery-focused
- copied SOP docs could drift from runtime-specific usage if the `ai/*` namespace boundary is not kept current
