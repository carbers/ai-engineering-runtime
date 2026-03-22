from __future__ import annotations

from pathlib import Path

from ai_engineering_runtime.adapters import FileSystemAdapter
from ai_engineering_runtime.run_logs import select_latest_run_log
from ai_engineering_runtime.state import RuntimeReason


def resolve_run_log_query(
    adapter: FileSystemAdapter,
    *,
    log_path: Path | None = None,
    run_id: str | None = None,
    latest: bool = False,
    node_name: str | None = None,
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


def missing_run_log_reasons(
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
