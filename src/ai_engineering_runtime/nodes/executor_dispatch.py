from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_engineering_runtime.adapters import FileSystemAdapter, ShellExecutorAdapter
from ai_engineering_runtime.artifacts import TaskSpecArtifact, parse_list_block
from ai_engineering_runtime.engine import RunResult
from ai_engineering_runtime.nodes.task_spec_readiness_check import check_task_spec_readiness
from ai_engineering_runtime.state import (
    DispatchMode,
    DispatchPayload,
    DispatchResult,
    DispatchStatus,
    ExecutorTarget,
    RuntimeReason,
    executor_dispatch_transition,
)


@dataclass(frozen=True)
class ExecutorDispatchRequest:
    spec_path: Path
    target: ExecutorTarget = ExecutorTarget.SHELL
    mode: DispatchMode = DispatchMode.PREVIEW


class ExecutorDispatchNode:
    name = "executor-dispatch"

    def __init__(self, request: ExecutorDispatchRequest):
        self.request = request

    def execute(self, adapter: FileSystemAdapter) -> RunResult:
        checked_spec = check_task_spec_readiness(adapter, self.request.spec_path)
        payload = (
            build_dispatch_payload(checked_spec.task_spec)
            if checked_spec.task_spec is not None
            else None
        )

        if checked_spec.task_spec is None or not checked_spec.readiness.is_ready:
            dispatch = DispatchResult(
                target=self.request.target,
                status=DispatchStatus.REJECTED,
                mode=self.request.mode,
                payload=payload,
                reasons=checked_spec.readiness.reasons,
                execution_metadata={
                    "readiness_status": checked_spec.readiness.status.value,
                },
            )
        elif self.request.mode is DispatchMode.PREVIEW:
            dispatch = DispatchResult(
                target=self.request.target,
                status=DispatchStatus.PREVIEWED,
                mode=self.request.mode,
                payload=payload,
                execution_metadata={"preview_only": True},
            )
        else:
            shell_adapter = ShellExecutorAdapter()
            receipt = shell_adapter.dispatch_echo(f"ae-runtime dispatch {payload.title}")
            reasons: tuple[RuntimeReason, ...] = ()
            status = DispatchStatus.DISPATCHED
            if receipt.returncode != 0:
                status = DispatchStatus.REJECTED
                reasons = (
                    RuntimeReason(
                        code="dispatch-command-failed",
                        message="The shell echo dispatch command failed.",
                    ),
                )
            dispatch = DispatchResult(
                target=self.request.target,
                status=status,
                mode=self.request.mode,
                payload=payload,
                reasons=reasons,
                execution_metadata={
                    "command": list(receipt.command),
                    "returncode": receipt.returncode,
                    "stdout": receipt.stdout.strip(),
                    "stderr": receipt.stderr.strip(),
                },
            )

        transition = executor_dispatch_transition(dispatch)
        result = RunResult(
            node_name=self.name,
            success=dispatch.status in {DispatchStatus.PREVIEWED, DispatchStatus.DISPATCHED},
            from_state=transition.from_state,
            to_state=transition.to_state,
            issues=transition.issues,
            spec_path=checked_spec.spec_path,
            dispatch=dispatch,
        )
        log_path = adapter.build_run_log_path(self.name)
        result = result.with_log_path(log_path)
        adapter.write_json(log_path, result.to_log_record(adapter))
        return result


def build_dispatch_payload(task_spec: TaskSpecArtifact) -> DispatchPayload:
    return DispatchPayload(
        title=task_spec.title,
        goal=task_spec.sections["Goal"].strip(),
        in_scope=tuple(parse_list_block(task_spec.sections["In Scope"])),
        done_when=task_spec.sections["Done When"].strip(),
    )
