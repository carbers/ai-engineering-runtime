from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable

from ai_engineering_runtime.run_logs import ReplayResult, ReplaySignalKind


class ProjectedSignalKey(str, Enum):
    READINESS_STATUS = "readiness_status"
    VALIDATION_STATUS = "validation_status"
    WRITEBACK_DESTINATION = "writeback_destination"
    FOLLOWUP_ACTION = "followup_action"
    DISPATCH_STATUS = "dispatch_status"


_SIGNAL_KEY_MAP: dict[ReplaySignalKind, ProjectedSignalKey] = {
    ReplaySignalKind.READINESS: ProjectedSignalKey.READINESS_STATUS,
    ReplaySignalKind.VALIDATION: ProjectedSignalKey.VALIDATION_STATUS,
    ReplaySignalKind.WRITEBACK: ProjectedSignalKey.WRITEBACK_DESTINATION,
    ReplaySignalKind.FOLLOWUP: ProjectedSignalKey.FOLLOWUP_ACTION,
    ReplaySignalKind.DISPATCH: ProjectedSignalKey.DISPATCH_STATUS,
}


@dataclass(frozen=True)
class ProjectedSignal:
    key: ProjectedSignalKey
    value: str
    source_log_path: Path
    ordered_at: datetime
    node_name: str

    def to_record(self, display_path: Callable[[Path], str]) -> dict[str, str]:
        return {
            "key": self.key.value,
            "value": self.value,
            "source_log_path": display_path(self.source_log_path),
            "ordered_at": self.ordered_at.isoformat(),
            "node": self.node_name,
        }


@dataclass(frozen=True)
class HistorySignalProjection:
    source_count: int
    signals: tuple[ProjectedSignal, ...] = ()

    def get(self, key: ProjectedSignalKey) -> ProjectedSignal | None:
        for signal in self.signals:
            if signal.key is key:
                return signal
        return None

    def to_record(self, display_path: Callable[[Path], str]) -> dict[str, object]:
        return {
            "source_count": self.source_count,
            "signals": [signal.to_record(display_path) for signal in self.signals],
        }


def project_history_signals(matches: Iterable[ReplayResult]) -> HistorySignalProjection:
    ordered_matches = tuple(matches)
    projected: dict[ProjectedSignalKey, ProjectedSignal] = {}
    for match in ordered_matches:
        if (
            match.signal_kind is None
            or match.signal_value is None
            or match.source_log_path is None
            or match.ordered_at is None
            or match.node_name is None
        ):
            continue
        key = _SIGNAL_KEY_MAP.get(match.signal_kind)
        if key is None or key in projected:
            continue
        projected[key] = ProjectedSignal(
            key=key,
            value=match.signal_value,
            source_log_path=match.source_log_path,
            ordered_at=match.ordered_at,
            node_name=match.node_name,
        )

    ordered_signals = tuple(projected[key] for key in ProjectedSignalKey if key in projected)
    return HistorySignalProjection(
        source_count=len(ordered_matches),
        signals=ordered_signals,
    )
