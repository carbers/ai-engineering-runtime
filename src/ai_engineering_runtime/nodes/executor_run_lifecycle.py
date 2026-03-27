from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
from typing import Callable

from ai_engineering_runtime.adapters import (
    ExecutorAdapter,
    ExecutorRunHandle,
    PreparedDispatch,
    build_executor_adapter,
)
from ai_engineering_runtime.engine import RunResult
from ai_engineering_runtime.run_logs import RunRecordStatus, load_run_record
from ai_engineering_runtime.runtime_queries import missing_run_log_reasons, resolve_run_log_query
from ai_engineering_runtime.state import (
    DispatchPayload,
    ExecutionResult,
    ExecutionStatus,
    ExecutorLifecycleAction,
    ExecutorRequirements,
    ExecutorTarget,
    RuntimeReason,
    WorkflowState,
    executor_run_lifecycle_transition,
)
from ai_engineering_runtime.run_logs import ArtifactTargetKind


@dataclass(frozen=True)
class ExecutorRunLifecycleRequest:
    log_path: Path | None = None
    run_id: str | None = None
    latest: bool = False
    node_name: str | None = None
    action: ExecutorLifecycleAction = ExecutorLifecycleAction.POLL


class ExecutorRunLifecycleNode:
    name = "executor-run-lifecycle"

    def __init__(
        self,
        request: ExecutorRunLifecycleRequest,
        executor_factory: Callable[[ExecutorTarget], ExecutorAdapter] | None = None,
    ):
        self.request = request
        self.executor_factory = executor_factory or build_executor_adapter

    def execute(self, adapter) -> RunResult:
        selected_log = resolve_run_log_query(
            adapter,
            log_path=self.request.log_path,
            run_id=self.request.run_id,
            latest=self.request.latest,
            node_name=self.request.node_name,
        )
        if selected_log is None:
            return self._reject(
                adapter,
                reasons=missing_run_log_reasons(
                    log_path=self.request.log_path,
                    run_id=self.request.run_id,
                    latest=self.request.latest,
                    node_name=self.request.node_name,
                ),
                metadata={},
            )

        record = load_run_record(selected_log)
        if record.status is not RunRecordStatus.LOADABLE:
            return self._reject(adapter, reasons=record.reasons, metadata={"source_run_id": selected_log.stem})
        if record.dispatch is None:
            return self._reject(
                adapter,
                reasons=(
                    RuntimeReason(
                        code="missing-dispatch-result",
                        message="The selected run log does not contain a dispatch result payload.",
                        field="dispatch",
                    ),
                ),
                metadata={"source_run_id": selected_log.stem},
            )
        if record.execution is None:
            return self._reject(
                adapter,
                reasons=(
                    RuntimeReason(
                        code="missing-execution-result",
                        message="The selected run log does not contain an execution result payload.",
                        field="execution",
                    ),
                ),
                metadata={"source_run_id": selected_log.stem},
                spec_path=None,
            )

        executor = self.executor_factory(record.dispatch.target)
        handle = executor.restore_handle(record.dispatch)
        if handle is None:
            return self._reject(
                adapter,
                reasons=(
                    RuntimeReason(
                        code="missing-executor-handle",
                        message="The selected run log does not preserve enough executor handle data to revisit the run.",
                        field="dispatch.execution_metadata",
                    ),
                ),
                metadata={"source_run_id": selected_log.stem},
            )

        if self.request.action is ExecutorLifecycleAction.RESUME and not executor.descriptor.capabilities.supports_resume:
            return self._reject(
                adapter,
                reasons=(
                    RuntimeReason(
                        code="executor-resume-unsupported",
                        message=f"Executor {executor.descriptor.name} does not support resume for previously submitted runs.",
                        field="action",
                    ),
                ),
                metadata={"source_run_id": selected_log.stem},
            )

        poll_result = (
            executor.resume(handle)
            if self.request.action is ExecutorLifecycleAction.RESUME
            else executor.poll(handle)
        )
        prepared = _prepared_dispatch_from_record(record)
        if poll_result.is_terminal:
            collected = executor.collect(handle)
            execution = executor.normalize(prepared, handle, poll_result, collected)
        else:
            summary = poll_result.summary or f"Executor run {handle.run_id} is still in progress ({poll_result.status})."
            suggested_followups = record.execution.suggested_followups
            if "Poll or resume the executor run after it reaches a terminal state." not in suggested_followups:
                suggested_followups = (
                    *suggested_followups,
                    "Poll or resume the executor run after it reaches a terminal state.",
                )
            execution = replace(
                record.execution,
                executor=prepared.executor,
                spec_identity=prepared.spec_identity,
                dispatch_summary=prepared.payload_summary.to_record(),
                final_status=ExecutionStatus.RUNNING,
                summary=summary,
                log_summary=poll_result.summary,
                suggested_followups=suggested_followups,
            )

        transition = executor_run_lifecycle_transition(execution)
        issues = transition.issues
        result = RunResult(
            node_name=self.name,
            success=execution.final_status not in {ExecutionStatus.FAILED, ExecutionStatus.BLOCKED},
            from_state=transition.from_state,
            to_state=transition.to_state,
            issues=issues,
            spec_path=adapter.resolve(spec_path) if (spec_path := _spec_path_from_record(record)) is not None else None,
            dispatch=record.dispatch,
            execution=execution,
            metadata={
                "source_run_id": selected_log.stem,
                "source_log_path": adapter.display_path(selected_log),
                "executor_lifecycle_action": self.request.action.value,
                "poll_status": poll_result.status,
                "handle_run_id": handle.run_id,
            },
        )
        log_path = adapter.build_run_log_path(self.name)
        result = result.with_log_path(log_path)
        adapter.write_json(log_path, result.to_log_record(adapter))
        return result

    def _reject(
        self,
        adapter,
        *,
        reasons: tuple[RuntimeReason, ...],
        metadata: dict[str, object],
        spec_path: Path | None = None,
    ) -> RunResult:
        result = RunResult(
            node_name=self.name,
            success=False,
            from_state=WorkflowState.BLOCKED,
            to_state=WorkflowState.BLOCKED,
            issues=reasons,
            spec_path=spec_path,
            metadata={
                **metadata,
                "executor_lifecycle_action": self.request.action.value,
            },
        )
        log_path = adapter.build_run_log_path(self.name)
        result = result.with_log_path(log_path)
        adapter.write_json(log_path, result.to_log_record(adapter))
        return result


def _prepared_dispatch_from_record(record) -> PreparedDispatch:
    dispatch = record.dispatch
    execution = record.execution
    if dispatch is None:
        raise ValueError("Prepared dispatch reconstruction requires a dispatch result.")
    payload = dispatch.payload or DispatchPayload(title="Executor Run", goal="Revisit executor run.", in_scope=(), done_when="Run lifecycle revisited.")
    spec_identity = execution.spec_identity if execution is not None else None
    if spec_identity is None:
        spec_path = _spec_path_from_record(record)
        if spec_path is not None:
            spec_identity = spec_path.as_posix()
    return PreparedDispatch(
        target=dispatch.target,
        mode=dispatch.mode,
        spec_identity=spec_identity or "unknown-spec",
        executor=dispatch.executor or build_executor_adapter(dispatch.target).descriptor,
        requirements=dispatch.requirements or ExecutorRequirements(),
        payload_summary=payload,
        payload_body={},
        context_summary={},
    )


def _spec_path_from_record(record) -> Path | None:
    if record.artifact_target is None or record.artifact_target.kind is not ArtifactTargetKind.SPEC:
        return None
    return Path(record.artifact_target.path)
