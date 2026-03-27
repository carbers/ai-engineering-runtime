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

- `spec-ready` -> `spec-ready`
  happens when a task spec readiness check is `ready` or `needs_clarification`, meaning the spec remains in review at the spec layer until a later dispatch step hands work to the worker plane

- `spec-ready` -> `blocked`
  happens when task-spec readiness is `blocked`, meaning required execution contract structure or status is invalid

- `spec-ready` -> `spec-ready`
  happens when executor dispatch runs in `preview` mode, meaning the handoff was prepared, capability-checked, and held in the control plane without worker execution

- `spec-ready` -> `executing`
  happens when executor dispatch runs in `echo` or `submit` mode for a ready and compatible task spec, meaning the control plane handed off the narrow payload to one executor adapter and captured a normalized execution result

- `spec-ready` -> `blocked`
  happens when executor dispatch rejects a non-ready task spec, fails capability gating, or receives a blocking executor outcome

- `executing` -> `executing`
  happens when `executor-run-lifecycle` revisits a previously submitted run and the executor still reports a non-terminal outcome

- `executing` -> `validating`
  happens when `executor-run-lifecycle` revisits a previously submitted run and captures a terminal successful execution result that is ready for explicit validation handling

- `executing` -> `blocked`
  happens when executor-run revisit selection is invalid, resume is unsupported, or the revisited execution result ends in `failed` or `blocked`

- `validating` -> `writeback-review`
  happens when validation collection returns `passed`, meaning required supplied validation evidence exists and no critical failures remain

- `validating` -> `blocked`
  happens when validation collection returns `failed` or `incomplete`, meaning required evidence failed or is still missing

- `writeback-review` -> `writeback-review`
  happens when the write-back classifier emits a destination decision for a closeout candidate. The runtime still requires explicit human-reviewed artifact updates before the workflow can move to `complete`.

- `writeback-review` -> `planning`
  happens when the follow-up suggester returns `clarify_plan`

- `writeback-review` -> `blocked`
  happens when the follow-up suggester returns `fix_validation_failure`

- `writeback-review` -> `spec-ready`
  happens when the follow-up suggester returns `implement_next_task`

- `writeback-review` -> `complete`
  happens when the follow-up suggester returns `no_followup_needed`

## Planned next transitions

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
- executor capability mismatches should block dispatch before a worker-plane handoff happens
- only explicit validation should move work beyond execution
- future nodes should preserve the copied SOP boundary between plan, spec, implementation, and write-back
