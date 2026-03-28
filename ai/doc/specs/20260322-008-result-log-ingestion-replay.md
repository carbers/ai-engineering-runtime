# Implement Result Log Ingestion Replay

## Metadata

### Source Plan / Request
Directly scoped task request in Codex chat on 2026-03-22 to add a control-plane run-log ingestion and replay foundation without changing the repository into an analytics, recovery, or executor platform.

### Status
`draft`

### Related Specs
- `20260322-001-runtime-plan-to-spec-foundation.md`
- `20260322-002-runtime-plan-readiness-check.md`
- `20260322-005-validation-collect-foundation.md`
- `20260322-006-followup-suggester.md`
- `20260322-007-executor-dispatch-adapter-shell.md`

## Goal
Implement a narrow `result-log-replay` capability that loads one prior runtime run log at a time, reconstructs a normalized control-plane outcome without re-running node logic, and exposes a replay-facing view that downstream code can consume without depending on raw log shape.

## In Scope
- discover prior run logs from `.runtime/runs/*.json` and support explicit log-path loading
- add a dedicated run-log parsing and normalization module outside `state.py` so replay complexity does not accumulate in `state.py`, `engine.py`, or `cli.py`
- define a replay-facing result contract that exposes exactly:
  - source log path
  - ordered timestamp derived from the run-log filename
  - node identity
  - replay status: `replayable` or `rejected`
  - artifact target kind and path
  - normalized signal kind and value
  - reason codes
- reconstruct normalized outcomes for logs emitted by:
  - `plan-readiness-check`
  - `task-spec-readiness-check`
  - `validation-collect`
  - `writeback-classifier`
  - `followup-suggester`
  - `executor-dispatch`
- load `plan-to-spec` logs for inspection but treat them as non-replayable in this slice unless they contain a stable replayable signal payload
- apply a minimum compatibility layer for legacy or partial logs already written by this repo:
  - derive ordering from the filename timestamp rather than requiring a JSON timestamp field
  - resolve artifact target as `spec_path` -> `plan_path` -> `output_path` -> none
  - reject partial or malformed logs with stable reason codes instead of raising uncaught parser failures
- emit stable replay rejection reasons for:
  - missing log selection
  - malformed JSON
  - invalid outer run-log envelope
  - unknown node
  - missing replayable signal
  - ambiguous replayable signal
  - invalid filename timestamp
- add a thin CLI path `result-log-replay` that supports:
  - `--log <path>` to inspect one explicit run log
  - `--latest` with optional `--node <name>` to inspect the newest matching log under `.runtime/runs/`
- keep the CLI human-readable and summary-oriented rather than exposing raw JSON as a public stdout contract
- add focused tests using fixture-style run logs for valid current logs, legacy partial logs, malformed logs, and latest-selection behavior
- update runtime docs only if the replay contract becomes stable enough to describe

## Out of Scope
- event sourcing
- automatic workflow replay across multiple nodes
- replay-based resume or recovery
- watcher, daemon, CI, or GitHub automation
- dashboard or visualization work
- deep executor integrations
- cross-run analytics or reporting
- turning run-log history into a new source of truth for workflow state
- re-running readiness, validation, write-back, or follow-up logic from artifacts instead of reconstructing logged outcomes
- broad log storage redesign or schema-versioning system
- retrofitting `validation-collect` or `writeback-classifier` to consume replayed history directly in this slice
- broad expansion of `state.py` or conversion of `engine.py` into a history service

## Affected Area
- `src/ai_engineering_runtime/run_logs.py`
- `src/ai_engineering_runtime/engine.py`
- `src/ai_engineering_runtime/nodes/result_log_replay.py`
- `src/ai_engineering_runtime/cli.py`
- `tests/test_result_log_replay.py`
- `tests/test_cli.py`
- `tests/fixtures/run_logs/*`
- `ai/doc/runtime/protocol.md`
- `README.md` if the replay CLI surface becomes stable enough to document

## Task Checklist
- [ ] add a dedicated run-log discovery, parsing, and normalization module with a small replay-facing result model
- [ ] reconstruct one normalized signal per supported log without re-reading source artifacts or re-running node logic
- [ ] implement stable legacy, partial, invalid, and latest-selection handling
- [ ] add a thin `result-log-replay` node and CLI command that inspect one log at a time
- [ ] add focused unit and CLI coverage using current, legacy, and malformed run-log fixtures

## Done When
A contributor can run `python -m ai_engineering_runtime result-log-replay --log .runtime/runs/<timestamp>-validation-collect.json` or `python -m ai_engineering_runtime result-log-replay --latest --node validation-collect` and receive one stable replay summary that includes `replayable` or `rejected`, ordered timestamp, artifact target, normalized signal kind/value, and reason codes, without the runtime treating history as the authoritative state source.

## Validation

### Black-box Checks
- replay a valid `validation-collect` log by explicit `--log` and report a replayable normalized validation signal
- replay a valid `followup-suggester` or `writeback-classifier` log by explicit `--log` and report the expected normalized signal value
- select the newest matching log via `--latest --node <name>` and preserve stable filename-based ordering behavior
- reject a malformed JSON log cleanly with a stable rejection reason
- reject a legacy or partial log that lacks a replayable signal cleanly without crashing
- verify the CLI output stays thin and understandable while not exposing raw log internals as the contract
- run `python -m unittest tests.test_result_log_replay tests.test_cli -v`

### White-box Needed
Yes

### White-box Trigger
This slice adds historical result reconstruction and backward-compatible log parsing. Black-box checks alone will not reliably protect filename-based ordering, node-to-signal mapping, replayable vs rejected classification, or the rule that replay reconstructs prior signals instead of recalculating node logic.

### Internal Logic To Protect
- run-log discovery and selection
- filename timestamp parsing and ordering
- outer envelope validation
- node-specific signal reconstruction
- replayable vs rejected distinction
- stable rejection reason-code emission
- separation between replay normalization and original node logic

## Write-back Needed
Yes, but keep it narrow by updating `ai/doc/runtime/protocol.md` and `README.md` only if the replay contract and CLI semantics stabilize during implementation. Do not add facts or skills by default from this slice.

## Risks / Notes
- keep the primary outcome narrow: one-log-at-a-time discovery, parsing, normalization, and replay view
- expose a normalized replay contract rather than the raw log payload shape
- deduplicate reason codes from typed signal reasons first and top-level issues second
- treat replayed history as context and evidence only, not as the runtime's state truth
- the first downstream-ready projection is follow-up-friendly signal consumption; direct producer-node consumption can wait for a later spec
- create a follow-on spec before implementation if scope expands to:
  - multi-log workflow composition
  - replay-driven resume or recovery behavior
  - cross-run analytics or reporting
  - direct downstream node rewiring beyond normalized signal projection
  - log storage redesign or explicit schema-version negotiation
