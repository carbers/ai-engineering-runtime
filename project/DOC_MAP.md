# DOC MAP

This file explains which document answers which question.
It is intentionally short.

## Start order

1. `project/CURRENT.md` for current status, active slice, next actions, and recovery context.
2. `README.md` for repository purpose, runtime scope, and top-level navigation.
3. `AGENTS.md` for repository-level operating rules.
4. `ai/README.md` for the copied SOP workflow layer and namespace map.

## Document roles

- `project/CURRENT.md`
  Current human-facing operating state.

- `project/decisions/*`
  Frozen project-level decisions worth re-reading later.

- `project/experiments/*`
  Readable experiment summaries when experiments become part of the workflow.

- `ai/doc/runtime/*`
  Runtime-specific architecture, protocol, state-machine, and roadmap documents.

- `ai/doc/change-summaries/*`
  Task-local delivery notes worth keeping for review history.

- `ai/doc/specs/*`
  Narrow execution contracts between planning and implementation.

- `ai/doc/facts/*`
  Stable reusable context, not a current-status dashboard.

- `ai/skill/*`
  Repeatable workflows that reduce repeated reasoning.

## Priority rule

When documents appear to overlap, choose the layer that matches the question:

1. For current project state, recovery context, and next durable actions, prefer `project/CURRENT.md`.
2. For task execution scope, validation, allowed edits, and done conditions, prefer the active task spec in `ai/doc/specs/*`.
3. For repository-wide operating rules and routing boundaries, prefer `README.md`, `AGENTS.md`, and `ai/README.md`.
4. For runtime architecture and control-plane behavior, prefer `ai/doc/runtime/*`.
5. For stable reusable context, prefer `ai/doc/facts/*`.
6. For task-local delivery detail, prefer the change summary or handoff notes.
