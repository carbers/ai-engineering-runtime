# Runtime Artifact Protocol

The runtime consumes repository artifacts through lightweight Markdown contracts. It does not require YAML frontmatter, a database, or a web service layer.

## Artifact kinds

- `plan`
  Durable roadmap or plan documents. The current canonical plan is `docs/runtime/roadmap.md`.

- `task-spec`
  Narrow execution contracts stored in `docs/specs/YYYYMMDD-NNN-task-slug.md`.

- `fact`
  Stable reusable context stored in `docs/facts/*.md`.

- `skill`
  Reusable workflow guidance stored in `skills/*.md`.

- `change-summary`
  Optional task-local delivery notes. The runtime may discover them if a dedicated summary directory is added later.

## Discovery rules

- treat the repository root as the protocol boundary
- discover the current durable plan from `docs/runtime/roadmap.md`
- discover task specs from `docs/specs/*.md`
- discover facts from `docs/facts/*.md`
- discover skills from `skills/*.md`
- ignore templates and guides unless a future node explicitly consumes them

## Markdown parsing contract

Plans are parsed from top-level `##` headings.

The required plan sections for the current runtime slice are:

- `Problem`
- `Goal`
- `Non-goals`
- `Constraints`
- `Proposed Approach`
- `Risks`
- `Phase Split`
- `First Slice`

Inside `## First Slice`, the runtime expects `###` subheadings for the fields it compiles into a task spec:

- `Spec Title`
- `In Scope`
- `Out of Scope`
- `Affected Area`
- `Task Checklist`
- `Done When`
- `Black-box Checks`
- `White-box Needed`
- `White-box Trigger`
- `Internal Logic To Protect`
- `Write-back Needed`
- `Risks / Notes`

## Field format rules

- list-shaped fields must use Markdown list syntax. Plain paragraphs are invalid for those fields.
- `White-box Needed` must start with `Yes` or `No`
- `Write-back Needed` must start with `Yes` or `No`
- the plan `Goal` becomes the generated task spec `Goal`
- the runtime preserves the copied SOP task-spec structure when rendering output

Task specs are parsed from top-level `##` headings using the current contract in `docs/templates/task-spec-template.md`.

The required task-spec sections for the current runtime slice are:

- `Metadata`
- `Goal`
- `In Scope`
- `Out of Scope`
- `Affected Area`
- `Task Checklist`
- `Done When`
- `Validation`
- `Write-back Needed`
- `Risks / Notes`

Inside `## Metadata`, the runtime currently requires:

- `Source Plan / Request`
- `Status`

Inside `## Validation`, the runtime currently requires:

- `Black-box Checks`
- `White-box Needed`
- `White-box Trigger`
- `Internal Logic To Protect`

## Readiness rules

- `ready`
  the plan satisfies the required section and `First Slice` contract checks and does not contain placeholder content in required fields

- `needs_clarification`
  the plan satisfies the required structure, but one or more required sections or fields still contain placeholder text such as `TBD`, `TODO`, `to be decided`, or `to be determined`

- `blocked`
  the plan is missing required sections or fields, or violates required field-format rules such as list syntax or `Yes` / `No` choice fields

For task specs:

- `ready`
  the task spec satisfies the required section, metadata, validation, list-field, and executable-status checks and does not contain placeholder content in required implementation fields

- `needs_clarification`
  the task spec satisfies the required structure, but one or more required implementation fields still contain placeholder content

- `blocked`
  the task spec is missing required structure, violates list or choice-field rules, or has a non-executable status such as `done` or `blocked`

## Validation collection rules

- `passed`
  required supplied evidence is present and no critical validation evidence failed or remains incomplete

- `failed`
  one or more supplied command, black-box, or white-box evidence entries failed

- `incomplete`
  required validation evidence is missing or explicitly marked incomplete

## Follow-up suggestion rules

The follow-up suggester consumes structured status signals from earlier nodes instead of re-deriving them.

It currently supports these suggestion outcomes:

- `implement_next_task`
- `clarify_plan`
- `fix_validation_failure`
- `write_back_stable_context`
- `promote_skill_candidate`
- `no_followup_needed`

## Executor dispatch rules

The executor-dispatch slice stays in the control plane:

- it requires a `ready` task spec before handoff
- it shapes a narrow payload summary from the task spec
- `preview` shows the prepared handoff without executing anything
- `echo` proves local shell dispatch plumbing without integrating a real worker-plane executor

## Run-log replay rules

The run-log replay slice also stays in the control plane:

- it inspects one prior run log at a time from `.runtime/runs/*.json`
- latest-selection ordering comes from the run-log filename timestamp rather than from a JSON timestamp field
- it reconstructs normalized signal outputs from recorded node outcomes instead of re-running node logic
- it returns `replayable` or `rejected` with stable reason codes
- replayed history is context and evidence input only, not the authoritative workflow state source

## Run-history selection rules

- `run-history-select` requires one explicit artifact target selector:
  - `spec`
  - `plan`
  - `output`
- optional `node` and replay `signal-kind` filters further narrow the match set
- selection reuses replay-normalized history rather than scanning raw log payloads directly as a public contract
- matches are ordered newest first from filename timestamps
- exact multiple matches are returned as an ordered result set rather than treated as ambiguity in this slice
- no-match results return stable reason codes

## Run-summary rules

- each node run materializes a summary artifact under `.runtime/summaries/<run-id>.json`
- a run summary is a control-plane artifact, not a narrative report
- summary query supports:
  - explicit run-log path
  - run id
  - latest run-log selection with optional node filter
- summary loading reuses normalized history selection, compact signal projection, and terminal-state resolution
- if a requested summary artifact is missing or invalid, the runtime rebuilds it from the source run log
- summary remains a derived review view over run logs, not a new authoritative workflow state source

## Artifact-ref rules

- runtime-generated control-plane artifacts use one narrow internal `ArtifactRef` shape:
  - artifact kind
  - repo-relative or absolute path
- runtime-generated ref families currently include:
  - run log
  - run summary
  - validation rollup
  - write-back package
  - follow-up package
- artifact refs are linkage helpers for control-plane artifacts, not a general registry or new source of truth

## Node-contract and gate rules

- node contracts stay as static declarations rather than reflective registration
- `node-gate` evaluates one declared node at a time against:
  - available artifact refs
  - available terminal signal kind
  - current terminal status
  - existence of the node's primary output artifact when declared
- gate results are inspection-oriented only:
  - `eligible`
  - `blocked`
  - `skipped`
  - `not_applicable`
  - `unknown`
- gate evaluation is not a scheduler, planner, or automatic next-step selector

## Validation-rollup rules

- `validation-rollup` consumes one existing validation result and materializes one stable artifact under `.runtime/rollups/validation/<run-id>.json`
- rollups keep a minimal decision-facing status set:
  - `clean`
  - `advisory`
  - `blocking`
- rollups normalize existing validation findings without re-running validation logic

## Package-builder rules

- `writeback-package` and `followup-package` materialize review artifacts under `.runtime/packages/`
- packages link back to source run logs, summaries, and related artifact refs when that context is available
- optional validation-rollup linkage is best-effort; package builders do not invent missing task correlation
- packages are suggestion artifacts only and do not perform write-back, task creation, or dispatch automatically

## Write-back destination rules

- `facts`
  stable reusable project context that should be available later outside one task closeout

- `skills`
  repeatable execution guidance that would reduce future repeated reasoning effort

- `change_summary_only`
  useful task-local delivery detail that should stay in closeout notes instead of durable facts or skills

- `ignore`
  transient debugging, one-off exploration, or low-value detail that should not be written back

## Support level in this pass

- fully supported: discovery and parsing for the canonical roadmap plan, task specs, facts, and skills
- executable support: `plan-readiness-check`, `task-spec-readiness-check`, `plan` -> `task-spec`, `validation-collect`, `writeback-classifier`, `followup-suggester`, `executor-dispatch`, `result-log-replay`, `run-history-select`, `run-summary`, `node-gate`, `validation-rollup`, `writeback-package`, and `followup-package`
- internal normalized support: exact replay-backed history selection, compact replay-signal projection, canonical terminal-state resolution, artifact refs, static node contracts, and stable package artifacts
