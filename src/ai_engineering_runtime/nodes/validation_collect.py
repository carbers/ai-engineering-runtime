from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_engineering_runtime.adapters import FileSystemAdapter
from ai_engineering_runtime.artifacts import TaskSpecArtifact
from ai_engineering_runtime.engine import RunResult
from ai_engineering_runtime.state import (
    RuntimeReason,
    ValidationEvidence,
    ValidationEvidenceKind,
    ValidationEvidenceStatus,
    ValidationResult,
    ValidationStatus,
    validation_collect_transition,
)

_FAILED_CODES = {
    ValidationEvidenceKind.COMMAND: "command-failed",
    ValidationEvidenceKind.BLACK_BOX: "black-box-failed",
    ValidationEvidenceKind.WHITE_BOX: "white-box-failed",
}

_INCOMPLETE_CODES = {
    ValidationEvidenceKind.COMMAND: "incomplete-command-evidence",
    ValidationEvidenceKind.BLACK_BOX: "incomplete-black-box-evidence",
    ValidationEvidenceKind.WHITE_BOX: "incomplete-white-box-evidence",
}

_MISSING_CODES = {
    ValidationEvidenceKind.COMMAND: "missing-command-evidence",
    ValidationEvidenceKind.BLACK_BOX: "missing-black-box-evidence",
    ValidationEvidenceKind.WHITE_BOX: "missing-white-box-evidence",
}

_SUMMARIES = {
    ValidationEvidenceKind.COMMAND: "Command evidence reported.",
    ValidationEvidenceKind.BLACK_BOX: "Black-box validation evidence reported.",
    ValidationEvidenceKind.WHITE_BOX: "White-box validation evidence reported.",
}


@dataclass(frozen=True)
class ValidationCollectRequest:
    spec_path: Path | None = None
    command_status: ValidationEvidenceStatus | None = None
    command_summary: str | None = None
    black_box_status: ValidationEvidenceStatus | None = None
    black_box_summary: str | None = None
    white_box_status: ValidationEvidenceStatus | None = None
    white_box_summary: str | None = None
    notes: tuple[str, ...] = ()


class ValidationCollectNode:
    name = "validation-collect"

    def __init__(self, request: ValidationCollectRequest):
        self.request = request

    def execute(self, adapter: FileSystemAdapter) -> RunResult:
        issues: list[RuntimeReason] = []
        task_spec: TaskSpecArtifact | None = None
        resolved_spec_path: Path | None = None

        if self.request.spec_path is not None:
            resolved_spec_path = adapter.resolve(self.request.spec_path)
            if not resolved_spec_path.exists():
                issues.append(
                    RuntimeReason(
                        code="missing-task-spec",
                        message=f"Task spec not found: {adapter.display_path(resolved_spec_path)}",
                        field="spec_path",
                    )
                )
            else:
                task_spec = TaskSpecArtifact.from_markdown(
                    resolved_spec_path,
                    adapter.read_text(resolved_spec_path),
                )

        if issues:
            result = RunResult(
                node_name=self.name,
                success=False,
                from_state=validation_collect_transition(
                    ValidationResult(status=ValidationStatus.INCOMPLETE)
                ).from_state,
                to_state=validation_collect_transition(
                    ValidationResult(status=ValidationStatus.INCOMPLETE)
                ).to_state,
                issues=tuple(issues),
                spec_path=resolved_spec_path,
            )
            log_path = adapter.build_run_log_path(self.name)
            result = result.with_log_path(log_path)
            adapter.write_json(log_path, result.to_log_record(adapter))
            return result

        validation = collect_validation(self.request, adapter, task_spec)
        transition = validation_collect_transition(validation)
        result = RunResult(
            node_name=self.name,
            success=validation.status is ValidationStatus.PASSED,
            from_state=transition.from_state,
            to_state=transition.to_state,
            issues=transition.issues,
            validation=validation,
            spec_path=resolved_spec_path,
        )
        log_path = adapter.build_run_log_path(self.name)
        result = result.with_log_path(log_path)
        adapter.write_json(log_path, result.to_log_record(adapter))
        return result


def collect_validation(
    request: ValidationCollectRequest,
    adapter: FileSystemAdapter,
    task_spec: TaskSpecArtifact | None = None,
) -> ValidationResult:
    evidence: list[ValidationEvidence] = []
    reasons: list[RuntimeReason] = []

    command = _build_evidence(
        ValidationEvidenceKind.COMMAND,
        request.command_status,
        request.command_summary,
        task_spec,
        adapter,
    )
    black_box = _build_evidence(
        ValidationEvidenceKind.BLACK_BOX,
        request.black_box_status,
        request.black_box_summary,
        task_spec,
        adapter,
    )
    white_box = _build_evidence(
        ValidationEvidenceKind.WHITE_BOX,
        request.white_box_status,
        request.white_box_summary,
        task_spec,
        adapter,
    )

    for entry in (command, black_box, white_box):
        if entry is not None:
            evidence.append(entry)
            if entry.status is ValidationEvidenceStatus.FAILED:
                reasons.append(
                    RuntimeReason(
                        code=_FAILED_CODES[entry.kind],
                        message=f"{entry.kind.value.replace('_', '-')} validation failed.",
                    )
                )
            elif entry.status is ValidationEvidenceStatus.INCOMPLETE:
                reasons.append(
                    RuntimeReason(
                        code=_INCOMPLETE_CODES[entry.kind],
                        message=f"{entry.kind.value.replace('_', '-')} validation is incomplete.",
                    )
                )

    for note in request.notes:
        normalized = note.strip()
        if normalized:
            evidence.append(
                ValidationEvidence(
                    kind=ValidationEvidenceKind.MANUAL_NOTE,
                    status=ValidationEvidenceStatus.NOTED,
                    summary=normalized,
                    source=adapter.display_path(task_spec.path) if task_spec is not None else None,
                )
            )

    required_kinds = {
        ValidationEvidenceKind.COMMAND,
        ValidationEvidenceKind.BLACK_BOX,
    }
    if _requires_white_box(task_spec):
        required_kinds.add(ValidationEvidenceKind.WHITE_BOX)

    present_kinds = {entry.kind for entry in evidence}
    for kind in sorted(required_kinds, key=lambda item: item.value):
        if kind not in present_kinds:
            reasons.append(
                RuntimeReason(
                    code=_MISSING_CODES[kind],
                    message=f"Missing required {kind.value.replace('_', '-')} evidence.",
                )
            )

    if any(reason.code.endswith("-failed") for reason in reasons):
        status = ValidationStatus.FAILED
    elif any(reason.code.startswith("missing-") or reason.code.startswith("incomplete-") for reason in reasons):
        status = ValidationStatus.INCOMPLETE
    else:
        status = ValidationStatus.PASSED

    return ValidationResult(
        status=status,
        evidence=tuple(evidence),
        reasons=tuple(reasons),
    )


def _build_evidence(
    kind: ValidationEvidenceKind,
    status: ValidationEvidenceStatus | None,
    summary: str | None,
    task_spec: TaskSpecArtifact | None,
    adapter: FileSystemAdapter,
) -> ValidationEvidence | None:
    if status is None:
        return None
    return ValidationEvidence(
        kind=kind,
        status=status,
        summary=(summary or _SUMMARIES[kind]).strip(),
        source=adapter.display_path(task_spec.path) if task_spec is not None else None,
    )


def _requires_white_box(task_spec: TaskSpecArtifact | None) -> bool:
    if task_spec is None:
        return False
    value = task_spec.validation.get("White-box Needed", "").strip().lower()
    return value.startswith("yes")
