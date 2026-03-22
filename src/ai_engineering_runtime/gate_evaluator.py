from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json

from ai_engineering_runtime.adapters import FileSystemAdapter
from ai_engineering_runtime.artifact_refs import (
    ArtifactRef,
    ArtifactRefKind,
    artifact_ref_exists,
    artifact_ref_from_artifact_target,
    build_runtime_artifact_ref,
)
from ai_engineering_runtime.node_contracts import get_node_contract
from ai_engineering_runtime.run_logs import ReplaySignalKind
from ai_engineering_runtime.run_summary import RunSummary
from ai_engineering_runtime.state import RuntimeReason


class GateStatus(str, Enum):
    ELIGIBLE = "eligible"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class NodeGateResult:
    node_name: str
    status: GateStatus
    summary_run_id: str | None = None
    blocking_reasons: tuple[RuntimeReason, ...] = ()
    advisory_reasons: tuple[RuntimeReason, ...] = ()

    def to_record(self) -> dict[str, object]:
        return {
            "node": self.node_name,
            "status": self.status.value,
            "summary_run_id": self.summary_run_id,
            "blocking_reasons": [reason.to_record() for reason in self.blocking_reasons],
            "advisory_reasons": [reason.to_record() for reason in self.advisory_reasons],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_record(), indent=2, sort_keys=True)


def evaluate_node_gate(
    adapter: FileSystemAdapter,
    *,
    node_name: str,
    summary: RunSummary,
) -> NodeGateResult:
    contract = get_node_contract(node_name)
    if contract is None:
        return NodeGateResult(
            node_name=node_name,
            status=GateStatus.UNKNOWN,
            summary_run_id=summary.run_id,
            blocking_reasons=(
                RuntimeReason(
                    code="unknown-node-contract",
                    message=f"No declared node contract exists for: {node_name}",
                    field="node",
                ),
            ),
        )

    available_refs = _available_refs(adapter, summary)
    available_ref_kinds = {artifact_ref.kind for artifact_ref in available_refs}
    available_signal_kinds = _available_signal_kinds(summary)

    if contract.applicable_terminal_statuses and summary.terminal_state.status not in contract.applicable_terminal_statuses:
        return NodeGateResult(
            node_name=node_name,
            status=GateStatus.NOT_APPLICABLE,
            summary_run_id=summary.run_id,
            blocking_reasons=(
                RuntimeReason(
                    code="terminal-status-not-applicable",
                    message=(
                        f"Node {node_name} is not applicable for terminal status "
                        f"{summary.terminal_state.status.value}."
                    ),
                    field="terminal_status",
                ),
            ),
        )

    primary_output_ref = _primary_output_ref(adapter, contract.primary_output_kind, summary.run_id)
    if primary_output_ref is not None and artifact_ref_exists(adapter.repo_root, primary_output_ref):
        return NodeGateResult(
            node_name=node_name,
            status=GateStatus.SKIPPED,
            summary_run_id=summary.run_id,
            advisory_reasons=(
                RuntimeReason(
                    code="primary-output-already-exists",
                    message=(
                        f"Primary output for node {node_name} already exists: "
                        f"{primary_output_ref.path}"
                    ),
                    field="output",
                ),
            ),
        )

    blocking_reasons: list[RuntimeReason] = []
    for ref_kind in contract.required_ref_kinds:
        if ref_kind not in available_ref_kinds:
            blocking_reasons.append(
                RuntimeReason(
                    code="missing-required-artifact-ref",
                    message=f"Required artifact ref kind is missing: {ref_kind.value}",
                    field="artifact_ref",
                )
            )

    for signal_kind in contract.required_signal_kinds:
        if signal_kind not in available_signal_kinds:
            blocking_reasons.append(
                RuntimeReason(
                    code="missing-required-signal",
                    message=f"Required signal kind is missing: {signal_kind.value}",
                    field="signal",
                )
            )

    for group in contract.required_any_signal_groups:
        if not any(signal_kind in available_signal_kinds for signal_kind in group):
            blocking_reasons.append(
                RuntimeReason(
                    code="missing-required-any-signal-group",
                    message=(
                        "At least one signal from the declared group is required: "
                        + ", ".join(signal_kind.value for signal_kind in group)
                    ),
                    field="signal",
                )
            )

    if blocking_reasons:
        return NodeGateResult(
            node_name=node_name,
            status=GateStatus.BLOCKED,
            summary_run_id=summary.run_id,
            blocking_reasons=tuple(blocking_reasons),
        )

    advisory_reasons: list[RuntimeReason] = []
    if summary.artifact_target is None:
        advisory_reasons.append(
            RuntimeReason(
                code="no-artifact-target-context",
                message="Current run summary does not carry an artifact target; downstream correlation is limited.",
                field="artifact_target",
            )
        )

    return NodeGateResult(
        node_name=node_name,
        status=GateStatus.ELIGIBLE,
        summary_run_id=summary.run_id,
        advisory_reasons=tuple(advisory_reasons),
    )


def _available_refs(adapter: FileSystemAdapter, summary: RunSummary) -> tuple[ArtifactRef, ...]:
    refs: list[ArtifactRef] = [
        build_runtime_artifact_ref(
            adapter.repo_root,
            kind=ArtifactRefKind.RUN_LOG,
            run_id=summary.run_id,
        ),
        build_runtime_artifact_ref(
            adapter.repo_root,
            kind=ArtifactRefKind.RUN_SUMMARY,
            run_id=summary.run_id,
        ),
    ]
    if summary.artifact_target is not None:
        refs.append(artifact_ref_from_artifact_target(adapter.repo_root, summary.artifact_target))

    for ref_kind in (
        ArtifactRefKind.VALIDATION_ROLLUP,
        ArtifactRefKind.WRITEBACK_PACKAGE,
        ArtifactRefKind.FOLLOWUP_PACKAGE,
    ):
        runtime_ref = build_runtime_artifact_ref(adapter.repo_root, kind=ref_kind, run_id=summary.run_id)
        if artifact_ref_exists(adapter.repo_root, runtime_ref):
            refs.append(runtime_ref)

    return tuple(refs)


def _available_signal_kinds(summary: RunSummary) -> set[ReplaySignalKind]:
    if summary.terminal_state.signal_kind is None:
        return set()
    try:
        return {ReplaySignalKind(summary.terminal_state.signal_kind)}
    except ValueError:
        return set()


def _primary_output_ref(
    adapter: FileSystemAdapter,
    primary_output_kind: ArtifactRefKind | None,
    run_id: str,
) -> ArtifactRef | None:
    if primary_output_kind is None:
        return None
    return build_runtime_artifact_ref(
        adapter.repo_root,
        kind=primary_output_kind,
        run_id=run_id,
    )
