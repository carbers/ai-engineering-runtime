# Runtime Closeout Validation And Docs

## Metadata

### Source Plan / Request
Scoped closeout request on 2026-03-23 to harden existing `ai-engineering-runtime` behavior without adding new control-plane features.

### Status
`done`

### Related Specs
- `ai/doc/specs/20260322-001-runtime-plan-to-spec-foundation.md`
- `ai/doc/specs/20260322-016-validation-rollup-policy.md`
- `ai/doc/specs/20260322-017-writeback-package-builder.md`
- `ai/doc/specs/20260322-018-followup-package-builder.md`

## Goal
Close the current runtime slice with one reproducible local validation path, realistic multi-node regression coverage, and minimal documentation and CLI hardening that improve readiness without expanding runtime scope.

## In Scope
- make the current test suite runnable through one stable repository-local validation path
- add realistic multi-node integration coverage for existing control-plane workflows
- harden the CLI's handling of obvious runtime I/O failures so local execution errors are reviewable
- document the validated local workflow and complete currently thin golden cases

## Out of Scope
- new runtime nodes, new control-plane capabilities, or specs for future features
- executor expansion beyond the current shell preview and echo slice
- broad module decomposition or architectural redesign
- dashboards, daemon behavior, GitHub automation, or worker-plane behavior

## Affected Area
- `ai/doc/specs/*`
- `ai/doc/facts/golden-cases.md`
- `README.md`
- `src/ai_engineering_runtime/cli.py`
- `tests/*`

## Task Checklist
- [x] capture the closeout boundary and validation path in this spec
- [x] replace fragile test temp-root usage with one repository-local strategy that works in constrained environments
- [x] add at least one happy-path and one validation-affected multi-node integration test
- [x] add a narrow CLI error-reporting path for runtime I/O failures
- [x] document the validated local workflow and complete the runtime golden cases

## Done When
The existing runtime can be validated locally through one documented command path, the full test suite passes in the current constrained environment, at least two representative multi-node workflows are protected end-to-end, and the docs describe the validated workflow without claiming new runtime scope.

## Validation

### Black-box Checks
- run the full `unittest` suite with the documented local command sequence
- run the new integration workflow tests directly
- validate one local CLI workflow invocation against the real repository
- validate the editable-install console-script path locally if the environment permits it

### White-box Needed
Yes

### White-box Trigger
This slice changes the test execution harness and the CLI's runtime-error surface. Black-box acceptance is primary, but focused internal protection is needed so the temp-root strategy and error handling do not regress silently.

### Internal Logic To Protect
- constrained-environment repo temp-root creation and cleanup
- CLI translation of runtime I/O failures into stable user-facing failure output

## Write-back Needed
Yes

If yes, what stable information should be written back, and where does it belong?
- add stable workflow examples to `ai/doc/facts/golden-cases.md`
- update `README.md` with the validated local execution and validation path

## Risks / Notes
- keep the change centered on validation closure rather than general test refactoring
- do not spread new control-plane semantics into docs while improving usage guidance
- if editable install still requires unsandboxed permissions, document the verified fallback and report the install validation separately
