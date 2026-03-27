from __future__ import annotations

from dataclasses import replace
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ai_engineering_runtime.adapters import (
    ExecutorAdapter,
    ExecutorDispatchContext,
    FileSystemAdapter,
    build_executor_adapter,
    evaluate_executor_compatibility,
)
from ai_engineering_runtime.engine import RunResult
from ai_engineering_runtime.nodes.task_spec_readiness_check import check_task_spec_readiness
from ai_engineering_runtime.state import (
    DispatchMode,
    DispatchResult,
    DispatchStatus,
    ExecutionResult,
    ExecutionStatus,
    ExecutorTarget,
    ReviewFindingSeverity,
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

    def __init__(
        self,
        request: ExecutorDispatchRequest,
        executor_factory: Callable[[ExecutorTarget], ExecutorAdapter] | None = None,
    ):
        self.request = request
        self.executor_factory = executor_factory or build_executor_adapter

    def execute(self, adapter: FileSystemAdapter) -> RunResult:
        checked_spec = check_task_spec_readiness(adapter, self.request.spec_path)
        prepared = None
        executor = self.executor_factory(self.request.target)
        execution: ExecutionResult | None = None
        compatibility_reasons: tuple[RuntimeReason, ...] = ()

        if checked_spec.task_spec is not None:
            prepared = executor.prepare(
                checked_spec.task_spec,
                ExecutorDispatchContext(
                    repo_root=adapter.repo_root,
                    spec_path=adapter.resolve(self.request.spec_path),
                    repo_label=adapter.repo_root.name,
                ),
            )
            prepared = replace(prepared, mode=self.request.mode)
            compatibility_reasons = evaluate_executor_compatibility(
                requirements=prepared.requirements,
                executor=prepared.executor,
                mode=self.request.mode,
                supported_modes=executor.supported_modes,
            )

        payload = prepared.payload_summary if prepared is not None else None

        if checked_spec.task_spec is None or not checked_spec.readiness.is_ready:
            dispatch = DispatchResult(
                target=self.request.target,
                status=DispatchStatus.REJECTED,
                mode=self.request.mode,
                payload=payload,
                reasons=checked_spec.readiness.reasons,
                executor=prepared.executor if prepared is not None else executor.descriptor,
                requirements=prepared.requirements if prepared is not None else None,
                execution_metadata={
                    "readiness_status": checked_spec.readiness.status.value,
                },
            )
        elif compatibility_reasons:
            dispatch = DispatchResult(
                target=self.request.target,
                status=DispatchStatus.REJECTED,
                mode=self.request.mode,
                payload=payload,
                reasons=compatibility_reasons,
                executor=prepared.executor,
                requirements=prepared.requirements,
                execution_metadata={
                    "readiness_status": checked_spec.readiness.status.value,
                    "required_capabilities": list(prepared.requirements.required_capabilities()),
                },
            )
        elif self.request.mode is DispatchMode.PREVIEW:
            execution = ExecutionResult(
                executor=prepared.executor,
                spec_identity=prepared.spec_identity,
                dispatch_summary=prepared.payload_summary.to_record(),
                final_status=ExecutionStatus.PREVIEWED,
                summary="Dispatch payload prepared successfully and held in the control plane preview path.",
                suggested_followups=("Submit the prepared task to an executor when ready.",),
            )
            dispatch = DispatchResult(
                target=self.request.target,
                status=DispatchStatus.PREVIEWED,
                mode=self.request.mode,
                payload=payload,
                executor=prepared.executor,
                requirements=prepared.requirements,
                execution_metadata={
                    "preview_only": True,
                    "required_capabilities": list(prepared.requirements.required_capabilities()),
                },
            )
        else:
            handle = executor.dispatch(prepared)
            poll_result = executor.poll(handle)
            if poll_result.is_terminal:
                collected = executor.collect(handle)
                execution = executor.normalize(prepared, handle, poll_result, collected)
            else:
                execution = ExecutionResult(
                    executor=prepared.executor,
                    spec_identity=prepared.spec_identity,
                    dispatch_summary=prepared.payload_summary.to_record(),
                    final_status=ExecutionStatus.RUNNING,
                    summary=(
                        poll_result.summary
                        or f"Executor run {handle.run_id} is still in progress ({poll_result.status})."
                    ),
                    log_summary=poll_result.summary,
                    suggested_followups=("Poll or resume the executor run after it reaches a terminal state.",),
                )
            reasons: tuple[RuntimeReason, ...] = tuple(
                RuntimeReason(code=finding.code, message=finding.message, field=finding.field)
                for finding in execution.findings
                if finding.severity is ReviewFindingSeverity.BLOCKING
            )
            status = DispatchStatus.DISPATCHED if execution.final_status is not ExecutionStatus.BLOCKED else DispatchStatus.REJECTED
            if execution.final_status is ExecutionStatus.FAILED:
                status = DispatchStatus.REJECTED
            dispatch = DispatchResult(
                target=self.request.target,
                status=status,
                mode=self.request.mode,
                payload=payload,
                reasons=reasons,
                executor=prepared.executor,
                requirements=prepared.requirements,
                execution_metadata={
                    "run_id": handle.run_id,
                    "submitted_at": handle.submitted_at.isoformat(),
                    "poll_status": poll_result.status,
                    "handle_metadata": handle.metadata,
                    "required_capabilities": list(prepared.requirements.required_capabilities()),
                    "execution_final_status": execution.final_status.value,
                },
            )

        transition = executor_dispatch_transition(dispatch, execution)
        issues = transition.issues
        if execution is not None and execution.final_status in {ExecutionStatus.FAILED, ExecutionStatus.BLOCKED}:
            issues = transition.issues + tuple(
                RuntimeReason(code=finding.code, message=finding.message, field=finding.field)
                for finding in execution.findings
                if finding.severity is ReviewFindingSeverity.BLOCKING
            )
        result = RunResult(
            node_name=self.name,
            success=(
                dispatch.status in {DispatchStatus.PREVIEWED, DispatchStatus.DISPATCHED}
                and (execution is None or execution.final_status not in {ExecutionStatus.FAILED, ExecutionStatus.BLOCKED})
            ),
            from_state=transition.from_state,
            to_state=transition.to_state,
            issues=issues,
            spec_path=checked_spec.spec_path,
            dispatch=dispatch,
            execution=execution,
        )
        log_path = adapter.build_run_log_path(self.name)
        result = result.with_log_path(log_path)
        adapter.write_json(log_path, result.to_log_record(adapter))
        return result
