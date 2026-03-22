from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from ai_engineering_runtime.adapters import FileSystemAdapter
from ai_engineering_runtime.artifact_refs import (
    ArtifactRef,
    ArtifactRefKind,
    artifact_ref_from_artifact_target,
    build_runtime_artifact_ref,
)
from ai_engineering_runtime.history_selection import select_correlated_history
from ai_engineering_runtime.run_logs import ReplaySignalKind, RunRecordStatus, load_run_record
from ai_engineering_runtime.run_summary import RunSummary, resolve_summary_query
from ai_engineering_runtime.runtime_queries import missing_run_log_reasons, resolve_run_log_query
from ai_engineering_runtime.state import RuntimeReason, WritebackDestination
from ai_engineering_runtime.validation_rollup import resolve_validation_rollup_query

_WRITEBACK_SOURCE_NODE = "writeback-classifier"
_PACKAGE_VERSION = 1


@dataclass(frozen=True)
class WritebackPackage:
    version: int
    run_id: str
    destination: WritebackDestination
    actionable: bool
    rationale: str
    source_log_ref: ArtifactRef
    summary_ref: ArtifactRef
    supporting_refs: tuple[ArtifactRef, ...] = ()
    suggested_next_action: str | None = None
    validation_rollup_ref: ArtifactRef | None = None
    reasons: tuple[RuntimeReason, ...] = ()
    candidate_kind: str | None = None

    def to_record(self) -> dict[str, object]:
        return {
            "version": self.version,
            "run_id": self.run_id,
            "destination": self.destination.value,
            "actionable": self.actionable,
            "rationale": self.rationale,
            "source_log_ref": self.source_log_ref.to_record(),
            "summary_ref": self.summary_ref.to_record(),
            "supporting_refs": [artifact_ref.to_record() for artifact_ref in self.supporting_refs],
            "suggested_next_action": self.suggested_next_action,
            "validation_rollup_ref": (
                self.validation_rollup_ref.to_record() if self.validation_rollup_ref is not None else None
            ),
            "reasons": [reason.to_record() for reason in self.reasons],
            "candidate_kind": self.candidate_kind,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_record(), indent=2, sort_keys=True)

    @classmethod
    def from_record(cls, payload: object) -> "WritebackPackage" | None:
        if not isinstance(payload, dict):
            return None
        version = payload.get("version")
        run_id = payload.get("run_id")
        destination = payload.get("destination")
        actionable = payload.get("actionable")
        rationale = payload.get("rationale")
        suggested_next_action = payload.get("suggested_next_action")
        candidate_kind = payload.get("candidate_kind")
        source_log_ref = ArtifactRef.from_record(payload.get("source_log_ref"))
        summary_ref = ArtifactRef.from_record(payload.get("summary_ref"))
        validation_rollup_ref = ArtifactRef.from_record(payload.get("validation_rollup_ref"))
        supporting_refs_payload = payload.get("supporting_refs")
        reasons_payload = payload.get("reasons")
        if not isinstance(version, int) or not isinstance(run_id, str):
            return None
        if not isinstance(destination, str) or not isinstance(actionable, bool) or not isinstance(rationale, str):
            return None
        if suggested_next_action is not None and not isinstance(suggested_next_action, str):
            return None
        if candidate_kind is not None and not isinstance(candidate_kind, str):
            return None
        if source_log_ref is None or summary_ref is None:
            return None
        if not isinstance(supporting_refs_payload, list) or not isinstance(reasons_payload, list):
            return None

        supporting_refs: list[ArtifactRef] = []
        for item in supporting_refs_payload:
            parsed = ArtifactRef.from_record(item)
            if parsed is None:
                return None
            supporting_refs.append(parsed)

        reasons = _parse_reason_records(reasons_payload)
        if reasons is None:
            return None

        try:
            return cls(
                version=version,
                run_id=run_id,
                destination=WritebackDestination(destination),
                actionable=actionable,
                rationale=rationale,
                source_log_ref=source_log_ref,
                summary_ref=summary_ref,
                supporting_refs=tuple(supporting_refs),
                suggested_next_action=suggested_next_action,
                validation_rollup_ref=validation_rollup_ref,
                reasons=reasons,
                candidate_kind=candidate_kind,
            )
        except ValueError:
            return None


def resolve_writeback_package_query(
    adapter: FileSystemAdapter,
    *,
    log_path: Path | None = None,
    run_id: str | None = None,
    latest: bool = False,
    node_name: str | None = None,
) -> tuple[WritebackPackage | None, tuple[RuntimeReason, ...]]:
    selected_log = resolve_run_log_query(
        adapter,
        log_path=log_path,
        run_id=run_id,
        latest=latest,
        node_name=node_name or (_WRITEBACK_SOURCE_NODE if latest else None),
    )
    if selected_log is None:
        return None, missing_run_log_reasons(
            log_path=log_path,
            run_id=run_id,
            latest=latest,
            node_name=node_name or (_WRITEBACK_SOURCE_NODE if latest else None),
        )

    package_path = adapter.build_writeback_package_path(selected_log.stem)
    loaded = _load_package(package_path)
    if loaded is not None:
        return loaded, ()
    return materialize_writeback_package_for_log(adapter, selected_log)


def materialize_writeback_package_for_log(
    adapter: FileSystemAdapter,
    log_path: Path,
) -> tuple[WritebackPackage | None, tuple[RuntimeReason, ...]]:
    record = load_run_record(log_path)
    if record.status is not RunRecordStatus.LOADABLE:
        return None, record.reasons
    if record.source_log_path is None:
        return None, (
            RuntimeReason(
                code="missing-run-log",
                message="Write-back package requires a source run log path.",
                field="log_path",
            ),
        )
    if record.writeback is None:
        return None, (
            RuntimeReason(
                code="missing-writeback-result",
                message="The selected run log does not contain a write-back result payload.",
                field="writeback",
            ),
        )

    summary, reasons = resolve_summary_query(adapter, log_path=record.source_log_path)
    if summary is None:
        return None, reasons

    package = build_writeback_package(adapter, summary=summary)
    path = adapter.build_writeback_package_path(package.run_id)
    adapter.write_json(path, package.to_record())
    return package, ()


def build_writeback_package(
    adapter: FileSystemAdapter,
    *,
    summary: RunSummary,
) -> WritebackPackage:
    record = load_run_record(summary.source_log_path)
    writeback = record.writeback
    if writeback is None:
        raise ValueError("Write-back package requires a run log with a write-back result payload.")

    source_log_ref = build_runtime_artifact_ref(
        adapter.repo_root,
        kind=ArtifactRefKind.RUN_LOG,
        run_id=summary.run_id,
    )
    summary_ref = build_runtime_artifact_ref(
        adapter.repo_root,
        kind=ArtifactRefKind.RUN_SUMMARY,
        run_id=summary.run_id,
    )
    supporting_refs: list[ArtifactRef] = [source_log_ref, summary_ref]
    if summary.artifact_target is not None:
        supporting_refs.append(artifact_ref_from_artifact_target(adapter.repo_root, summary.artifact_target))

    validation_rollup_ref = _resolve_related_validation_rollup_ref(adapter, summary)
    rationale = writeback.reasons[0].message if writeback.reasons else "Write-back classification is available for review."
    if validation_rollup_ref is not None:
        supporting_refs.append(validation_rollup_ref)

    return WritebackPackage(
        version=_PACKAGE_VERSION,
        run_id=summary.run_id,
        destination=writeback.destination,
        actionable=writeback.should_write_back,
        rationale=rationale,
        source_log_ref=source_log_ref,
        summary_ref=summary_ref,
        supporting_refs=tuple(_dedupe_refs(supporting_refs)),
        suggested_next_action=_suggested_next_action(writeback.destination),
        validation_rollup_ref=validation_rollup_ref,
        reasons=writeback.reasons,
        candidate_kind=writeback.candidate_kind.value if writeback.candidate_kind is not None else None,
    )


def _resolve_related_validation_rollup_ref(
    adapter: FileSystemAdapter,
    summary: RunSummary,
) -> ArtifactRef | None:
    if summary.artifact_target is None:
        return None

    selection = select_correlated_history(
        adapter.repo_root,
        artifact_kind=summary.artifact_target.kind,
        artifact_path=summary.artifact_target.path,
        node_name="validation-collect",
        signal_kind=ReplaySignalKind.VALIDATION,
        limit=1,
    )
    if not selection.matches:
        return None

    validation_log_path = selection.matches[0].source_log_path
    if validation_log_path is None:
        return None

    rollup, _ = resolve_validation_rollup_query(adapter, run_id=validation_log_path.stem)
    if rollup is None:
        return None

    return build_runtime_artifact_ref(
        adapter.repo_root,
        kind=ArtifactRefKind.VALIDATION_ROLLUP,
        run_id=rollup.run_id,
    )


def _suggested_next_action(destination: WritebackDestination) -> str | None:
    if destination is WritebackDestination.FACTS:
        return "Review the candidate and write the stable context into docs/facts/."
    if destination is WritebackDestination.SKILLS:
        return "Review the candidate and promote the reusable workflow into skills/."
    if destination is WritebackDestination.CHANGE_SUMMARY_ONLY:
        return "Keep the note in the task closeout or change summary only."
    return None


def _dedupe_refs(artifact_refs: list[ArtifactRef]) -> list[ArtifactRef]:
    deduped: list[ArtifactRef] = []
    seen: set[tuple[str, str]] = set()
    for artifact_ref in artifact_refs:
        identity = (artifact_ref.kind.value, artifact_ref.path)
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append(artifact_ref)
    return deduped


def _load_package(path: Path) -> WritebackPackage | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return WritebackPackage.from_record(payload)


def _parse_reason_records(payload: list[object]) -> tuple[RuntimeReason, ...] | None:
    reasons: list[RuntimeReason] = []
    for item in payload:
        if not isinstance(item, dict):
            return None
        code = item.get("code")
        message = item.get("message")
        field = item.get("field")
        if not isinstance(code, str) or not isinstance(message, str):
            return None
        if field is not None and not isinstance(field, str):
            return None
        reasons.append(RuntimeReason(code=code, message=message, field=field))
    return tuple(reasons)
