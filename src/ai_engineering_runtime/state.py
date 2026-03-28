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
class ExecutorCapabilityProfile:
    can_edit_files: bool = False
    can_run_shell: bool = False
    can_open_repo_context: bool = False
    can_return_patch: bool = False
    can_return_commit: bool = False
    can_run_tests: bool = False
    can_review: bool = False
    can_generate_docs: bool = False
    can_score_or_judge: bool = False
    can_do_review_only: bool = False
    supports_noninteractive: bool = False
    supports_retry: bool = False
    supports_resume: bool = False

    def to_record(self) -> dict[str, bool]:
        return {
            "can_edit_files": self.can_edit_files,
            "can_run_shell": self.can_run_shell,
            "can_open_repo_context": self.can_open_repo_context,
            "can_return_patch": self.can_return_patch,
            "can_return_commit": self.can_return_commit,
            "can_run_tests": self.can_run_tests,
            "can_review": self.can_review,
            "can_generate_docs": self.can_generate_docs,
            "can_score_or_judge": self.can_score_or_judge,
            "can_do_review_only": self.can_do_review_only,
            "supports_noninteractive": self.supports_noninteractive,
            "supports_retry": self.supports_retry,
            "supports_resume": self.supports_resume,
        }


@dataclass(frozen=True)
class ExecutorRequirements:
    can_edit_files: bool = False
    can_run_shell: bool = False
    can_open_repo_context: bool = False
    can_return_patch: bool = False
    can_return_commit: bool = False
    can_run_tests: bool = False
    can_review: bool = False
    can_generate_docs: bool = False
    can_score_or_judge: bool = False
    can_do_review_only: bool = False
    supports_noninteractive: bool = False
    supports_retry: bool = False
    supports_resume: bool = False

    def to_record(self) -> dict[str, bool]:
        return {
            "can_edit_files": self.can_edit_files,
            "can_run_shell": self.can_run_shell,
            "can_open_repo_context": self.can_open_repo_context,
            "can_return_patch": self.can_return_patch,
            "can_return_commit": self.can_return_commit,
            "can_run_tests": self.can_run_tests,
            "can_review": self.can_review,
            "can_generate_docs": self.can_generate_docs,
            "can_score_or_judge": self.can_score_or_judge,
            "can_do_review_only": self.can_do_review_only,
            "supports_noninteractive": self.supports_noninteractive,
            "supports_retry": self.supports_retry,
            "supports_resume": self.supports_resume,
        }

    def required_capabilities(self) -> tuple[str, ...]:
        return tuple(name for name, enabled in self.to_record().items() if enabled)


@dataclass(frozen=True)
class ExecutorDescriptor:
    name: str
    executor_type: str
    version: str
    capabilities: ExecutorCapabilityProfile

    def to_record(self) -> dict[str, object]:
        return {
            "name": self.name,
            "type": self.executor_type,
            "version": self.version,
            "capabilities": self.capabilities.to_record(),
        }


class ReviewFindingSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


class ReviewFindingStatus(str, Enum):
    OPEN = "open"
    REPAIRED = "repaired"
    CLOSED = "closed"
    ESCALATED = "escalated"


@dataclass(frozen=True)
class ReviewFinding:
    code: str
    message: str
    severity: ReviewFindingSeverity
    field: str | None = None
    source: str | None = None
    category: str = "quality"
    scope: str = "task"
    affected_files: tuple[str, ...] = ()
    affected_artifacts: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    blocking: bool | None = None
    status: ReviewFindingStatus = ReviewFindingStatus.OPEN
    suggested_fix_kind: str = "repair"
    finding_id: str | None = None

    @property
    def summary(self) -> str:
        return self.message

    @property
    def normalized_finding_id(self) -> str:
        return self.finding_id or self.code

    @property
    def is_blocking(self) -> bool:
        if self.blocking is not None:
            return self.blocking
        return self.severity is ReviewFindingSeverity.BLOCKING

    def to_record(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "code": self.code,
            "message": self.message,
            "finding_id": self.normalized_finding_id,
            "summary": self.summary,
            "severity": self.severity.value,
            "category": self.category,
            "scope": self.scope,
            "affected_files": list(self.affected_files),
            "affected_artifacts": list(self.affected_artifacts),
            "evidence": list(self.evidence),
            "blocking": self.is_blocking,
            "status": self.status.value,
            "suggested_fix_kind": self.suggested_fix_kind,
        }
        if self.field is not None:
            payload["field"] = self.field
        if self.source is not None:
            payload["source"] = self.source
        return payload

    @classmethod
    def from_record(cls, value: object) -> "ReviewFinding" | None:
        if not isinstance(value, dict):
            return None
        code = value.get("code") or value.get("finding_id")
        message = value.get("message") or value.get("summary")
        severity = value.get("severity")
        field = value.get("field")
        source = value.get("source")
        category = value.get("category", "quality")
        scope = value.get("scope", "task")
        affected_files = value.get("affected_files", [])
        affected_artifacts = value.get("affected_artifacts", [])
        evidence = value.get("evidence", [])
        blocking = value.get("blocking")
        status = value.get("status", ReviewFindingStatus.OPEN.value)
        suggested_fix_kind = value.get("suggested_fix_kind", "repair")
        finding_id = value.get("finding_id")
        if not isinstance(code, str) or not isinstance(message, str) or not isinstance(severity, str):
            return None
        if field is not None and not isinstance(field, str):
            return None
        if source is not None and not isinstance(source, str):
            return None
        if not isinstance(category, str) or not isinstance(scope, str):
            return None
        for items in (affected_files, affected_artifacts, evidence):
            if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
                return None
        if blocking is not None and not isinstance(blocking, bool):
            return None
        if not isinstance(suggested_fix_kind, str):
            return None
        if finding_id is not None and not isinstance(finding_id, str):
            return None
        try:
            parsed_severity = ReviewFindingSeverity(severity)
            parsed_status = ReviewFindingStatus(status)
        except ValueError:
            return None
        return cls(
            code=code,
            message=message,
            severity=parsed_severity,
            field=field,
            source=source,
            category=category,
            scope=scope,
            affected_files=tuple(affected_files),
            affected_artifacts=tuple(affected_artifacts),
            evidence=tuple(evidence),
            blocking=blocking,
            status=parsed_status,
            suggested_fix_kind=suggested_fix_kind,
            finding_id=finding_id,
        )


@dataclass(frozen=True)
class ExecutionArtifactRef:
    kind: str
    value: str

    def to_record(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "value": self.value,
        }


@dataclass(frozen=True)
class RepairSpecCandidate:
    title: str
    goal: str
    in_scope: tuple[str, ...]
    validation_focus: tuple[str, ...] = ()
    triggering_findings: tuple[ReviewFinding, ...] = ()
    source_finding_ids: tuple[str, ...] = ()
    repair_objective: str | None = None
    allowed_scope: tuple[str, ...] = ()
    forbidden_expansion: tuple[str, ...] = ()
    success_criteria: tuple[str, ...] = ()
    validation_expectation: tuple[str, ...] = ()
    repair_round: int = 0

    def to_record(self) -> dict[str, object]:
        return {
            "title": self.title,
            "goal": self.goal,
            "in_scope": list(self.in_scope),
            "validation_focus": list(self.validation_focus),
            "triggering_findings": [finding.to_record() for finding in self.triggering_findings],
            "source_finding_ids": list(self.source_finding_ids),
            "repair_objective": self.repair_objective,
            "allowed_scope": list(self.allowed_scope),
            "forbidden_expansion": list(self.forbidden_expansion),
            "success_criteria": list(self.success_criteria),
            "validation_expectation": list(self.validation_expectation),
            "repair_round": self.repair_round,
        }

    @classmethod
    def from_record(cls, value: object) -> "RepairSpecCandidate" | None:
        if not isinstance(value, dict):
            return None
        title = value.get("title")
        goal = value.get("goal")
        in_scope = value.get("in_scope", [])
        validation_focus = value.get("validation_focus", [])
        triggering_findings = value.get("triggering_findings", [])
        source_finding_ids = value.get("source_finding_ids", [])
        repair_objective = value.get("repair_objective")
        allowed_scope = value.get("allowed_scope", [])
        forbidden_expansion = value.get("forbidden_expansion", [])
        success_criteria = value.get("success_criteria", [])
        validation_expectation = value.get("validation_expectation", [])
        repair_round = value.get("repair_round", 0)
        if not isinstance(title, str) or not isinstance(goal, str):
            return None
        for items in (
            in_scope,
            validation_focus,
            source_finding_ids,
            allowed_scope,
            forbidden_expansion,
            success_criteria,
            validation_expectation,
        ):
            if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
                return None
        if repair_objective is not None and not isinstance(repair_objective, str):
            return None
        if not isinstance(repair_round, int):
            return None
        parsed_findings: list[ReviewFinding] = []
        for item in triggering_findings:
            finding = ReviewFinding.from_record(item)
            if finding is None:
                return None
            parsed_findings.append(finding)
        return cls(
            title=title,
            goal=goal,
            in_scope=tuple(in_scope),
            validation_focus=tuple(validation_focus),
            triggering_findings=tuple(parsed_findings),
            source_finding_ids=tuple(source_finding_ids),
            repair_objective=repair_objective,
            allowed_scope=tuple(allowed_scope),
            forbidden_expansion=tuple(forbidden_expansion),
            success_criteria=tuple(success_criteria),
            validation_expectation=tuple(validation_expectation),
            repair_round=repair_round,
        )


class ExecutionStatus(str, Enum):
    PREVIEWED = "previewed"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ExecutionResult:
    executor: ExecutorDescriptor
    spec_identity: str | None
    dispatch_summary: dict[str, object]
    final_status: ExecutionStatus
    summary: str
    changed_files: tuple[str, ...] = ()
    patch_ref: str | None = None
    branch_ref: str | None = None
    commit_ref: str | None = None
    stdout_summary: str | None = None
    stderr_summary: str | None = None
    log_summary: str | None = None
    validations_claimed: tuple[str, ...] = ()
    uncovered_items: tuple[str, ...] = ()
    suggested_followups: tuple[str, ...] = ()
    raw_artifact_refs: tuple[ExecutionArtifactRef, ...] = ()
    findings: tuple[ReviewFinding, ...] = ()
    repair_spec_candidate: RepairSpecCandidate | None = None

    def to_record(self) -> dict[str, object]:
        return {
            "executor": self.executor.to_record(),
            "spec_identity": self.spec_identity,
            "dispatch_summary": self.dispatch_summary,
            "final_status": self.final_status.value,
            "summary": self.summary,
            "changed_files": list(self.changed_files),
            "patch_ref": self.patch_ref,
            "branch_ref": self.branch_ref,
            "commit_ref": self.commit_ref,
            "stdout_summary": self.stdout_summary,
            "stderr_summary": self.stderr_summary,
            "log_summary": self.log_summary,
            "validations_claimed": list(self.validations_claimed),
            "uncovered_items": list(self.uncovered_items),
            "suggested_followups": list(self.suggested_followups),
            "raw_artifact_refs": [reference.to_record() for reference in self.raw_artifact_refs],
            "findings": [finding.to_record() for finding in self.findings],
            "repair_spec_candidate": (
                self.repair_spec_candidate.to_record() if self.repair_spec_candidate is not None else None
            ),
        }


def derive_repair_spec_candidate(
    *,
    spec_title: str,
    findings: tuple[ReviewFinding, ...],
    uncovered_items: tuple[str, ...],
    validations_claimed: tuple[str, ...],
    repair_round: int = 0,
) -> RepairSpecCandidate | None:
    blocking_findings = tuple(
        finding for finding in findings if finding.is_blocking and finding.status is ReviewFindingStatus.OPEN
    )
    if not blocking_findings and not uncovered_items:
        return None

    scope_hints = list(uncovered_items)
    for finding in blocking_findings:
        scope_hints.append(finding.summary)

    validation_focus = list(validations_claimed)
    if not validation_focus:
        validation_focus.append("Re-run the executor-reported validation path after repair.")

    allowed_scope = tuple(scope_hints)
    source_finding_ids = tuple(finding.normalized_finding_id for finding in blocking_findings)
    success_criteria = tuple(
        list(source_finding_ids)
        + ["Validation evidence is refreshed after repair.", "Closeout no longer reports blocking findings."]
    )
    forbidden_expansion = (
        "Do not expand the repair into new planning or adjacent roadmap work.",
        "Do not widen file scope beyond the cited findings unless validation requires it.",
    )

    return RepairSpecCandidate(
        title=f"Repair {spec_title}",
        goal="Close the blocking findings and uncovered items reported during executor run closeout.",
        in_scope=tuple(scope_hints),
        validation_focus=tuple(validation_focus),
        triggering_findings=blocking_findings,
        source_finding_ids=source_finding_ids,
        repair_objective="Implement the smallest repair that closes the cited findings without expanding task scope.",
        allowed_scope=allowed_scope,
        forbidden_expansion=forbidden_expansion,
        success_criteria=success_criteria,
        validation_expectation=tuple(validation_focus),
        repair_round=repair_round,
    )


def normalize_review_finding(
    finding: ReviewFinding,
    *,
    default_source: str | None = None,
    category: str | None = None,
    scope: str | None = None,
    affected_files: tuple[str, ...] = (),
    affected_artifacts: tuple[str, ...] = (),
    evidence: tuple[str, ...] = (),
    suggested_fix_kind: str | None = None,
) -> ReviewFinding:
    return ReviewFinding(
        code=finding.code,
        message=finding.message,
        severity=finding.severity,
        field=finding.field,
        source=finding.source or default_source,
        category=category or finding.category,
        scope=scope or finding.scope,
        affected_files=finding.affected_files or affected_files,
        affected_artifacts=finding.affected_artifacts or affected_artifacts,
        evidence=finding.evidence or evidence,
        blocking=finding.blocking,
        status=finding.status,
        suggested_fix_kind=suggested_fix_kind or finding.suggested_fix_kind,
        finding_id=finding.finding_id or finding.code,
    )


def normalize_review_findings(
    findings: tuple[ReviewFinding, ...],
    *,
    default_source: str | None = None,
    category: str | None = None,
    scope: str | None = None,
    affected_files: tuple[str, ...] = (),
    affected_artifacts: tuple[str, ...] = (),
    evidence: tuple[str, ...] = (),
    suggested_fix_kind: str | None = None,
) -> tuple[ReviewFinding, ...]:
    return tuple(
        normalize_review_finding(
            finding,
            default_source=default_source,
            category=category,
            scope=scope,
            affected_files=affected_files,
            affected_artifacts=affected_artifacts,
            evidence=evidence,
            suggested_fix_kind=suggested_fix_kind,
        )
        for finding in findings
    )


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
    CODEX = "codex"


class DispatchMode(str, Enum):
    PREVIEW = "preview"
    ECHO = "echo"
    SUBMIT = "submit"


class ExecutorLifecycleAction(str, Enum):
    POLL = "poll"
    RESUME = "resume"


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
    executor: ExecutorDescriptor | None = None
    requirements: ExecutorRequirements | None = None
    execution_metadata: dict[str, object] = field(default_factory=dict)

    def to_record(self) -> dict[str, object]:
        return {
            "target": self.target.value,
            "status": self.status.value,
            "mode": self.mode.value,
            "payload": self.payload.to_record() if self.payload is not None else None,
            "reasons": [reason.to_record() for reason in self.reasons],
            "executor": self.executor.to_record() if self.executor is not None else None,
            "requirements": self.requirements.to_record() if self.requirements is not None else None,
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


def executor_dispatch_transition(
    dispatch: DispatchResult,
    execution: ExecutionResult | None = None,
) -> TransitionResult:
    state_map = {
        DispatchStatus.PREVIEWED: WorkflowState.SPEC_READY,
        DispatchStatus.DISPATCHED: WorkflowState.EXECUTING,
        DispatchStatus.REJECTED: WorkflowState.BLOCKED,
    }
    to_state = state_map[dispatch.status]
    if (
        dispatch.status is DispatchStatus.DISPATCHED
        and execution is not None
        and execution.final_status in {ExecutionStatus.FAILED, ExecutionStatus.BLOCKED}
    ):
        to_state = WorkflowState.BLOCKED
    return TransitionResult(
        from_state=WorkflowState.SPEC_READY,
        to_state=to_state,
        issues=dispatch.reasons,
    )


def executor_run_lifecycle_transition(execution: ExecutionResult) -> TransitionResult:
    state_map = {
        ExecutionStatus.RUNNING: WorkflowState.EXECUTING,
        ExecutionStatus.SUCCEEDED: WorkflowState.VALIDATING,
        ExecutionStatus.FAILED: WorkflowState.BLOCKED,
        ExecutionStatus.BLOCKED: WorkflowState.BLOCKED,
        ExecutionStatus.PREVIEWED: WorkflowState.EXECUTING,
    }
    return TransitionResult(
        from_state=WorkflowState.EXECUTING,
        to_state=state_map[execution.final_status],
        issues=tuple(
            RuntimeReason(code=finding.code, message=finding.message, field=finding.field)
            for finding in execution.findings
            if finding.severity is ReviewFindingSeverity.BLOCKING
        ),
    )
