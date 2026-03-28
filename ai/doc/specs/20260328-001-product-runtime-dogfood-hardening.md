# Harden Product Runtime For Daily Dogfood

## Metadata

### Source Plan / Request
Direct product-runtime hardening request on 2026-03-28 to complete one-step productization beyond the existing V1 baseline.

### Status
`done`

### Related Specs
- `20260327-001-executor-adapter-codex-v1.md`

## Goal
Turn the existing product runtime into a daily-dogfood-ready CLI by hardening executor routing, making review-repair-closeout a runtime-native loop, improving handoff preview and input stability, and strengthening `inspect` / `retry` / `resume` / `close` UX.

## In Scope
- default implementation and repair routing to Codex with fallback retained
- default review routing through a review executor path
- normalized finding model and repair-spec derivation
- repair policy and closeout summary
- handoff input profiling, defaults, warnings, and preview output
- richer CLI state summaries and timeline output
- realistic product fixtures and focused regression coverage

## Out of Scope
- replacing the existing runtime architecture
- mandatory live Codex backend wiring
- dashboard or web UI work
- speculative multi-agent scheduling or autonomy expansion

## Affected Area
- `src/ai_engineering_runtime/state.py`
- `src/ai_engineering_runtime/handoffs.py`
- `src/ai_engineering_runtime/product_runtime.py`
- `src/ai_engineering_runtime/cli.py`
- `src/ai_engineering_runtime/adapters.py`
- `src/ai_engineering_runtime/run_logs.py`
- `tests/test_product_cli.py`
- `tests/fixtures/product/*`
- `README.md`
- `project/CURRENT.md`

## Task Checklist
- [x] harden node-level executor defaults and fallback policy
- [x] normalize review findings into one runtime-native repair surface
- [x] derive narrow repair specs from blocking findings
- [x] enforce repair rounds and closeout policy
- [x] preview handoff compilation with defaults, warnings, and candidate actions
- [x] enrich CLI inspect-style output with timelines, artifact summaries, and closeout state
- [x] preserve and extend JX3 acceptance behavior
- [x] add focused product CLI regression tests and realistic fixtures

## Done When
The runtime can preview intake, hold instead of auto-advancing when appropriate, route implementation and repair to Codex by default, route review through a review executor path, carry blocking findings into repair-dispatch and closeout, and expose the resulting state clearly through the product CLI.

## Validation

### Black-box Checks
- `ae compile-handoff --preview` shows defaults, warnings, and candidate actions
- `ae run --from-chat tests/fixtures/product/jx3-chat.txt` keeps the parked lane parked and holds instead of auto-advancing into more planning
- `ae run --from-prompt tests/fixtures/product/review-loop-prompt.txt` enters the review-repair loop
- `ae retry <run-id> --node repair-dispatch` reaches a closeable state
- `ae close <run-id>` closes the run once closeout passes

### White-box Needed
Yes

### White-box Trigger
This slice changes cross-layer product state: finding normalization, repair policy, closeout assessment, preview defaults, and CLI rendering all rely on consistent internal contracts.

### Internal Logic To Protect
- finding serialization compatibility
- repair policy enforcement and closeout assessment
- handoff profile/default/warning derivation
- decision ordering so closeout wins over "no active lane"

## Write-back Needed
Yes. Update the repository README and product control surface, and record a task-local closeout summary.