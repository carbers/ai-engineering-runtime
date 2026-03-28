from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = ROOT / "tests"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))
from support import activate_repo_tempdir  # noqa: E402

activate_repo_tempdir(tempfile)
from ai_engineering_runtime.adapters import FileSystemAdapter  # noqa: E402
from ai_engineering_runtime.engine import RuntimeEngine  # noqa: E402
from ai_engineering_runtime.nodes.task_spec_readiness_check import (  # noqa: E402
    TaskSpecReadinessCheckNode,
    TaskSpecReadinessCheckRequest,
)
from ai_engineering_runtime.state import (  # noqa: E402
    ReadinessIssue,
    ReadinessResult,
    ReadinessStatus,
    WorkflowState,
    task_spec_to_execution_transition,
)


READY_TASK_SPEC = """
# Sample Task Spec

## Metadata

### Source Plan / Request
`ai/doc/runtime/roadmap.md`

### Status
`draft`

### Related Specs
None.

## Goal
Implement a narrow runtime slice.

## In Scope
- add a dedicated checker node
- add a CLI command

## Out of Scope
- executor dispatch

## Affected Area
- `src/ai_engineering_runtime/*`
- `tests/*`

## Task Checklist
- [ ] add the readiness checker
- [ ] add tests

## Done When
The runtime can classify whether this spec is ready for implementation.

## Validation

### Black-box Checks
- ready spec returns ready

### White-box Needed
Yes

### White-box Trigger
The contract parser and readiness gate are regression-sensitive.

### Internal Logic To Protect
- spec field parsing
- readiness status mapping

## Write-back Needed
No

## Risks / Notes
- keep it small
"""

NEEDS_CLARIFICATION_TASK_SPEC = READY_TASK_SPEC.replace(
    "## Done When\nThe runtime can classify whether this spec is ready for implementation.\n\n",
    "## Done When\nTBD after the acceptance signal is clarified.\n\n",
)

BLOCKED_TASK_SPEC = READY_TASK_SPEC.replace(
    "### Status\n`draft`\n\n",
    "### Status\n`done`\n\n",
)


def _write_repo_file(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


class TaskSpecReadinessCheckNodeTests(unittest.TestCase):
    def test_execute_reports_ready_for_implementable_task_spec(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "ai/doc/specs/20260322-999-sample.md", READY_TASK_SPEC)

            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)
            result = engine.run(
                TaskSpecReadinessCheckNode(
                    TaskSpecReadinessCheckRequest(
                        spec_path=Path("ai/doc/specs/20260322-999-sample.md")
                    )
                )
            )

            self.assertTrue(result.success)
            self.assertEqual(result.from_state, WorkflowState.SPEC_READY)
            self.assertEqual(result.to_state, WorkflowState.SPEC_READY)
            self.assertIsNotNone(result.readiness)
            self.assertEqual(result.readiness.status, ReadinessStatus.READY)
            self.assertEqual(result.readiness.reasons, ())
            self.assertTrue(result.log_path.exists())

            payload = json.loads(result.log_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["readiness"]["status"], "ready")
            self.assertEqual(payload["spec_path"], "ai/doc/specs/20260322-999-sample.md")

    def test_execute_reports_needs_clarification_for_placeholder_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "ai/doc/specs/20260322-999-sample.md", NEEDS_CLARIFICATION_TASK_SPEC)

            adapter = FileSystemAdapter(root)
            result = TaskSpecReadinessCheckNode(
                TaskSpecReadinessCheckRequest(
                    spec_path=Path("ai/doc/specs/20260322-999-sample.md")
                )
            ).execute(adapter)

            self.assertFalse(result.success)
            self.assertEqual(result.to_state, WorkflowState.SPEC_READY)
            self.assertIsNotNone(result.readiness)
            self.assertEqual(result.readiness.status, ReadinessStatus.NEEDS_CLARIFICATION)
            self.assertEqual([issue.code for issue in result.issues], ["placeholder-task-spec-field"])
            self.assertEqual(result.issues[0].field, "Done When")

    def test_execute_reports_blocked_for_non_executable_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "ai/doc/specs/20260322-999-sample.md", BLOCKED_TASK_SPEC)

            adapter = FileSystemAdapter(root)
            result = TaskSpecReadinessCheckNode(
                TaskSpecReadinessCheckRequest(
                    spec_path=Path("ai/doc/specs/20260322-999-sample.md")
                )
            ).execute(adapter)

            self.assertFalse(result.success)
            self.assertEqual(result.to_state, WorkflowState.BLOCKED)
            self.assertIsNotNone(result.readiness)
            self.assertEqual(result.readiness.status, ReadinessStatus.BLOCKED)
            self.assertEqual([issue.code for issue in result.issues], ["non-executable-task-spec-status"])
            self.assertEqual(result.issues[0].field, "Status")

    def test_missing_task_spec_path_returns_blocked_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            adapter = FileSystemAdapter(root)
            result = TaskSpecReadinessCheckNode(
                TaskSpecReadinessCheckRequest(
                    spec_path=Path("ai/doc/specs/missing.md")
                )
            ).execute(adapter)

            self.assertFalse(result.success)
            self.assertEqual(result.to_state, WorkflowState.BLOCKED)
            self.assertEqual(result.issues[0].code, "missing-task-spec")
            self.assertEqual(result.issues[0].field, "spec_path")


class TaskSpecReadinessTransitionTests(unittest.TestCase):
    def test_task_spec_to_execution_transition_maps_all_readiness_statuses(self) -> None:
        ready = task_spec_to_execution_transition(ReadinessResult(status=ReadinessStatus.READY))
        needs_clarification = task_spec_to_execution_transition(
            ReadinessResult(
                status=ReadinessStatus.NEEDS_CLARIFICATION,
                reasons=(ReadinessIssue(code="placeholder-task-spec-field", message="x"),),
            )
        )
        blocked = task_spec_to_execution_transition(
            ReadinessResult(
                status=ReadinessStatus.BLOCKED,
                reasons=(ReadinessIssue(code="missing-task-spec-section", message="x"),),
            )
        )

        self.assertEqual(ready.to_state, WorkflowState.SPEC_READY)
        self.assertEqual(needs_clarification.to_state, WorkflowState.SPEC_READY)
        self.assertEqual(blocked.to_state, WorkflowState.BLOCKED)


if __name__ == "__main__":
    unittest.main()


