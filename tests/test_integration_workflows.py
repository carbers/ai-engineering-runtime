from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import date
import io
from pathlib import Path
import sys
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = ROOT / "tests"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from support import repo_temp_dir  # noqa: E402

from ai_engineering_runtime.cli import main  # noqa: E402


READY_ROADMAP = """
# Runtime Roadmap

## Problem
The runtime needs one realistic happy-path workflow proof.

## Goal
Validate a narrow control-plane path end to end.

## Non-goals
- new runtime features

## Constraints
- keep the workflow CLI-first

## Proposed Approach
Compile a ready plan into a task spec and preview dispatch.

## Risks
- workflow drift between nodes

## Phase Split
- phase closeout

## First Slice
Prove a plan-to-dispatch happy path.

### Spec Title
Integration Dispatch Happy Path

### In Scope
- compile a ready plan
- validate the generated task spec
- preview dispatch

### Out of Scope
- new executor integrations

### Affected Area
- `src/ai_engineering_runtime/*`
- `tests/*`

### Task Checklist
- compile the plan
- check the generated spec
- preview dispatch

### Done When
The runtime can turn this roadmap into one ready task spec and preview dispatch without manual artifact repair.

### Black-box Checks
- the ready plan produces a task spec
- the generated task spec is ready
- dispatch preview succeeds

### White-box Needed
No

### White-box Trigger
Black-box workflow checks are sufficient for this integration path.

### Internal Logic To Protect
- none

### Write-back Needed
No

### Risks / Notes
- keep the flow narrow
"""


READY_SPEC = """
# Integration Validation Failure Sample

## Metadata

### Source Plan / Request
`docs/runtime/roadmap.md`

### Status
`in-progress`

### Related Specs
None.

## Goal
Exercise the validation failure closeout path.

## In Scope
- collect failing validation evidence
- roll up the validation result
- suggest and package the follow-up action

## Out of Scope
- new follow-up logic

## Affected Area
- `src/ai_engineering_runtime/*`
- `tests/*`

## Task Checklist
- [ ] collect evidence
- [ ] materialize the rollup
- [ ] package the follow-up

## Done When
The runtime reports a blocking validation failure and suggests a fix-focused follow-up.

## Validation

### Black-box Checks
- failed command evidence produces a failed validation result
- the validation rollup becomes blocking
- the follow-up package remains actionable

### White-box Needed
No

### White-box Trigger
Black-box workflow checks are sufficient for this integration path.

### Internal Logic To Protect
- none

## Write-back Needed
No

## Risks / Notes
- keep the failure path deterministic
"""


def _write_repo_file(root: Path, relative_path: str, content: str) -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return path


def _run_cli(root: Path, argv: list[str], *, today: date = date(2026, 3, 23)) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(argv, repo_root=root, today=today)
    return exit_code, stdout.getvalue(), stderr.getvalue()


class WorkflowIntegrationTests(unittest.TestCase):
    def test_ready_plan_can_flow_through_spec_readiness_and_dispatch_preview(self) -> None:
        with repo_temp_dir() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "docs/runtime/roadmap.md", READY_ROADMAP)

            exit_code, stdout, stderr = _run_cli(
                root,
                ["plan-readiness-check", "--plan", "docs/runtime/roadmap.md"],
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr, "")
            self.assertIn("Readiness: ready", stdout)

            exit_code, stdout, stderr = _run_cli(
                root,
                ["plan-to-spec", "--plan", "docs/runtime/roadmap.md"],
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr, "")
            self.assertIn("plan-to-spec completed", stdout)

            spec_paths = sorted((root / "docs" / "specs").glob("*.md"))
            self.assertEqual(len(spec_paths), 1)
            spec_path = spec_paths[0]
            relative_spec = spec_path.relative_to(root).as_posix()

            exit_code, stdout, stderr = _run_cli(
                root,
                ["task-spec-readiness-check", "--spec", relative_spec],
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr, "")
            self.assertIn("Readiness: ready", stdout)

            exit_code, stdout, stderr = _run_cli(
                root,
                ["executor-dispatch", "--spec", relative_spec, "--mode", "preview"],
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr, "")
            self.assertIn("Dispatch: previewed", stdout)

            run_logs = sorted((root / ".runtime" / "runs").glob("*.json"))
            summaries = sorted((root / ".runtime" / "summaries").glob("*.json"))
            self.assertGreaterEqual(len(run_logs), 4)
            self.assertEqual(len(summaries), len(run_logs))

    def test_validation_failure_flow_produces_blocking_rollup_and_fix_followup(self) -> None:
        with repo_temp_dir() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "docs/specs/20260323-099-validation-failure-sample.md", READY_SPEC)

            exit_code, stdout, stderr = _run_cli(
                root,
                [
                    "validation-collect",
                    "--spec",
                    "docs/specs/20260323-099-validation-failure-sample.md",
                    "--command-status",
                    "failed",
                    "--black-box-status",
                    "passed",
                ],
            )
            self.assertEqual(exit_code, 1)
            self.assertEqual(stdout, "")
            self.assertIn("Validation: failed", stderr)

            exit_code, stdout, stderr = _run_cli(
                root,
                ["run-summary", "--latest", "--node", "validation-collect"],
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr, "")
            self.assertIn("Summary Node: validation-collect", stdout)
            self.assertIn("Summary Signal: validation=failed", stdout)

            exit_code, stdout, stderr = _run_cli(
                root,
                ["node-gate", "--node", "validation-rollup", "--latest", "--summary-node", "validation-collect"],
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr, "")
            self.assertIn("Gate: eligible", stdout)

            exit_code, stdout, stderr = _run_cli(
                root,
                ["validation-rollup", "--latest"],
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr, "")
            self.assertIn("Validation Rollup: blocking", stdout)

            exit_code, stdout, stderr = _run_cli(
                root,
                ["followup-suggester", "--validation-status", "failed"],
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr, "")
            self.assertIn("Follow-up: fix_validation_failure", stdout)

            exit_code, stdout, stderr = _run_cli(
                root,
                ["followup-package", "--latest"],
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr, "")
            self.assertIn("Follow-up Package: fix_validation_failure", stdout)
            self.assertIn("Actionable: yes", stdout)


if __name__ == "__main__":
    unittest.main()
