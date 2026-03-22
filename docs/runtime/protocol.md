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

## Readiness rules

- `ready`
  the plan satisfies the required section and `First Slice` contract checks and does not contain placeholder content in required fields

- `needs_clarification`
  the plan satisfies the required structure, but one or more required sections or fields still contain placeholder text such as `TBD`, `TODO`, `to be decided`, or `to be determined`

- `blocked`
  the plan is missing required sections or fields, or violates required field-format rules such as list syntax or `Yes` / `No` choice fields

## Support level in this pass

- fully supported: discovery and parsing for the canonical roadmap plan, task specs, facts, and skills
- executable support: `plan-readiness-check` and `plan` -> `task-spec`
- documented only for now: executor dispatch, validation result ingestion, write-back suggestions, and follow-up suggestions
