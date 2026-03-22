from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_engineering_runtime.adapters import FileSystemAdapter
from ai_engineering_runtime.engine import RunResult
from ai_engineering_runtime.history_selection import HistorySelectionStatus, select_correlated_history
from ai_engineering_runtime.run_logs import ArtifactTargetKind, ReplaySignalKind
from ai_engineering_runtime.state import RuntimeReason, WorkflowState


@dataclass(frozen=True)
class RunHistorySelectRequest:
    artifact_kind: ArtifactTargetKind
    artifact_path: Path
    node_name: str | None = None
    signal_kind: ReplaySignalKind | None = None
    limit: int = 5


class RunHistorySelectNode:
    name = "run-history-select"

    def __init__(self, request: RunHistorySelectRequest):
        self.request = request

    def execute(self, adapter: FileSystemAdapter) -> RunResult:
        if self.request.limit < 1:
            result = RunResult(
                node_name=self.name,
                success=False,
                from_state=WorkflowState.BLOCKED,
                to_state=WorkflowState.BLOCKED,
                issues=(
                    RuntimeReason(
                        code="invalid-history-limit",
                        message="History selection limit must be at least 1.",
                        field="limit",
                    ),
                ),
                spec_path=adapter.resolve(self.request.artifact_path)
                if self.request.artifact_kind is ArtifactTargetKind.SPEC
                else None,
                plan_path=adapter.resolve(self.request.artifact_path)
                if self.request.artifact_kind is ArtifactTargetKind.PLAN
                else None,
                output_path=adapter.resolve(self.request.artifact_path)
                if self.request.artifact_kind is ArtifactTargetKind.OUTPUT
                else None,
                metadata={"limit": self.request.limit},
            )
            log_path = adapter.build_run_log_path(self.name)
            result = result.with_log_path(log_path)
            adapter.write_json(log_path, result.to_log_record(adapter))
            return result

        selection = select_correlated_history(
            adapter.repo_root,
            artifact_kind=self.request.artifact_kind,
            artifact_path=self.request.artifact_path,
            node_name=self.request.node_name,
            signal_kind=self.request.signal_kind,
            limit=self.request.limit,
        )
        state = WorkflowState.COMPLETE if selection.status is HistorySelectionStatus.SELECTED else WorkflowState.BLOCKED
        result = RunResult(
            node_name=self.name,
            success=selection.status is HistorySelectionStatus.SELECTED,
            from_state=state,
            to_state=state,
            issues=selection.reasons,
            history_selection=selection,
            spec_path=adapter.resolve(self.request.artifact_path)
            if self.request.artifact_kind is ArtifactTargetKind.SPEC
            else None,
            plan_path=adapter.resolve(self.request.artifact_path)
            if self.request.artifact_kind is ArtifactTargetKind.PLAN
            else None,
            output_path=adapter.resolve(self.request.artifact_path)
            if self.request.artifact_kind is ArtifactTargetKind.OUTPUT
            else None,
            metadata={
                "limit": self.request.limit,
                "node_filter": self.request.node_name,
                "signal_kind": self.request.signal_kind.value if self.request.signal_kind is not None else None,
            },
        )
        log_path = adapter.build_run_log_path(self.name)
        result = result.with_log_path(log_path)
        adapter.write_json(log_path, result.to_log_record(adapter))
        return result
