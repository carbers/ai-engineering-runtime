from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from ai_engineering_runtime.state import ReadinessIssue, WorkflowState

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
    issues: tuple[ReadinessIssue, ...] = ()
    plan_path: Path | None = None
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
            "output_path": adapter.display_path(self.output_path) if self.output_path else None,
            "log_path": adapter.display_path(self.log_path) if self.log_path else None,
            "issues": [{"code": issue.code, "message": issue.message} for issue in self.issues],
            "metadata": self.metadata,
            "rendered_output": self.rendered_output,
        }


class RuntimeEngine:
    def __init__(self, adapter: "FileSystemAdapter"):
        self.adapter = adapter

    def run(self, node: RuntimeNode) -> RunResult:
        return node.execute(self.adapter)
