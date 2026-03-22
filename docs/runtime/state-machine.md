# Runtime State Machine

The runtime models workflow state at the level of durable artifacts and narrow executable nodes.

## States

- `planning`
  A plan exists, but it has not yet been compiled into a valid narrow spec.

- `spec-ready`
  A plan has passed runtime contract validation and can produce a reviewable draft spec.

- `executing`
  A task spec is being acted on by an external executor or adapter.

- `validating`
  implementation is complete enough to run required validation

- `writeback-review`
  validation has completed and stable write-back decisions are being reviewed

- `complete`
  the slice is implemented, validated, and closed out cleanly

- `blocked`
  progress cannot safely continue because a required artifact, field, decision, or validation result is missing

## Current implemented transition

The current runtime slice implements the transitions below:

- `planning` -> `spec-ready`
  happens when the plan readiness result is `ready`

- `planning` -> `planning`
  happens when the plan readiness result is `needs_clarification`, meaning the structure is valid but targeted clarification is still required before safe spec creation

- `planning` -> `blocked`
  happens when the plan readiness result is `blocked`, meaning required structure is missing or a contract field is invalid

## Planned next transitions

- `spec-ready` -> `executing`
  once a future executor-dispatch node is available

- `executing` -> `validating`
  once execution reports completion and required checks can run

- `validating` -> `writeback-review`
  once required validation passes

- `writeback-review` -> `complete`
  once stable facts, summaries, or skills are updated when justified

- `executing` or `validating` -> `blocked`
  when ambiguity, missing validation, or scope pressure prevents safe progress

## Gate conditions

- no transition should silently widen scope
- non-ready outcomes should report concrete readiness reason codes and messages
- `needs_clarification` should keep the workflow in `planning`
- only explicit validation should move work beyond execution
- future nodes should preserve the copied SOP boundary between plan, spec, implementation, and write-back
