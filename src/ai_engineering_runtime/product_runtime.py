from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
from pathlib import Path

from ai_engineering_runtime.handoffs import (
    ArtifactCategory,
    HandoffDocument,
    HandoffLane,
    LaneStatus,
    load_handoff,
    validate_handoff,
)
from ai_engineering_runtime.state import (
    ExecutionResult,
    ExecutionStatus,
    ExecutorCapabilityProfile,
    ExecutorDescriptor,
    RepairSpecCandidate,
    ReviewFinding,
    ReviewFindingSeverity,
    ReviewFindingStatus,
    RuntimeReason,
    ValidationStatus,
    derive_repair_spec_candidate,
    normalize_review_findings,
)


class GateStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NEEDS_REVIEW = "needs_review"
    BLOCKED = "blocked"


class ProductErrorKind(str, Enum):
    EXECUTOR_FAILURE = "executor_failure"
    VALIDATION_FAILURE = "validation_failure"
    CAPABILITY_MISMATCH = "capability_mismatch"
    MISSING_ARTIFACT = "missing_artifact"
    BLOCKED_ON_RESOURCE = "blocked_on_resource"
    RETRY_EXHAUSTED = "retry_exhausted"
    REVIEW_REQUIRED = "review_required"


class RecoveryAction(str, Enum):
    RETRY_SAME_EXECUTOR = "retry_same_executor"
    SWITCH_EXECUTOR = "switch_executor"
    HOLD_FOR_REVIEW = "hold_for_review"
    DERIVE_FOLLOWUP = "derive_followup"
    ABORT_RUN = "abort_run"
    PARK_LANE = "park_lane"


@dataclass(frozen=True)
class PhaseGateResult:
    gate_id: str
    status: GateStatus
    missing_requirements: tuple[str, ...] = ()
    auto_advance_allowed: bool = False
    explanation: str = ""

    def to_record(self) -> dict[str, object]:
        return {
            "gate_id": self.gate_id,
            "status": self.status.value,
            "missing_requirements": list(self.missing_requirements),
            "auto_advance_allowed": self.auto_advance_allowed,
            "explanation": self.explanation,
        }

    @classmethod
    def from_record(cls, value: object) -> "PhaseGateResult" | None:
        if not isinstance(value, dict):
            return None
        gate_id = value.get("gate_id")
        status = value.get("status")
        missing_requirements = value.get("missing_requirements", [])
        auto_advance_allowed = value.get("auto_advance_allowed")
        explanation = value.get("explanation", "")
        if not isinstance(gate_id, str) or not isinstance(status, str):
            return None
        if not isinstance(missing_requirements, list) or not all(isinstance(item, str) for item in missing_requirements):
            return None
        if not isinstance(auto_advance_allowed, bool) or not isinstance(explanation, str):
            return None
        try:
            parsed_status = GateStatus(status)
        except ValueError:
            return None
        return cls(
            gate_id=gate_id,
            status=parsed_status,
            missing_requirements=tuple(missing_requirements),
            auto_advance_allowed=auto_advance_allowed,
            explanation=explanation,
        )


@dataclass(frozen=True)
class ExecutionReadiness:
    ready: bool
    missing_requirements: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    recommended_dispatch_targets: tuple[str, ...] = ()
    blocking_reason: str | None = None

    def to_record(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "missing_requirements": list(self.missing_requirements),
            "required_capabilities": list(self.required_capabilities),
            "recommended_dispatch_targets": list(self.recommended_dispatch_targets),
            "blocking_reason": self.blocking_reason,
        }

    @classmethod
    def from_record(cls, value: object) -> "ExecutionReadiness" | None:
        if not isinstance(value, dict):
            return None
        ready = value.get("ready")
        missing_requirements = value.get("missing_requirements", [])
        required_capabilities = value.get("required_capabilities", [])
        recommended_dispatch_targets = value.get("recommended_dispatch_targets", [])
        blocking_reason = value.get("blocking_reason")
        if not isinstance(ready, bool):
            return None
        for items in (missing_requirements, required_capabilities, recommended_dispatch_targets):
            if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
                return None
        if blocking_reason is not None and not isinstance(blocking_reason, str):
            return None
        return cls(
            ready=ready,
            missing_requirements=tuple(missing_requirements),
            required_capabilities=tuple(required_capabilities),
            recommended_dispatch_targets=tuple(recommended_dispatch_targets),
            blocking_reason=blocking_reason,
        )


@dataclass(frozen=True)
class AdvanceDecision:
    next_legal_actions: tuple[str, ...]
    default_action: str
    stop_reason: str
    blocked_reason: str | None = None
    parked_lane_summary: tuple[str, ...] = ()
    why_not_auto_advance: str | None = None

    def to_record(self) -> dict[str, object]:
        return {
            "next_legal_actions": list(self.next_legal_actions),
            "default_action": self.default_action,
            "stop_reason": self.stop_reason,
            "blocked_reason": self.blocked_reason,
            "parked_lane_summary": list(self.parked_lane_summary),
            "why_not_auto_advance": self.why_not_auto_advance,
        }

    @classmethod
    def from_record(cls, value: object) -> "AdvanceDecision" | None:
        if not isinstance(value, dict):
            return None
        next_legal_actions = value.get("next_legal_actions", [])
        default_action = value.get("default_action")
        stop_reason = value.get("stop_reason")
        blocked_reason = value.get("blocked_reason")
        parked_lane_summary = value.get("parked_lane_summary", [])
        why_not_auto_advance = value.get("why_not_auto_advance")
        if not isinstance(next_legal_actions, list) or not all(isinstance(item, str) for item in next_legal_actions):
            return None
        if not isinstance(default_action, str) or not isinstance(stop_reason, str):
            return None
        if blocked_reason is not None and not isinstance(blocked_reason, str):
            return None
        if not isinstance(parked_lane_summary, list) or not all(isinstance(item, str) for item in parked_lane_summary):
            return None
        if why_not_auto_advance is not None and not isinstance(why_not_auto_advance, str):
            return None
        return cls(
            next_legal_actions=tuple(next_legal_actions),
            default_action=default_action,
            stop_reason=stop_reason,
            blocked_reason=blocked_reason,
            parked_lane_summary=tuple(parked_lane_summary),
            why_not_auto_advance=why_not_auto_advance,
        )


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    on_error: tuple[RecoveryAction, ...]


@dataclass(frozen=True)
class RepairPolicy:
    max_rounds: int
    escalate_after_rounds: int
    blocking_severities: tuple[ReviewFindingSeverity, ...] = (ReviewFindingSeverity.BLOCKING,)


@dataclass(frozen=True)
class CloseoutSummary:
    closeable: bool
    blocking_findings: int
    non_blocking_findings: int
    repair_rounds: int
    max_repair_rounds: int
    can_continue_repair: bool
    status: str
    reason: str

    def to_record(self) -> dict[str, object]:
        return {
            "closeable": self.closeable,
            "blocking_findings": self.blocking_findings,
            "non_blocking_findings": self.non_blocking_findings,
            "repair_rounds": self.repair_rounds,
            "max_repair_rounds": self.max_repair_rounds,
            "can_continue_repair": self.can_continue_repair,
            "status": self.status,
            "reason": self.reason,
        }

    @classmethod
    def from_record(cls, value: object) -> "CloseoutSummary" | None:
        if not isinstance(value, dict):
            return None
        closeable = value.get("closeable")
        blocking_findings = value.get("blocking_findings")
        non_blocking_findings = value.get("non_blocking_findings")
        repair_rounds = value.get("repair_rounds")
        max_repair_rounds = value.get("max_repair_rounds")
        can_continue_repair = value.get("can_continue_repair")
        status = value.get("status")
        reason = value.get("reason")
        if not all(isinstance(item, bool) for item in (closeable, can_continue_repair)):
            return None
        if not all(isinstance(item, int) for item in (blocking_findings, non_blocking_findings, repair_rounds, max_repair_rounds)):
            return None
        if not isinstance(status, str) or not isinstance(reason, str):
            return None
        return cls(
            closeable=closeable,
            blocking_findings=blocking_findings,
            non_blocking_findings=non_blocking_findings,
            repair_rounds=repair_rounds,
            max_repair_rounds=max_repair_rounds,
            can_continue_repair=can_continue_repair,
            status=status,
            reason=reason,
        )


@dataclass(frozen=True)
class WorkflowNodeDefinition:
    node_id: str
    phase: str
    primary_executor: str | None = None
    fallback_executor: str | None = None
    required_capabilities: tuple[str, ...] = ()
    retry_policy: RetryPolicy = RetryPolicy(max_attempts=1, on_error=(RecoveryAction.HOLD_FOR_REVIEW,))
    review_point: bool = False
    closeout_behavior: str = "hold"


@dataclass(frozen=True)
class WorkflowDefinition:
    workflow_id: str
    phases: tuple[str, ...]
    nodes: tuple[WorkflowNodeDefinition, ...]

    def node(self, node_id: str) -> WorkflowNodeDefinition | None:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None


@dataclass
class ProductRunState:
    run_id: str
    workflow_id: str
    handoff: HandoffDocument
    created_at: str
    updated_at: str
    lanes: tuple[HandoffLane, ...]
    gates: dict[str, PhaseGateResult]
    decision: AdvanceDecision
    execution_readiness: ExecutionReadiness
    open_findings: tuple[ReviewFinding, ...] = ()
    validation_status: ValidationStatus | None = None
    last_execution_record: dict[str, object] | None = None
    repair_spec_record: dict[str, object] | None = None
    review_status: str = "not_started"
    repair_rounds: int = 0
    closeout_summary: CloseoutSummary | None = None
    last_node_id: str | None = None
    last_executor_name: str | None = None
    attempt_counts: dict[str, int] = field(default_factory=dict)
    last_error_kind: ProductErrorKind | None = None
    event_log: tuple[str, ...] = ()
    status: str = "active"

    def to_record(self) -> dict[str, object]:
        return {
            "version": 1,
            "run_id": self.run_id,
            "workflow_id": self.workflow_id,
            "handoff": self.handoff.to_record(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "lanes": [lane.to_record() for lane in self.lanes],
            "gates": {name: gate.to_record() for name, gate in self.gates.items()},
            "decision": self.decision.to_record(),
            "execution_readiness": self.execution_readiness.to_record(),
            "open_findings": [finding.to_record() for finding in self.open_findings],
            "validation_status": self.validation_status.value if self.validation_status is not None else None,
            "last_execution_record": self.last_execution_record,
            "repair_spec_record": self.repair_spec_record,
            "review_status": self.review_status,
            "repair_rounds": self.repair_rounds,
            "closeout_summary": self.closeout_summary.to_record() if self.closeout_summary is not None else None,
            "last_node_id": self.last_node_id,
            "last_executor_name": self.last_executor_name,
            "attempt_counts": self.attempt_counts,
            "last_error_kind": self.last_error_kind.value if self.last_error_kind is not None else None,
            "event_log": list(self.event_log),
            "status": self.status,
        }

    @classmethod
    def from_record(cls, value: object) -> "ProductRunState" | None:
        if not isinstance(value, dict):
            return None
        handoff = HandoffDocument.from_record(value.get("handoff"))
        lanes_payload = value.get("lanes")
        if handoff is None or not isinstance(lanes_payload, list):
            return None
        lanes: list[HandoffLane] = []
        for item in lanes_payload:
            lane = HandoffLane.from_record(item)
            if lane is None:
                return None
            lanes.append(lane)
        gates_payload = value.get("gates", {})
        if not isinstance(gates_payload, dict):
            return None
        gates: dict[str, PhaseGateResult] = {}
        for name, item in gates_payload.items():
            if not isinstance(name, str):
                return None
            gate = PhaseGateResult.from_record(item)
            if gate is None:
                return None
            gates[name] = gate
        decision = AdvanceDecision.from_record(value.get("decision"))
        execution_readiness = ExecutionReadiness.from_record(value.get("execution_readiness"))
        if decision is None or execution_readiness is None:
            return None
        open_findings = _parse_review_findings(value.get("open_findings", []))
        if open_findings is None:
            return None
        run_id = value.get("run_id")
        workflow_id = value.get("workflow_id")
        created_at = value.get("created_at")
        updated_at = value.get("updated_at")
        review_status = value.get("review_status", "not_started")
        repair_rounds = value.get("repair_rounds", 0)
        closeout_summary = CloseoutSummary.from_record(value.get("closeout_summary"))
        last_node_id = value.get("last_node_id")
        last_executor_name = value.get("last_executor_name")
        attempt_counts = value.get("attempt_counts", {})
        event_log = value.get("event_log", [])
        status = value.get("status", "active")
        validation_status = value.get("validation_status")
        last_execution_record = value.get("last_execution_record")
        repair_spec_record = value.get("repair_spec_record")
        last_error_kind = value.get("last_error_kind")
        if not all(isinstance(item, str) for item in (run_id, workflow_id, created_at, updated_at, review_status, status)):
            return None
        if repair_rounds is None or not isinstance(repair_rounds, int):
            return None
        if last_node_id is not None and not isinstance(last_node_id, str):
            return None
        if last_executor_name is not None and not isinstance(last_executor_name, str):
            return None
        if not isinstance(attempt_counts, dict) or not all(isinstance(key, str) and isinstance(item, int) for key, item in attempt_counts.items()):
            return None
        if not isinstance(event_log, list) or not all(isinstance(item, str) for item in event_log):
            return None
        parsed_validation = None
        if validation_status is not None:
            if not isinstance(validation_status, str):
                return None
            try:
                parsed_validation = ValidationStatus(validation_status)
            except ValueError:
                return None
        parsed_error_kind = None
        if last_error_kind is not None:
            if not isinstance(last_error_kind, str):
                return None
            try:
                parsed_error_kind = ProductErrorKind(last_error_kind)
            except ValueError:
                return None
        if last_execution_record is not None and not isinstance(last_execution_record, dict):
            return None
        if repair_spec_record is not None and not isinstance(repair_spec_record, dict):
            return None
        return cls(
            run_id=run_id,
            workflow_id=workflow_id,
            handoff=handoff,
            created_at=created_at,
            updated_at=updated_at,
            lanes=tuple(lanes),
            gates=gates,
            decision=decision,
            execution_readiness=execution_readiness,
            open_findings=open_findings,
            validation_status=parsed_validation,
            last_execution_record=last_execution_record,
            repair_spec_record=repair_spec_record,
            review_status=review_status,
            repair_rounds=repair_rounds,
            closeout_summary=closeout_summary,
            last_node_id=last_node_id,
            last_executor_name=last_executor_name,
            attempt_counts=attempt_counts,
            last_error_kind=parsed_error_kind,
            event_log=tuple(event_log),
            status=status,
        )


@dataclass(frozen=True)
class ProductCommandResult:
    success: bool
    state: ProductRunState | None = None
    reasons: tuple[RuntimeReason, ...] = ()
    rendered_output: str | None = None


def workflow_definitions() -> dict[str, WorkflowDefinition]:
    retry_standard = RetryPolicy(
        max_attempts=2,
        on_error=(
            RecoveryAction.RETRY_SAME_EXECUTOR,
            RecoveryAction.SWITCH_EXECUTOR,
            RecoveryAction.HOLD_FOR_REVIEW,
        ),
    )
    retry_review = RetryPolicy(
        max_attempts=1,
        on_error=(RecoveryAction.DERIVE_FOLLOWUP, RecoveryAction.HOLD_FOR_REVIEW),
    )
    return {
        "repo-coding-task": WorkflowDefinition(
            workflow_id="repo-coding-task",
            phases=(
                "intake",
                "handoff-compile",
                "planning",
                "execution",
                "review",
                "validation",
                "closeout",
            ),
            nodes=(
                WorkflowNodeDefinition(node_id="handoff-compile", phase="handoff-compile"),
                WorkflowNodeDefinition(node_id="planning-spec-check", phase="planning"),
                WorkflowNodeDefinition(
                    node_id="executor-dispatch",
                    phase="execution",
                    primary_executor="codex-coder",
                    fallback_executor="mock-coder",
                    required_capabilities=("can_edit_files", "can_run_shell", "supports_noninteractive"),
                    retry_policy=retry_standard,
                ),
                WorkflowNodeDefinition(
                    node_id="review-dispatch",
                    phase="review",
                    primary_executor="review-executor",
                    fallback_executor="mock-review",
                    required_capabilities=("can_review", "can_score_or_judge"),
                    retry_policy=retry_review,
                    review_point=True,
                ),
                WorkflowNodeDefinition(
                    node_id="repair-dispatch",
                    phase="validation",
                    primary_executor="codex-coder",
                    fallback_executor="mock-coder",
                    required_capabilities=("can_edit_files", "supports_retry"),
                    retry_policy=retry_standard,
                ),
                WorkflowNodeDefinition(node_id="closeout", phase="closeout", closeout_behavior="close"),
            ),
        ),
        "chat-to-execution": WorkflowDefinition(
            workflow_id="chat-to-execution",
            phases=("input-normalize", "handoff-compile", "workflow-select", "decision", "dispatch", "closeout"),
            nodes=(
                WorkflowNodeDefinition(node_id="handoff-compile", phase="handoff-compile"),
                WorkflowNodeDefinition(
                    node_id="executor-dispatch",
                    phase="dispatch",
                    primary_executor="codex-coder",
                    fallback_executor="mock-coder",
                    required_capabilities=("can_edit_files", "supports_noninteractive"),
                    retry_policy=retry_standard,
                ),
                WorkflowNodeDefinition(
                    node_id="review-dispatch",
                    phase="dispatch",
                    primary_executor="review-executor",
                    fallback_executor="mock-review",
                    required_capabilities=("can_review",),
                    retry_policy=retry_review,
                    review_point=True,
                ),
                WorkflowNodeDefinition(node_id="closeout", phase="closeout", closeout_behavior="close"),
            ),
        ),
    }


def available_executors() -> dict[str, ExecutorDescriptor]:
    return {
        "mock-coder": ExecutorDescriptor(
            name="mock-coder",
            executor_type="mock-coding-executor",
            version="v1",
            capabilities=ExecutorCapabilityProfile(
                can_edit_files=True,
                can_run_shell=True,
                can_open_repo_context=True,
                can_return_patch=True,
                can_run_tests=True,
                supports_noninteractive=True,
                supports_retry=True,
            ),
        ),
        "codex-coder": ExecutorDescriptor(
            name="codex-coder",
            executor_type="coding-executor-adapter",
            version="v1",
            capabilities=ExecutorCapabilityProfile(
                can_edit_files=True,
                can_run_shell=True,
                can_open_repo_context=True,
                can_return_patch=True,
                can_run_tests=True,
                can_review=True,
                can_generate_docs=True,
                can_score_or_judge=True,
                supports_noninteractive=True,
                supports_retry=True,
                supports_resume=True,
            ),
        ),
        "review-executor": ExecutorDescriptor(
            name="review-executor",
            executor_type="review-executor-adapter",
            version="v1",
            capabilities=ExecutorCapabilityProfile(
                can_review=True,
                can_generate_docs=True,
                can_score_or_judge=True,
                can_do_review_only=True,
                supports_noninteractive=True,
                supports_retry=True,
            ),
        ),
        "mock-review": ExecutorDescriptor(
            name="mock-review",
            executor_type="review-executor-adapter",
            version="skeleton-v1",
            capabilities=ExecutorCapabilityProfile(
                can_review=True,
                can_generate_docs=True,
                can_score_or_judge=True,
                can_do_review_only=True,
                supports_noninteractive=True,
                supports_retry=True,
            ),
        ),
    }


def run_from_handoff(
    adapter,
    handoff: HandoffDocument,
    *,
    force_workflow_id: str | None = None,
    persist: bool = True,
    allow_auto_dispatch: bool = True,
) -> ProductCommandResult:
    validation_reasons = validate_handoff(handoff)
    if validation_reasons:
        return ProductCommandResult(success=False, reasons=validation_reasons)
    workflow_id = force_workflow_id or handoff.workflow_id
    definitions = workflow_definitions()
    workflow = definitions.get(workflow_id)
    if workflow is None:
        return ProductCommandResult(
            success=False,
            reasons=(
                RuntimeReason(
                    code="unknown-workflow",
                    message=f"Unknown workflow id: {workflow_id}",
                    field="workflow_id",
                ),
            ),
        )
    now = datetime.utcnow().isoformat(timespec="seconds")
    run_id = datetime.utcnow().strftime("%Y%m%dT%H%M%S") + f"-{workflow.workflow_id}"
    state = ProductRunState(
        run_id=run_id,
        workflow_id=workflow.workflow_id,
        handoff=handoff,
        created_at=now,
        updated_at=now,
        lanes=handoff.lanes,
        gates={},
        decision=AdvanceDecision(next_legal_actions=("hold-for-review",), default_action="hold-for-review", stop_reason="initializing"),
        execution_readiness=ExecutionReadiness(ready=False),
        closeout_summary=None,
        event_log=("intake:compiled", "decision:initialized"),
    )
    refreshed = refresh_run_state(state)
    if allow_auto_dispatch and handoff.initial_execution_intent.dispatch_mode == "auto" and refreshed.decision.default_action.startswith("dispatch-"):
        refreshed = _execute_node(adapter, refreshed, refreshed.handoff.initial_execution_intent.preferred_node)
        if workflow.node("review-dispatch") is not None:
            refreshed = _execute_node(adapter, refreshed, "review-dispatch")
        refreshed = refresh_run_state(refreshed)
    if persist:
        save_product_run(adapter, refreshed)
    return ProductCommandResult(success=True, state=refreshed)


def preview_run_from_handoff(
    adapter,
    handoff: HandoffDocument,
    *,
    force_workflow_id: str | None = None,
) -> ProductCommandResult:
    return run_from_handoff(
        adapter,
        handoff,
        force_workflow_id=force_workflow_id,
        persist=False,
        allow_auto_dispatch=False,
    )


def inspect_run(adapter, run_id: str) -> ProductCommandResult:
    state = load_product_run(adapter, run_id)
    if state is None:
        return ProductCommandResult(success=False, reasons=_missing_run_reasons(run_id))
    return ProductCommandResult(success=True, state=state)


def resume_run(adapter, run_id: str) -> ProductCommandResult:
    state = load_product_run(adapter, run_id)
    if state is None:
        return ProductCommandResult(success=False, reasons=_missing_run_reasons(run_id))
    refreshed = refresh_run_state(state)
    save_product_run(adapter, refreshed)
    return ProductCommandResult(success=True, state=refreshed)


def retry_run(adapter, run_id: str, node_id: str) -> ProductCommandResult:
    state = load_product_run(adapter, run_id)
    if state is None:
        return ProductCommandResult(success=False, reasons=_missing_run_reasons(run_id))
    workflow = workflow_definitions().get(state.workflow_id)
    node = workflow.node(node_id) if workflow is not None else None
    if workflow is None or node is None:
        return ProductCommandResult(
            success=False,
            reasons=(
                RuntimeReason(code="unknown-retry-node", message=f"Unknown retry node: {node_id}", field="node"),
            ),
        )
    if node_id == "repair-dispatch":
        policy = repair_policy_for_workflow(state.workflow_id)
        if state.repair_rounds >= policy.max_rounds:
            refreshed = refresh_run_state(state)
            save_product_run(adapter, refreshed)
            return ProductCommandResult(
                success=False,
                state=refreshed,
                reasons=(
                    RuntimeReason(
                        code="repair-round-limit-reached",
                        message="Repair policy is exhausted for this run; hold for review instead of continuing automatic repair.",
                        field="node",
                    ),
                ),
            )
    attempts = state.attempt_counts.get(node_id, 0)
    selected_executor = _select_executor(node, attempts)
    if selected_executor is None:
        state.last_error_kind = ProductErrorKind.RETRY_EXHAUSTED
        state = refresh_run_state(state)
        save_product_run(adapter, state)
        return ProductCommandResult(success=False, state=state, reasons=(RuntimeReason(code="retry-exhausted", message="Retry policy is exhausted for the selected node.", field="node"),))
    executed = _execute_node(adapter, state, node_id, forced_executor=selected_executor)
    executed = refresh_run_state(executed)
    save_product_run(adapter, executed)
    return ProductCommandResult(success=True, state=executed)


def close_run(adapter, run_id: str) -> ProductCommandResult:
    state = load_product_run(adapter, run_id)
    if state is None:
        return ProductCommandResult(success=False, reasons=_missing_run_reasons(run_id))
    refreshed = refresh_run_state(state)
    closeout_gate = refreshed.gates.get("closeout_gate")
    if closeout_gate is None or closeout_gate.status is not GateStatus.PASS:
        save_product_run(adapter, refreshed)
        return ProductCommandResult(
            success=False,
            state=refreshed,
            reasons=(
                RuntimeReason(
                    code="closeout-gate-blocked",
                    message="Closeout gate is not yet passable for this run.",
                    field="closeout_gate",
                ),
            ),
        )
    refreshed.status = "complete"
    refreshed.updated_at = datetime.utcnow().isoformat(timespec="seconds")
    refreshed.last_node_id = "closeout"
    refreshed.last_executor_name = None
    refreshed.event_log = refreshed.event_log + ("closeout:run-closed",)
    refreshed.decision = AdvanceDecision(
        next_legal_actions=("close-run",),
        default_action="close-run",
        stop_reason="closeout_complete",
        parked_lane_summary=tuple(
            f"{lane.lane_id}: {', '.join(lane.unblock_conditions) or 'waiting on mainline progress'}"
            for lane in refreshed.lanes
            if lane.status is LaneStatus.PARKED
        ),
        why_not_auto_advance="The run is already closed.",
    )
    refreshed.closeout_summary = assess_closeout(refreshed, refreshed.open_findings)
    save_product_run(adapter, refreshed)
    return ProductCommandResult(success=True, state=refreshed)


def save_product_run(adapter, state: ProductRunState) -> Path:
    path = adapter.build_product_run_path(state.run_id)
    adapter.write_json(path, state.to_record())
    return path


def load_product_run(adapter, run_id: str) -> ProductRunState | None:
    path = adapter.build_product_run_path(run_id)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ProductRunState.from_record(payload)


def refresh_run_state(state: ProductRunState) -> ProductRunState:
    active_lane = _active_lane(state.lanes)
    parked_summary = tuple(
        f"{lane.lane_id}: {', '.join(lane.unblock_conditions) or 'waiting on mainline progress'}"
        for lane in state.lanes
        if lane.status is LaneStatus.PARKED
    )
    execution_readiness = assess_execution_readiness(state)
    gates = {
        "scope_gate": evaluate_scope_gate(state),
        "spec_gate": evaluate_spec_gate(state),
        "execution_gate": evaluate_execution_gate(state, execution_readiness),
        "validation_gate": evaluate_validation_gate(state, state.open_findings),
        "closeout_gate": evaluate_closeout_gate(state, state.open_findings),
    }
    open_findings = _collect_open_findings(state, execution_readiness, gates)
    closeout_summary = assess_closeout(state, open_findings)
    gates["validation_gate"] = evaluate_validation_gate(state, open_findings)
    gates["closeout_gate"] = evaluate_closeout_gate(state, open_findings)
    decision = decide_next_action(state, execution_readiness, gates, parked_summary, closeout_summary, open_findings)
    return ProductRunState(
        run_id=state.run_id,
        workflow_id=state.workflow_id,
        handoff=state.handoff,
        created_at=state.created_at,
        updated_at=datetime.utcnow().isoformat(timespec="seconds"),
        lanes=_update_lane_actions(state.lanes, decision, active_lane.lane_id if active_lane is not None else None),
        gates=gates,
        decision=decision,
        execution_readiness=execution_readiness,
        open_findings=open_findings,
        validation_status=state.validation_status,
        last_execution_record=state.last_execution_record,
        repair_spec_record=state.repair_spec_record,
        review_status=state.review_status,
        repair_rounds=state.repair_rounds,
        closeout_summary=closeout_summary,
        last_node_id=state.last_node_id,
        last_executor_name=state.last_executor_name,
        attempt_counts=state.attempt_counts,
        last_error_kind=state.last_error_kind,
        event_log=state.event_log,
        status=state.status,
    )


def repair_policy_for_workflow(workflow_id: str) -> RepairPolicy:
    return RepairPolicy(max_rounds=2, escalate_after_rounds=2)


def assess_closeout(state: ProductRunState, findings: tuple[ReviewFinding, ...]) -> CloseoutSummary:
    policy = repair_policy_for_workflow(state.workflow_id)
    blocking_findings = sum(1 for finding in findings if finding.is_blocking and finding.status is ReviewFindingStatus.OPEN)
    non_blocking_findings = sum(1 for finding in findings if not finding.is_blocking and finding.status is ReviewFindingStatus.OPEN)
    can_continue_repair = blocking_findings > 0 and state.repair_rounds < policy.max_rounds
    if blocking_findings > 0:
        reason = "Blocking findings remain open."
        if not can_continue_repair:
            reason = "Blocking findings remain open and repair rounds are exhausted."
        return CloseoutSummary(
            closeable=False,
            blocking_findings=blocking_findings,
            non_blocking_findings=non_blocking_findings,
            repair_rounds=state.repair_rounds,
            max_repair_rounds=policy.max_rounds,
            can_continue_repair=can_continue_repair,
            status="needs_repair" if can_continue_repair else "needs_review",
            reason=reason,
        )
    if state.validation_status is not ValidationStatus.PASSED:
        return CloseoutSummary(
            closeable=False,
            blocking_findings=0,
            non_blocking_findings=non_blocking_findings,
            repair_rounds=state.repair_rounds,
            max_repair_rounds=policy.max_rounds,
            can_continue_repair=False,
            status="validation_pending",
            reason="Validation has not passed yet.",
        )
    active_lanes = [lane for lane in state.lanes if lane.status is not LaneStatus.PARKED]
    incomplete_lanes = [lane.lane_id for lane in active_lanes if lane.status is not LaneStatus.COMPLETE]
    if incomplete_lanes:
        return CloseoutSummary(
            closeable=False,
            blocking_findings=0,
            non_blocking_findings=non_blocking_findings,
            repair_rounds=state.repair_rounds,
            max_repair_rounds=policy.max_rounds,
            can_continue_repair=False,
            status="lane_incomplete",
            reason="Active lanes are not complete yet.",
        )
    return CloseoutSummary(
        closeable=True,
        blocking_findings=0,
        non_blocking_findings=non_blocking_findings,
        repair_rounds=state.repair_rounds,
        max_repair_rounds=policy.max_rounds,
        can_continue_repair=False,
        status="closeable",
        reason="Validation passed and no blocking findings remain.",
    )


def assess_execution_readiness(state: ProductRunState) -> ExecutionReadiness:
    workflow = workflow_definitions()[state.workflow_id]
    node = workflow.node(state.handoff.initial_execution_intent.preferred_node)
    active_lane = _active_lane(state.lanes)
    if active_lane is None:
        return ExecutionReadiness(ready=False, blocking_reason="No active lane is available.")
    required_capabilities = node.required_capabilities if node is not None else ()
    recommended_dispatch_targets = _matching_executors(required_capabilities)
    missing_requirements: list[str] = []
    missing_execution_artifacts = [artifact.name for artifact in active_lane.missing_artifacts if artifact.category is ArtifactCategory.EXECUTION]
    present_planning_artifacts = [artifact.name for artifact in active_lane.current_artifacts if artifact.category is ArtifactCategory.PLANNING]
    if not state.handoff.initial_execution_intent.executable_package_present and not present_planning_artifacts:
        missing_requirements.append("executable package")
    if not recommended_dispatch_targets:
        missing_requirements.append("executor capability match")
    blocking_reason = None
    if state.handoff.initial_execution_intent.blocked_on_external_resource:
        blocking_reason = "blocked on external resource"
    ready = not missing_requirements and blocking_reason is None and bool(recommended_dispatch_targets)
    if missing_execution_artifacts and ready:
        # Execution can dispatch to produce these artifacts; this should hold rather than auto-plan.
        ready = True
    return ExecutionReadiness(
        ready=ready,
        missing_requirements=tuple(missing_requirements),
        required_capabilities=required_capabilities,
        recommended_dispatch_targets=recommended_dispatch_targets,
        blocking_reason=blocking_reason,
    )


def evaluate_scope_gate(state: ProductRunState) -> PhaseGateResult:
    if not state.handoff.request_summary.strip() or not state.lanes:
        return PhaseGateResult(
            gate_id="scope_gate",
            status=GateStatus.FAIL,
            missing_requirements=("request summary", "lane"),
            explanation="Scope gate requires a normalized request summary and at least one lane.",
        )
    return PhaseGateResult(
        gate_id="scope_gate",
        status=GateStatus.PASS,
        auto_advance_allowed=True,
        explanation="Scope is normalized into a handoff and lane model.",
    )


def evaluate_spec_gate(state: ProductRunState) -> PhaseGateResult:
    active_lane = _active_lane(state.lanes)
    if active_lane is None:
        return PhaseGateResult(gate_id="spec_gate", status=GateStatus.BLOCKED, missing_requirements=("active lane",), explanation="Spec gate requires one active lane.")
    planning_artifacts = [artifact.name for artifact in active_lane.current_artifacts if artifact.category is ArtifactCategory.PLANNING]
    if planning_artifacts:
        return PhaseGateResult(
            gate_id="spec_gate",
            status=GateStatus.PASS,
            auto_advance_allowed=True,
            explanation="Planning artifacts are present; the workflow can evaluate execution dispatch readiness.",
        )
    return PhaseGateResult(
        gate_id="spec_gate",
        status=GateStatus.NEEDS_REVIEW,
        missing_requirements=("planning artifacts",),
        explanation="Planning artifacts are still incomplete, so the workflow should hold before deeper execution steps.",
    )


def evaluate_execution_gate(state: ProductRunState, readiness: ExecutionReadiness) -> PhaseGateResult:
    if readiness.blocking_reason is not None:
        return PhaseGateResult(
            gate_id="execution_gate",
            status=GateStatus.BLOCKED,
            missing_requirements=tuple(readiness.missing_requirements),
            explanation=f"Execution gate is blocked: {readiness.blocking_reason}.",
        )
    if not readiness.ready:
        return PhaseGateResult(
            gate_id="execution_gate",
            status=GateStatus.FAIL,
            missing_requirements=tuple(readiness.missing_requirements),
            explanation="Execution gate failed because dispatch prerequisites are not satisfied.",
        )
    if state.handoff.initial_execution_intent.requires_human_approval:
        return PhaseGateResult(
            gate_id="execution_gate",
            status=GateStatus.NEEDS_REVIEW,
            auto_advance_allowed=False,
            explanation="Execution is ready for dispatch but requires an explicit control-plane approval decision.",
        )
    return PhaseGateResult(
        gate_id="execution_gate",
        status=GateStatus.PASS,
        auto_advance_allowed=True,
        explanation="Execution can dispatch now.",
    )


def evaluate_validation_gate(state: ProductRunState, findings: tuple[ReviewFinding, ...]) -> PhaseGateResult:
    blocking_findings = tuple(finding.summary for finding in findings if finding.is_blocking and finding.status is ReviewFindingStatus.OPEN)
    if blocking_findings:
        return PhaseGateResult(
            gate_id="validation_gate",
            status=GateStatus.NEEDS_REVIEW,
            missing_requirements=blocking_findings,
            explanation="Validation gate is waiting on review findings to be repaired and revalidated.",
        )
    if state.validation_status is ValidationStatus.PASSED:
        return PhaseGateResult(
            gate_id="validation_gate",
            status=GateStatus.PASS,
            auto_advance_allowed=True,
            explanation="Validation has passed for the active lane.",
        )
    if state.validation_status in {ValidationStatus.FAILED, ValidationStatus.INCOMPLETE}:
        return PhaseGateResult(
            gate_id="validation_gate",
            status=GateStatus.BLOCKED,
            explanation="Validation did not pass, so closeout cannot proceed.",
        )
    return PhaseGateResult(
        gate_id="validation_gate",
        status=GateStatus.NEEDS_REVIEW,
        explanation="Validation has not been collected yet.",
    )


def evaluate_closeout_gate(state: ProductRunState, findings: tuple[ReviewFinding, ...]) -> PhaseGateResult:
    active_lanes = [lane for lane in state.lanes if lane.status is not LaneStatus.PARKED]
    if any(finding.is_blocking and finding.status is ReviewFindingStatus.OPEN for finding in findings):
        return PhaseGateResult(
            gate_id="closeout_gate",
            status=GateStatus.NEEDS_REVIEW,
            missing_requirements=("open review findings",),
            explanation="Closeout must hold while review findings remain open.",
        )
    if state.validation_status is not ValidationStatus.PASSED:
        return PhaseGateResult(
            gate_id="closeout_gate",
            status=GateStatus.BLOCKED,
            missing_requirements=("passed validation",),
            explanation="Closeout requires a passed validation result.",
        )
    incomplete_lanes = [lane.lane_id for lane in active_lanes if lane.status is not LaneStatus.COMPLETE]
    if incomplete_lanes:
        return PhaseGateResult(
            gate_id="closeout_gate",
            status=GateStatus.NEEDS_REVIEW,
            missing_requirements=tuple(incomplete_lanes),
            explanation="Closeout is waiting for all active lanes to complete.",
        )
    return PhaseGateResult(
        gate_id="closeout_gate",
        status=GateStatus.PASS,
        auto_advance_allowed=False,
        explanation="Closeout can complete the run now.",
    )


def decide_next_action(
    state: ProductRunState,
    readiness: ExecutionReadiness,
    gates: dict[str, PhaseGateResult],
    parked_summary: tuple[str, ...],
    closeout_summary: CloseoutSummary,
    findings: tuple[ReviewFinding, ...],
) -> AdvanceDecision:
    active_lane = _active_lane(state.lanes)

    closeout_gate = gates["closeout_gate"]
    if closeout_gate.status is GateStatus.PASS:
        return AdvanceDecision(
            next_legal_actions=("close-phase", "close-run"),
            default_action="close-run",
            stop_reason="closeout_ready",
            parked_lane_summary=parked_summary,
            why_not_auto_advance="Phase closeout requires an explicit closing action even after the phase is complete.",
        )

    if active_lane is None:
        return AdvanceDecision(
            next_legal_actions=("hold-for-review",),
            default_action="hold-for-review",
            stop_reason="no-active-lane",
            blocked_reason="All lanes are parked or complete.",
            parked_lane_summary=parked_summary,
            why_not_auto_advance="There is no active lane to advance.",
        )

    blocking_findings = tuple(
        finding for finding in findings if finding.is_blocking and finding.status is ReviewFindingStatus.OPEN
    )
    if blocking_findings:
        if closeout_summary.can_continue_repair:
            return AdvanceDecision(
                next_legal_actions=("repair-dispatch", "hold-for-review"),
                default_action="repair-dispatch",
                stop_reason="repair_loop_active",
                blocked_reason=None,
                parked_lane_summary=parked_summary,
                why_not_auto_advance="The run is inside the review-repair loop; closeout is blocked until the blocking findings are repaired and validation passes.",
            )
        return AdvanceDecision(
            next_legal_actions=("hold-for-review",),
            default_action="hold-for-review",
            stop_reason="review_required",
            blocked_reason=closeout_summary.reason,
            parked_lane_summary=parked_summary,
            why_not_auto_advance="Repair rounds are exhausted or the findings require human review before the workflow can continue.",
        )

    if readiness.blocking_reason is not None:
        return AdvanceDecision(
            next_legal_actions=("hold-for-review", "park-lane"),
            default_action="hold-for-review",
            stop_reason="blocked",
            blocked_reason=readiness.blocking_reason,
            parked_lane_summary=parked_summary,
            why_not_auto_advance="The workflow is blocked on an external dependency and cannot dispatch automatically.",
        )

    execution_gate = gates["execution_gate"]
    if execution_gate.status in {GateStatus.PASS, GateStatus.NEEDS_REVIEW}:
        dispatch_actions = _derive_dispatch_actions(active_lane)
        if not dispatch_actions:
            dispatch_actions = ("dispatch-execution",)
        default_action = dispatch_actions[0] if execution_gate.auto_advance_allowed else "hold-for-review"
        return AdvanceDecision(
            next_legal_actions=dispatch_actions + ("hold-for-review",),
            default_action=default_action,
            stop_reason="execution_gate_pending",
            parked_lane_summary=parked_summary,
            why_not_auto_advance=(
                None
                if execution_gate.auto_advance_allowed
                else "The lane is ready for executor dispatch, but automatic continuation is disabled until an explicit approval decision is made."
            ),
        )

    spec_gate = gates["spec_gate"]
    if spec_gate.status in {GateStatus.FAIL, GateStatus.NEEDS_REVIEW}:
        return AdvanceDecision(
            next_legal_actions=("hold-for-review", "compile-planning-artifacts"),
            default_action="hold-for-review",
            stop_reason="spec_gate_pending",
            blocked_reason=None,
            parked_lane_summary=parked_summary,
            why_not_auto_advance="Planning readiness is incomplete, so the control plane will not derive more planning docs by default.",
        )

    return AdvanceDecision(
        next_legal_actions=("hold-for-review",),
        default_action="hold-for-review",
        stop_reason="held",
        parked_lane_summary=parked_summary,
        why_not_auto_advance="No legal auto-advance path is available.",
    )


def render_state_summary(state: ProductRunState) -> str:
    active_lane = _active_lane(state.lanes)
    blocked = [lane.lane_id for lane in state.lanes if lane.status is LaneStatus.BLOCKED]
    lines = [
        f"Run: {state.run_id}",
        f"Workflow: {state.workflow_id}",
        f"Current Phase: {active_lane.parent_phase if active_lane is not None else state.handoff.phase_hint or 'unknown'}",
        f"Request: {state.handoff.request_summary}",
        f"Status: {state.status}",
    ]
    if active_lane is not None:
        lines.append(f"Active Lane: {active_lane.lane_id} ({active_lane.parent_phase})")
    parked = [lane.lane_id for lane in state.lanes if lane.status is LaneStatus.PARKED]
    if parked:
        lines.append(f"Parked Lanes: {', '.join(parked)}")
    if blocked:
        lines.append(f"Blocked Lanes: {', '.join(blocked)}")
    lines.append(f"Default Action: {state.decision.default_action}")
    lines.append(f"Next Legal Actions: {', '.join(state.decision.next_legal_actions)}")
    if state.decision.stop_reason:
        lines.append(f"Stop Reason: {state.decision.stop_reason}")
    if state.decision.blocked_reason is not None:
        lines.append(f"Blocked Reason: {state.decision.blocked_reason}")
    if state.decision.why_not_auto_advance is not None:
        lines.append(f"Why Not Auto Advance: {state.decision.why_not_auto_advance}")
    lines.append(f"Execution Ready: {'yes' if state.execution_readiness.ready else 'no'}")
    if state.execution_readiness.missing_requirements:
        lines.append(f"Missing Requirements: {', '.join(state.execution_readiness.missing_requirements)}")
    if state.execution_readiness.recommended_dispatch_targets:
        lines.append(
            f"Dispatch Targets: {', '.join(state.execution_readiness.recommended_dispatch_targets)}"
        )
    lines.extend(_render_artifact_summary(state, active_lane))
    for gate_name in ("scope_gate", "spec_gate", "execution_gate", "validation_gate", "closeout_gate"):
        gate = state.gates.get(gate_name)
        if gate is not None:
            lines.append(f"{gate_name}: {gate.status.value}")
    lines.append(_render_findings_summary(state.open_findings))
    if state.open_findings:
        lines.append("Open Findings:")
        lines.extend(
            f"- {finding.normalized_finding_id}: {finding.summary} [{finding.severity.value}/{finding.status.value}]"
            for finding in state.open_findings
        )
    active_missing = []
    if active_lane is not None:
        active_missing = [artifact.name for artifact in active_lane.missing_artifacts]
    if active_missing:
        lines.append(f"Missing Artifacts: {', '.join(active_missing)}")
    if state.last_node_id is not None:
        lines.append(f"Last Node: {state.last_node_id}")
    if state.last_executor_name is not None:
        lines.append(f"Last Executor: {state.last_executor_name}")
    if state.last_execution_record is not None:
        last_status = state.last_execution_record.get("final_status")
        last_summary = state.last_execution_record.get("summary")
        if isinstance(last_status, str):
            lines.append(f"Last Executor Result: {last_status}")
        if isinstance(last_summary, str):
            lines.append(f"Last Result Summary: {last_summary}")
    if state.closeout_summary is not None:
        lines.append(
            "Closeout Summary: "
            + (
                "closeable"
                if state.closeout_summary.closeable
                else f"{state.closeout_summary.status} ({state.closeout_summary.reason})"
            )
        )
        lines.append(
            f"Repair Rounds: {state.closeout_summary.repair_rounds}/{state.closeout_summary.max_repair_rounds}"
        )
        lines.append(
            "Closeable: " + ("yes" if state.closeout_summary.closeable else "no")
        )
    lines.extend(_render_event_timeline(state.event_log))
    return "\n".join(lines)


def _execute_node(
    adapter,
    state: ProductRunState,
    node_id: str,
    *,
    forced_executor: str | None = None,
) -> ProductRunState:
    workflow = workflow_definitions()[state.workflow_id]
    node = workflow.node(node_id)
    if node is None:
        return state
    attempts = dict(state.attempt_counts)
    attempts[node_id] = attempts.get(node_id, 0) + 1
    executor_name = forced_executor or _select_executor(node, attempts[node_id] - 1)
    if executor_name is None:
        state.last_error_kind = ProductErrorKind.CAPABILITY_MISMATCH
        state.event_log = state.event_log + (f"{node_id}: capability-mismatch",)
        return state
    descriptor = available_executors()[executor_name]
    if node_id == "review-dispatch":
        findings = _build_review_findings(state, descriptor)
        repair_candidate = derive_repair_spec_candidate(
            spec_title=state.handoff.request_summary,
            findings=findings,
            uncovered_items=tuple(finding.summary for finding in findings),
            validations_claimed=("review loop closeout",),
            repair_round=state.repair_rounds + 1,
        )
        review_execution = ExecutionResult(
            executor=descriptor,
            spec_identity=state.run_id,
            dispatch_summary={"workflow": state.workflow_id, "node": node_id},
            final_status=ExecutionStatus.SUCCEEDED,
            summary=f"{descriptor.name} reviewed the execution output and produced normalized findings.",
            findings=findings,
            repair_spec_candidate=repair_candidate,
            suggested_followups=("repair-dispatch", "validation-collect"),
        )
        updated_lane = _set_active_lane_status(state.lanes, LaneStatus.AWAITING_REVIEW)
        return ProductRunState(
            run_id=state.run_id,
            workflow_id=state.workflow_id,
            handoff=state.handoff,
            created_at=state.created_at,
            updated_at=datetime.utcnow().isoformat(timespec="seconds"),
            lanes=updated_lane,
            gates=state.gates,
            decision=state.decision,
            execution_readiness=state.execution_readiness,
            open_findings=findings,
            validation_status=ValidationStatus.INCOMPLETE if findings else ValidationStatus.PASSED,
            last_execution_record=review_execution.to_record(),
            repair_spec_record=repair_candidate.to_record() if repair_candidate is not None else None,
            review_status="review_required" if findings else "passed",
            repair_rounds=state.repair_rounds,
            closeout_summary=state.closeout_summary,
            last_node_id=node_id,
            last_executor_name=executor_name,
            attempt_counts=attempts,
            last_error_kind=ProductErrorKind.REVIEW_REQUIRED if findings else None,
            event_log=state.event_log + (f"review:{node_id}:{executor_name}",),
            status=state.status,
        )

    execution = _build_execution_result(state, descriptor, node_id)
    updated_lane_status = LaneStatus.AWAITING_REVIEW if workflow.node("review-dispatch") is not None else LaneStatus.COMPLETE
    if node_id == "repair-dispatch":
        updated_lane_status = LaneStatus.COMPLETE
    return ProductRunState(
        run_id=state.run_id,
        workflow_id=state.workflow_id,
        handoff=state.handoff,
        created_at=state.created_at,
        updated_at=datetime.utcnow().isoformat(timespec="seconds"),
        lanes=_set_active_lane_status(state.lanes, updated_lane_status),
        gates=state.gates,
        decision=state.decision,
        execution_readiness=state.execution_readiness,
        open_findings=() if node_id == "repair-dispatch" else state.open_findings,
        validation_status=ValidationStatus.PASSED if node_id == "repair-dispatch" else state.validation_status,
        last_execution_record=execution.to_record(),
        repair_spec_record=None if node_id == "repair-dispatch" else state.repair_spec_record,
        review_status="repaired" if node_id == "repair-dispatch" else state.review_status,
        repair_rounds=state.repair_rounds + (1 if node_id == "repair-dispatch" else 0),
        closeout_summary=state.closeout_summary,
        last_node_id=node_id,
        last_executor_name=executor_name,
        attempt_counts=attempts,
        last_error_kind=None,
        event_log=state.event_log + (_timeline_event_for_node(node_id, executor_name),),
        status=state.status,
    )


def _build_execution_result(state: ProductRunState, descriptor: ExecutorDescriptor, node_id: str) -> ExecutionResult:
    active_lane = _active_lane(state.lanes)
    changed_files = ()
    if state.workflow_id == "repo-coding-task":
        changed_files = ("src/ai_engineering_runtime/cli.py",)
    summary = f"{descriptor.name} completed {node_id} for lane {active_lane.lane_id if active_lane is not None else 'none'}."
    if node_id == "repair-dispatch":
        summary = f"{descriptor.name} repaired the review findings and revalidated the lane."
    return ExecutionResult(
        executor=descriptor,
        spec_identity=state.run_id,
        dispatch_summary={"workflow": state.workflow_id, "node": node_id},
        final_status=ExecutionStatus.SUCCEEDED,
        summary=summary,
        changed_files=changed_files,
        validations_claimed=("validation-rollup",) if node_id == "repair-dispatch" else ("executor-dispatch",),
        suggested_followups=("review-dispatch",) if node_id == "executor-dispatch" else (),
    )


def _build_review_findings(state: ProductRunState, descriptor: ExecutorDescriptor) -> tuple[ReviewFinding, ...]:
    if not state.handoff.review_expectations:
        return ()
    changed_files = ()
    if isinstance(state.last_execution_record, dict):
        raw_changed_files = state.last_execution_record.get("changed_files", [])
        if isinstance(raw_changed_files, list) and all(isinstance(item, str) for item in raw_changed_files):
            changed_files = tuple(raw_changed_files)
    findings: list[ReviewFinding] = []
    for index, item in enumerate(state.handoff.review_expectations[:3], start=1):
        suggested_fix_kind = "repair"
        category = "review"
        if "validation" in item.lower():
            category = "validation"
            suggested_fix_kind = "validation"
        elif "closeout" in item.lower() or "documentation" in item.lower():
            category = "closeout"
            suggested_fix_kind = "closeout"
        findings.append(
            ReviewFinding(
                code="review-required",
                message=item,
                severity=ReviewFindingSeverity.BLOCKING,
                source=descriptor.name,
                category=category,
                scope=state.handoff.phase_hint or "review-loop",
                affected_files=changed_files,
                affected_artifacts=("review-closeout-summary",),
                evidence=(state.last_execution_record.get("summary", "review expectation requested by runtime") if isinstance(state.last_execution_record, dict) else "review expectation requested by runtime",),
                suggested_fix_kind=suggested_fix_kind,
                finding_id=f"{descriptor.name}/review-{index}",
            )
        )
    return tuple(findings)


def _collect_open_findings(
    state: ProductRunState,
    readiness: ExecutionReadiness,
    gates: dict[str, PhaseGateResult],
) -> tuple[ReviewFinding, ...]:
    findings = list(
        normalize_review_findings(
            state.open_findings,
            scope=state.handoff.phase_hint or "runtime",
        )
    )
    if state.validation_status in {ValidationStatus.FAILED, ValidationStatus.INCOMPLETE} and not any(
        finding.code == "validation-not-passed" for finding in findings
    ):
        findings.append(
            ReviewFinding(
                code="validation-not-passed",
                message="Validation has not passed for the active lane.",
                severity=ReviewFindingSeverity.BLOCKING,
                source="validation-collect",
                category="validation",
                scope=state.handoff.phase_hint or "validation",
                affected_artifacts=("validation-rollup",),
                evidence=(f"validation_status={state.validation_status.value}",),
                suggested_fix_kind="validation",
                finding_id="validation/not-passed",
            )
        )
    if (
        readiness.blocking_reason is not None
        and _active_lane(state.lanes) is not None
        and state.validation_status is not ValidationStatus.PASSED
        and not any(finding.code == "runtime-blocked" for finding in findings)
    ):
        findings.append(
            ReviewFinding(
                code="runtime-blocked",
                message=f"Runtime is blocked: {readiness.blocking_reason}.",
                severity=ReviewFindingSeverity.BLOCKING,
                source="execution-gate",
                category="gate",
                scope=state.handoff.phase_hint or "dispatch",
                affected_artifacts=("execution-readiness",),
                evidence=tuple(gates["execution_gate"].missing_requirements),
                suggested_fix_kind="manual_decision",
                finding_id="runtime/execution-blocked",
            )
        )
    deduped: list[ReviewFinding] = []
    seen: set[str] = set()
    for finding in findings:
        key = finding.normalized_finding_id
        if key in seen or finding.status is not ReviewFindingStatus.OPEN:
            continue
        seen.add(key)
        deduped.append(finding)
    return tuple(deduped)


def _render_findings_summary(findings: tuple[ReviewFinding, ...]) -> str:
    blocking = sum(1 for finding in findings if finding.is_blocking and finding.status is ReviewFindingStatus.OPEN)
    non_blocking = sum(1 for finding in findings if not finding.is_blocking and finding.status is ReviewFindingStatus.OPEN)
    return f"Open Findings Summary: blocking={blocking}, non-blocking={non_blocking}"


def _render_artifact_summary(state: ProductRunState, active_lane: HandoffLane | None) -> list[str]:
    if active_lane is None:
        return []
    categories = {
        ArtifactCategory.PLANNING: ([], []),
        ArtifactCategory.EXECUTION: ([], []),
        ArtifactCategory.REVIEW_CLOSEOUT: ([], []),
    }
    for artifact in active_lane.current_artifacts:
        categories[artifact.category][0].append(artifact.name)
    for artifact in active_lane.missing_artifacts:
        categories[artifact.category][1].append(artifact.name)
    lines: list[str] = []
    for category, label in (
        (ArtifactCategory.PLANNING, "Planning Artifacts"),
        (ArtifactCategory.EXECUTION, "Execution Artifacts"),
        (ArtifactCategory.REVIEW_CLOSEOUT, "Review/Closeout Artifacts"),
    ):
        present, missing = categories[category]
        if present:
            lines.append(f"{label} Present: {', '.join(present)}")
        if missing:
            lines.append(f"{label} Missing: {', '.join(missing)}")
    return lines


def _render_event_timeline(event_log: tuple[str, ...]) -> list[str]:
    if not event_log:
        return []
    lines = ["Timeline:"]
    for entry in event_log:
        lines.append(f"- {entry}")
    return lines


def _timeline_event_for_node(node_id: str, executor_name: str) -> str:
    if node_id == "executor-dispatch":
        return f"dispatch:{node_id}:{executor_name}"
    if node_id == "repair-dispatch":
        return f"repair:{node_id}:{executor_name}"
    return f"node:{node_id}:{executor_name}"


def _matching_executors(required_capabilities: tuple[str, ...]) -> tuple[str, ...]:
    matches: list[str] = []
    for name, descriptor in available_executors().items():
        capabilities = descriptor.capabilities.to_record()
        if all(bool(capabilities.get(capability)) for capability in required_capabilities):
            matches.append(name)
    return tuple(matches)


def _select_executor(node: WorkflowNodeDefinition, prior_attempts: int) -> str | None:
    matched = _matching_executors(node.required_capabilities)
    if node.primary_executor in matched and prior_attempts < node.retry_policy.max_attempts:
        return node.primary_executor
    if node.fallback_executor in matched:
        return node.fallback_executor
    if node.primary_executor in matched:
        return node.primary_executor
    return matched[0] if matched else None


def _derive_dispatch_actions(lane: HandoffLane) -> tuple[str, ...]:
    execution_missing = [artifact.name for artifact in lane.missing_artifacts if artifact.category is ArtifactCategory.EXECUTION]
    if not execution_missing:
        return ("dispatch-execution",)
    actions: list[str] = []
    for item in execution_missing:
        lowered = item.lower()
        if "baseline" in lowered:
            actions.append("dispatch-baseline-eval")
        elif "teacher" in lowered and ("expand" in lowered or "expansion" in lowered):
            actions.append("dispatch-teacher-expand")
        elif "sft" in lowered:
            actions.append("dispatch-sft-run")
        else:
            actions.append("dispatch-" + _slug(item))
    return tuple(_unique(actions))


def _set_active_lane_status(lanes: tuple[HandoffLane, ...], status: LaneStatus) -> tuple[HandoffLane, ...]:
    active = _active_lane(lanes)
    updated: list[HandoffLane] = []
    for lane in lanes:
        if active is not None and lane.lane_id == active.lane_id:
            updated.append(
                HandoffLane(
                    lane_id=lane.lane_id,
                    title=lane.title,
                    status=status,
                    priority=lane.priority,
                    goal=lane.goal,
                    parent_phase=lane.parent_phase,
                    unblock_conditions=lane.unblock_conditions,
                    next_legal_actions=lane.next_legal_actions,
                    deferred_scope=lane.deferred_scope,
                    not_doing_now=lane.not_doing_now,
                    current_artifacts=lane.current_artifacts,
                    missing_artifacts=lane.missing_artifacts,
                )
            )
            continue
        updated.append(lane)
    return tuple(updated)


def _update_lane_actions(
    lanes: tuple[HandoffLane, ...],
    decision: AdvanceDecision,
    active_lane_id: str | None,
) -> tuple[HandoffLane, ...]:
    updated: list[HandoffLane] = []
    for lane in lanes:
        next_actions = lane.next_legal_actions
        if active_lane_id is not None and lane.lane_id == active_lane_id:
            next_actions = decision.next_legal_actions
        updated.append(
            HandoffLane(
                lane_id=lane.lane_id,
                title=lane.title,
                status=lane.status,
                priority=lane.priority,
                goal=lane.goal,
                parent_phase=lane.parent_phase,
                unblock_conditions=lane.unblock_conditions,
                next_legal_actions=next_actions,
                deferred_scope=lane.deferred_scope,
                not_doing_now=lane.not_doing_now,
                current_artifacts=lane.current_artifacts,
                missing_artifacts=lane.missing_artifacts,
            )
        )
    return tuple(updated)


def _active_lane(lanes: tuple[HandoffLane, ...]) -> HandoffLane | None:
    candidates = [lane for lane in lanes if lane.status not in {LaneStatus.PARKED, LaneStatus.COMPLETE}]
    if not candidates:
        return None
    candidates.sort(key=lambda lane: lane.priority)
    return candidates[0]


def _parse_review_findings(value: object) -> tuple[ReviewFinding, ...] | None:
    if not isinstance(value, list):
        return None
    findings: list[ReviewFinding] = []
    for item in value:
        finding = ReviewFinding.from_record(item)
        if finding is None:
            return None
        findings.append(finding)
    return tuple(findings)


def _missing_run_reasons(run_id: str) -> tuple[RuntimeReason, ...]:
    return (
        RuntimeReason(code="missing-product-run", message=f"Product run not found: {run_id}", field="run_id"),
    )


def _slug(value: str) -> str:
    filtered = []
    for char in value.lower():
        filtered.append(char if char.isalnum() else "-")
    rendered = "".join(filtered)
    while "--" in rendered:
        rendered = rendered.replace("--", "-")
    return rendered.strip("-") or "action"


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered
