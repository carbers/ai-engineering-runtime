from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from ai_engineering_runtime.history_projection import HistorySignalProjection
from ai_engineering_runtime.run_logs import RunRecord
from ai_engineering_runtime.state import RuntimeReason

if TYPE_CHECKING:
    from ai_engineering_runtime.engine import RunResult


class TerminalStatus(str, Enum):
    PLANNING = "planning"
    READY = "ready"
    EXECUTING = "executing"
    REVIEW = "review"
    COMPLETE = "complete"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TerminalState:
    status: TerminalStatus
    workflow_state: str | None
    terminal_node: str | None
    stop_reason_code: str | None = None
    stop_reason_message: str | None = None
    signal_kind: str | None = None
    signal_value: str | None = None

    def to_record(self) -> dict[str, str | None]:
        return {
            "status": self.status.value,
            "workflow_state": self.workflow_state,
            "terminal_node": self.terminal_node,
            "stop_reason_code": self.stop_reason_code,
            "stop_reason_message": self.stop_reason_message,
            "signal_kind": self.signal_kind,
            "signal_value": self.signal_value,
        }


def resolve_terminal_state_for_result(
    result: "RunResult",
    projection: HistorySignalProjection | None = None,
) -> TerminalState:
    reason = _choose_reason(result.issues, _signal_reasons_for_result(result))
    signal_kind, signal_value = _signal_for_result(result)
    if signal_kind is None or signal_value is None:
        signal_kind, signal_value = _signal_from_projection(projection)
    return TerminalState(
        status=_map_workflow_state(result.to_state.value),
        workflow_state=result.to_state.value,
        terminal_node=result.node_name,
        stop_reason_code=reason.code,
        stop_reason_message=reason.message,
        signal_kind=signal_kind,
        signal_value=signal_value,
    )


def resolve_terminal_state_for_record(
    record: RunRecord,
    projection: HistorySignalProjection | None = None,
) -> TerminalState:
    reason = _choose_reason(record.issues, record.signal_reasons)
    signal_kind = record.signal_kind.value if record.signal_kind is not None else None
    signal_value = record.signal_value
    if signal_kind is None or signal_value is None:
        signal_kind, signal_value = _signal_from_projection(projection)
    return TerminalState(
        status=_map_workflow_state(record.to_state),
        workflow_state=record.to_state,
        terminal_node=record.node_name,
        stop_reason_code=reason.code,
        stop_reason_message=reason.message,
        signal_kind=signal_kind,
        signal_value=signal_value,
    )


def _choose_reason(
    primary_reasons: tuple[RuntimeReason, ...],
    signal_reasons: tuple[RuntimeReason, ...],
) -> RuntimeReason:
    if primary_reasons:
        return primary_reasons[0]
    if signal_reasons:
        return signal_reasons[0]
    return RuntimeReason(
        code="workflow-state-fallback",
        message="Terminal state resolved from workflow state without a more specific reason.",
    )


def _signal_for_result(result: "RunResult") -> tuple[str | None, str | None]:
    if result.readiness is not None:
        return "readiness", result.readiness.status.value
    if result.validation is not None:
        return "validation", result.validation.status.value
    if result.writeback is not None:
        return "writeback", result.writeback.destination.value
    if result.followup is not None:
        return "followup", result.followup.action.value
    if result.dispatch is not None:
        return "dispatch", result.dispatch.status.value
    if result.replay is not None and result.replay.signal_kind is not None and result.replay.signal_value is not None:
        return result.replay.signal_kind.value, result.replay.signal_value
    return None, None


def _signal_reasons_for_result(result: "RunResult") -> tuple[RuntimeReason, ...]:
    if result.readiness is not None:
        return result.readiness.reasons
    if result.validation is not None:
        return result.validation.reasons
    if result.writeback is not None:
        return result.writeback.reasons
    if result.followup is not None:
        return result.followup.reasons
    if result.dispatch is not None:
        return result.dispatch.reasons
    if result.replay is not None:
        return result.replay.reasons
    return ()


def _signal_from_projection(
    projection: HistorySignalProjection | None,
) -> tuple[str | None, str | None]:
    if projection is None or not projection.signals:
        return None, None
    latest = projection.signals[0]
    return latest.key.value, latest.value


def _map_workflow_state(workflow_state: str | None) -> TerminalStatus:
    mapping = {
        "planning": TerminalStatus.PLANNING,
        "spec-ready": TerminalStatus.READY,
        "executing": TerminalStatus.EXECUTING,
        "writeback-review": TerminalStatus.REVIEW,
        "complete": TerminalStatus.COMPLETE,
        "blocked": TerminalStatus.BLOCKED,
    }
    return mapping.get(workflow_state or "", TerminalStatus.UNKNOWN)
