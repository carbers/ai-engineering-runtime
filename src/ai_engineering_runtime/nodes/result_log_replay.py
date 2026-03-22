from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_engineering_runtime.adapters import FileSystemAdapter
from ai_engineering_runtime.engine import RunResult
from ai_engineering_runtime.run_logs import (
    ReplayResult,
    ReplayStatus,
    load_replay_result,
    missing_selection_result,
    select_latest_run_log,
)
from ai_engineering_runtime.state import WorkflowState


@dataclass(frozen=True)
class ResultLogReplayRequest:
    log_path: Path | None = None
    latest: bool = False
    node_name: str | None = None


class ResultLogReplayNode:
    name = "result-log-replay"

    def __init__(self, request: ResultLogReplayRequest):
        self.request = request

    def execute(self, adapter: FileSystemAdapter) -> RunResult:
        replay = self._resolve_replay(adapter)
        success = replay.status is ReplayStatus.REPLAYABLE
        state = WorkflowState.COMPLETE if success else WorkflowState.BLOCKED
        result = RunResult(
            node_name=self.name,
            success=success,
            from_state=state,
            to_state=state,
            issues=replay.reasons,
            replay=replay,
            metadata={
                "selection": "latest" if self.request.latest else "explicit",
                "node_filter": self.request.node_name,
            },
        )
        log_path = adapter.build_run_log_path(self.name)
        result = result.with_log_path(log_path)
        adapter.write_json(log_path, result.to_log_record(adapter))
        return result

    def _resolve_replay(self, adapter: FileSystemAdapter) -> ReplayResult:
        if self.request.latest:
            selected_log = select_latest_run_log(adapter.repo_root, node_name=self.request.node_name)
            if selected_log is None:
                return missing_selection_result(node_name=self.request.node_name)
            return load_replay_result(selected_log)

        if self.request.log_path is None:
            return missing_selection_result(node_name=self.request.node_name)

        return load_replay_result(adapter.resolve(self.request.log_path))
