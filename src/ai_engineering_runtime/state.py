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


@dataclass(frozen=True)
class ReadinessIssue:
    code: str
    message: str


@dataclass(frozen=True)
class TransitionResult:
    from_state: WorkflowState
    to_state: WorkflowState
    issues: tuple[ReadinessIssue, ...]


def plan_to_spec_transition(issues: list[ReadinessIssue]) -> TransitionResult:
    return TransitionResult(
        from_state=WorkflowState.PLANNING,
        to_state=WorkflowState.BLOCKED if issues else WorkflowState.SPEC_READY,
        issues=tuple(issues),
    )
