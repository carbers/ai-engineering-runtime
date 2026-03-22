from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from ai_engineering_runtime.history_selection import HistorySelectionResult
from ai_engineering_runtime.run_logs import ReplayResult
from ai_engineering_runtime.followup_package import FollowupPackage
from ai_engineering_runtime.gate_evaluator import NodeGateResult
from ai_engineering_runtime.run_summary import RunSummary
from ai_engineering_runtime.state import (
    DispatchResult,
    FollowupResult,
    ReadinessResult,
    RuntimeReason,
    ValidationResult,
    WorkflowState,
    WritebackResult,
)
from ai_engineering_runtime.validation_rollup import ValidationRollup
from ai_engineering_runtime.writeback_package import WritebackPackage

if TYPE_CHECKING:
    from ai_engineering_runtime.adapters import FileSystemAdapter


class RuntimeNode(Protocol):
    name: str

    def execute(self, adapter: "FileSystemAdapter") -> "RunResult":
        ...


@dataclass(frozen=True)
class RunResult:
    node_name: str
    success: bool
    from_state: WorkflowState
    to_state: WorkflowState
    issues: tuple[RuntimeReason, ...] = ()
    readiness: ReadinessResult | None = None
    validation: ValidationResult | None = None
    writeback: WritebackResult | None = None
    followup: FollowupResult | None = None
    dispatch: DispatchResult | None = None
    replay: ReplayResult | None = None
    history_selection: HistorySelectionResult | None = None
    summary: RunSummary | None = None
    gate: NodeGateResult | None = None
    validation_rollup: ValidationRollup | None = None
    writeback_package: WritebackPackage | None = None
    followup_package: FollowupPackage | None = None
    plan_path: Path | None = None
    spec_path: Path | None = None
    output_path: Path | None = None
    log_path: Path | None = None
    rendered_output: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def with_log_path(self, log_path: Path) -> "RunResult":
        return replace(self, log_path=log_path)

    def to_log_record(self, adapter: "FileSystemAdapter") -> dict[str, object]:
        return {
            "node": self.node_name,
            "success": self.success,
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "plan_path": adapter.display_path(self.plan_path) if self.plan_path else None,
            "spec_path": adapter.display_path(self.spec_path) if self.spec_path else None,
            "output_path": adapter.display_path(self.output_path) if self.output_path else None,
            "log_path": adapter.display_path(self.log_path) if self.log_path else None,
            "issues": [issue.to_record() for issue in self.issues],
            "readiness": self.readiness.to_record() if self.readiness is not None else None,
            "validation": self.validation.to_record() if self.validation is not None else None,
            "writeback": self.writeback.to_record() if self.writeback is not None else None,
            "followup": self.followup.to_record() if self.followup is not None else None,
            "dispatch": self.dispatch.to_record() if self.dispatch is not None else None,
            "replay": self.replay.to_record(adapter.display_path) if self.replay is not None else None,
            "history_selection": (
                self.history_selection.to_record(adapter.display_path)
                if self.history_selection is not None
                else None
            ),
            "summary": self.summary.to_record(adapter.display_path) if self.summary is not None else None,
            "gate": self.gate.to_record() if self.gate is not None else None,
            "validation_rollup": (
                self.validation_rollup.to_record() if self.validation_rollup is not None else None
            ),
            "writeback_package": (
                self.writeback_package.to_record() if self.writeback_package is not None else None
            ),
            "followup_package": (
                self.followup_package.to_record() if self.followup_package is not None else None
            ),
            "metadata": self.metadata,
            "rendered_output": self.rendered_output,
        }


class RuntimeEngine:
    def __init__(self, adapter: "FileSystemAdapter"):
        self.adapter = adapter

    def run(self, node: RuntimeNode) -> RunResult:
        result = node.execute(self.adapter)
        if result.log_path is not None:
            from ai_engineering_runtime.run_summary import materialize_summary_for_result

            materialize_summary_for_result(self.adapter, result)
        return result
