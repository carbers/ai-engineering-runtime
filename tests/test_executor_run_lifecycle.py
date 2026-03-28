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
from ai_engineering_runtime.nodes.executor_run_lifecycle import (  # noqa: E402
    ExecutorRunLifecycleNode,
    ExecutorRunLifecycleRequest,
)
from ai_engineering_runtime.state import (  # noqa: E402
    DispatchMode,
    ExecutionStatus,
    ExecutorLifecycleAction,
    ExecutorTarget,
    WorkflowState,
)


READY_TASK_SPEC = """
# Dispatch Sample

## Metadata

### Source Plan / Request
`ai/doc/runtime/roadmap.md`

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


class LifecycleCodexAdapter(CodexExecutorAdapter):
    def __init__(self) -> None:
        super().__init__()
        self._terminal_results: dict[str, CodexBackendRunResult] = {}
        self._poll_counts: dict[str, int] = {}
        self._counter = 0

    def dispatch(self, prepared) -> ExecutorRunHandle:
        self._counter += 1
        run_id = f"codex-life-{self._counter:04d}"
        self._poll_counts[run_id] = 0
        self._terminal_results[run_id] = CodexBackendRunResult(
            success=True,
            summary=f"Lifecycle adapter completed {prepared.payload_summary.title}.",
            changed_files=("src/ai_engineering_runtime/nodes/executor_run_lifecycle.py",),
            stdout="terminal lifecycle path completed",
            validations_claimed=("ready spec can dispatch",),
        )
        return ExecutorRunHandle(
            run_id=run_id,
            target=ExecutorTarget.CODEX,
            mode=DispatchMode.SUBMIT,
            submitted_at=datetime(2026, 3, 27, 14, 0, 0),
            status_hint="running",
            metadata={"repo_root": prepared.context_summary.get("repo_root")},
        )

    def poll(self, handle: ExecutorRunHandle) -> ExecutorPollResult:
        count = self._poll_counts.get(handle.run_id, 0)
        self._poll_counts[handle.run_id] = count + 1
        if count == 0:
            return ExecutorPollResult(
                status="running",
                is_terminal=False,
                summary="Executor run is still in progress.",
            )
        terminal = self._terminal_results.get(handle.run_id)
        return ExecutorPollResult(
            status="completed" if terminal is not None and terminal.success else "failed",
            is_terminal=True,
            summary=terminal.summary if terminal is not None else "No lifecycle run was recorded.",
        )

    def collect(self, handle: ExecutorRunHandle) -> CodexBackendRunResult | None:
        return self._terminal_results.get(handle.run_id)

    def resume(self, handle: ExecutorRunHandle) -> ExecutorPollResult:
        return self.poll(handle)


class ResumeCapableLifecycleBackend:
    supports_resume = True

    def __init__(self) -> None:
        self._results: dict[str, CodexBackendRunResult] = {}
        self.resume_calls = 0

    def run(self, prepared, handle: ExecutorRunHandle) -> CodexBackendRunResult:
        result = CodexBackendRunResult(
            success=True,
            summary=f"Resume-capable lifecycle backend completed {prepared.payload_summary.title}.",
        )
        self._results[handle.run_id] = result
        return result

    def poll(self, handle: ExecutorRunHandle) -> ExecutorPollResult:
        return ExecutorPollResult(
            status="running",
            is_terminal=False,
            summary="Executor run is still in progress.",
        )

    def resume(self, handle: ExecutorRunHandle) -> ExecutorPollResult:
        self.resume_calls += 1
        result = self._results.get(handle.run_id)
        return ExecutorPollResult(
            status="completed" if result is not None and result.success else "missing",
            is_terminal=True,
            summary=result.summary if result is not None else "No lifecycle run was recorded.",
        )

    def collect(self, handle: ExecutorRunHandle) -> CodexBackendRunResult | None:
        return self._results.get(handle.run_id)


def _write_repo_file(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


class ExecutorRunLifecycleNodeTests(unittest.TestCase):
    def test_poll_revisits_running_executor_run_and_advances_to_validating(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "ai/doc/specs/20260327-999-dispatch.md", READY_TASK_SPEC)

            lifecycle_adapter = LifecycleCodexAdapter()
            adapter = FileSystemAdapter(root)
            dispatch_result = RuntimeEngine(adapter).run(
                ExecutorDispatchNode(
                    ExecutorDispatchRequest(
                        spec_path=Path("ai/doc/specs/20260327-999-dispatch.md"),
                        target=ExecutorTarget.CODEX,
                        mode=DispatchMode.SUBMIT,
                    ),
                    executor_factory=lambda _target: lifecycle_adapter,
                )
            )

            self.assertEqual(dispatch_result.execution.final_status, ExecutionStatus.RUNNING)
            self.assertEqual(dispatch_result.to_state, WorkflowState.EXECUTING)

            lifecycle_result = RuntimeEngine(adapter).run(
                ExecutorRunLifecycleNode(
                    ExecutorRunLifecycleRequest(
                        run_id=dispatch_result.log_path.stem,
                        action=ExecutorLifecycleAction.POLL,
                    ),
                    executor_factory=lambda _target: lifecycle_adapter,
                )
            )

            self.assertTrue(lifecycle_result.success)
            self.assertEqual(lifecycle_result.to_state, WorkflowState.VALIDATING)
            self.assertEqual(lifecycle_result.execution.final_status, ExecutionStatus.SUCCEEDED)
            self.assertEqual(lifecycle_result.metadata["source_run_id"], dispatch_result.log_path.stem)

    def test_resume_rejects_executor_without_resume_capability(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "ai/doc/specs/20260327-999-dispatch.md", READY_TASK_SPEC)

            adapter = FileSystemAdapter(root)
            dispatch_result = RuntimeEngine(adapter).run(
                ExecutorDispatchNode(
                    ExecutorDispatchRequest(
                        spec_path=Path("ai/doc/specs/20260327-999-dispatch.md"),
                        target=ExecutorTarget.CODEX,
                        mode=DispatchMode.SUBMIT,
                    )
                )
            )

            lifecycle_result = ExecutorRunLifecycleNode(
                ExecutorRunLifecycleRequest(
                    run_id=dispatch_result.log_path.stem,
                    action=ExecutorLifecycleAction.RESUME,
                )
            ).execute(adapter)

            self.assertFalse(lifecycle_result.success)
            self.assertEqual(lifecycle_result.to_state, WorkflowState.BLOCKED)
            self.assertEqual(lifecycle_result.issues[0].code, "executor-resume-unsupported")

    def test_resume_advances_when_backend_declares_resume_capability(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "ai/doc/specs/20260327-999-dispatch.md", READY_TASK_SPEC)

            backend = ResumeCapableLifecycleBackend()
            resume_capable_adapter = CodexExecutorAdapter(backend=backend)
            adapter = FileSystemAdapter(root)
            dispatch_result = RuntimeEngine(adapter).run(
                ExecutorDispatchNode(
                    ExecutorDispatchRequest(
                        spec_path=Path("ai/doc/specs/20260327-999-dispatch.md"),
                        target=ExecutorTarget.CODEX,
                        mode=DispatchMode.SUBMIT,
                    ),
                    executor_factory=lambda _target: resume_capable_adapter,
                )
            )

            self.assertEqual(dispatch_result.execution.final_status, ExecutionStatus.RUNNING)
            self.assertTrue(dispatch_result.dispatch.executor.capabilities.supports_resume)

            lifecycle_result = RuntimeEngine(adapter).run(
                ExecutorRunLifecycleNode(
                    ExecutorRunLifecycleRequest(
                        run_id=dispatch_result.log_path.stem,
                        action=ExecutorLifecycleAction.RESUME,
                    ),
                    executor_factory=lambda _target: resume_capable_adapter,
                )
            )

            self.assertTrue(lifecycle_result.success)
            self.assertEqual(lifecycle_result.to_state, WorkflowState.VALIDATING)
            self.assertEqual(lifecycle_result.execution.final_status, ExecutionStatus.SUCCEEDED)
            self.assertEqual(backend.resume_calls, 1)

    def test_poll_preserves_existing_execution_context_for_non_terminal_revisit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "ai/doc/specs/20260327-999-dispatch.md", READY_TASK_SPEC)

            lifecycle_adapter = LifecycleCodexAdapter()
            adapter = FileSystemAdapter(root)
            dispatch_result = RuntimeEngine(adapter).run(
                ExecutorDispatchNode(
                    ExecutorDispatchRequest(
                        spec_path=Path("ai/doc/specs/20260327-999-dispatch.md"),
                        target=ExecutorTarget.CODEX,
                        mode=DispatchMode.SUBMIT,
                    ),
                    executor_factory=lambda _target: lifecycle_adapter,
                )
            )
            dispatch_execution = dispatch_result.execution
            self.assertIsNotNone(dispatch_execution)
            run_id = dispatch_result.dispatch.execution_metadata["run_id"]
            lifecycle_adapter._poll_counts[run_id] = 0

            enriched_execution = dispatch_execution.to_record()
            enriched_execution["validations_claimed"] = ["ready spec can dispatch"]
            enriched_execution["uncovered_items"] = ["wait for executor completion"]
            enriched_execution["findings"] = [
                {
                    "code": "still-running",
                    "message": "Executor run has not reached a terminal state yet.",
                    "severity": "warning",
                    "field": None,
                }
            ]
            enriched_execution["repair_spec_candidate"] = {
                "title": "Follow up on running executor",
                "goal": "Revisit the executor run after it completes.",
                "in_scope": ["wait for executor completion"],
                "validation_focus": ["ready spec can dispatch"],
                "triggering_findings": [],
            }

            log_payload = json.loads(dispatch_result.log_path.read_text(encoding="utf-8"))
            log_payload["execution"] = enriched_execution
            dispatch_result.log_path.write_text(json.dumps(log_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            lifecycle_result = RuntimeEngine(adapter).run(
                ExecutorRunLifecycleNode(
                    ExecutorRunLifecycleRequest(
                        run_id=dispatch_result.log_path.stem,
                        action=ExecutorLifecycleAction.POLL,
                    ),
                    executor_factory=lambda _target: lifecycle_adapter,
                )
            )

            self.assertTrue(lifecycle_result.success)
            self.assertEqual(lifecycle_result.to_state, WorkflowState.EXECUTING)
            self.assertEqual(lifecycle_result.execution.final_status, ExecutionStatus.RUNNING)
            self.assertEqual(lifecycle_result.execution.validations_claimed, ("ready spec can dispatch",))
            self.assertEqual(lifecycle_result.execution.uncovered_items, ("wait for executor completion",))
            self.assertEqual(lifecycle_result.execution.findings[0].code, "still-running")
            self.assertIsNotNone(lifecycle_result.execution.repair_spec_candidate)

    def test_poll_revisits_shell_run_from_persisted_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "ai/doc/specs/20260327-999-dispatch.md", READY_TASK_SPEC)

            adapter = FileSystemAdapter(root)
            dispatch_result = RuntimeEngine(adapter).run(
                ExecutorDispatchNode(
                    ExecutorDispatchRequest(
                        spec_path=Path("ai/doc/specs/20260327-999-dispatch.md"),
                        target=ExecutorTarget.SHELL,
                        mode=DispatchMode.ECHO,
                    )
                )
            )

            lifecycle_result = RuntimeEngine(adapter).run(
                ExecutorRunLifecycleNode(
                    ExecutorRunLifecycleRequest(
                        run_id=dispatch_result.log_path.stem,
                        action=ExecutorLifecycleAction.POLL,
                    )
                )
            )

            self.assertTrue(lifecycle_result.success)
            self.assertEqual(lifecycle_result.to_state, WorkflowState.VALIDATING)
            self.assertEqual(lifecycle_result.execution.final_status, ExecutionStatus.SUCCEEDED)


if __name__ == "__main__":
    unittest.main()
