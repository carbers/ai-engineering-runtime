# Runtime Architecture

`ai-engineering-runtime` is the execution/orchestration layer that sits on top of the copied SOP starter in this repository.

The copied SOP remains the development operating model. The runtime consumes the resulting artifacts and turns them into narrow executable workflow steps.

## Responsibilities

- discover runtime-consumed SOP artifacts from canonical repository locations
- parse and validate artifact contracts without redefining the SOP itself
- track workflow readiness and state transitions
- run narrow workflow nodes from a CLI
- persist lightweight run results for review and follow-up

## Non-goals

- inventing a second methodology beside the copied SOP
- replacing external coding agents or editors
- building a dashboard, daemon, or web product
- implementing full autonomy, PR automation, or merge automation in this pass

## Runtime layers

- `protocol`
  Markdown artifact contracts, discovery rules, and parsing helpers

- `state`
  Workflow states, readiness results, and transition decisions

- `nodes`
  Narrow executable workflow steps such as `plan-to-spec`

- `adapters`
  Filesystem and external executor integrations behind a narrow adapter contract

- `engine`
  Small node runner and run/result handling

- `cli`
  Human-facing command entrypoints

## Current slice boundary

The current implemented slice now spans the narrow control-plane path from artifact readiness through executor handoff, validation closeout packaging, and follow-up suggestion:

- plan and artifact discovery
- Markdown contract parsing
- plan and task-spec readiness classification
- workflow-state transitions across readiness, dispatch, validation, write-back review, and closeout suggestion
- draft spec rendering
- adapter-backed executor dispatch with capability gating
- explicit revisit of previously submitted executor runs through a narrow lifecycle node
- a minimal Codex adapter v1 with a mockable backend seam
- normalized execution results, findings, and repair-spec seeds for later review loops
- JSON run logging and summary materialization
- CLI invocation through the currently implemented runtime commands

The runtime still stops at orchestration boundaries:

- it prepares and routes narrow work to executors
- it records normalized execution outputs and follow-up inputs
- it does not replace the external coding agent, perform autonomous review loops, or automate commits/write-back
