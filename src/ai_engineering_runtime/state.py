from __future__ import annotations

from dataclasses import dataclass, field
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
class RuntimeReason:
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


ReadinessIssue = RuntimeReason


@dataclass(frozen=True)
class ReadinessResult:
    status: ReadinessStatus
    reasons: tuple[RuntimeReason, ...] = ()

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
    issues: tuple[RuntimeReason, ...]


class WritebackDestination(str, Enum):
    FACTS = "facts"
    SKILLS = "skills"
    CHANGE_SUMMARY_ONLY = "change_summary_only"
    IGNORE = "ignore"


class WritebackCandidateKind(str, Enum):
    PROJECT_CONTEXT = "project_context"
    WORKFLOW_PATTERN = "workflow_pattern"
    DELIVERY_DETAIL = "delivery_detail"
    TRANSIENT_DETAIL = "transient_detail"


@dataclass(frozen=True)
class WritebackResult:
    destination: WritebackDestination
    should_write_back: bool
    reasons: tuple[RuntimeReason, ...] = ()
    candidate_kind: WritebackCandidateKind | None = None

    def to_record(self) -> dict[str, object]:
        return {
            "destination": self.destination.value,
            "should_write_back": self.should_write_back,
            "candidate_kind": self.candidate_kind.value if self.candidate_kind is not None else None,
            "reasons": [reason.to_record() for reason in self.reasons],
        }


class ValidationStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    INCOMPLETE = "incomplete"


class ValidationEvidenceStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    INCOMPLETE = "incomplete"
    NOTED = "noted"


class ValidationEvidenceKind(str, Enum):
    COMMAND = "command"
    BLACK_BOX = "black_box"
    WHITE_BOX = "white_box"
    MANUAL_NOTE = "manual_note"


@dataclass(frozen=True)
class ValidationEvidence:
    kind: ValidationEvidenceKind
    status: ValidationEvidenceStatus
    summary: str
    source: str | None = None

    def to_record(self) -> dict[str, str]:
        payload = {
            "kind": self.kind.value,
            "status": self.status.value,
            "summary": self.summary,
        }
        if self.source is not None:
            payload["source"] = self.source
        return payload


@dataclass(frozen=True)
class ValidationResult:
    status: ValidationStatus
    evidence: tuple[ValidationEvidence, ...] = ()
    reasons: tuple[RuntimeReason, ...] = ()

    def to_record(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "evidence": [entry.to_record() for entry in self.evidence],
            "reasons": [reason.to_record() for reason in self.reasons],
        }


class FollowupAction(str, Enum):
    IMPLEMENT_NEXT_TASK = "implement_next_task"
    CLARIFY_PLAN = "clarify_plan"
    FIX_VALIDATION_FAILURE = "fix_validation_failure"
    WRITE_BACK_STABLE_CONTEXT = "write_back_stable_context"
    PROMOTE_SKILL_CANDIDATE = "promote_skill_candidate"
    NO_FOLLOWUP_NEEDED = "no_followup_needed"


class CloseoutHint(str, Enum):
    COMPLETE = "complete"


@dataclass(frozen=True)
class FollowupResult:
    action: FollowupAction
    explanation: str
    reasons: tuple[RuntimeReason, ...] = ()

    def to_record(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "explanation": self.explanation,
            "reasons": [reason.to_record() for reason in self.reasons],
        }


class ExecutorTarget(str, Enum):
    SHELL = "shell"


class DispatchMode(str, Enum):
    PREVIEW = "preview"
    ECHO = "echo"


class DispatchStatus(str, Enum):
    PREVIEWED = "previewed"
    DISPATCHED = "dispatched"
    REJECTED = "rejected"


@dataclass(frozen=True)
class DispatchPayload:
    title: str
    goal: str
    in_scope: tuple[str, ...]
    done_when: str

    def to_record(self) -> dict[str, object]:
        return {
            "title": self.title,
            "goal": self.goal,
            "in_scope": list(self.in_scope),
            "done_when": self.done_when,
        }


@dataclass(frozen=True)
class DispatchResult:
    target: ExecutorTarget
    status: DispatchStatus
    mode: DispatchMode
    payload: DispatchPayload | None = None
    reasons: tuple[RuntimeReason, ...] = ()
    execution_metadata: dict[str, object] = field(default_factory=dict)

    def to_record(self) -> dict[str, object]:
        return {
            "target": self.target.value,
            "status": self.status.value,
            "mode": self.mode.value,
            "payload": self.payload.to_record() if self.payload is not None else None,
            "reasons": [reason.to_record() for reason in self.reasons],
            "execution_metadata": self.execution_metadata,
        }


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


def task_spec_to_execution_transition(readiness: ReadinessResult) -> TransitionResult:
    state_map = {
        ReadinessStatus.READY: WorkflowState.SPEC_READY,
        ReadinessStatus.NEEDS_CLARIFICATION: WorkflowState.SPEC_READY,
        ReadinessStatus.BLOCKED: WorkflowState.BLOCKED,
    }
    return TransitionResult(
        from_state=WorkflowState.SPEC_READY,
        to_state=state_map[readiness.status],
        issues=readiness.reasons,
    )


def validation_collect_transition(validation: ValidationResult) -> TransitionResult:
    state_map = {
        ValidationStatus.PASSED: WorkflowState.WRITEBACK_REVIEW,
        ValidationStatus.FAILED: WorkflowState.BLOCKED,
        ValidationStatus.INCOMPLETE: WorkflowState.BLOCKED,
    }
    return TransitionResult(
        from_state=WorkflowState.VALIDATING,
        to_state=state_map[validation.status],
        issues=validation.reasons,
    )


def followup_transition(followup: FollowupResult) -> TransitionResult:
    state_map = {
        FollowupAction.IMPLEMENT_NEXT_TASK: WorkflowState.SPEC_READY,
        FollowupAction.CLARIFY_PLAN: WorkflowState.PLANNING,
        FollowupAction.FIX_VALIDATION_FAILURE: WorkflowState.BLOCKED,
        FollowupAction.WRITE_BACK_STABLE_CONTEXT: WorkflowState.WRITEBACK_REVIEW,
        FollowupAction.PROMOTE_SKILL_CANDIDATE: WorkflowState.WRITEBACK_REVIEW,
        FollowupAction.NO_FOLLOWUP_NEEDED: WorkflowState.COMPLETE,
    }
    return TransitionResult(
        from_state=WorkflowState.WRITEBACK_REVIEW,
        to_state=state_map[followup.action],
        issues=followup.reasons,
    )


def executor_dispatch_transition(dispatch: DispatchResult) -> TransitionResult:
    state_map = {
        DispatchStatus.PREVIEWED: WorkflowState.SPEC_READY,
        DispatchStatus.DISPATCHED: WorkflowState.EXECUTING,
        DispatchStatus.REJECTED: WorkflowState.BLOCKED,
    }
    return TransitionResult(
        from_state=WorkflowState.SPEC_READY,
        to_state=state_map[dispatch.status],
        issues=dispatch.reasons,
    )
