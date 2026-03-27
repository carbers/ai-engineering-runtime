# Executor Run Poll And Resume Lifecycle Closeout

Added a narrow `executor-run-lifecycle` control-plane node and CLI entrypoint so the runtime can revisit one previously submitted executor run without redispatching the original task.

Completed in this slice:

- typed run-log parsing for structured `dispatch` payloads alongside `execution`
- executor-handle restoration from prior dispatch metadata
- explicit lifecycle actions for `poll` and capability-gated `resume`
- workflow transitions from `executing` to `executing`, `validating`, or `blocked` based on revisited execution outcome
- CLI reporting for lifecycle action, source run identity, and updated execution status
- focused tests for running-to-terminal lifecycle behavior, unsupported resume rejection, and CLI lifecycle polling

## Validation

- `python -m unittest tests.test_executor_run_lifecycle tests.test_executor_dispatch tests.test_cli`
- `python -m unittest tests.test_result_log_replay tests.test_history_selection tests.test_run_summary`
- `python -m unittest discover -s tests`

## Notes

- the default Codex mock backend now persists enough mock run state under `.runtime/` for same-repo lifecycle polling
- `resume` is intentionally wired as a capability-gated path even though current built-in adapters do not yet advertise `supports_resume`
