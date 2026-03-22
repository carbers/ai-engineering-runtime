from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from ai_engineering_runtime.adapters import FileSystemAdapter
from ai_engineering_runtime.artifacts import (
    ALLOWED_TASK_SPEC_STATUSES,
    EXECUTABLE_TASK_SPEC_STATUSES,
    REQUIRED_TASK_SPEC_SECTIONS,
    TASK_SPEC_LIST_FIELDS,
    TASK_SPEC_METADATA_FIELDS,
    TASK_SPEC_VALIDATION_FIELDS,
    TaskSpecArtifact,
    discover_artifacts,
    is_markdown_list_block,
)
from ai_engineering_runtime.engine import RunResult
from ai_engineering_runtime.state import (
    ReadinessResult,
    ReadinessStatus,
    RuntimeReason,
    task_spec_to_execution_transition,
)

_PLACEHOLDER_PATTERNS = (
    re.compile(r"\btbd\b", re.IGNORECASE),
    re.compile(r"\btodo\b", re.IGNORECASE),
    re.compile(r"\bto be decided\b", re.IGNORECASE),
    re.compile(r"\bto be determined\b", re.IGNORECASE),
)


@dataclass(frozen=True)
class TaskSpecReadinessCheckRequest:
    spec_path: Path


@dataclass(frozen=True)
class CheckedTaskSpec:
    spec_path: Path
    task_spec: TaskSpecArtifact | None
    readiness: ReadinessResult


class TaskSpecReadinessCheckNode:
    name = "task-spec-readiness-check"

    def __init__(self, request: TaskSpecReadinessCheckRequest):
        self.request = request

    def execute(self, adapter: FileSystemAdapter) -> RunResult:
        discovered = discover_artifacts(adapter.repo_root)
        checked_spec = check_task_spec_readiness(adapter, self.request.spec_path)
        transition = task_spec_to_execution_transition(checked_spec.readiness)
        result = RunResult(
            node_name=self.name,
            success=checked_spec.readiness.is_ready,
            from_state=transition.from_state,
            to_state=transition.to_state,
            issues=transition.issues,
            readiness=checked_spec.readiness,
            spec_path=checked_spec.spec_path,
            metadata={"artifact_count": len(discovered)},
        )
        log_path = adapter.build_run_log_path(self.name)
        result = result.with_log_path(log_path)
        adapter.write_json(log_path, result.to_log_record(adapter))
        return result


def check_task_spec_readiness(adapter: FileSystemAdapter, spec_path: Path) -> CheckedTaskSpec:
    resolved_spec_path = adapter.resolve(spec_path)
    if not resolved_spec_path.exists():
        return CheckedTaskSpec(
            spec_path=resolved_spec_path,
            task_spec=None,
            readiness=ReadinessResult(
                status=ReadinessStatus.BLOCKED,
                reasons=(
                    RuntimeReason(
                        code="missing-task-spec",
                        message=f"Task spec not found: {adapter.display_path(resolved_spec_path)}",
                        field="spec_path",
                    ),
                ),
            ),
        )

    task_spec = TaskSpecArtifact.from_markdown(
        resolved_spec_path,
        adapter.read_text(resolved_spec_path),
    )
    return CheckedTaskSpec(
        spec_path=resolved_spec_path,
        task_spec=task_spec,
        readiness=assess_task_spec_readiness(task_spec),
    )


def assess_task_spec_readiness(task_spec: TaskSpecArtifact) -> ReadinessResult:
    blocked_reasons: list[RuntimeReason] = []

    for section_name in REQUIRED_TASK_SPEC_SECTIONS:
        if not task_spec.sections.get(section_name, "").strip():
            blocked_reasons.append(
                RuntimeReason(
                    code="missing-task-spec-section",
                    message=f"Missing required task spec section: {section_name}",
                    field=section_name,
                )
            )

    for field_name in TASK_SPEC_METADATA_FIELDS:
        if not task_spec.metadata.get(field_name, "").strip():
            blocked_reasons.append(
                RuntimeReason(
                    code="missing-task-spec-metadata-field",
                    message=f"Missing required task spec metadata field: {field_name}",
                    field=field_name,
                )
            )

    for field_name in TASK_SPEC_VALIDATION_FIELDS:
        if not task_spec.validation.get(field_name, "").strip():
            blocked_reasons.append(
                RuntimeReason(
                    code="missing-task-spec-validation-field",
                    message=f"Missing required task spec validation field: {field_name}",
                    field=field_name,
                )
            )

    if blocked_reasons:
        return ReadinessResult(
            status=ReadinessStatus.BLOCKED,
            reasons=tuple(blocked_reasons),
        )

    for field_name in TASK_SPEC_LIST_FIELDS:
        text = _get_list_field(task_spec, field_name)
        if not is_markdown_list_block(text):
            blocked_reasons.append(
                RuntimeReason(
                    code="invalid-task-spec-list-field",
                    message=f"Task spec field must use Markdown list items: {field_name}",
                    field=field_name,
                )
            )

    if task_spec.status not in ALLOWED_TASK_SPEC_STATUSES:
        blocked_reasons.append(
            RuntimeReason(
                code="invalid-task-spec-status",
                message=f"Task spec status must be one of: {', '.join(sorted(ALLOWED_TASK_SPEC_STATUSES))}",
                field="Status",
            )
        )
    elif task_spec.status not in EXECUTABLE_TASK_SPEC_STATUSES:
        blocked_reasons.append(
            RuntimeReason(
                code="non-executable-task-spec-status",
                message=f"Task spec status is not executable: {task_spec.status}",
                field="Status",
            )
        )

    for field_name in ("White-box Needed", "Write-back Needed"):
        text = _get_choice_field(task_spec, field_name)
        if not _starts_with_yes_or_no(text):
            blocked_reasons.append(
                RuntimeReason(
                    code="invalid-task-spec-choice-field",
                    message=f"Task spec field must start with Yes or No: {field_name}",
                    field=field_name,
                )
            )

    if blocked_reasons:
        return ReadinessResult(
            status=ReadinessStatus.BLOCKED,
            reasons=tuple(blocked_reasons),
        )

    clarification_reasons: list[RuntimeReason] = []
    for field_name in (
        "Goal",
        "In Scope",
        "Out of Scope",
        "Affected Area",
        "Done When",
        "Black-box Checks",
        "White-box Trigger",
        "Internal Logic To Protect",
        "Write-back Needed",
    ):
        if _contains_placeholder_text(_get_clarification_field(task_spec, field_name)):
            clarification_reasons.append(
                RuntimeReason(
                    code="placeholder-task-spec-field",
                    message=f"Task spec field needs clarification before implementation: {field_name}",
                    field=field_name,
                )
            )

    if clarification_reasons:
        return ReadinessResult(
            status=ReadinessStatus.NEEDS_CLARIFICATION,
            reasons=tuple(clarification_reasons),
        )

    return ReadinessResult(status=ReadinessStatus.READY)


def _get_list_field(task_spec: TaskSpecArtifact, field_name: str) -> str:
    if field_name == "Black-box Checks":
        return task_spec.validation.get(field_name, "")
    return task_spec.sections.get(field_name, "")


def _get_choice_field(task_spec: TaskSpecArtifact, field_name: str) -> str:
    if field_name == "White-box Needed":
        return task_spec.validation.get(field_name, "")
    return task_spec.sections.get(field_name, "")


def _get_clarification_field(task_spec: TaskSpecArtifact, field_name: str) -> str:
    if field_name in task_spec.validation:
        return task_spec.validation.get(field_name, "")
    return task_spec.sections.get(field_name, "")


def _contains_placeholder_text(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return False
    return any(pattern.search(normalized) for pattern in _PLACEHOLDER_PATTERNS)


def _starts_with_yes_or_no(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized.startswith("yes") or normalized.startswith("no")
