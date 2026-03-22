from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class WorkflowState(str, Enum):
    PLANNING = "planning"
    SPEC_READY = "spec-ready"
    EXECUTING = "executing"
    VALIDATING = "validating"
    WRITEBACK_REVIEW = "writeback-review"
    COMPLETE = "complete"
    BLOCKED = "blocked"


class ReadinessStatus(str, Enum):
    READY = "ready"
    NEEDS_CLARIFICATION = "needs_clarification"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ReadinessIssue:
    code: str
    message: str
    field: str | None = None

    def to_record(self) -> dict[str, str]:
        payload = {
            "code": self.code,
            "message": self.message,
        }
        if self.field is not None:
            payload["field"] = self.field
        return payload


@dataclass(frozen=True)
class ReadinessResult:
    status: ReadinessStatus
    reasons: tuple[ReadinessIssue, ...] = ()

    @property
    def is_ready(self) -> bool:
        return self.status is ReadinessStatus.READY

    def to_record(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "eligible_for_plan_to_spec": self.is_ready,
            "reasons": [reason.to_record() for reason in self.reasons],
        }


@dataclass(frozen=True)
class TransitionResult:
    from_state: WorkflowState
    to_state: WorkflowState
    issues: tuple[ReadinessIssue, ...]


def plan_to_spec_transition(readiness: ReadinessResult) -> TransitionResult:
    state_map = {
        ReadinessStatus.READY: WorkflowState.SPEC_READY,
        ReadinessStatus.NEEDS_CLARIFICATION: WorkflowState.PLANNING,
        ReadinessStatus.BLOCKED: WorkflowState.BLOCKED,
    }
    return TransitionResult(
        from_state=WorkflowState.PLANNING,
        to_state=state_map[readiness.status],
        issues=readiness.reasons,
    )
