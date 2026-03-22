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
  Filesystem and future external executor integrations

- `engine`
  Small node runner and run/result handling

- `cli`
  Human-facing command entrypoints

## Current slice boundary

The current implemented slice provides only enough runtime to check plan readiness and compile a durable plan into a draft task spec:

- plan and artifact discovery
- Markdown contract parsing
- plan readiness classification for `ready`, `needs_clarification`, and `blocked`
- workflow-state transitions from `planning` to `planning`, `spec-ready`, or `blocked`
- draft spec rendering
- JSON run logging
- CLI invocation through `ae-runtime plan-readiness-check` and `ae-runtime plan-to-spec`

Future slices may add executor dispatch, validation ingestion, and write-back suggestions, but they are intentionally not part of this landing.
