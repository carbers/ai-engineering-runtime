from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json
from pathlib import Path
import re
from typing import Any, Callable

from ai_engineering_runtime.state import RuntimeReason
from ai_engineering_runtime.state import (
    DispatchMode,
    DispatchPayload,
    DispatchResult,
    DispatchStatus,
    ExecutionArtifactRef,
    ExecutionResult,
    ExecutionStatus,
    FollowupAction,
    FollowupResult,
    ExecutorCapabilityProfile,
    ExecutorDescriptor,
    ExecutorRequirements,
    ExecutorTarget,
    RepairSpecCandidate,
    ReviewFinding,
    ReviewFindingSeverity,
    ValidationEvidence,
    ValidationEvidenceKind,
    ValidationEvidenceStatus,
    ValidationResult,
    ValidationStatus,
    WritebackCandidateKind,
    WritebackDestination,
    WritebackResult,
)

_RUN_LOG_NAME_RE = re.compile(r"^(?P<timestamp>\d{8}T\d{12})-(?P<node>.+)\.json$")
_REPLAY_SIGNAL_FIELDS = (
    "readiness",
    "validation",
    "writeback",
    "followup",
    "dispatch",
)
_DEFAULT_DISCOVERY_EXCLUSIONS = {
    "result-log-replay",
    "run-history-select",
    "run-summary",
    "node-gate",
    "validation-rollup",
    "writeback-package",
    "followup-package",
}


class ReplayStatus(str, Enum):
    REPLAYABLE = "replayable"
    REJECTED = "rejected"


class ArtifactTargetKind(str, Enum):
    SPEC = "spec"
    PLAN = "plan"
    OUTPUT = "output"


class ReplaySignalKind(str, Enum):
    READINESS = "readiness"
    VALIDATION = "validation"
    WRITEBACK = "writeback"
    FOLLOWUP = "followup"
    DISPATCH = "dispatch"


@dataclass(frozen=True)
class ArtifactTarget:
    kind: ArtifactTargetKind
    path: str

    def to_record(self) -> dict[str, str]:
        return {
            "kind": self.kind.value,
            "path": self.path,
        }


@dataclass(frozen=True)
class ReplayResult:
    status: ReplayStatus
    source_log_path: Path | None = None
    ordered_at: datetime | None = None
    node_name: str | None = None
    artifact_target: ArtifactTarget | None = None
    signal_kind: ReplaySignalKind | None = None
    signal_value: str | None = None
    reasons: tuple[RuntimeReason, ...] = ()

    @property
    def is_replayable(self) -> bool:
        return self.status is ReplayStatus.REPLAYABLE

    def to_record(self, display_path: Callable[[Path], str]) -> dict[str, object]:
        return {
            "status": self.status.value,
            "source_log_path": display_path(self.source_log_path) if self.source_log_path is not None else None,
            "ordered_at": self.ordered_at.isoformat() if self.ordered_at is not None else None,
            "node": self.node_name,
            "artifact_target": self.artifact_target.to_record() if self.artifact_target is not None else None,
            "signal_kind": self.signal_kind.value if self.signal_kind is not None else None,
            "signal_value": self.signal_value,
            "reasons": [reason.to_record() for reason in self.reasons],
        }


class RunRecordStatus(str, Enum):
    LOADABLE = "loadable"
    REJECTED = "rejected"


@dataclass(frozen=True)
class RunRecord:
    status: RunRecordStatus
    source_log_path: Path | None = None
    ordered_at: datetime | None = None
    node_name: str | None = None
    success: bool | None = None
    from_state: str | None = None
    to_state: str | None = None
    artifact_target: ArtifactTarget | None = None
    signal_kind: ReplaySignalKind | None = None
    signal_value: str | None = None
    signal_reasons: tuple[RuntimeReason, ...] = ()
    validation: ValidationResult | None = None
    writeback: WritebackResult | None = None
    followup: FollowupResult | None = None
    dispatch: DispatchResult | None = None
    execution: ExecutionResult | None = None
    issues: tuple[RuntimeReason, ...] = ()
    reasons: tuple[RuntimeReason, ...] = ()

    @property
    def is_loadable(self) -> bool:
        return self.status is RunRecordStatus.LOADABLE


@dataclass(frozen=True)
class _SignalSpec:
    field: str
    kind: ReplaySignalKind
    value_key: str


_SUPPORTED_SIGNAL_SPECS: dict[str, _SignalSpec] = {
    "plan-readiness-check": _SignalSpec("readiness", ReplaySignalKind.READINESS, "status"),
    "task-spec-readiness-check": _SignalSpec("readiness", ReplaySignalKind.READINESS, "status"),
    "validation-collect": _SignalSpec("validation", ReplaySignalKind.VALIDATION, "status"),
    "writeback-classifier": _SignalSpec("writeback", ReplaySignalKind.WRITEBACK, "destination"),
    "followup-suggester": _SignalSpec("followup", ReplaySignalKind.FOLLOWUP, "action"),
    "executor-dispatch": _SignalSpec("dispatch", ReplaySignalKind.DISPATCH, "status"),
}


def discover_run_logs(repo_root: Path, *, node_name: str | None = None) -> list[Path]:
    run_dir = repo_root.resolve() / ".runtime" / "runs"
    if not run_dir.exists():
        return []

    ordered: list[tuple[datetime, Path]] = []
    for path in run_dir.glob("*.json"):
        parsed = _parse_run_log_name(path.name)
        if parsed is None:
            continue
        ordered_at, parsed_node = parsed
        if node_name is not None and parsed_node != node_name:
            continue
        if node_name is None and parsed_node in _DEFAULT_DISCOVERY_EXCLUSIONS:
            continue
        ordered.append((ordered_at, path.resolve()))

    ordered.sort(key=lambda item: (item[0], item[1].name))
    return [path for _, path in ordered]


def select_latest_run_log(repo_root: Path, *, node_name: str | None = None) -> Path | None:
    discovered = discover_run_logs(repo_root, node_name=node_name)
    if not discovered:
        return None
    return discovered[-1]


def load_replay_result(log_path: Path) -> ReplayResult:
    resolved_log_path = log_path.resolve()
    if not resolved_log_path.exists():
        return ReplayResult(
            status=ReplayStatus.REJECTED,
            source_log_path=resolved_log_path,
            reasons=(
                RuntimeReason(
                    code="missing-run-log",
                    message=f"Run log not found: {resolved_log_path.as_posix()}",
                    field="log_path",
                ),
            ),
        )

    parsed_name = _parse_run_log_name(resolved_log_path.name)
    if parsed_name is None:
        return ReplayResult(
            status=ReplayStatus.REJECTED,
            source_log_path=resolved_log_path,
            node_name=_fallback_node_name(resolved_log_path.name),
            reasons=(
                RuntimeReason(
                    code="invalid-run-log-filename-timestamp",
                    message=f"Run log filename does not contain a valid ordering timestamp: {resolved_log_path.name}",
                    field="log_path",
                ),
            ),
        )

    ordered_at, fallback_node = parsed_name
    try:
        payload = json.loads(resolved_log_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ReplayResult(
            status=ReplayStatus.REJECTED,
            source_log_path=resolved_log_path,
            ordered_at=ordered_at,
            node_name=fallback_node,
            reasons=(
                RuntimeReason(
                    code="malformed-run-log-json",
                    message=f"Run log is not valid JSON: {resolved_log_path.name}",
                    field="log_path",
                ),
            ),
        )

    if not isinstance(payload, dict):
        return ReplayResult(
            status=ReplayStatus.REJECTED,
            source_log_path=resolved_log_path,
            ordered_at=ordered_at,
            node_name=fallback_node,
            reasons=(
                RuntimeReason(
                    code="invalid-run-log-envelope",
                    message="Run log root payload must be a JSON object.",
                    field="payload",
                ),
            ),
        )

    issues = _parse_reason_list(payload.get("issues"), field="issues")
    if issues is None:
        return ReplayResult(
            status=ReplayStatus.REJECTED,
            source_log_path=resolved_log_path,
            ordered_at=ordered_at,
            node_name=_coerce_str(payload.get("node")) or fallback_node,
            reasons=(
                RuntimeReason(
                    code="invalid-run-log-envelope",
                    message="Run log issues must be a list of structured reasons.",
                    field="issues",
                ),
            ),
        )

    envelope_errors = _validate_run_log_envelope(payload)
    if envelope_errors:
        return ReplayResult(
            status=ReplayStatus.REJECTED,
            source_log_path=resolved_log_path,
            ordered_at=ordered_at,
            node_name=_coerce_str(payload.get("node")) or fallback_node,
            reasons=_dedupe_reasons((*envelope_errors, *issues)),
        )

    typed_dispatch = _parse_dispatch_result(payload.get("dispatch"))
    if typed_dispatch is _INVALID:
        return ReplayResult(
            status=ReplayStatus.REJECTED,
            source_log_path=resolved_log_path,
            ordered_at=ordered_at,
            node_name=_coerce_str(payload.get("node")) or fallback_node,
            reasons=_dedupe_reasons(
                (
                    RuntimeReason(
                        code="invalid-run-log-envelope",
                        message="Run log dispatch payload must use the current structured schema.",
                        field="dispatch",
                    ),
                    *issues,
                )
            ),
        )

    typed_execution = _parse_execution_result(payload.get("execution"))
    if typed_execution is _INVALID:
        return ReplayResult(
            status=ReplayStatus.REJECTED,
            source_log_path=resolved_log_path,
            ordered_at=ordered_at,
            node_name=_coerce_str(payload.get("node")) or fallback_node,
            reasons=_dedupe_reasons(
                (
                    RuntimeReason(
                        code="invalid-run-log-envelope",
                        message="Run log execution payload must use the current structured schema.",
                        field="execution",
                    ),
                    *issues,
                )
            ),
        )

    node_name = str(payload["node"])
    artifact_target = _resolve_artifact_target(payload)
    present_signal_fields = [field for field in _REPLAY_SIGNAL_FIELDS if payload.get(field) is not None]

    if len(present_signal_fields) > 1:
        return ReplayResult(
            status=ReplayStatus.REJECTED,
            source_log_path=resolved_log_path,
            ordered_at=ordered_at,
            node_name=node_name,
            artifact_target=artifact_target,
            reasons=_dedupe_reasons(
                (
                    RuntimeReason(
                        code="ambiguous-replayable-signal",
                        message="Run log contains multiple replayable signal sections.",
                    ),
                    *issues,
                )
            ),
        )

    signal_spec = _SUPPORTED_SIGNAL_SPECS.get(node_name)
    if signal_spec is None:
        rejection_code = "missing-replayable-signal" if node_name == "plan-to-spec" else "unknown-run-log-node"
        rejection_message = (
            "Run log does not expose a stable replayable signal in this slice."
            if node_name == "plan-to-spec"
            else f"Run log node is not supported for replay: {node_name}"
        )
        return ReplayResult(
            status=ReplayStatus.REJECTED,
            source_log_path=resolved_log_path,
            ordered_at=ordered_at,
            node_name=node_name,
            artifact_target=artifact_target,
            reasons=_dedupe_reasons(
                (
                    RuntimeReason(code=rejection_code, message=rejection_message, field="node"),
                    *issues,
                )
            ),
        )

    if present_signal_fields and present_signal_fields[0] != signal_spec.field:
        return ReplayResult(
            status=ReplayStatus.REJECTED,
            source_log_path=resolved_log_path,
            ordered_at=ordered_at,
            node_name=node_name,
            artifact_target=artifact_target,
            reasons=_dedupe_reasons(
                (
                    RuntimeReason(
                        code="ambiguous-replayable-signal",
                        message="Run log signal payload does not match the recorded node identity.",
                        field=signal_spec.field,
                    ),
                    *issues,
                )
            ),
        )

    signal_payload = payload.get(signal_spec.field)
    if signal_payload is None:
        return ReplayResult(
            status=ReplayStatus.REJECTED,
            source_log_path=resolved_log_path,
            ordered_at=ordered_at,
            node_name=node_name,
            artifact_target=artifact_target,
            reasons=_dedupe_reasons(
                (
                    RuntimeReason(
                        code="missing-replayable-signal",
                        message=f"Run log does not include a replayable {signal_spec.field} payload.",
                        field=signal_spec.field,
                    ),
                    *issues,
                )
            ),
        )

    if not isinstance(signal_payload, dict):
        return ReplayResult(
            status=ReplayStatus.REJECTED,
            source_log_path=resolved_log_path,
            ordered_at=ordered_at,
            node_name=node_name,
            artifact_target=artifact_target,
            reasons=_dedupe_reasons(
                (
                    RuntimeReason(
                        code="invalid-run-log-envelope",
                        message=f"Run log {signal_spec.field} payload must be a JSON object.",
                        field=signal_spec.field,
                    ),
                    *issues,
                )
            ),
        )

    typed_reasons = _parse_reason_list(signal_payload.get("reasons", []), field=f"{signal_spec.field}.reasons")
    if typed_reasons is None:
        return ReplayResult(
            status=ReplayStatus.REJECTED,
            source_log_path=resolved_log_path,
            ordered_at=ordered_at,
            node_name=node_name,
            artifact_target=artifact_target,
            reasons=_dedupe_reasons(
                (
                    RuntimeReason(
                        code="invalid-run-log-envelope",
                        message=f"Run log {signal_spec.field} reasons must be a list of structured reasons.",
                        field=f"{signal_spec.field}.reasons",
                    ),
                    *issues,
                )
            ),
        )

    signal_value = _coerce_str(signal_payload.get(signal_spec.value_key))
    if signal_value is None:
        return ReplayResult(
            status=ReplayStatus.REJECTED,
            source_log_path=resolved_log_path,
            ordered_at=ordered_at,
            node_name=node_name,
            artifact_target=artifact_target,
            reasons=_dedupe_reasons(
                (
                    RuntimeReason(
                        code="missing-replayable-signal",
                        message=f"Run log {signal_spec.field} payload is missing {signal_spec.value_key}.",
                        field=f"{signal_spec.field}.{signal_spec.value_key}",
                    ),
                    *typed_reasons,
                    *issues,
                )
            ),
        )

    return ReplayResult(
        status=ReplayStatus.REPLAYABLE,
        source_log_path=resolved_log_path,
        ordered_at=ordered_at,
        node_name=node_name,
        artifact_target=artifact_target,
        signal_kind=signal_spec.kind,
        signal_value=signal_value,
        reasons=_dedupe_reasons((*typed_reasons, *issues)),
    )


def missing_selection_result(*, node_name: str | None = None) -> ReplayResult:
    message = (
        f"No run logs found under .runtime/runs/ for node: {node_name}"
        if node_name
        else "No run logs found under .runtime/runs/."
    )
    return ReplayResult(
        status=ReplayStatus.REJECTED,
        node_name=node_name,
        reasons=(
            RuntimeReason(
                code="missing-run-log-selection",
                message=message,
                field="log_path",
            ),
        ),
    )


def parse_run_log_name(name: str) -> tuple[datetime, str] | None:
    return _parse_run_log_name(name)


def load_run_record(log_path: Path) -> RunRecord:
    resolved_log_path = log_path.resolve()
    if not resolved_log_path.exists():
        return RunRecord(
            status=RunRecordStatus.REJECTED,
            source_log_path=resolved_log_path,
            reasons=(
                RuntimeReason(
                    code="missing-run-log",
                    message=f"Run log not found: {resolved_log_path.as_posix()}",
                    field="log_path",
                ),
            ),
        )

    parsed_name = _parse_run_log_name(resolved_log_path.name)
    if parsed_name is None:
        return RunRecord(
            status=RunRecordStatus.REJECTED,
            source_log_path=resolved_log_path,
            node_name=_fallback_node_name(resolved_log_path.name),
            reasons=(
                RuntimeReason(
                    code="invalid-run-log-filename-timestamp",
                    message=f"Run log filename does not contain a valid ordering timestamp: {resolved_log_path.name}",
                    field="log_path",
                ),
            ),
        )

    ordered_at, fallback_node = parsed_name
    try:
        payload = json.loads(resolved_log_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return RunRecord(
            status=RunRecordStatus.REJECTED,
            source_log_path=resolved_log_path,
            ordered_at=ordered_at,
            node_name=fallback_node,
            reasons=(
                RuntimeReason(
                    code="malformed-run-log-json",
                    message=f"Run log is not valid JSON: {resolved_log_path.name}",
                    field="log_path",
                ),
            ),
        )

    if not isinstance(payload, dict):
        return RunRecord(
            status=RunRecordStatus.REJECTED,
            source_log_path=resolved_log_path,
            ordered_at=ordered_at,
            node_name=fallback_node,
            reasons=(
                RuntimeReason(
                    code="invalid-run-log-envelope",
                    message="Run log root payload must be a JSON object.",
                    field="payload",
                ),
            ),
        )

    issues = _parse_reason_list(payload.get("issues"), field="issues")
    if issues is None:
        return RunRecord(
            status=RunRecordStatus.REJECTED,
            source_log_path=resolved_log_path,
            ordered_at=ordered_at,
            node_name=_coerce_str(payload.get("node")) or fallback_node,
            reasons=(
                RuntimeReason(
                    code="invalid-run-log-envelope",
                    message="Run log issues must be a list of structured reasons.",
                    field="issues",
                ),
            ),
        )

    envelope_errors = _validate_run_log_envelope(payload)
    if envelope_errors:
        return RunRecord(
            status=RunRecordStatus.REJECTED,
            source_log_path=resolved_log_path,
            ordered_at=ordered_at,
            node_name=_coerce_str(payload.get("node")) or fallback_node,
            issues=issues,
            reasons=_dedupe_reasons((*envelope_errors, *issues)),
        )

    typed_validation = _parse_validation_result(payload.get("validation"))
    if typed_validation is _INVALID:
        return RunRecord(
            status=RunRecordStatus.REJECTED,
            source_log_path=resolved_log_path,
            ordered_at=ordered_at,
            node_name=_coerce_str(payload.get("node")) or fallback_node,
            issues=issues,
            reasons=_dedupe_reasons(
                (
                    RuntimeReason(
                        code="invalid-run-log-envelope",
                        message="Run log validation payload must use the current structured schema.",
                        field="validation",
                    ),
                    *issues,
                )
            ),
        )

    typed_writeback = _parse_writeback_result(payload.get("writeback"))
    if typed_writeback is _INVALID:
        return RunRecord(
            status=RunRecordStatus.REJECTED,
            source_log_path=resolved_log_path,
            ordered_at=ordered_at,
            node_name=_coerce_str(payload.get("node")) or fallback_node,
            issues=issues,
            reasons=_dedupe_reasons(
                (
                    RuntimeReason(
                        code="invalid-run-log-envelope",
                        message="Run log writeback payload must use the current structured schema.",
                        field="writeback",
                    ),
                    *issues,
                )
            ),
        )

    typed_followup = _parse_followup_result(payload.get("followup"))
    if typed_followup is _INVALID:
        return RunRecord(
            status=RunRecordStatus.REJECTED,
            source_log_path=resolved_log_path,
            ordered_at=ordered_at,
            node_name=_coerce_str(payload.get("node")) or fallback_node,
            issues=issues,
            reasons=_dedupe_reasons(
                (
                    RuntimeReason(
                        code="invalid-run-log-envelope",
                        message="Run log followup payload must use the current structured schema.",
                        field="followup",
                    ),
                    *issues,
                )
            ),
        )

    typed_dispatch = _parse_dispatch_result(payload.get("dispatch"))
    if typed_dispatch is _INVALID:
        return RunRecord(
            status=RunRecordStatus.REJECTED,
            source_log_path=resolved_log_path,
            ordered_at=ordered_at,
            node_name=_coerce_str(payload.get("node")) or fallback_node,
            issues=issues,
            reasons=_dedupe_reasons(
                (
                    RuntimeReason(
                        code="invalid-run-log-envelope",
                        message="Run log dispatch payload must use the current structured schema.",
                        field="dispatch",
                    ),
                    *issues,
                )
            ),
        )

    typed_execution = _parse_execution_result(payload.get("execution"))
    if typed_execution is _INVALID:
        return RunRecord(
            status=RunRecordStatus.REJECTED,
            source_log_path=resolved_log_path,
            ordered_at=ordered_at,
            node_name=_coerce_str(payload.get("node")) or fallback_node,
            issues=issues,
            reasons=_dedupe_reasons(
                (
                    RuntimeReason(
                        code="invalid-run-log-envelope",
                        message="Run log execution payload must use the current structured schema.",
                        field="execution",
                    ),
                    *issues,
                )
            ),
        )

    node_name = str(payload["node"])
    signal_kind, signal_value, signal_reasons = _extract_record_signal(node_name, payload)
    return RunRecord(
        status=RunRecordStatus.LOADABLE,
        source_log_path=resolved_log_path,
        ordered_at=ordered_at,
        node_name=node_name,
        success=bool(payload["success"]),
        from_state=str(payload["from_state"]),
        to_state=str(payload["to_state"]),
        artifact_target=_resolve_artifact_target(payload),
        signal_kind=signal_kind,
        signal_value=signal_value,
        signal_reasons=signal_reasons,
        validation=typed_validation,
        writeback=typed_writeback,
        followup=typed_followup,
        dispatch=typed_dispatch,
        execution=typed_execution,
        issues=issues,
    )


def _parse_run_log_name(name: str) -> tuple[datetime, str] | None:
    match = _RUN_LOG_NAME_RE.match(name)
    if match is None:
        return None

    try:
        ordered_at = datetime.strptime(match.group("timestamp"), "%Y%m%dT%H%M%S%f")
    except ValueError:
        return None
    return ordered_at, match.group("node")


def _fallback_node_name(name: str) -> str | None:
    stem = Path(name).stem
    if "-" not in stem:
        return None
    _, node_name = stem.split("-", 1)
    return node_name or None


def _validate_run_log_envelope(payload: dict[str, Any]) -> tuple[RuntimeReason, ...]:
    errors: list[RuntimeReason] = []

    if not isinstance(payload.get("node"), str) or not payload["node"].strip():
        errors.append(
            RuntimeReason(
                code="invalid-run-log-envelope",
                message="Run log must include a non-empty node name.",
                field="node",
            )
        )
    if not isinstance(payload.get("success"), bool):
        errors.append(
            RuntimeReason(
                code="invalid-run-log-envelope",
                message="Run log must include a boolean success field.",
                field="success",
            )
        )
    for field in ("from_state", "to_state"):
        if not isinstance(payload.get(field), str) or not str(payload[field]).strip():
            errors.append(
                RuntimeReason(
                    code="invalid-run-log-envelope",
                    message=f"Run log must include a non-empty {field} field.",
                    field=field,
                )
            )

    for field in ("plan_path", "spec_path", "output_path", "log_path", "rendered_output"):
        value = payload.get(field)
        if value is not None and not isinstance(value, str):
            errors.append(
                RuntimeReason(
                    code="invalid-run-log-envelope",
                    message=f"Run log field must be a string or null: {field}",
                    field=field,
                )
            )

    metadata = payload.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        errors.append(
            RuntimeReason(
                code="invalid-run-log-envelope",
                message="Run log metadata must be a JSON object when present.",
                field="metadata",
            )
        )

    return tuple(errors)


def _resolve_artifact_target(payload: dict[str, Any]) -> ArtifactTarget | None:
    if _coerce_str(payload.get("spec_path")) is not None:
        return ArtifactTarget(ArtifactTargetKind.SPEC, str(payload["spec_path"]))
    if _coerce_str(payload.get("plan_path")) is not None:
        return ArtifactTarget(ArtifactTargetKind.PLAN, str(payload["plan_path"]))
    if _coerce_str(payload.get("output_path")) is not None:
        return ArtifactTarget(ArtifactTargetKind.OUTPUT, str(payload["output_path"]))
    return None


def _extract_record_signal(
    node_name: str,
    payload: dict[str, Any],
) -> tuple[ReplaySignalKind | None, str | None, tuple[RuntimeReason, ...]]:
    signal_spec = _SUPPORTED_SIGNAL_SPECS.get(node_name)
    if signal_spec is None:
        return None, None, ()

    signal_payload = payload.get(signal_spec.field)
    if not isinstance(signal_payload, dict):
        return None, None, ()

    signal_value = _coerce_str(signal_payload.get(signal_spec.value_key))
    if signal_value is None:
        return None, None, ()

    typed_reasons = _parse_reason_list(signal_payload.get("reasons", []), field=f"{signal_spec.field}.reasons")
    return signal_spec.kind, signal_value, typed_reasons or ()


_INVALID = object()


def _parse_validation_result(value: object) -> ValidationResult | None | object:
    if value is None:
        return None
    if not isinstance(value, dict):
        return _INVALID

    status = _parse_enum(value.get("status"), ValidationStatus)
    if status is None:
        return _INVALID

    evidence_payload = value.get("evidence", [])
    if not isinstance(evidence_payload, list):
        return _INVALID

    evidence: list[ValidationEvidence] = []
    for entry in evidence_payload:
        parsed = _parse_validation_evidence(entry)
        if parsed is _INVALID:
            return _INVALID
        evidence.append(parsed)

    reasons = _parse_reason_list(value.get("reasons", []), field="validation.reasons")
    if reasons is None:
        return _INVALID

    return ValidationResult(
        status=status,
        evidence=tuple(evidence),
        reasons=reasons,
    )


def _parse_validation_evidence(value: object) -> ValidationEvidence | object:
    if not isinstance(value, dict):
        return _INVALID

    kind = _parse_enum(value.get("kind"), ValidationEvidenceKind)
    status = _parse_enum(value.get("status"), ValidationEvidenceStatus)
    summary = _coerce_str(value.get("summary"))
    source = value.get("source")
    if kind is None or status is None or summary is None:
        return _INVALID
    if source is not None and not isinstance(source, str):
        return _INVALID

    return ValidationEvidence(
        kind=kind,
        status=status,
        summary=summary,
        source=source,
    )


def _parse_writeback_result(value: object) -> WritebackResult | None | object:
    if value is None:
        return None
    if not isinstance(value, dict):
        return _INVALID

    destination = _parse_enum(value.get("destination"), WritebackDestination)
    candidate_kind = _parse_optional_enum(value.get("candidate_kind"), WritebackCandidateKind)
    should_write_back = value.get("should_write_back")
    reasons = _parse_reason_list(value.get("reasons", []), field="writeback.reasons")
    if destination is None or not isinstance(should_write_back, bool) or reasons is None:
        return _INVALID

    return WritebackResult(
        destination=destination,
        should_write_back=should_write_back,
        reasons=reasons,
        candidate_kind=candidate_kind,
    )


def _parse_followup_result(value: object) -> FollowupResult | None | object:
    if value is None:
        return None
    if not isinstance(value, dict):
        return _INVALID

    action = _parse_enum(value.get("action"), FollowupAction)
    explanation = _coerce_str(value.get("explanation"))
    reasons = _parse_reason_list(value.get("reasons", []), field="followup.reasons")
    if action is None or explanation is None or reasons is None:
        return _INVALID

    return FollowupResult(
        action=action,
        explanation=explanation,
        reasons=reasons,
    )


def _parse_dispatch_result(value: object) -> DispatchResult | None | object:
    if value is None:
        return None
    if not isinstance(value, dict):
        return _INVALID

    target = _parse_enum(value.get("target"), ExecutorTarget)
    status = _parse_enum(value.get("status"), DispatchStatus)
    mode = _parse_enum(value.get("mode"), DispatchMode)
    payload = _parse_dispatch_payload(value.get("payload"))
    reasons = _parse_reason_list(value.get("reasons", []), field="dispatch.reasons")
    executor = _parse_executor_descriptor(value.get("executor")) if value.get("executor") is not None else None
    requirements = (
        _parse_executor_requirements(value.get("requirements"))
        if value.get("requirements") is not None
        else None
    )
    execution_metadata = value.get("execution_metadata", {})
    if target is None or status is None or mode is None or payload is _INVALID or reasons is None:
        return _INVALID
    if requirements is _INVALID:
        return _INVALID
    if not isinstance(execution_metadata, dict):
        return _INVALID

    return DispatchResult(
        target=target,
        status=status,
        mode=mode,
        payload=payload,
        reasons=reasons,
        executor=executor,
        requirements=requirements,
        execution_metadata=execution_metadata,
    )


def _parse_dispatch_payload(value: object) -> DispatchPayload | None | object:
    if value is None:
        return None
    if not isinstance(value, dict):
        return _INVALID
    title = _coerce_str(value.get("title"))
    goal = _coerce_str(value.get("goal"))
    in_scope = value.get("in_scope", [])
    done_when = _coerce_str(value.get("done_when"))
    if title is None or goal is None or done_when is None or not _is_list_of_strings(in_scope):
        return _INVALID
    return DispatchPayload(
        title=title,
        goal=goal,
        in_scope=tuple(in_scope),
        done_when=done_when,
    )


def _parse_execution_result(value: object) -> ExecutionResult | None | object:
    if value is None:
        return None
    if not isinstance(value, dict):
        return _INVALID

    executor = _parse_executor_descriptor(value.get("executor"))
    final_status = _parse_enum(value.get("final_status"), ExecutionStatus)
    spec_identity = value.get("spec_identity")
    dispatch_summary = value.get("dispatch_summary")
    summary = _coerce_str(value.get("summary"))
    changed_files = value.get("changed_files", [])
    validations_claimed = value.get("validations_claimed", [])
    uncovered_items = value.get("uncovered_items", [])
    suggested_followups = value.get("suggested_followups", [])
    raw_artifact_refs = value.get("raw_artifact_refs", [])
    findings = value.get("findings", [])
    repair_spec_candidate = value.get("repair_spec_candidate")
    if executor is None or final_status is None or summary is None or not isinstance(dispatch_summary, dict):
        return _INVALID
    if spec_identity is not None and not isinstance(spec_identity, str):
        return _INVALID
    if not _is_list_of_strings(changed_files):
        return _INVALID
    if not _is_list_of_strings(validations_claimed):
        return _INVALID
    if not _is_list_of_strings(uncovered_items):
        return _INVALID
    if not _is_list_of_strings(suggested_followups):
        return _INVALID

    parsed_refs: list[ExecutionArtifactRef] = []
    for item in raw_artifact_refs:
        parsed = _parse_execution_artifact_ref(item)
        if parsed is _INVALID:
            return _INVALID
        parsed_refs.append(parsed)

    parsed_findings: list[ReviewFinding] = []
    for item in findings:
        parsed = _parse_review_finding(item)
        if parsed is _INVALID:
            return _INVALID
        parsed_findings.append(parsed)

    parsed_candidate = _parse_repair_spec_candidate(repair_spec_candidate)
    if parsed_candidate is _INVALID:
        return _INVALID

    stdout_summary = value.get("stdout_summary")
    stderr_summary = value.get("stderr_summary")
    log_summary = value.get("log_summary")
    patch_ref = value.get("patch_ref")
    branch_ref = value.get("branch_ref")
    commit_ref = value.get("commit_ref")
    for item in (stdout_summary, stderr_summary, log_summary, patch_ref, branch_ref, commit_ref):
        if item is not None and not isinstance(item, str):
            return _INVALID

    return ExecutionResult(
        executor=executor,
        spec_identity=spec_identity,
        dispatch_summary=dispatch_summary,
        final_status=final_status,
        summary=summary,
        changed_files=tuple(changed_files),
        patch_ref=patch_ref,
        branch_ref=branch_ref,
        commit_ref=commit_ref,
        stdout_summary=stdout_summary,
        stderr_summary=stderr_summary,
        log_summary=log_summary,
        validations_claimed=tuple(validations_claimed),
        uncovered_items=tuple(uncovered_items),
        suggested_followups=tuple(suggested_followups),
        raw_artifact_refs=tuple(parsed_refs),
        findings=tuple(parsed_findings),
        repair_spec_candidate=parsed_candidate,
    )


def _parse_executor_descriptor(value: object) -> ExecutorDescriptor | None:
    if not isinstance(value, dict):
        return None
    name = _coerce_str(value.get("name"))
    executor_type = _coerce_str(value.get("type"))
    version = _coerce_str(value.get("version"))
    capabilities = value.get("capabilities")
    if name is None or executor_type is None or version is None or not isinstance(capabilities, dict):
        return None
    parsed_capabilities = _parse_capability_profile(capabilities)
    if parsed_capabilities is None:
        return None
    return ExecutorDescriptor(
        name=name,
        executor_type=executor_type,
        version=version,
        capabilities=parsed_capabilities,
    )


def _parse_executor_requirements(value: object) -> ExecutorRequirements | object:
    if not isinstance(value, dict):
        return _INVALID
    parsed = _parse_capability_profile(value)
    if parsed is None:
        return _INVALID
    return ExecutorRequirements(**parsed.to_record())


def _parse_capability_profile(value: dict[str, Any]) -> ExecutorCapabilityProfile | None:
    keys = (
        "can_edit_files",
        "can_run_shell",
        "can_open_repo_context",
        "can_return_patch",
        "can_return_commit",
        "can_run_tests",
        "can_do_review_only",
        "supports_noninteractive",
        "supports_resume",
    )
    payload: dict[str, bool] = {}
    for key in keys:
        item = value.get(key)
        if not isinstance(item, bool):
            return None
        payload[key] = item
    return ExecutorCapabilityProfile(**payload)


def _parse_execution_artifact_ref(value: object) -> ExecutionArtifactRef | object:
    if not isinstance(value, dict):
        return _INVALID
    kind = _coerce_str(value.get("kind"))
    raw_value = _coerce_str(value.get("value"))
    if kind is None or raw_value is None:
        return _INVALID
    return ExecutionArtifactRef(kind=kind, value=raw_value)


def _parse_review_finding(value: object) -> ReviewFinding | object:
    if not isinstance(value, dict):
        return _INVALID
    code = _coerce_str(value.get("code"))
    message = _coerce_str(value.get("message"))
    severity = _parse_enum(value.get("severity"), ReviewFindingSeverity)
    field_name = value.get("field")
    source = value.get("source")
    if code is None or message is None or severity is None:
        return _INVALID
    if field_name is not None and not isinstance(field_name, str):
        return _INVALID
    if source is not None and not isinstance(source, str):
        return _INVALID
    return ReviewFinding(code=code, message=message, severity=severity, field=field_name, source=source)


def _parse_repair_spec_candidate(value: object) -> RepairSpecCandidate | None | object:
    if value is None:
        return None
    if not isinstance(value, dict):
        return _INVALID
    title = _coerce_str(value.get("title"))
    goal = _coerce_str(value.get("goal"))
    in_scope = value.get("in_scope", [])
    validation_focus = value.get("validation_focus", [])
    triggering_findings = value.get("triggering_findings", [])
    if title is None or goal is None or not _is_list_of_strings(in_scope) or not _is_list_of_strings(validation_focus):
        return _INVALID
    parsed_findings: list[ReviewFinding] = []
    for item in triggering_findings:
        parsed = _parse_review_finding(item)
        if parsed is _INVALID:
            return _INVALID
        parsed_findings.append(parsed)
    return RepairSpecCandidate(
        title=title,
        goal=goal,
        in_scope=tuple(in_scope),
        validation_focus=tuple(validation_focus),
        triggering_findings=tuple(parsed_findings),
    )


def _parse_reason_list(value: object, *, field: str) -> tuple[RuntimeReason, ...] | None:
    if value is None:
        return ()
    if not isinstance(value, list):
        return None

    reasons: list[RuntimeReason] = []
    for item in value:
        if not isinstance(item, dict):
            return None
        code = _coerce_str(item.get("code"))
        message = _coerce_str(item.get("message"))
        field_name = item.get("field")
        if code is None or message is None:
            return None
        if field_name is not None and not isinstance(field_name, str):
            return None
        reasons.append(RuntimeReason(code=code, message=message, field=field_name))
    return tuple(reasons)


def _dedupe_reasons(reasons: tuple[RuntimeReason, ...] | list[RuntimeReason]) -> tuple[RuntimeReason, ...]:
    deduped: list[RuntimeReason] = []
    seen: set[tuple[str, str, str | None]] = set()
    for reason in reasons:
        identity = (reason.code, reason.message, reason.field)
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append(reason)
    return tuple(deduped)


def _coerce_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def _is_list_of_strings(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _parse_enum(value: object, enum_type: type[Enum]) -> Enum | None:
    if not isinstance(value, str):
        return None
    try:
        return enum_type(value)
    except ValueError:
        return None


def _parse_optional_enum(value: object, enum_type: type[Enum]) -> Enum | None | object:
    if value is None:
        return None
    parsed = _parse_enum(value, enum_type)
    if parsed is None:
        return _INVALID
    return parsed
