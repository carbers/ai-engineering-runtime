# Product Control Plane Upgrade and Dogfood Hardening Closeout

## Delivered

- Added a validated handoff schema plus compiler for `chat`, `prompt`, and `handoff` intake.
- Added workflow definitions for `repo-coding-task` and `chat-to-execution`.
- Added product-run persistence under `.runtime/product-runs/`.
- Added structured lane state, artifact categorization, phase gates, execution readiness, and next-step decision logic.
- Added node-level executor routing with primary/fallback selection and capability matching; implementation and repair default to `codex-coder`, review defaults to `review-executor`.
- Review findings carry normalized identifiers, scope, evidence, artifact/file impact, blocking state, and suggested fix kind.
- Repair specs derive from blocking findings with allowed scope, forbidden expansion, success criteria, and validation expectations.
- Closeout tracks repair rounds, blocking and non-blocking counts, and explicit closeability.
- Handoff preview surfaces intake profile, defaults applied, warnings, required artifacts, candidate actions, and why auto-advance will or will not happen.
- Added `run`, `inspect`, `resume`, `retry`, and `close` CLI commands with rich state rendering.
- CLI shows: active/parked lanes, artifact groups by category, last node/executor results, findings summary, repair status, timeline, and closeout summary.
- Added CLI acceptance coverage for the JX3 multi-lane case, review-repair-closeout loop, and compile preview.

## Validation

- `python -m unittest tests.test_product_cli -v` (5 targeted acceptance tests)
- `python -m unittest` across all 22 test modules (122 tests, all passing)

## Behavioral Change

- Users no longer need to hand-author the first handoff artifact to enter the runtime.
- The runtime now stops on structured hold states instead of defaulting to continued planning-like generation.
- Review findings now seed a repair path that the control plane can retry and close explicitly.
- Phase complete does not auto-advance; inspect shows why and what legal actions remain.

## Follow-up Worth Tracking

- Wire the Codex adapter backend seam to a live Codex CLI when that integration need surfaces (current backend is mock-backed).
- Wire a live external review backend if a real review executor beyond the runtime-native path is needed.
- Expand the handoff compiler heuristics beyond labeled plain-text sections if broader natural-language coverage becomes necessary.