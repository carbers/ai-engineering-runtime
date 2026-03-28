# Golden Cases

These are stable reference cases for this SOP repository.

## Case 1: Plan to SPEC conversion

### Input
A phase-level plan that includes:
- problem
- goal
- constraints
- risks
- phased direction

### Expected outcome
The plan is converted into one or more narrow task specs that:
- define in-scope vs out-of-scope
- stay small enough to review independently, splitting when one spec would become too large
- define validation clearly
- identify white-box triggers
- identify write-back needs

### Why it matters
This is the main bridge between planning and execution.

---

## Case 2: Ready plan to dispatch preview

### Input
A ready roadmap whose First Slice contract is executable as written.

### Expected outcome
The runtime can:
- report `ready` from `plan-readiness-check`
- write one narrow task spec from `plan-to-spec`
- report `ready` from `task-spec-readiness-check`
- preview a handoff from `executor-dispatch`
- materialize run logs and summaries under `.runtime/`

### Why it matters
This is the current happy-path control-plane proof that planning artifacts can move cleanly into reviewable execution handoff without adding worker-plane behavior.

---

## Case 3: Validation failure follow-up closure

### Input
A ready task spec plus failing command evidence with otherwise valid black-box evidence.

### Expected outcome
The runtime can:
- report `failed` from `validation-collect`
- materialize a `blocking` artifact from `validation-rollup`
- keep `validation-rollup` eligible from `node-gate`
- suggest `fix_validation_failure` from `followup-suggester`
- materialize one actionable follow-up package

### Why it matters
This protects the current closeout path where existing control-plane artifacts should make failure review explicit without inventing new planning or automation behavior.

---

## Case 4: Bugfix with white-box trigger

### Input
A deterministic bugfix in branch-heavy or stateful logic.

### Expected outcome
The task still uses black-box validation for acceptance, but also adds white-box protection for the internal regression path when appropriate.

### Why it matters
This demonstrates the layered validation model.

---

## Case 5: Selective write-back

### Input
A completed task with both temporary reasoning and one stable new decision.

### Expected outcome
Only the stable, reusable decision is written back. Temporary working notes stay out of facts.

### Why it matters
This protects the repository from documentation sprawl.
