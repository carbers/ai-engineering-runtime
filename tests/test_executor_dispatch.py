from __future__ import annotations

from datetime import datetime
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
from ai_engineering_runtime.adapters import (  # noqa: E402
    CodexBackendRunResult,
    CodexExecutorAdapter,
    ExecutorPollResult,
    ExecutorRunHandle,
    FileSystemAdapter,
)
from ai_engineering_runtime.engine import RuntimeEngine  # noqa: E402
from ai_engineering_runtime.nodes.executor_dispatch import (  # noqa: E402
    ExecutorDispatchNode,
    ExecutorDispatchRequest,
)
from ai_engineering_runtime.run_logs import load_run_record  # noqa: E402
from ai_engineering_runtime.state import (  # noqa: E402
    DispatchMode,
    DispatchStatus,
    ExecutorTarget,
    ExecutionResult,
    ExecutionStatus,
    ReviewFinding,
    ReviewFindingSeverity,
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

SHELL_REQUIRED_TASK_SPEC = READY_TASK_SPEC + """

## Executor Requirements

### can_edit_files
Yes
"""

RESUME_REQUIRED_TASK_SPEC = READY_TASK_SPEC + """

## Executor Requirements

### supports_resume
Yes
"""


class BlockingCodexBackend:
    def run(self, prepared):
        return CodexBackendRunResult(
            success=False,
            summary="Mock Codex backend reported blocking findings.",
            findings=(
                ReviewFinding(
                    code="review-blocker",
                    message="A blocking review finding still needs repair.",
                    severity=ReviewFindingSeverity.BLOCKING,
                ),
            ),
            uncovered_items=("Remove the blocking review finding and re-run validation.",),
        )


class PendingCodexExecutorAdapter(CodexExecutorAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.collect_called = False
        self.normalize_called = False

    def dispatch(self, prepared) -> ExecutorRunHandle:
        return ExecutorRunHandle(
            run_id="codex-pending-run",
            target=ExecutorTarget.CODEX,
            mode=DispatchMode.SUBMIT,
            submitted_at=datetime(2026, 3, 27, 12, 0, 0),
            status_hint="running",
        )

    def poll(self, handle: ExecutorRunHandle) -> ExecutorPollResult:
        return ExecutorPollResult(
            status="running",
            is_terminal=False,
            summary="Executor run is still in progress.",
        )

    def collect(self, handle: ExecutorRunHandle) -> object:
        self.collect_called = True
        raise AssertionError("collect should not run before a terminal poll result")

    def normalize(
        self,
        prepared,
        handle: ExecutorRunHandle,
        poll_result: ExecutorPollResult,
        collected: object,
    ) -> ExecutionResult:
        self.normalize_called = True
        raise AssertionError("normalize should not run before a terminal poll result")


class ResumeCapableCodexBackend:
    supports_resume = True

    def __init__(self) -> None:
        self._results: dict[str, CodexBackendRunResult] = {}

    def run(self, prepared, handle: ExecutorRunHandle) -> CodexBackendRunResult:
        result = CodexBackendRunResult(
            success=True,
            summary=f"Resume-capable backend completed {prepared.payload_summary.title}.",
        )
        self._results[handle.run_id] = result
        return result

    def poll(self, handle: ExecutorRunHandle) -> ExecutorPollResult:
        result = self._results.get(handle.run_id)
        return ExecutorPollResult(
            status="completed" if result is not None and result.success else "missing",
            is_terminal=True,
            summary=result.summary if result is not None else "No Codex run was recorded.",
        )

    def resume(self, handle: ExecutorRunHandle) -> ExecutorPollResult:
        return self.poll(handle)

    def collect(self, handle: ExecutorRunHandle) -> CodexBackendRunResult | None:
        return self._results.get(handle.run_id)


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
            self.assertEqual(result.execution.final_status, ExecutionStatus.SUCCEEDED)
            self.assertEqual(result.dispatch.execution_metadata["poll_status"], "completed")

    def test_execute_rejects_capability_mismatch_for_shell_executor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "docs/specs/20260322-999-dispatch.md", SHELL_REQUIRED_TASK_SPEC)

            adapter = FileSystemAdapter(root)
            result = ExecutorDispatchNode(
                ExecutorDispatchRequest(
                    spec_path=Path("docs/specs/20260322-999-dispatch.md"),
                    target=ExecutorTarget.SHELL,
                    mode=DispatchMode.PREVIEW,
                )
            ).execute(adapter)

            self.assertFalse(result.success)
            self.assertEqual(result.dispatch.status, DispatchStatus.REJECTED)
            self.assertEqual(result.dispatch.reasons[0].code, "executor-capability-mismatch")
            self.assertEqual(result.dispatch.reasons[0].field, "can_edit_files")

    def test_execute_accepts_resume_requirement_for_resume_capable_codex_backend(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "docs/specs/20260322-999-dispatch.md", RESUME_REQUIRED_TASK_SPEC)

            backend = ResumeCapableCodexBackend()
            adapter = FileSystemAdapter(root)
            result = ExecutorDispatchNode(
                ExecutorDispatchRequest(
                    spec_path=Path("docs/specs/20260322-999-dispatch.md"),
                    target=ExecutorTarget.CODEX,
                    mode=DispatchMode.SUBMIT,
                ),
                executor_factory=lambda _target: CodexExecutorAdapter(backend=backend),
            ).execute(adapter)

            self.assertTrue(result.success)
            self.assertEqual(result.dispatch.status, DispatchStatus.DISPATCHED)
            self.assertTrue(result.dispatch.executor.capabilities.supports_resume)
            self.assertTrue(result.execution.executor.capabilities.supports_resume)

    def test_execute_submits_codex_dispatch_and_writes_execution_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "docs/specs/20260322-999-dispatch.md", READY_TASK_SPEC)

            adapter = FileSystemAdapter(root)
            result = RuntimeEngine(adapter).run(
                ExecutorDispatchNode(
                    ExecutorDispatchRequest(
                        spec_path=Path("docs/specs/20260322-999-dispatch.md"),
                        target=ExecutorTarget.CODEX,
                        mode=DispatchMode.SUBMIT,
                    )
                )
            )

            self.assertTrue(result.success)
            self.assertEqual(result.to_state, WorkflowState.EXECUTING)
            self.assertEqual(result.dispatch.status, DispatchStatus.DISPATCHED)
            self.assertEqual(result.execution.final_status, ExecutionStatus.SUCCEEDED)
            self.assertEqual(result.execution.executor.name, "codex")
            self.assertTrue(result.execution.patch_ref.startswith("mock://codex/patch/"))
            self.assertIsNotNone(result.log_path)

            record = load_run_record(result.log_path)
            self.assertIsNotNone(record.execution)
            self.assertEqual(record.execution.final_status, ExecutionStatus.SUCCEEDED)

    def test_execute_codex_failure_surfaces_repair_seed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "docs/specs/20260322-999-dispatch.md", READY_TASK_SPEC)

            adapter = FileSystemAdapter(root)
            result = ExecutorDispatchNode(
                ExecutorDispatchRequest(
                    spec_path=Path("docs/specs/20260322-999-dispatch.md"),
                    target=ExecutorTarget.CODEX,
                    mode=DispatchMode.SUBMIT,
                ),
                executor_factory=lambda _target: CodexExecutorAdapter(backend=BlockingCodexBackend()),
            ).execute(adapter)

            self.assertFalse(result.success)
            self.assertEqual(result.to_state, WorkflowState.BLOCKED)
            self.assertEqual(result.execution.final_status, ExecutionStatus.FAILED)
            self.assertIsNotNone(result.execution.repair_spec_candidate)
            self.assertEqual(result.execution.repair_spec_candidate.title, "Repair Dispatch Sample")

    def test_execute_keeps_nonterminal_codex_run_in_running_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "docs/specs/20260322-999-dispatch.md", READY_TASK_SPEC)

            pending_adapter = PendingCodexExecutorAdapter()
            adapter = FileSystemAdapter(root)
            result = RuntimeEngine(adapter).run(
                ExecutorDispatchNode(
                    ExecutorDispatchRequest(
                        spec_path=Path("docs/specs/20260322-999-dispatch.md"),
                        target=ExecutorTarget.CODEX,
                        mode=DispatchMode.SUBMIT,
                    ),
                    executor_factory=lambda _target: pending_adapter,
                )
            )

            self.assertTrue(result.success)
            self.assertEqual(result.to_state, WorkflowState.EXECUTING)
            self.assertEqual(result.dispatch.status, DispatchStatus.DISPATCHED)
            self.assertEqual(result.execution.final_status, ExecutionStatus.RUNNING)
            self.assertEqual(result.dispatch.execution_metadata["poll_status"], "running")
            self.assertFalse(pending_adapter.collect_called)
            self.assertFalse(pending_adapter.normalize_called)
            self.assertIsNotNone(result.log_path)

            record = load_run_record(result.log_path)
            self.assertIsNotNone(record.execution)
            self.assertEqual(record.execution.final_status, ExecutionStatus.RUNNING)


if __name__ == "__main__":
    unittest.main()
