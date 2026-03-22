# Follow-up Suggester Closeout

## What Changed
Added a first-class `followup-suggester` runtime slice with:
- a structured follow-up result model
- a dedicated `followup-suggester` node and CLI command
- a small explicit priority order across readiness, validation, write-back, and closeout signals
- focused tests for category selection, closeout handling, and priority behavior

## Scope Completed
Completed the narrow control-plane follow-up slice for:
- mapping structured upstream statuses to one clear next-step suggestion
- stable reason-code and explanation emission
- workflow-state suggestions for continue, clarify, fix, write back, promote skill, or stop
- run-log serialization for follow-up results
- stable runtime-doc updates for the implemented command and suggestion taxonomy

## Black-box Validation
- `python -m unittest tests.test_followup_suggester tests.test_cli -v`
- `python -m unittest discover -s tests -v`
- `$env:PYTHONPATH='src'; python -m ai_engineering_runtime followup-suggester --validation-status failed`

Result:
- targeted follow-up and CLI tests passed
- all 44 repository tests passed in the full regression run
- the CLI reported `fix_validation_failure` for the failed validation signal and wrote a JSON run log under `.runtime/runs/`

## White-box Validation
Protected by focused `unittest` coverage for:
- clarify-plan mapping from non-ready readiness
- fix-validation mapping from failed validation
- write-back mapping for facts destinations
- guarded `no_followup_needed` handling
- validation-over-writeback priority

## Regression Path Protected
The runtime now has explicit coverage for the decision priority between “clarify”, “fix”, “write back”, “continue”, and “stop”, instead of leaving next-step decisions to informal interpretation of multiple upstream statuses.

## Facts / Skills Updated
- no new facts were written
- no new skills were created
- updated stable runtime docs in `README.md` and `docs/runtime/*` to reflect the implemented follow-up suggester

## Remaining Gaps
- the suggester consumes structured statuses only and intentionally does not read arbitrary run logs or create artifacts automatically
- dispatch and executor handoff remain separate later work
- `python -m ai_engineering_runtime` still requires `PYTHONPATH=src` or package installation because of the repo's `src/` layout
