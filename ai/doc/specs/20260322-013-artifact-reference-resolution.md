# Implement Artifact Reference Resolution

## Metadata

### Source Plan / Request
Directly scoped phase request in Codex chat on 2026-03-23 to continue the post-summary control-plane chain with artifact refs, node contracts, gate evaluation, validation rollups, and package builders.

### Status
`done`

### Related Specs
- `20260322-012-run-summary-materialization.md`
- `20260322-014-node-io-contract-and-dependency-declarations.md`
- `20260322-017-writeback-package-builder.md`
- `20260322-018-followup-package-builder.md`

## Goal
Implement one lightweight artifact-reference model and resolver layer that gives runtime modules a stable internal way to point at control-plane artifacts without hard-coding path assembly throughout the codebase.

## In Scope
- define one small serializable `ArtifactRef` contract with:
  - artifact kind
  - repo-relative path
- cover the artifact kinds already exercised by the runtime:
  - plan
  - task spec
  - fact
  - skill
  - output
  - run log
  - run summary
  - validation rollup
  - write-back package
  - follow-up package
- add focused resolver helpers that:
  - normalize refs from repo-relative or absolute paths
  - resolve refs back to concrete filesystem paths
  - construct refs for runtime-generated artifacts under `.runtime/*`
- use the new ref model in newly added rollup and package artifacts instead of duplicating path linkage rules
- add focused tests for serialization, normalization, and runtime-generated artifact refs

## Out of Scope
- remote artifact registries
- content-addressed storage
- database-backed indexing
- dashboard or document-management behavior
- watcher, daemon, or GitHub automation
- broad migration of every existing log payload field away from path strings in this slice
- a dedicated artifact-ref inspection CLI

## Affected Area
- `src/ai_engineering_runtime/artifact_refs.py`
- `src/ai_engineering_runtime/adapters.py`
- `src/ai_engineering_runtime/run_summary.py`
- `src/ai_engineering_runtime/validation_rollup.py`
- `src/ai_engineering_runtime/writeback_package.py`
- `src/ai_engineering_runtime/followup_package.py`
- `tests/test_artifact_refs.py`

## Task Checklist
- [ ] define the narrow artifact-ref model and supported artifact kinds for current control-plane use
- [ ] add resolver helpers for repo-relative, absolute, and runtime-generated artifact paths
- [ ] adopt artifact refs in new rollup and package artifacts instead of ad hoc path linkage
- [ ] add focused unit coverage for serialization and resolution behavior

## Done When
Runtime code can create, serialize, and resolve stable artifact refs for the current control-plane artifact set, and newly added rollup or package artifacts carry refs instead of duplicating hard-coded path semantics.

## Validation

### Black-box Checks
- create and round-trip repo artifact refs for plans, task specs, and runtime-generated artifacts
- resolve runtime-generated refs for summaries, rollups, and packages to the expected filesystem paths
- run `python -m unittest tests.test_artifact_refs -v`

### White-box Needed
Yes

### White-box Trigger
This slice establishes a shared internal contract for later phases. Black-box checks alone will not reliably protect kind-to-path resolution, repo-relative normalization, or runtime-generated artifact path conventions.

### Internal Logic To Protect
- repo-relative path normalization
- artifact-kind to path-family mapping
- runtime-generated artifact-ref construction
- ref serialization and resolution symmetry

## Write-back Needed
Yes - update `ai/doc/runtime/protocol.md` only if the internal artifact-ref contract becomes stable enough to describe.

## Risks / Notes
### Implementation Shape
Keep this as one focused internal service layer. Do not migrate every historical run-log field to artifact refs or turn the runtime into a generic artifact platform.

### Artifact / Data Contract Impact
This slice adds a narrow internal artifact-ref contract for current runtime-generated control-plane artifacts and repo artifacts. It does not replace existing replay artifact-target fields in this slice.

### CLI Impact
No dedicated CLI command in this slice.

### Split / Defer
Create a follow-on spec before implementation if work expands to remote registries, content addressing, or full historical schema migration.
