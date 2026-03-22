# Validation Collect Foundation Closeout

## What Changed
Added a first-class `validation-collect` runtime slice with:
- a structured validation result model and evidence-entry model
- a dedicated `validation-collect` node and CLI command
- status derivation for `passed`, `failed`, and `incomplete`
- task-spec-aware handling for required white-box evidence
- focused tests and a small CLI output polish fix

## Scope Completed
Completed the narrow control-plane aggregation slice for:
- explicit command, black-box, white-box, and manual-note evidence inputs
- validation-state transitions from `validating`
- missing-evidence vs failed-evidence distinction
- run-log serialization for structured validation results
- stable runtime-doc updates for the implemented command and semantics

## Black-box Validation
- `python -m unittest tests.test_validation_collect tests.test_cli -v`
- `python -m unittest discover -s tests -v`
- `$env:PYTHONPATH='src'; python -m ai_engineering_runtime validation-collect --spec docs/specs/20260322-005-validation-collect-foundation.md --command-status passed --black-box-status passed --white-box-status passed`

Result:
- targeted validation and CLI tests passed
- all 37 repository tests passed in the full regression run
- the CLI reported `passed` for the current spec and wrote a JSON run log under `.runtime/runs/`

## White-box Validation
Protected by focused `unittest` coverage for:
- complete passing aggregation
- failure mapping from supplied failing evidence
- incomplete mapping from missing required white-box evidence
- missing-spec failure handling
- CLI output stability for the passing path

## Regression Path Protected
The runtime now has explicit coverage for the closeout boundary between failed evidence and missing evidence, and it no longer relies on informal judgment alone to decide whether validation can move into write-back review.

## Facts / Skills Updated
- no new facts were written
- no new skills were created
- updated stable runtime docs in `README.md` and `docs/runtime/*` to reflect the implemented validation collector

## Remaining Gaps
- the collector accepts explicit evidence inputs only and intentionally does not parse test-runner output formats
- automatic command or test execution orchestration remains out of scope
- `python -m ai_engineering_runtime` still requires `PYTHONPATH=src` or package installation because of the repo's `src/` layout
