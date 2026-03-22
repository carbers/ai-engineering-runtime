from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

from ai_engineering_runtime.run_logs import (
    ArtifactTargetKind,
    ReplayResult,
    ReplaySignalKind,
    ReplayStatus,
    discover_run_logs,
    load_replay_result,
)
from ai_engineering_runtime.state import RuntimeReason


class HistorySelectionStatus(str, Enum):
    SELECTED = "selected"
    NO_MATCH = "no_match"


@dataclass(frozen=True)
class HistorySelectionResult:
    status: HistorySelectionStatus
    matches: tuple[ReplayResult, ...] = ()
    selection_basis: tuple[str, ...] = ()
    reasons: tuple[RuntimeReason, ...] = ()

    @property
    def is_selected(self) -> bool:
        return self.status is HistorySelectionStatus.SELECTED

    def to_record(self, display_path: Callable[[Path], str]) -> dict[str, object]:
        return {
            "status": self.status.value,
            "selection_basis": list(self.selection_basis),
            "matches": [match.to_record(display_path) for match in self.matches],
            "reasons": [reason.to_record() for reason in self.reasons],
        }


def select_correlated_history(
    repo_root: Path,
    *,
    artifact_kind: ArtifactTargetKind,
    artifact_path: Path | str,
    node_name: str | None = None,
    signal_kind: ReplaySignalKind | None = None,
    limit: int = 5,
    exclude_log_path: Path | None = None,
) -> HistorySelectionResult:
    normalized_target = normalize_artifact_selector(repo_root, artifact_path)
    selection_basis = build_selection_basis(
        artifact_kind=artifact_kind,
        artifact_path=normalized_target,
        node_name=node_name,
        signal_kind=signal_kind,
        limit=limit,
    )
    if limit < 1:
        return HistorySelectionResult(
            status=HistorySelectionStatus.NO_MATCH,
            selection_basis=selection_basis,
            reasons=(
                RuntimeReason(
                    code="invalid-history-limit",
                    message="History selection limit must be at least 1.",
                    field="limit",
                ),
            ),
        )

    ignored_log = exclude_log_path.resolve() if exclude_log_path is not None else None
    matches: list[ReplayResult] = []
    discovered = discover_run_logs(repo_root, node_name=node_name)
    for log_path in reversed(discovered):
        resolved = log_path.resolve()
        if ignored_log is not None and resolved == ignored_log:
            continue

        replay = load_replay_result(resolved)
        if replay.status is not ReplayStatus.REPLAYABLE:
            continue
        if replay.artifact_target is None:
            continue
        if replay.artifact_target.kind is not artifact_kind:
            continue
        if replay.artifact_target.path != normalized_target:
            continue
        if signal_kind is not None and replay.signal_kind is not signal_kind:
            continue
        matches.append(replay)
        if len(matches) >= limit:
            break

    if matches:
        return HistorySelectionResult(
            status=HistorySelectionStatus.SELECTED,
            matches=tuple(matches),
            selection_basis=selection_basis,
        )

    return HistorySelectionResult(
        status=HistorySelectionStatus.NO_MATCH,
        selection_basis=selection_basis,
        reasons=(
            RuntimeReason(
                code="no-correlated-history-match",
                message=(
                    "No replayable prior runs matched the exact selector: "
                    f"{artifact_kind.value} {normalized_target}"
                ),
                field="artifact_path",
            ),
        ),
    )


def normalize_artifact_selector(repo_root: Path, artifact_path: Path | str) -> str:
    raw_path = Path(artifact_path)
    if raw_path.is_absolute():
        resolved = raw_path.resolve()
    else:
        resolved = (repo_root.resolve() / raw_path).resolve()
    try:
        return resolved.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def build_selection_basis(
    *,
    artifact_kind: ArtifactTargetKind,
    artifact_path: str,
    node_name: str | None,
    signal_kind: ReplaySignalKind | None,
    limit: int,
) -> tuple[str, ...]:
    basis = [f"{artifact_kind.value}:{artifact_path}", f"limit:{limit}"]
    if node_name is not None:
        basis.append(f"node:{node_name}")
    if signal_kind is not None:
        basis.append(f"signal:{signal_kind.value}")
    return tuple(basis)
