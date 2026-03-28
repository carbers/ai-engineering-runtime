# ai-engineering-runtime

`ai-engineering-runtime` is a lightweight, CLI-first workflow runtime built on top of the copied `ai-engineering-sop` starter in this repository.

The copied SOP remains the operating model for how this repository is planned, specified, implemented, validated, and written back. The runtime exists to consume those artifacts and turn them into narrow executable workflow steps.

The copied SOP assets in this repository now live under `ai/` so they stay aligned with the upstream starter. Runtime-specific design docs remain under `ai/doc/runtime/*`, and task-local closeout notes remain under `ai/doc/change-summaries/*`.

## What this repository is for

This repository establishes a practical runtime layer that can:

1. discover SOP artifacts such as plans, task specs, facts, skills, and summaries
2. determine workflow readiness and state
3. compile plans into narrow executable task specs
4. dispatch work to external executors or adapters
5. collect validation results
6. suggest write-back and follow-up work

The current implementation is intentionally smaller than that full direction: one stdlib-only Python CLI, fifteen real nodes, and one documented contract for checking plan readiness, checking task-spec readiness, compiling a plan into a narrow draft task spec, aggregating validation evidence, classifying closeout write-back candidates, suggesting the next control-plane action, preparing a minimal shell-based executor handoff, revisiting one previously submitted executor run, reconstructing replay-friendly outcomes from prior run logs, selecting replayable relevant history, materializing stable run summaries, evaluating downstream node eligibility, rolling up validation outcomes, and packaging write-back and follow-up review artifacts.

The current implementation now also includes a vendor-neutral executor adapter contract, capability gating, a minimal Codex adapter v1 with a mockable backend seam, and normalized execution results that preserve the boundary of `runtime = control plane` and `executor = worker plane`.

The runtime now also exposes a product-oriented intake layer on top of those node-level contracts:

- consume `chat`, `prompt`, or normalized `handoff` input directly
- compile natural-language input into a validated internal handoff schema
- select a workflow and evaluate structured phase gates
- keep lane state, artifact class, executor routing, and next-step decisions explicit
- hold instead of auto-continuing when approval, review, or blocked state should stop progress
- run a minimal review-repair-closeout loop with retry and fallback policy

## What stays the same

The copied SOP starter is still the canonical development model for this repo:

1. start from a plan or phase slice
2. derive or refine one or more narrow task specs
3. implement narrowly
4. validate explicitly
5. write back only stable facts
6. promote repeated workflows into skills when they stabilize

See `AGENTS.md` for the full repository rules.

The copied SOP layer in this repository now also includes:

- the default lightweight `small task` path plus the optional phase-aware long-task path
- a minimal `project/*` control surface for human recovery
- the upstream `ai/README.md`, `ai/doc/*`, and `ai/skill/*` namespace layout

## Repository layout

- `AGENTS.md`
  Canonical repository guidance. The copied SOP still governs how this repo is developed.

- `ai/README.md`
  Namespace map for the copied SOP workflow layer under `ai/*`.

- `project/*`
  Recovery-first human control surface for current state, document roles, durable decisions, and experiments.

- `ai/doc/runtime/*`
  Runtime-specific design artifacts: architecture, protocol, state machine, and roadmap.

- `ai/doc/change-summaries/*`
  Task-local delivery notes and closeout summaries.

- `ai/doc/specs/*`
  Narrow execution contracts, including specs produced by the runtime.

- `ai/doc/facts/*`
  Stable reusable project context.

- `ai/doc/guides/*`, `ai/doc/templates/*`, `ai/skill/*`
  The copied SOP starter materials that this runtime consumes and dogfoods.

- `src/ai_engineering_runtime/*`
  The runtime CLI and internal layers.

- `tests/*`
  `unittest` coverage for the implemented runtime slice.

## Implemented commands

The product-oriented control-plane entrypoints are:

```text
ae run --from-chat tests/fixtures/product/jx3-chat.txt
ae run --from-prompt tests/fixtures/product/review-loop-prompt.txt
ae run --from-handoff .runtime/compiled/review-loop.json
ae run --from-chat tests/fixtures/product/jx3-chat.txt --preview-handoff
ae run --from-prompt tests/fixtures/product/review-loop-prompt.txt --dry-run
ae compile-handoff --from-prompt tests/fixtures/product/review-loop-prompt.txt --out .runtime/compiled/review-loop.json
ae compile-handoff --from-prompt tests/fixtures/product/review-loop-prompt.txt --preview
ae validate-handoff --handoff .runtime/compiled/review-loop.json
ae inspect <run-id>
ae resume <run-id>
ae retry <run-id> --node repair-dispatch
ae close <run-id>
```

Those commands persist product-run state under `.runtime/product-runs/` and report:

- active, parked, and blocked lanes
- phase gate outcomes and why auto-advance is or is not allowed
- compile preview defaults, warnings, and unresolved ambiguity before dispatch
- artifact gaps grouped by planning, execution, and review/closeout needs
- executor dispatch candidates, node-level default routing, and capability-matched routes
- normalized review findings with repair-loop status, repair rounds, and closeout readiness
- last node result, last executor result, and a compact run timeline across intake, dispatch, review, repair, validation, and closeout

The current productized runtime now treats next-step control as a gated action rather than a default continuation:

- `phase complete` does not auto-advance into more planning or closeout work
- `inspect` shows the default action, all legal actions, and why auto-advance is disabled
- review findings are normalized into one repair surface and can drive `repair-dispatch -> validation -> closeout`
- repair rounds are capped by policy and escalate to review when the loop should stop

The lower-level node commands remain available:

The current executable slice is:

```text
ae-runtime plan-readiness-check --plan ai/doc/runtime/roadmap.md
ae-runtime task-spec-readiness-check --spec ai/doc/specs/20260322-003-writeback-classifier.md
ae-runtime plan-to-spec --plan ai/doc/runtime/roadmap.md
ae-runtime validation-collect --spec ai/doc/specs/20260322-003-writeback-classifier.md --command-status passed --black-box-status passed
ae-runtime writeback-classifier --text "..." --kind workflow_pattern
ae-runtime followup-suggester --validation-status failed
ae-runtime executor-dispatch --spec ai/doc/specs/20260322-007-executor-dispatch-adapter-shell.md --mode preview
ae-runtime executor-dispatch --spec ai/doc/specs/20260327-001-executor-adapter-codex-v1.md --executor codex --mode submit
ae-runtime executor-run-lifecycle --run-id 20260327T120000000000-executor-dispatch --action poll
ae-runtime result-log-replay --latest --node validation-collect
ae-runtime run-history-select --spec ai/doc/specs/20260322-005-validation-collect-foundation.md --node validation-collect
ae-runtime run-summary --latest --node validation-collect
ae-runtime node-gate --node validation-rollup --run-id 20260322T191755447854-validation-collect
ae-runtime validation-rollup --latest
ae-runtime writeback-package --latest
ae-runtime followup-package --latest
```

The `ae-runtime` command path assumes the project has been installed into the current Python environment.
The `ae` command is now also exported as a product-oriented alias for the same CLI entrypoint.
Before installation, use the module form from the repository root:

```powershell
$env:PYTHONPATH = "src"
python -m ai_engineering_runtime plan-readiness-check --plan ai/doc/runtime/roadmap.md
```

Use `plan-readiness-check` to inspect a plan artifact and return a structured readiness outcome with stable reason codes.

Use `plan-to-spec --dry-run` to preview the generated spec and readiness outcome without writing a spec file.
Omit `--dry-run` to write the next dated spec under `ai/doc/specs/`.

These commands currently:

- parse a roadmap or plan artifact from Markdown
- classify plan readiness as `ready`, `needs_clarification`, or `blocked`
- classify task-spec readiness as `ready`, `needs_clarification`, or `blocked`
- return stable reason codes and messages for non-ready outcomes
- render a narrow draft task spec only when readiness is `ready`
- aggregate supplied validation evidence as `passed`, `failed`, or `incomplete`
- classify write-back candidates as `facts`, `skills`, `change_summary_only`, or `ignore`
- suggest a single next control-plane action from readiness, validation, write-back, and closeout signals
- prepare or dispatch a ready task spec through a vendor-neutral executor adapter contract
- capability-check a task against one executor adapter before handoff
- normalize executor outputs into a structured execution result with findings and repair-spec seed hints
- revisit one previously submitted executor run through an explicit poll or resume lifecycle path without redispatching the original task
- inspect one prior run log at a time and normalize its recorded signal as replay-oriented context
- select replayable prior runs relevant to one exact artifact target
- project compact history signals and canonical terminal state into stable run summaries
- evaluate one declared node against the current summary context as `eligible`, `blocked`, `skipped`, `not_applicable`, or `unknown`
- materialize stable validation rollups under `.runtime/rollups/validation/`
- materialize stable write-back and follow-up packages under `.runtime/packages/`
- write a JSON run log under `.runtime/runs/`
- write a JSON run summary under `.runtime/summaries/`

The runtime creates the `.runtime/` directory tree on demand when one of those artifacts is first materialized.

Task specs may optionally declare `## Executor Requirements` using capability fields such as `can_edit_files`, `can_run_shell`, `can_open_repo_context`, `can_return_patch`, `can_return_commit`, `can_run_tests`, `can_do_review_only`, `supports_noninteractive`, and `supports_resume`.
If declared, `executor-dispatch` will block incompatible adapters before worker-plane handoff.
`executor-run-lifecycle` can then revisit a previously submitted run log and either keep the workflow in `executing` or advance it toward `validating` once a terminal execution result is available.

## Local validation

Use one narrow local validation path for closeout work:

```powershell
python -m unittest discover -s tests -v

$env:PYTHONPATH = "src"
python -m ai_engineering_runtime plan-readiness-check --plan ai/doc/runtime/roadmap.md
```

If you also want to validate the installed console script path in the same environment:

```powershell
python -m pip install -e .
ae run --from-chat tests/fixtures/product/jx3-chat.txt
ae-runtime plan-readiness-check --plan ai/doc/runtime/roadmap.md
```

## What this repository is not

This repository is not:

- a replacement for the SOP itself
- a replacement for Claude Code or Codex CLI
- a dashboard or web product
- a full autonomy, PR automation, or merge automation platform

## Where to look next

1. if you need the current operating state, read `project/CURRENT.md`
2. read `AGENTS.md`
3. read `ai/README.md`
4. read `ai/doc/runtime/architecture.md`
5. read `ai/doc/runtime/roadmap.md`
6. for the copied SOP workflow layer, read `ai/doc/guides/new-project-sop.md` and `ai/doc/specs/README.md`
7. run `$env:PYTHONPATH='src'; python -m ai_engineering_runtime plan-readiness-check --plan ai/doc/runtime/roadmap.md`
