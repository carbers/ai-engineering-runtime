from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_engineering_runtime.adapters import FileSystemAdapter
from ai_engineering_runtime.engine import RunResult
from ai_engineering_runtime.run_summary import resolve_summary_query
from ai_engineering_runtime.state import WorkflowState


@dataclass(frozen=True)
class RunSummaryRequest:
    log_path: Path | None = None
    run_id: str | None = None
    latest: bool = False
    node_name: str | None = None
    json_output: bool = False


class RunSummaryNode:
    name = "run-summary"

    def __init__(self, request: RunSummaryRequest):
        self.request = request

    def execute(self, adapter: FileSystemAdapter) -> RunResult:
        summary, reasons = resolve_summary_query(
            adapter,
            log_path=self.request.log_path,
            run_id=self.request.run_id,
            latest=self.request.latest,
            node_name=self.request.node_name,
        )
        success = summary is not None
        state = WorkflowState.COMPLETE if success else WorkflowState.BLOCKED
        result = RunResult(
            node_name=self.name,
            success=success,
            from_state=state,
            to_state=state,
            issues=reasons,
            summary=summary,
            rendered_output=summary.to_json(adapter.display_path) if success and self.request.json_output else None,
            metadata={
                "selection": "latest" if self.request.latest else "explicit",
                "node_filter": self.request.node_name,
                "summary_output_format": "json" if self.request.json_output else "text",
            },
        )
        log_path = adapter.build_run_log_path(self.name)
        result = result.with_log_path(log_path)
        adapter.write_json(log_path, result.to_log_record(adapter))
        return result
