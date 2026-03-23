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
from ai_engineering_runtime.nodes.executor_dispatch import (  # noqa: E402
    ExecutorDispatchNode,
    ExecutorDispatchRequest,
)
from ai_engineering_runtime.state import (  # noqa: E402
    DispatchMode,
    DispatchStatus,
    ExecutorTarget,
    WorkflowState,
)


READY_TASK_SPEC = """
# Dispatch Sample

## Metadata

### Source Plan / Request
`docs/runtime/roadmap.md`

### Status
`in-progress`

### Related Specs
None.

## Goal
Hand off a narrow task safely.

## In Scope
- prepare a handoff payload

## Out of Scope
- deep executor integration

## Affected Area
- `src/ai_engineering_runtime/*`

## Task Checklist
- [ ] prepare the shell handoff

## Done When
The control plane can prepare or echo a narrow task handoff.

## Validation

### Black-box Checks
- ready spec can dispatch

### White-box Needed
Yes

### White-box Trigger
The handoff gate and payload shaping are contract-sensitive.

### Internal Logic To Protect
- readiness gating
- payload shaping

## Write-back Needed
No

## Risks / Notes
- keep it small
"""

BLOCKED_TASK_SPEC = READY_TASK_SPEC.replace(
    "### Status\n`in-progress`\n\n",
    "### Status\n`done`\n\n",
)


def _write_repo_file(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


class ExecutorDispatchNodeTests(unittest.TestCase):
    def test_execute_rejects_non_ready_task_spec(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "docs/specs/20260322-999-dispatch.md", BLOCKED_TASK_SPEC)

            adapter = FileSystemAdapter(root)
            result = ExecutorDispatchNode(
                ExecutorDispatchRequest(
                    spec_path=Path("docs/specs/20260322-999-dispatch.md"),
                    mode=DispatchMode.PREVIEW,
                )
            ).execute(adapter)

            self.assertFalse(result.success)
            self.assertEqual(result.to_state, WorkflowState.BLOCKED)
            self.assertIsNotNone(result.dispatch)
            self.assertEqual(result.dispatch.status, DispatchStatus.REJECTED)
            self.assertEqual(result.dispatch.reasons[0].code, "non-executable-task-spec-status")

    def test_execute_previews_dispatch_for_ready_task_spec(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "docs/specs/20260322-999-dispatch.md", READY_TASK_SPEC)

            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)
            result = engine.run(
                ExecutorDispatchNode(
                    ExecutorDispatchRequest(
                        spec_path=Path("docs/specs/20260322-999-dispatch.md"),
                        mode=DispatchMode.PREVIEW,
                    )
                )
            )

            self.assertTrue(result.success)
            self.assertEqual(result.from_state, WorkflowState.SPEC_READY)
            self.assertEqual(result.to_state, WorkflowState.SPEC_READY)
            self.assertIsNotNone(result.dispatch)
            self.assertEqual(result.dispatch.status, DispatchStatus.PREVIEWED)
            self.assertEqual(result.dispatch.target, ExecutorTarget.SHELL)
            self.assertEqual(result.dispatch.payload.title, "Dispatch Sample")
            self.assertTrue(result.log_path.exists())

            payload = json.loads(result.log_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["dispatch"]["status"], "previewed")

    def test_execute_echo_dispatches_for_ready_task_spec(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "docs/specs/20260322-999-dispatch.md", READY_TASK_SPEC)

            adapter = FileSystemAdapter(root)
            result = ExecutorDispatchNode(
                ExecutorDispatchRequest(
                    spec_path=Path("docs/specs/20260322-999-dispatch.md"),
                    mode=DispatchMode.ECHO,
                )
            ).execute(adapter)

            self.assertTrue(result.success)
            self.assertEqual(result.to_state, WorkflowState.EXECUTING)
            self.assertIsNotNone(result.dispatch)
            self.assertEqual(result.dispatch.status, DispatchStatus.DISPATCHED)
            self.assertEqual(result.dispatch.mode, DispatchMode.ECHO)
            self.assertEqual(result.dispatch.execution_metadata["returncode"], 0)
            self.assertIn("ae-runtime dispatch", result.dispatch.execution_metadata["stdout"])


if __name__ == "__main__":
    unittest.main()


