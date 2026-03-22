from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path

from ai_engineering_runtime.adapters import FileSystemAdapter
from ai_engineering_runtime.artifact_refs import (
    ArtifactRef,
    ArtifactRefKind,
    artifact_ref_from_artifact_target,
    build_runtime_artifact_ref,
)
from ai_engineering_runtime.run_logs import RunRecordStatus, load_run_record
from ai_engineering_runtime.run_summary import RunSummary, resolve_summary_query
from ai_engineering_runtime.runtime_queries import missing_run_log_reasons, resolve_run_log_query
from ai_engineering_runtime.state import (
    RuntimeReason,
    ValidationEvidenceKind,
    ValidationResult,
    ValidationStatus,
)

_VALIDATION_SOURCE_NODE = "validation-collect"
_ROLLUP_VERSION = 1


class ValidationFindingSeverity(str, Enum):
    BLOCKING = "blocking"
    ADVISORY = "advisory"
    INFO = "info"


class ValidationRollupStatus(str, Enum):
    CLEAN = "clean"
    ADVISORY = "advisory"
    BLOCKING = "blocking"


@dataclass(frozen=True)
class ValidationFinding:
    severity: ValidationFindingSeverity
    code: str
    message: str
    field: str | None = None
    source_kind: str | None = None

    def to_record(self) -> dict[str, str]:
        payload = {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
        }
        if self.field is not None:
            payload["field"] = self.field
        if self.source_kind is not None:
            payload["source_kind"] = self.source_kind
        return payload

    @classmethod
    def from_record(cls, payload: object) -> "ValidationFinding" | None:
        if not isinstance(payload, dict):
            return None
        severity = payload.get("severity")
        code = payload.get("code")
        message = payload.get("message")
        field = payload.get("field")
        source_kind = payload.get("source_kind")
        if not isinstance(severity, str) or not isinstance(code, str) or not isinstance(message, str):
            return None
        if field is not None and not isinstance(field, str):
            return None
        if source_kind is not None and not isinstance(source_kind, str):
            return None
        try:
            return cls(
                severity=ValidationFindingSeverity(severity),
                code=code,
                message=message,
                field=field,
                source_kind=source_kind,
            )
        except ValueError:
            return None


@dataclass(frozen=True)
class ValidationRollup:
    version: int
    run_id: str
    validation_status: ValidationStatus
    status: ValidationRollupStatus
    source_log_ref: ArtifactRef
    summary_ref: ArtifactRef
    artifact_target_ref: ArtifactRef | None = None
    findings: tuple[ValidationFinding, ...] = ()

    def to_record(self) -> dict[str, object]:
        return {
            "version": self.version,
            "run_id": self.run_id,
            "validation_status": self.validation_status.value,
            "status": self.status.value,
            "source_log_ref": self.source_log_ref.to_record(),
            "summary_ref": self.summary_ref.to_record(),
            "artifact_target_ref": self.artifact_target_ref.to_record() if self.artifact_target_ref is not None else None,
            "findings": [finding.to_record() for finding in self.findings],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_record(), indent=2, sort_keys=True)

    @classmethod
    def from_record(cls, payload: object) -> "ValidationRollup" | None:
        if not isinstance(payload, dict):
            return None
        version = payload.get("version")
        run_id = payload.get("run_id")
        validation_status = payload.get("validation_status")
        status = payload.get("status")
        findings_payload = payload.get("findings")
        source_log_ref = ArtifactRef.from_record(payload.get("source_log_ref"))
        summary_ref = ArtifactRef.from_record(payload.get("summary_ref"))
        artifact_target_ref = ArtifactRef.from_record(payload.get("artifact_target_ref"))
        if not isinstance(version, int) or not isinstance(run_id, str):
            return None
        if not isinstance(validation_status, str) or not isinstance(status, str):
            return None
        if source_log_ref is None or summary_ref is None:
            return None
        if not isinstance(findings_payload, list):
            return None
        findings: list[ValidationFinding] = []
        for item in findings_payload:
            finding = ValidationFinding.from_record(item)
            if finding is None:
                return None
            findings.append(finding)
        try:
            return cls(
                version=version,
                run_id=run_id,
                validation_status=ValidationStatus(validation_status),
                status=ValidationRollupStatus(status),
                source_log_ref=source_log_ref,
                summary_ref=summary_ref,
                artifact_target_ref=artifact_target_ref,
                findings=tuple(findings),
            )
        except ValueError:
            return None


def resolve_validation_rollup_query(
    adapter: FileSystemAdapter,
    *,
    log_path: Path | None = None,
    run_id: str | None = None,
    latest: bool = False,
    node_name: str | None = None,
) -> tuple[ValidationRollup | None, tuple[RuntimeReason, ...]]:
    selected_log = resolve_run_log_query(
        adapter,
        log_path=log_path,
        run_id=run_id,
        latest=latest,
        node_name=node_name or (_VALIDATION_SOURCE_NODE if latest else None),
    )
    if selected_log is None:
        return None, missing_run_log_reasons(
            log_path=log_path,
            run_id=run_id,
            latest=latest,
            node_name=node_name or (_VALIDATION_SOURCE_NODE if latest else None),
        )

    rollup_path = adapter.build_validation_rollup_path(selected_log.stem)
    loaded = _load_rollup(rollup_path)
    if loaded is not None:
        return loaded, ()
    return materialize_validation_rollup_for_log(adapter, selected_log)


def materialize_validation_rollup_for_log(
    adapter: FileSystemAdapter,
    log_path: Path,
) -> tuple[ValidationRollup | None, tuple[RuntimeReason, ...]]:
    record = load_run_record(log_path)
    if record.status is not RunRecordStatus.LOADABLE:
        return None, record.reasons
    if record.source_log_path is None:
        return None, (
            RuntimeReason(
                code="missing-run-log",
                message="Validation rollup requires a source run log path.",
                field="log_path",
            ),
        )
    if record.validation is None:
        return None, (
            RuntimeReason(
                code="missing-validation-result",
                message="The selected run log does not contain a validation result payload.",
                field="validation",
            ),
        )

    summary, reasons = resolve_summary_query(adapter, log_path=record.source_log_path)
    if summary is None:
        return None, reasons

    rollup = build_validation_rollup(adapter, summary=summary)
    path = adapter.build_validation_rollup_path(rollup.run_id)
    adapter.write_json(path, rollup.to_record())
    return rollup, ()


def build_validation_rollup(
    adapter: FileSystemAdapter,
    *,
    summary: RunSummary,
) -> ValidationRollup:
    record = load_run_record(summary.source_log_path)
    validation = record.validation
    if validation is None:
        raise ValueError("Validation rollup requires a run log with a validation result payload.")

    findings = _build_findings(validation)
    status = _derive_rollup_status(findings)
    artifact_target_ref = (
        artifact_ref_from_artifact_target(adapter.repo_root, summary.artifact_target)
        if summary.artifact_target is not None
        else None
    )
    return ValidationRollup(
        version=_ROLLUP_VERSION,
        run_id=summary.run_id,
        validation_status=validation.status,
        status=status,
        source_log_ref=build_runtime_artifact_ref(
            adapter.repo_root,
            kind=ArtifactRefKind.RUN_LOG,
            run_id=summary.run_id,
        ),
        summary_ref=build_runtime_artifact_ref(
            adapter.repo_root,
            kind=ArtifactRefKind.RUN_SUMMARY,
            run_id=summary.run_id,
        ),
        artifact_target_ref=artifact_target_ref,
        findings=findings,
    )


def _build_findings(validation: ValidationResult) -> tuple[ValidationFinding, ...]:
    findings: list[ValidationFinding] = []
    for reason in validation.reasons:
        findings.append(
            ValidationFinding(
                severity=_severity_for_reason(reason),
                code=reason.code,
                message=reason.message,
                field=reason.field,
                source_kind="reason",
            )
        )
    for evidence in validation.evidence:
        if evidence.kind is ValidationEvidenceKind.MANUAL_NOTE:
            findings.append(
                ValidationFinding(
                    severity=ValidationFindingSeverity.INFO,
                    code="manual-note",
                    message=evidence.summary,
                    source_kind=evidence.kind.value,
                )
            )
    return tuple(findings)


def _severity_for_reason(reason: RuntimeReason) -> ValidationFindingSeverity:
    if reason.code.endswith("-failed") or reason.code.startswith("missing-") or reason.code.startswith("incomplete-"):
        return ValidationFindingSeverity.BLOCKING
    return ValidationFindingSeverity.ADVISORY


def _derive_rollup_status(findings: tuple[ValidationFinding, ...]) -> ValidationRollupStatus:
    severities = {finding.severity for finding in findings}
    if ValidationFindingSeverity.BLOCKING in severities:
        return ValidationRollupStatus.BLOCKING
    if ValidationFindingSeverity.ADVISORY in severities:
        return ValidationRollupStatus.ADVISORY
    return ValidationRollupStatus.CLEAN


def _load_rollup(path: Path) -> ValidationRollup | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return ValidationRollup.from_record(payload)
