from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_engineering_runtime.adapters import FileSystemAdapter
from ai_engineering_runtime.engine import RunResult
from ai_engineering_runtime.gate_evaluator import evaluate_node_gate
from ai_engineering_runtime.run_summary import resolve_summary_query
from ai_engineering_runtime.state import WorkflowState


@dataclass(frozen=True)
class NodeGateRequest:
    node_name: str
    log_path: Path | None = None
    run_id: str | None = None
    latest: bool = False
    summary_node_name: str | None = None
    json_output: bool = False


class NodeGateNode:
    name = "node-gate"

    def __init__(self, request: NodeGateRequest):
        self.request = request

    def execute(self, adapter: FileSystemAdapter) -> RunResult:
        summary, reasons = resolve_summary_query(
            adapter,
            log_path=self.request.log_path,
            run_id=self.request.run_id,
            latest=self.request.latest,
            node_name=self.request.summary_node_name,
        )
        if summary is None:
            result = RunResult(
                node_name=self.name,
                success=False,
                from_state=WorkflowState.BLOCKED,
                to_state=WorkflowState.BLOCKED,
                issues=reasons,
                metadata={
                    "evaluated_node": self.request.node_name,
                    "summary_output_format": "json" if self.request.json_output else "text",
                },
            )
            log_path = adapter.build_run_log_path(self.name)
            result = result.with_log_path(log_path)
            adapter.write_json(log_path, result.to_log_record(adapter))
            return result

        gate = evaluate_node_gate(
            adapter,
            node_name=self.request.node_name,
            summary=summary,
        )
        result = RunResult(
            node_name=self.name,
            success=True,
            from_state=WorkflowState.COMPLETE,
            to_state=WorkflowState.COMPLETE,
            gate=gate,
            rendered_output=gate.to_json() if self.request.json_output else None,
            metadata={
                "evaluated_node": self.request.node_name,
                "summary_output_format": "json" if self.request.json_output else "text",
            },
        )
        log_path = adapter.build_run_log_path(self.name)
        result = result.with_log_path(log_path)
        adapter.write_json(log_path, result.to_log_record(adapter))
        return result
