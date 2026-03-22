from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from ai_engineering_runtime.adapters import FileSystemAdapter
from ai_engineering_runtime.history_projection import (
    HistorySignalProjection,
    ProjectedSignal,
    ProjectedSignalKey,
    project_history_signals,
)
from ai_engineering_runtime.history_selection import select_correlated_history
from ai_engineering_runtime.run_logs import (
    ArtifactTarget,
    ArtifactTargetKind,
    RunRecordStatus,
    load_run_record,
    parse_run_log_name,
    select_latest_run_log,
)
from ai_engineering_runtime.state import RuntimeReason
from ai_engineering_runtime.terminal_state import TerminalState, TerminalStatus, resolve_terminal_state_for_record, resolve_terminal_state_for_result

if TYPE_CHECKING:
    from ai_engineering_runtime.engine import RunResult

_SUMMARY_VERSION = 1


@dataclass(frozen=True)
class RunSummaryHistory:
    match_count: int
    selection_basis: tuple[str, ...] = ()
    signals: tuple[ProjectedSignal, ...] = ()

    def to_record(self, display_path: Callable[[Path], str]) -> dict[str, object]:
        return {
            "match_count": self.match_count,
            "selection_basis": list(self.selection_basis),
            "signals": [signal.to_record(display_path) for signal in self.signals],
        }


@dataclass(frozen=True)
class RunSummary:
    version: int
    run_id: str
    node_name: str
    source_log_path: Path
    ordered_at: datetime | None
    success: bool
    artifact_target: ArtifactTarget | None
    terminal_state: TerminalState
    history: RunSummaryHistory | None = None

    def to_record(self, display_path: Callable[[Path], str]) -> dict[str, object]:
        return {
            "version": self.version,
            "run_id": self.run_id,
            "node": self.node_name,
            "source_log_path": display_path(self.source_log_path),
            "ordered_at": self.ordered_at.isoformat() if self.ordered_at is not None else None,
            "success": self.success,
            "artifact_target": self.artifact_target.to_record() if self.artifact_target is not None else None,
            "terminal_state": self.terminal_state.to_record(),
            "history": self.history.to_record(display_path) if self.history is not None else None,
        }

    def to_json(self, display_path: Callable[[Path], str]) -> str:
        return json.dumps(self.to_record(display_path), indent=2, sort_keys=True)

    @classmethod
    def from_record(cls, repo_root: Path, payload: dict[str, object]) -> "RunSummary" | None:
        if not isinstance(payload, dict):
            return None
        version = payload.get("version")
        run_id = payload.get("run_id")
        node_name = payload.get("node")
        source_log_path = payload.get("source_log_path")
        success = payload.get("success")
        terminal_payload = payload.get("terminal_state")
        if not isinstance(version, int):
            return None
        if not isinstance(run_id, str) or not isinstance(node_name, str) or not isinstance(source_log_path, str):
            return None
        if not isinstance(success, bool) or not isinstance(terminal_payload, dict):
            return None

        terminal_state = _terminal_state_from_payload(terminal_payload)
        if terminal_state is None:
            return None

        history = _history_from_payload(repo_root, payload.get("history"))
        artifact_target = _artifact_target_from_payload(payload.get("artifact_target"))
        ordered_at = _parse_datetime(payload.get("ordered_at"))
        return cls(
            version=version,
            run_id=run_id,
            node_name=node_name,
            source_log_path=(repo_root.resolve() / Path(source_log_path)).resolve(),
            ordered_at=ordered_at,
            success=success,
            artifact_target=artifact_target,
            terminal_state=terminal_state,
            history=history,
        )


def materialize_summary_for_result(adapter: FileSystemAdapter, result: "RunResult") -> RunSummary | None:
    if result.log_path is None:
        return None

    ordered = parse_run_log_name(result.log_path.name)
    ordered_at = ordered[0] if ordered is not None else None
    artifact_target = _artifact_target_from_result(adapter, result)
    history, projection = _history_and_projection(
        adapter,
        artifact_target=artifact_target,
        exclude_log_path=result.log_path,
    )
    summary = RunSummary(
        version=_SUMMARY_VERSION,
        run_id=result.log_path.stem,
        node_name=result.node_name,
        source_log_path=result.log_path,
        ordered_at=ordered_at,
        success=result.success,
        artifact_target=artifact_target,
        terminal_state=resolve_terminal_state_for_result(result, projection),
        history=history,
    )
    adapter.write_json(adapter.build_run_summary_path(summary.run_id), summary.to_record(adapter.display_path))
    return summary


def resolve_summary_query(
    adapter: FileSystemAdapter,
    *,
    log_path: Path | None = None,
    run_id: str | None = None,
    latest: bool = False,
    node_name: str | None = None,
) -> tuple[RunSummary | None, tuple[RuntimeReason, ...]]:
    selected_log = _resolve_query_log_path(
        adapter,
        log_path=log_path,
        run_id=run_id,
        latest=latest,
        node_name=node_name,
    )
    if selected_log is None:
        return None, _missing_log_reasons(log_path=log_path, run_id=run_id, latest=latest, node_name=node_name)

    summary_path = adapter.build_run_summary_path(selected_log.stem)
    if summary_path.exists():
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            loaded = RunSummary.from_record(adapter.repo_root, payload)
            if loaded is not None:
                return loaded, ()

    return materialize_summary_for_log(adapter, selected_log)


def materialize_summary_for_log(
    adapter: FileSystemAdapter,
    log_path: Path,
) -> tuple[RunSummary | None, tuple[RuntimeReason, ...]]:
    record = load_run_record(log_path)
    if record.status is not RunRecordStatus.LOADABLE:
        return None, record.reasons
    if record.source_log_path is None:
        return None, (
            RuntimeReason(
                code="missing-run-log",
                message="Run log source path is required for summary materialization.",
                field="log_path",
            ),
        )

    history, projection = _history_and_projection(
        adapter,
        artifact_target=record.artifact_target,
        exclude_log_path=record.source_log_path,
    )
    summary = RunSummary(
        version=_SUMMARY_VERSION,
        run_id=record.source_log_path.stem,
        node_name=record.node_name or record.source_log_path.stem,
        source_log_path=record.source_log_path,
        ordered_at=record.ordered_at,
        success=bool(record.success),
        artifact_target=record.artifact_target,
        terminal_state=resolve_terminal_state_for_record(record, projection),
        history=history,
    )
    adapter.write_json(adapter.build_run_summary_path(summary.run_id), summary.to_record(adapter.display_path))
    return summary, ()


def _history_and_projection(
    adapter: FileSystemAdapter,
    *,
    artifact_target: ArtifactTarget | None,
    exclude_log_path: Path | None,
) -> tuple[RunSummaryHistory | None, HistorySignalProjection | None]:
    if artifact_target is None:
        return None, None
    selection = select_correlated_history(
        adapter.repo_root,
        artifact_kind=artifact_target.kind,
        artifact_path=artifact_target.path,
        limit=5,
        exclude_log_path=exclude_log_path,
    )
    projection = project_history_signals(selection.matches)
    history = RunSummaryHistory(
        match_count=len(selection.matches),
        selection_basis=selection.selection_basis,
        signals=projection.signals,
    )
    return history, projection if selection.matches else None


def _resolve_query_log_path(
    adapter: FileSystemAdapter,
    *,
    log_path: Path | None,
    run_id: str | None,
    latest: bool,
    node_name: str | None,
) -> Path | None:
    if latest:
        return select_latest_run_log(adapter.repo_root, node_name=node_name)
    if run_id is not None:
        candidate = adapter.repo_root / ".runtime" / "runs" / f"{run_id}.json"
        return candidate.resolve() if candidate.exists() else None
    if log_path is None:
        return None
    candidate = adapter.resolve(log_path)
    return candidate if candidate.exists() else None


def _missing_log_reasons(
    *,
    log_path: Path | None,
    run_id: str | None,
    latest: bool,
    node_name: str | None,
) -> tuple[RuntimeReason, ...]:
    if latest:
        return (
            RuntimeReason(
                code="missing-run-log-selection",
                message=(
                    f"No run logs found under .runtime/runs/ for node: {node_name}"
                    if node_name is not None
                    else "No run logs found under .runtime/runs/."
                ),
                field="log_path",
            ),
        )
    if run_id is not None:
        return (
            RuntimeReason(
                code="missing-run-log",
                message=f"Run log not found for run id: {run_id}",
                field="run_id",
            ),
        )
    return (
        RuntimeReason(
            code="missing-run-log",
            message=f"Run log not found: {log_path}",
            field="log_path",
        ),
    )


def _artifact_target_from_result(adapter: FileSystemAdapter, result: "RunResult") -> ArtifactTarget | None:
    if result.spec_path is not None:
        return ArtifactTarget(ArtifactTargetKind.SPEC, adapter.display_path(result.spec_path))
    if result.plan_path is not None:
        return ArtifactTarget(ArtifactTargetKind.PLAN, adapter.display_path(result.plan_path))
    if result.output_path is not None:
        return ArtifactTarget(ArtifactTargetKind.OUTPUT, adapter.display_path(result.output_path))
    return None


def _artifact_target_from_payload(payload: object) -> ArtifactTarget | None:
    if not isinstance(payload, dict):
        return None
    kind = payload.get("kind")
    path = payload.get("path")
    if not isinstance(kind, str) or not isinstance(path, str):
        return None
    try:
        return ArtifactTarget(ArtifactTargetKind(kind), path)
    except ValueError:
        return None


def _history_from_payload(repo_root: Path, payload: object) -> RunSummaryHistory | None:
    if payload is None or not isinstance(payload, dict):
        return None
    match_count = payload.get("match_count")
    selection_basis = payload.get("selection_basis")
    signals = payload.get("signals")
    if not isinstance(match_count, int):
        return None
    if not isinstance(selection_basis, list) or not all(isinstance(item, str) for item in selection_basis):
        return None
    if not isinstance(signals, list) or not all(isinstance(item, dict) for item in signals):
        return None

    parsed_signals: list[ProjectedSignal] = []
    for item in signals:
        key = item.get("key")
        value = item.get("value")
        source_log_path = item.get("source_log_path")
        ordered_at = item.get("ordered_at")
        node_name = item.get("node")
        if not all(isinstance(entry, str) for entry in (key, value, source_log_path, ordered_at, node_name)):
            continue
        try:
            parsed_signals.append(
                ProjectedSignal(
                    key=ProjectedSignalKey(key),
                    value=value,
                    source_log_path=(repo_root.resolve() / Path(source_log_path)).resolve(),
                    ordered_at=datetime.fromisoformat(ordered_at),
                    node_name=node_name,
                )
            )
        except (TypeError, ValueError):
            continue
    return RunSummaryHistory(
        match_count=match_count,
        selection_basis=tuple(selection_basis),
        signals=tuple(parsed_signals),
    )


def _terminal_state_from_payload(payload: dict[str, object]) -> TerminalState | None:
    status = payload.get("status")
    workflow_state = payload.get("workflow_state")
    terminal_node = payload.get("terminal_node")
    stop_reason_code = payload.get("stop_reason_code")
    stop_reason_message = payload.get("stop_reason_message")
    signal_kind = payload.get("signal_kind")
    signal_value = payload.get("signal_value")
    if not isinstance(status, str):
        return None
    try:
        resolved_status = TerminalStatus(status)
    except ValueError:
        return None
    if workflow_state is not None and not isinstance(workflow_state, str):
        return None
    if terminal_node is not None and not isinstance(terminal_node, str):
        return None
    if stop_reason_code is not None and not isinstance(stop_reason_code, str):
        return None
    if stop_reason_message is not None and not isinstance(stop_reason_message, str):
        return None
    if signal_kind is not None and not isinstance(signal_kind, str):
        return None
    if signal_value is not None and not isinstance(signal_value, str):
        return None
    return TerminalState(
        status=resolved_status,
        workflow_state=workflow_state,
        terminal_node=terminal_node,
        stop_reason_code=stop_reason_code,
        stop_reason_message=stop_reason_message,
        signal_kind=signal_kind,
        signal_value=signal_value,
    )


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
