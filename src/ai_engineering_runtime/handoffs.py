from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
import re

from ai_engineering_runtime.state import RuntimeReason

HANDOFF_SCHEMA_VERSION = 1


class IntakeSourceKind(str, Enum):
    CHAT = "chat"
    PROMPT = "prompt"
    HANDOFF = "handoff"


class IntakeProfileKind(str, Enum):
    CHAT_TRANSCRIPT = "chat_transcript"
    SINGLE_PROMPT = "single_prompt"
    TASK_REQUEST = "task_request"
    STRUCTURED_HANDOFF = "structured_handoff"


class ArtifactCategory(str, Enum):
    PLANNING = "planning"
    EXECUTION = "execution"
    REVIEW_CLOSEOUT = "review_closeout"


class ArtifactPresence(str, Enum):
    PRESENT = "present"
    MISSING = "missing"


class LaneStatus(str, Enum):
    ACTIVE = "active"
    PARKED = "parked"
    BLOCKED = "blocked"
    AWAITING_REVIEW = "awaiting_review"
    AWAITING_EXECUTOR = "awaiting_executor"
    READY_FOR_DISPATCH = "ready_for_dispatch"
    COMPLETE = "complete"


@dataclass(frozen=True)
class HandoffArtifact:
    name: str
    category: ArtifactCategory
    presence: ArtifactPresence
    detail: str | None = None

    def to_record(self) -> dict[str, str | None]:
        return {
            "name": self.name,
            "category": self.category.value,
            "presence": self.presence.value,
            "detail": self.detail,
        }

    @classmethod
    def from_record(cls, value: object) -> "HandoffArtifact" | None:
        if not isinstance(value, dict):
            return None
        name = value.get("name")
        category = value.get("category")
        presence = value.get("presence")
        detail = value.get("detail")
        if not isinstance(name, str) or not isinstance(category, str) or not isinstance(presence, str):
            return None
        if detail is not None and not isinstance(detail, str):
            return None
        try:
            return cls(
                name=name,
                category=ArtifactCategory(category),
                presence=ArtifactPresence(presence),
                detail=detail,
            )
        except ValueError:
            return None


@dataclass(frozen=True)
class ExecutionIntent:
    summary: str
    executable_package_present: bool = False
    requires_human_approval: bool = True
    blocked_on_external_resource: bool = False
    dispatch_mode: str = "manual"
    preferred_node: str = "executor-dispatch"

    def to_record(self) -> dict[str, object]:
        return {
            "summary": self.summary,
            "executable_package_present": self.executable_package_present,
            "requires_human_approval": self.requires_human_approval,
            "blocked_on_external_resource": self.blocked_on_external_resource,
            "dispatch_mode": self.dispatch_mode,
            "preferred_node": self.preferred_node,
        }

    @classmethod
    def from_record(cls, value: object) -> "ExecutionIntent" | None:
        if not isinstance(value, dict):
            return None
        summary = value.get("summary")
        executable_package_present = value.get("executable_package_present")
        requires_human_approval = value.get("requires_human_approval")
        blocked_on_external_resource = value.get("blocked_on_external_resource")
        dispatch_mode = value.get("dispatch_mode")
        preferred_node = value.get("preferred_node")
        if not isinstance(summary, str):
            return None
        if not isinstance(executable_package_present, bool):
            return None
        if not isinstance(requires_human_approval, bool):
            return None
        if not isinstance(blocked_on_external_resource, bool):
            return None
        if not isinstance(dispatch_mode, str) or not isinstance(preferred_node, str):
            return None
        return cls(
            summary=summary,
            executable_package_present=executable_package_present,
            requires_human_approval=requires_human_approval,
            blocked_on_external_resource=blocked_on_external_resource,
            dispatch_mode=dispatch_mode,
            preferred_node=preferred_node,
        )


@dataclass(frozen=True)
class HandoffLane:
    lane_id: str
    title: str
    status: LaneStatus
    priority: int
    goal: str
    parent_phase: str
    unblock_conditions: tuple[str, ...] = ()
    next_legal_actions: tuple[str, ...] = ()
    deferred_scope: tuple[str, ...] = ()
    not_doing_now: tuple[str, ...] = ()
    current_artifacts: tuple[HandoffArtifact, ...] = ()
    missing_artifacts: tuple[HandoffArtifact, ...] = ()

    def to_record(self) -> dict[str, object]:
        return {
            "lane_id": self.lane_id,
            "title": self.title,
            "status": self.status.value,
            "priority": self.priority,
            "goal": self.goal,
            "parent_phase": self.parent_phase,
            "unblock_conditions": list(self.unblock_conditions),
            "next_legal_actions": list(self.next_legal_actions),
            "deferred_scope": list(self.deferred_scope),
            "not_doing_now": list(self.not_doing_now),
            "current_artifacts": [artifact.to_record() for artifact in self.current_artifacts],
            "missing_artifacts": [artifact.to_record() for artifact in self.missing_artifacts],
        }

    @classmethod
    def from_record(cls, value: object) -> "HandoffLane" | None:
        if not isinstance(value, dict):
            return None
        lane_id = value.get("lane_id")
        title = value.get("title")
        status = value.get("status")
        priority = value.get("priority")
        goal = value.get("goal")
        parent_phase = value.get("parent_phase")
        if not all(isinstance(item, str) for item in (lane_id, title, status, goal, parent_phase)):
            return None
        if not isinstance(priority, int):
            return None
        try:
            lane_status = LaneStatus(status)
        except ValueError:
            return None

        parsed_current = _parse_artifact_list(value.get("current_artifacts"))
        parsed_missing = _parse_artifact_list(value.get("missing_artifacts"))
        if parsed_current is None or parsed_missing is None:
            return None
        sequences = {}
        for key in ("unblock_conditions", "next_legal_actions", "deferred_scope", "not_doing_now"):
            raw_value = value.get(key, [])
            if not isinstance(raw_value, list) or not all(isinstance(item, str) for item in raw_value):
                return None
            sequences[key] = tuple(raw_value)

        return cls(
            lane_id=lane_id,
            title=title,
            status=lane_status,
            priority=priority,
            goal=goal,
            parent_phase=parent_phase,
            unblock_conditions=sequences["unblock_conditions"],
            next_legal_actions=sequences["next_legal_actions"],
            deferred_scope=sequences["deferred_scope"],
            not_doing_now=sequences["not_doing_now"],
            current_artifacts=parsed_current,
            missing_artifacts=parsed_missing,
        )


@dataclass(frozen=True)
class HandoffDocument:
    schema_version: int
    source_kind: IntakeSourceKind
    intake_profile: IntakeProfileKind
    source_path: str | None
    request_summary: str
    normalized_objective: str
    workflow_id: str
    workflow_hint: str | None
    lane_hint: str | None
    phase_hint: str | None
    phase_metadata: dict[str, str]
    required_artifacts: tuple[HandoffArtifact, ...]
    initial_execution_intent: ExecutionIntent
    review_expectations: tuple[str, ...]
    constraints: tuple[str, ...]
    defaults_applied: tuple[str, ...]
    warnings: tuple[str, ...]
    lanes: tuple[HandoffLane, ...]
    repo_context: dict[str, str] = field(default_factory=dict)
    raw_request_excerpt: str = ""

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "source_kind": self.source_kind.value,
            "intake_profile": self.intake_profile.value,
            "source_path": self.source_path,
            "request_summary": self.request_summary,
            "normalized_objective": self.normalized_objective,
            "workflow_id": self.workflow_id,
            "workflow_hint": self.workflow_hint,
            "lane_hint": self.lane_hint,
            "phase_hint": self.phase_hint,
            "phase_metadata": self.phase_metadata,
            "required_artifacts": [artifact.to_record() for artifact in self.required_artifacts],
            "initial_execution_intent": self.initial_execution_intent.to_record(),
            "review_expectations": list(self.review_expectations),
            "constraints": list(self.constraints),
            "defaults_applied": list(self.defaults_applied),
            "warnings": list(self.warnings),
            "lanes": [lane.to_record() for lane in self.lanes],
            "repo_context": self.repo_context,
            "raw_request_excerpt": self.raw_request_excerpt,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_record(), indent=2, sort_keys=True)

    @classmethod
    def from_record(cls, value: object) -> "HandoffDocument" | None:
        if not isinstance(value, dict):
            return None
        schema_version = value.get("schema_version")
        source_kind = value.get("source_kind")
        intake_profile = value.get("intake_profile", IntakeProfileKind.STRUCTURED_HANDOFF.value)
        source_path = value.get("source_path")
        request_summary = value.get("request_summary")
        normalized_objective = value.get("normalized_objective")
        workflow_id = value.get("workflow_id")
        workflow_hint = value.get("workflow_hint")
        lane_hint = value.get("lane_hint")
        phase_hint = value.get("phase_hint")
        phase_metadata = value.get("phase_metadata")
        repo_context = value.get("repo_context", {})
        raw_request_excerpt = value.get("raw_request_excerpt", "")
        if not isinstance(schema_version, int):
            return None
        if not all(isinstance(item, str) for item in (source_kind, intake_profile, request_summary, normalized_objective, workflow_id)):
            return None
        if source_path is not None and not isinstance(source_path, str):
            return None
        if workflow_hint is not None and not isinstance(workflow_hint, str):
            return None
        if lane_hint is not None and not isinstance(lane_hint, str):
            return None
        if phase_hint is not None and not isinstance(phase_hint, str):
            return None
        if not isinstance(phase_metadata, dict) or not all(
            isinstance(key, str) and isinstance(item, str) for key, item in phase_metadata.items()
        ):
            return None
        if not isinstance(repo_context, dict) or not all(
            isinstance(key, str) and isinstance(item, str) for key, item in repo_context.items()
        ):
            return None
        if not isinstance(raw_request_excerpt, str):
            return None
        try:
            parsed_source_kind = IntakeSourceKind(source_kind)
            parsed_intake_profile = IntakeProfileKind(intake_profile)
        except ValueError:
            return None

        required_artifacts = _parse_artifact_list(value.get("required_artifacts"))
        lanes = _parse_lane_list(value.get("lanes"))
        intent = ExecutionIntent.from_record(value.get("initial_execution_intent"))
        review_expectations = value.get("review_expectations", [])
        constraints = value.get("constraints", [])
        defaults_applied = value.get("defaults_applied", [])
        warnings = value.get("warnings", [])
        if required_artifacts is None or lanes is None or intent is None:
            return None
        if not isinstance(review_expectations, list) or not all(isinstance(item, str) for item in review_expectations):
            return None
        if not isinstance(constraints, list) or not all(isinstance(item, str) for item in constraints):
            return None
        if not isinstance(defaults_applied, list) or not all(isinstance(item, str) for item in defaults_applied):
            return None
        if not isinstance(warnings, list) or not all(isinstance(item, str) for item in warnings):
            return None
        return cls(
            schema_version=schema_version,
            source_kind=parsed_source_kind,
            intake_profile=parsed_intake_profile,
            source_path=source_path,
            request_summary=request_summary,
            normalized_objective=normalized_objective,
            workflow_id=workflow_id,
            workflow_hint=workflow_hint,
            lane_hint=lane_hint,
            phase_hint=phase_hint,
            phase_metadata=phase_metadata,
            required_artifacts=required_artifacts,
            initial_execution_intent=intent,
            review_expectations=tuple(review_expectations),
            constraints=tuple(constraints),
            defaults_applied=tuple(defaults_applied),
            warnings=tuple(warnings),
            lanes=lanes,
            repo_context=repo_context,
            raw_request_excerpt=raw_request_excerpt,
        )


def compile_handoff(
    *,
    text: str,
    source_kind: IntakeSourceKind,
    repo_root: Path,
    source_path: Path | None = None,
    workflow_hint: str | None = None,
) -> HandoffDocument:
    stripped = text.strip()
    lines = [line.rstrip() for line in stripped.splitlines()]
    non_empty = [line.strip() for line in lines if line.strip()]
    request_summary = _derive_request_summary(non_empty)
    normalized_objective = _derive_normalized_objective(lines, request_summary)
    intake_profile = _infer_intake_profile(text, source_kind)
    parsed_workflow_hint = workflow_hint or _extract_single_label(text, ("workflow hint", "workflow", "流程 hint"))
    workflow_id = _select_workflow_id(text, parsed_workflow_hint)
    constraints = tuple(
        _extract_multi_label_items(text, ("constraint", "constraints", "约束", "forbidden scope", "forbidden expansion"))
    )
    review_expectations = tuple(
        _extract_multi_label_items(text, ("review expectation", "review expectations", "review", "验收", "review point"))
    )
    defaults_applied: list[str] = []
    warnings: list[str] = []
    lane_hint = _extract_single_label(text, ("lane hint", "lane", "主线 lane", "副线 lane"))
    phase_hint = _extract_single_label(text, ("phase hint", "current phase", "phase"))
    lanes = _parse_lanes(text)
    if not lanes:
        defaults_applied.append("defaulted one active main lane because no explicit lane block was provided")
        lanes = (
            HandoffLane(
                lane_id="main",
                title="main",
                status=LaneStatus.ACTIVE,
                priority=1,
                goal=request_summary,
                parent_phase=phase_hint or "intake",
            ),
        )
    if parsed_workflow_hint is None:
        defaults_applied.append(f"workflow inferred as {workflow_id}")
    if phase_hint is None:
        defaults_applied.append("phase defaulted from the first active lane or intake")
    if not review_expectations:
        warnings.append("No explicit review expectation was supplied; runtime review will fall back to executor and validation signals.")
    if source_kind is not IntakeSourceKind.HANDOFF and lane_hint is None:
        warnings.append("No explicit lane hint was supplied; lane routing was inferred from the request text.")

    required_artifacts = _collect_required_artifacts(lanes)
    execution_intent = ExecutionIntent(
        summary=_extract_single_label(text, ("execution intent", "dispatch intent"))
        or "Evaluate the next legal action after handoff compilation.",
        executable_package_present=bool(required_artifacts) or bool(_extract_single_label(text, ("current assets", "current asset"))),
        requires_human_approval=_extract_bool(text, ("requires approval", "human approval"), default=source_kind is not IntakeSourceKind.HANDOFF),
        blocked_on_external_resource=_extract_bool(text, ("blocked on external", "external block", "blocked on resource"), default=False),
        dispatch_mode="auto" if _extract_bool(text, ("auto dispatch", "auto-dispatch"), default=False) else "manual",
        preferred_node="executor-dispatch",
    )
    if execution_intent.dispatch_mode == "manual":
        defaults_applied.append("dispatch mode defaulted to manual")
    current_phase = next((lane.parent_phase for lane in lanes if lane.status is not LaneStatus.PARKED), lanes[0].parent_phase)
    return HandoffDocument(
        schema_version=HANDOFF_SCHEMA_VERSION,
        source_kind=source_kind,
        intake_profile=intake_profile,
        source_path=source_path.resolve().as_posix() if source_path is not None else None,
        request_summary=request_summary,
        normalized_objective=normalized_objective,
        workflow_id=workflow_id,
        workflow_hint=parsed_workflow_hint,
        lane_hint=lane_hint,
        phase_hint=phase_hint or current_phase,
        phase_metadata={
            "initial_phase": current_phase,
            "lane_count": str(len(lanes)),
            "repo_root": repo_root.name,
            "intake_profile": intake_profile.value,
        },
        required_artifacts=required_artifacts,
        initial_execution_intent=execution_intent,
        review_expectations=review_expectations,
        constraints=constraints,
        defaults_applied=tuple(_unique(defaults_applied)),
        warnings=tuple(_unique(warnings)),
        lanes=lanes,
        repo_context={"repo_root": repo_root.resolve().as_posix(), "repo_name": repo_root.name},
        raw_request_excerpt="\n".join(lines[:20]),
    )


def load_handoff(path: Path) -> HandoffDocument:
    payload = json.loads(path.read_text(encoding="utf-8"))
    handoff = HandoffDocument.from_record(payload)
    if handoff is None:
        raise ValueError(f"Invalid handoff payload: {path.as_posix()}")
    return handoff


def validate_handoff(handoff: HandoffDocument) -> tuple[RuntimeReason, ...]:
    reasons: list[RuntimeReason] = []
    if handoff.schema_version != HANDOFF_SCHEMA_VERSION:
        reasons.append(
            RuntimeReason(
                code="unsupported-handoff-schema",
                message=f"Unsupported handoff schema version: {handoff.schema_version}",
                field="schema_version",
            )
        )
    if not handoff.request_summary.strip():
        reasons.append(
            RuntimeReason(
                code="missing-request-summary",
                message="Handoff request summary is required.",
                field="request_summary",
            )
        )
    if not handoff.normalized_objective.strip():
        reasons.append(
            RuntimeReason(
                code="missing-normalized-objective",
                message="Handoff normalized objective is required.",
                field="normalized_objective",
            )
        )
    if not handoff.workflow_id.strip():
        reasons.append(
            RuntimeReason(
                code="missing-workflow-id",
                message="Handoff workflow id is required.",
                field="workflow_id",
            )
        )
    if not handoff.lanes:
        reasons.append(
            RuntimeReason(
                code="missing-lanes",
                message="Handoff must declare at least one lane.",
                field="lanes",
            )
        )
    for lane in handoff.lanes:
        if not lane.goal.strip():
            reasons.append(
                RuntimeReason(
                    code="missing-lane-goal",
                    message=f"Lane {lane.lane_id} is missing a goal.",
                    field="goal",
                )
            )
    return tuple(reasons)


def _parse_artifact_list(value: object) -> tuple[HandoffArtifact, ...] | None:
    if not isinstance(value, list):
        return None
    parsed: list[HandoffArtifact] = []
    for item in value:
        artifact = HandoffArtifact.from_record(item)
        if artifact is None:
            return None
        parsed.append(artifact)
    return tuple(parsed)


def _parse_lane_list(value: object) -> tuple[HandoffLane, ...] | None:
    if not isinstance(value, list):
        return None
    parsed: list[HandoffLane] = []
    for item in value:
        lane = HandoffLane.from_record(item)
        if lane is None:
            return None
        parsed.append(lane)
    return tuple(parsed)


def _derive_request_summary(non_empty_lines: list[str]) -> str:
    if not non_empty_lines:
        return "Untitled request"
    first_line = re.sub(r"^(?:user|assistant|system)\s*[:：]\s*", "", non_empty_lines[0].strip("- "), flags=re.IGNORECASE)
    match = re.match(r"^request summary\s*[:：]\s*(.+)$", first_line, re.IGNORECASE)
    if match:
        first_line = match.group(1).strip()
    first_line = re.sub(r"[`*_#]", "", first_line)
    return first_line[:140] if first_line else "Untitled request"


def _derive_normalized_objective(lines: list[str], request_summary: str) -> str:
    meaningful_lines = [
        re.sub(r"^(?:user|assistant|system)\s*[:：]\s*", "", line.strip(), flags=re.IGNORECASE)
        for line in lines
        if line.strip()
    ]
    if not meaningful_lines:
        return request_summary
    objective_lines = meaningful_lines[:12]
    rendered = "\n".join(objective_lines).strip()
    return rendered or request_summary


def _infer_intake_profile(text: str, source_kind: IntakeSourceKind) -> IntakeProfileKind:
    if source_kind is IntakeSourceKind.HANDOFF:
        return IntakeProfileKind.STRUCTURED_HANDOFF
    lowered = text.lower()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if any(re.match(r"^(user|assistant|system)\s*[:：]", line, re.IGNORECASE) for line in lines):
        return IntakeProfileKind.CHAT_TRANSCRIPT
    if len(lines) <= 3 and not any(":" in line for line in lines):
        return IntakeProfileKind.SINGLE_PROMPT
    if any(token in lowered for token in ("goal:", "constraints:", "issue:", "task:", "lane:", "current phase:")):
        return IntakeProfileKind.TASK_REQUEST
    return IntakeProfileKind.SINGLE_PROMPT


def _extract_single_label(text: str, labels: tuple[str, ...]) -> str | None:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        for label in labels:
            match = re.match(rf"^(?:[-*]\s*)?{re.escape(label)}\s*[:：]\s*(.+)$", line, re.IGNORECASE)
            if match:
                return match.group(1).strip().strip("`")
    return None


def _extract_multi_label_items(text: str, labels: tuple[str, ...]) -> list[str]:
    items: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        for label in labels:
            match = re.match(rf"^(?:[-*]\s*)?{re.escape(label)}\s*[:：]\s*(.+)$", line, re.IGNORECASE)
            if not match:
                continue
            values = re.split(r"\s*/\s*|\s*;\s*|\s*，\s*|\s*,\s*", match.group(1).strip())
            items.extend(item.strip().strip("`") for item in values if item.strip())
    return _unique(items)


def _extract_bool(text: str, labels: tuple[str, ...], *, default: bool) -> bool:
    value = _extract_single_label(text, labels)
    if value is None:
        return default
    normalized = value.strip().lower()
    return normalized in {"yes", "true", "y", "auto", "1", "是"}


def _parse_lanes(text: str) -> tuple[HandoffLane, ...]:
    lines = text.splitlines()
    lane_blocks: list[tuple[str, list[str], str]] = []
    current_name: str | None = None
    current_lines: list[str] = []
    current_role = "active"
    lane_pattern = re.compile(r"^(?:[-*]\s*)?(?:(主线|副线)\s+lane|(?:main|primary|secondary|parked)?\s*lane)\s*[:：]\s*(.+)$", re.IGNORECASE)
    for raw_line in lines:
        stripped = raw_line.strip()
        match = lane_pattern.match(stripped)
        if match:
            if current_name is not None:
                lane_blocks.append((current_name, current_lines, current_role))
            current_role = (match.group(1) or "active").lower()
            current_name = match.group(2).strip().strip("`")
            current_lines = []
            continue
        if current_name is not None:
            current_lines.append(stripped)
    if current_name is not None:
        lane_blocks.append((current_name, current_lines, current_role))

    parsed_lanes: list[HandoffLane] = []
    for index, (lane_name, block_lines, role) in enumerate(lane_blocks, start=1):
        block_text = "\n".join(block_lines)
        status_label = _extract_single_label(block_text, ("status",))
        phase = _extract_single_label(block_text, ("current phase", "phase")) or "intake"
        goal = _extract_single_label(block_text, ("goal",)) or lane_name
        unblock = _extract_multi_label_items(block_text, ("unblock condition", "unblock conditions"))
        deferred_scope = _extract_multi_label_items(block_text, ("deferred scope", "not doing now", "当前不参与默认推进"))
        present_names = _extract_multi_label_items(block_text, ("current assets", "current asset", "assets"))
        missing_names = _extract_multi_label_items(block_text, ("missing", "missing artifacts", "缺失"))
        if status_label is None:
            if "parked" in role or lane_name.lower().startswith("parked"):
                status = LaneStatus.PARKED
            else:
                status = LaneStatus.ACTIVE if index == 1 else LaneStatus.PARKED
        else:
            normalized_status = status_label.strip().lower().replace("-", "_")
            status = {
                "active": LaneStatus.ACTIVE,
                "parked": LaneStatus.PARKED,
                "blocked": LaneStatus.BLOCKED,
                "awaiting_review": LaneStatus.AWAITING_REVIEW,
                "awaiting review": LaneStatus.AWAITING_REVIEW,
                "awaiting_executor": LaneStatus.AWAITING_EXECUTOR,
                "awaiting executor": LaneStatus.AWAITING_EXECUTOR,
                "ready_for_dispatch": LaneStatus.READY_FOR_DISPATCH,
                "ready for dispatch": LaneStatus.READY_FOR_DISPATCH,
                "complete": LaneStatus.COMPLETE,
            }.get(normalized_status, LaneStatus.ACTIVE)
        current_artifacts = tuple(
            HandoffArtifact(name=item, category=_classify_artifact_category(item), presence=ArtifactPresence.PRESENT)
            for item in present_names
        )
        missing_artifacts = tuple(
            HandoffArtifact(name=item, category=_classify_artifact_category(item), presence=ArtifactPresence.MISSING)
            for item in missing_names
        )
        parsed_lanes.append(
            HandoffLane(
                lane_id=_slugify(lane_name),
                title=lane_name,
                status=status,
                priority=index,
                goal=goal,
                parent_phase=phase,
                unblock_conditions=tuple(unblock),
                deferred_scope=tuple(deferred_scope),
                current_artifacts=current_artifacts,
                missing_artifacts=missing_artifacts,
            )
        )
    return tuple(parsed_lanes)


def _collect_required_artifacts(lanes: tuple[HandoffLane, ...]) -> tuple[HandoffArtifact, ...]:
    ordered: list[HandoffArtifact] = []
    seen: set[tuple[str, str, str]] = set()
    for lane in lanes:
        for artifact in (*lane.current_artifacts, *lane.missing_artifacts):
            key = (artifact.name.lower(), artifact.category.value, artifact.presence.value)
            if key in seen:
                continue
            seen.add(key)
            ordered.append(artifact)
    return tuple(ordered)


def _select_workflow_id(text: str, workflow_hint: str | None) -> str:
    if workflow_hint is not None:
        return _slugify(workflow_hint)
    lowered = text.lower()
    if any(token in lowered for token in ("repo", "code", "spec", "validation", "executor", "lane", "artifact")):
        return "repo-coding-task"
    return "chat-to-execution"


def _classify_artifact_category(name: str) -> ArtifactCategory:
    lowered = name.lower()
    if any(token in lowered for token in ("run", "result", "baseline", "eval", "sft", "train", "expand")):
        return ArtifactCategory.EXECUTION
    if any(token in lowered for token in ("review", "closeout", "summary", "follow-up", "followup", "validation")):
        return ArtifactCategory.REVIEW_CLOSEOUT
    return ArtifactCategory.PLANNING


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        normalized = item.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(normalized)
    return ordered


def _slugify(text: str) -> str:
    lowered = text.strip().lower()
    lowered = re.sub(r"[`'\"]", "", lowered)
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    lowered = lowered.strip("-")
    return lowered or "lane"
