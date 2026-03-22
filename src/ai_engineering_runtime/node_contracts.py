from __future__ import annotations

from dataclasses import dataclass

from ai_engineering_runtime.artifact_refs import ArtifactRefKind
from ai_engineering_runtime.run_logs import ReplaySignalKind
from ai_engineering_runtime.terminal_state import TerminalStatus


@dataclass(frozen=True)
class NodeContract:
    node_name: str
    required_ref_kinds: tuple[ArtifactRefKind, ...] = ()
    required_signal_kinds: tuple[ReplaySignalKind, ...] = ()
    required_any_signal_groups: tuple[tuple[ReplaySignalKind, ...], ...] = ()
    produced_ref_kinds: tuple[ArtifactRefKind, ...] = ()
    produced_signal_kinds: tuple[ReplaySignalKind, ...] = ()
    applicable_terminal_statuses: tuple[TerminalStatus, ...] = ()
    primary_output_kind: ArtifactRefKind | None = None


_CONTRACTS: dict[str, NodeContract] = {
    "plan-readiness-check": NodeContract(
        node_name="plan-readiness-check",
        required_ref_kinds=(ArtifactRefKind.PLAN,),
        produced_signal_kinds=(ReplaySignalKind.READINESS,),
    ),
    "plan-to-spec": NodeContract(
        node_name="plan-to-spec",
        required_ref_kinds=(ArtifactRefKind.PLAN,),
        required_signal_kinds=(ReplaySignalKind.READINESS,),
        applicable_terminal_statuses=(TerminalStatus.READY,),
        produced_ref_kinds=(ArtifactRefKind.TASK_SPEC,),
        primary_output_kind=ArtifactRefKind.TASK_SPEC,
    ),
    "task-spec-readiness-check": NodeContract(
        node_name="task-spec-readiness-check",
        required_ref_kinds=(ArtifactRefKind.TASK_SPEC,),
        produced_signal_kinds=(ReplaySignalKind.READINESS,),
    ),
    "validation-collect": NodeContract(
        node_name="validation-collect",
        required_ref_kinds=(ArtifactRefKind.TASK_SPEC,),
        produced_signal_kinds=(ReplaySignalKind.VALIDATION,),
    ),
    "writeback-classifier": NodeContract(
        node_name="writeback-classifier",
        produced_signal_kinds=(ReplaySignalKind.WRITEBACK,),
    ),
    "followup-suggester": NodeContract(
        node_name="followup-suggester",
        required_any_signal_groups=(
            (
                ReplaySignalKind.READINESS,
                ReplaySignalKind.VALIDATION,
                ReplaySignalKind.WRITEBACK,
            ),
        ),
        produced_signal_kinds=(ReplaySignalKind.FOLLOWUP,),
    ),
    "executor-dispatch": NodeContract(
        node_name="executor-dispatch",
        required_ref_kinds=(ArtifactRefKind.TASK_SPEC,),
        required_signal_kinds=(ReplaySignalKind.READINESS,),
        applicable_terminal_statuses=(TerminalStatus.READY,),
        produced_signal_kinds=(ReplaySignalKind.DISPATCH,),
    ),
    "result-log-replay": NodeContract(
        node_name="result-log-replay",
        required_ref_kinds=(ArtifactRefKind.RUN_LOG,),
        produced_signal_kinds=(),
    ),
    "run-history-select": NodeContract(
        node_name="run-history-select",
        required_any_signal_groups=(
            (
                ReplaySignalKind.READINESS,
                ReplaySignalKind.VALIDATION,
                ReplaySignalKind.WRITEBACK,
                ReplaySignalKind.FOLLOWUP,
                ReplaySignalKind.DISPATCH,
            ),
        ),
    ),
    "run-summary": NodeContract(
        node_name="run-summary",
        required_ref_kinds=(ArtifactRefKind.RUN_LOG,),
        produced_ref_kinds=(ArtifactRefKind.RUN_SUMMARY,),
        primary_output_kind=ArtifactRefKind.RUN_SUMMARY,
    ),
    "validation-rollup": NodeContract(
        node_name="validation-rollup",
        required_ref_kinds=(ArtifactRefKind.RUN_SUMMARY,),
        required_signal_kinds=(ReplaySignalKind.VALIDATION,),
        produced_ref_kinds=(ArtifactRefKind.VALIDATION_ROLLUP,),
        primary_output_kind=ArtifactRefKind.VALIDATION_ROLLUP,
    ),
    "writeback-package": NodeContract(
        node_name="writeback-package",
        required_ref_kinds=(ArtifactRefKind.RUN_SUMMARY,),
        required_signal_kinds=(ReplaySignalKind.WRITEBACK,),
        produced_ref_kinds=(ArtifactRefKind.WRITEBACK_PACKAGE,),
        primary_output_kind=ArtifactRefKind.WRITEBACK_PACKAGE,
    ),
    "followup-package": NodeContract(
        node_name="followup-package",
        required_ref_kinds=(ArtifactRefKind.RUN_SUMMARY,),
        required_signal_kinds=(ReplaySignalKind.FOLLOWUP,),
        produced_ref_kinds=(ArtifactRefKind.FOLLOWUP_PACKAGE,),
        primary_output_kind=ArtifactRefKind.FOLLOWUP_PACKAGE,
    ),
}


def get_node_contract(node_name: str) -> NodeContract | None:
    return _CONTRACTS.get(node_name)


def list_node_contracts() -> tuple[NodeContract, ...]:
    return tuple(_CONTRACTS[name] for name in sorted(_CONTRACTS))
