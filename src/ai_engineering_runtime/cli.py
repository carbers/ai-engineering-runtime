from __future__ import annotations

from datetime import date
import argparse
from pathlib import Path
import sys
from typing import Sequence

from ai_engineering_runtime.adapters import FileSystemAdapter
from ai_engineering_runtime.engine import RunResult, RuntimeEngine
from ai_engineering_runtime.nodes.plan_readiness_check import (
    PlanReadinessCheckNode,
    PlanReadinessCheckRequest,
)
from ai_engineering_runtime.nodes.plan_to_spec import PlanToSpecNode, PlanToSpecRequest
from ai_engineering_runtime.nodes.result_log_replay import (
    ResultLogReplayNode,
    ResultLogReplayRequest,
)
from ai_engineering_runtime.nodes.executor_dispatch import (
    ExecutorDispatchNode,
    ExecutorDispatchRequest,
)
from ai_engineering_runtime.nodes.followup_suggester import (
    FollowupSuggesterNode,
    FollowupSuggesterRequest,
)
from ai_engineering_runtime.nodes.task_spec_readiness_check import (
    TaskSpecReadinessCheckNode,
    TaskSpecReadinessCheckRequest,
)
from ai_engineering_runtime.nodes.validation_collect import (
    ValidationCollectNode,
    ValidationCollectRequest,
)
from ai_engineering_runtime.nodes.writeback_classifier import (
    WritebackClassifierNode,
    WritebackClassifierRequest,
)
from ai_engineering_runtime.state import (
    CloseoutHint,
    DispatchMode,
    ExecutorTarget,
    ReadinessStatus,
    ValidationEvidenceStatus,
    ValidationStatus,
    WritebackCandidateKind,
    WritebackDestination,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ae-runtime",
        description="CLI-first workflow runtime for SOP artifacts.",
    )
    subparsers = parser.add_subparsers(dest="command")

    plan_readiness = subparsers.add_parser(
        "plan-readiness-check",
        help="Check whether a plan is ready to be compiled into a task spec.",
    )
    plan_readiness.add_argument("--plan", required=True, help="Path to the plan Markdown file.")

    task_spec_readiness = subparsers.add_parser(
        "task-spec-readiness-check",
        help="Check whether a task spec is ready to move into implementation or dispatch.",
    )
    task_spec_readiness.add_argument(
        "--spec",
        required=True,
        help="Path to the task spec Markdown file.",
    )

    validation_collect = subparsers.add_parser(
        "validation-collect",
        help="Aggregate supplied validation evidence into a structured closeout result.",
    )
    validation_collect.add_argument(
        "--spec",
        help="Optional task spec path used to determine whether white-box evidence is required.",
    )
    validation_collect.add_argument(
        "--command-status",
        choices=[status.value for status in ValidationEvidenceStatus if status is not ValidationEvidenceStatus.NOTED],
        help="Supplied command execution status.",
    )
    validation_collect.add_argument("--command-summary", help="Optional command evidence summary.")
    validation_collect.add_argument(
        "--black-box-status",
        choices=[status.value for status in ValidationEvidenceStatus if status is not ValidationEvidenceStatus.NOTED],
        help="Supplied black-box validation status.",
    )
    validation_collect.add_argument("--black-box-summary", help="Optional black-box evidence summary.")
    validation_collect.add_argument(
        "--white-box-status",
        choices=[status.value for status in ValidationEvidenceStatus if status is not ValidationEvidenceStatus.NOTED],
        help="Supplied white-box validation status.",
    )
    validation_collect.add_argument("--white-box-summary", help="Optional white-box evidence summary.")
    validation_collect.add_argument(
        "--note",
        action="append",
        default=[],
        help="Optional manual validation note. Repeat to add multiple notes.",
    )

    followup_suggester = subparsers.add_parser(
        "followup-suggester",
        help="Suggest the next narrow control-plane action from readiness, validation, and write-back signals.",
    )
    followup_suggester.add_argument(
        "--readiness-status",
        choices=[status.value for status in ReadinessStatus],
        help="Optional readiness result status.",
    )
    followup_suggester.add_argument(
        "--validation-status",
        choices=[status.value for status in ValidationStatus],
        help="Optional aggregated validation status.",
    )
    followup_suggester.add_argument(
        "--writeback-destination",
        choices=[destination.value for destination in WritebackDestination],
        help="Optional write-back destination result.",
    )
    followup_suggester.add_argument(
        "--closeout-hint",
        choices=[hint.value for hint in CloseoutHint],
        help="Optional explicit closeout hint.",
    )

    executor_dispatch = subparsers.add_parser(
        "executor-dispatch",
        help="Prepare or exercise a minimal shell-based handoff for a ready task spec.",
    )
    executor_dispatch.add_argument("--spec", required=True, help="Path to the task spec Markdown file.")
    executor_dispatch.add_argument(
        "--executor",
        choices=[target.value for target in ExecutorTarget],
        default=ExecutorTarget.SHELL.value,
        help="Executor target for dispatch.",
    )
    executor_dispatch.add_argument(
        "--mode",
        choices=[mode.value for mode in DispatchMode],
        default=DispatchMode.PREVIEW.value,
        help="Dispatch mode: preview or local echo.",
    )

    plan_to_spec = subparsers.add_parser(
        "plan-to-spec",
        help="Compile a plan or roadmap into a narrow draft task spec.",
    )
    plan_to_spec.add_argument("--plan", required=True, help="Path to the plan Markdown file.")
    plan_to_spec.add_argument(
        "--dry-run",
        action="store_true",
        help="Render the draft spec without writing the output file.",
    )
    plan_to_spec.add_argument(
        "--output",
        help="Optional explicit output path for the generated draft spec.",
    )

    writeback_classifier = subparsers.add_parser(
        "writeback-classifier",
        help="Classify whether a closeout item belongs in facts, skills, a change summary, or nowhere.",
    )
    writeback_classifier.add_argument(
        "--text",
        required=True,
        help="Candidate closeout text to classify.",
    )
    writeback_classifier.add_argument(
        "--kind",
        choices=[kind.value for kind in WritebackCandidateKind],
        help="Optional narrow kind hint for the candidate.",
    )

    result_log_replay = subparsers.add_parser(
        "result-log-replay",
        help="Inspect and normalize one prior runtime run log for replay-oriented downstream use.",
    )
    replay_selection = result_log_replay.add_mutually_exclusive_group(required=True)
    replay_selection.add_argument(
        "--log",
        help="Explicit path to a prior run log JSON file.",
    )
    replay_selection.add_argument(
        "--latest",
        action="store_true",
        help="Inspect the newest matching run log under .runtime/runs/.",
    )
    result_log_replay.add_argument(
        "--node",
        help="Optional node-name filter when selecting with --latest.",
    )

    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    repo_root: Path | None = None,
    today: date | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command not in {
        "plan-readiness-check",
        "task-spec-readiness-check",
        "validation-collect",
        "followup-suggester",
        "executor-dispatch",
        "plan-to-spec",
        "writeback-classifier",
        "result-log-replay",
    }:
        parser.print_help()
        return 1

    adapter = FileSystemAdapter(repo_root or Path.cwd())
    engine = RuntimeEngine(adapter)

    if args.command == "plan-readiness-check":
        result = engine.run(
            PlanReadinessCheckNode(
                PlanReadinessCheckRequest(
                    plan_path=Path(args.plan),
                )
            )
        )
        _emit_result(result, adapter, dry_run=False)
        return 0 if result.success else 1

    if args.command == "task-spec-readiness-check":
        result = engine.run(
            TaskSpecReadinessCheckNode(
                TaskSpecReadinessCheckRequest(
                    spec_path=Path(args.spec),
                )
            )
        )
        _emit_result(result, adapter, dry_run=False)
        return 0 if result.success else 1

    if args.command == "validation-collect":
        result = engine.run(
            ValidationCollectNode(
                ValidationCollectRequest(
                    spec_path=Path(args.spec) if args.spec else None,
                    command_status=_parse_validation_status(args.command_status),
                    command_summary=args.command_summary,
                    black_box_status=_parse_validation_status(args.black_box_status),
                    black_box_summary=args.black_box_summary,
                    white_box_status=_parse_validation_status(args.white_box_status),
                    white_box_summary=args.white_box_summary,
                    notes=tuple(args.note),
                )
            )
        )
        _emit_result(result, adapter, dry_run=False)
        return 0 if result.success else 1

    if args.command == "followup-suggester":
        result = engine.run(
            FollowupSuggesterNode(
                FollowupSuggesterRequest(
                    readiness_status=_parse_readiness_status(args.readiness_status),
                    validation_status=_parse_aggregate_validation_status(args.validation_status),
                    writeback_destination=_parse_writeback_destination(args.writeback_destination),
                    closeout_hint=_parse_closeout_hint(args.closeout_hint),
                )
            )
        )
        _emit_result(result, adapter, dry_run=False)
        return 0 if result.success else 1

    if args.command == "executor-dispatch":
        result = engine.run(
            ExecutorDispatchNode(
                ExecutorDispatchRequest(
                    spec_path=Path(args.spec),
                    target=_parse_executor_target(args.executor),
                    mode=_parse_dispatch_mode(args.mode),
                )
            )
        )
        _emit_result(result, adapter, dry_run=False)
        return 0 if result.success else 1

    if args.command == "writeback-classifier":
        result = engine.run(
            WritebackClassifierNode(
                WritebackClassifierRequest(
                    text=args.text,
                    candidate_kind=_parse_writeback_kind(args.kind),
                )
            )
        )
        _emit_result(result, adapter, dry_run=False)
        return 0 if result.success else 1

    if args.command == "result-log-replay":
        result = engine.run(
            ResultLogReplayNode(
                ResultLogReplayRequest(
                    log_path=Path(args.log) if args.log else None,
                    latest=bool(args.latest),
                    node_name=args.node,
                )
            )
        )
        _emit_result(result, adapter, dry_run=False)
        return 0 if result.success else 1

    request = PlanToSpecRequest(
        plan_path=Path(args.plan),
        dry_run=args.dry_run,
        output_path=Path(args.output) if args.output else None,
        created_on=today or date.today(),
    )
    result = engine.run(PlanToSpecNode(request))
    _emit_result(result, adapter, dry_run=args.dry_run)
    return 0 if result.success else 1


def _emit_result(result: RunResult, adapter: FileSystemAdapter, *, dry_run: bool) -> None:
    stream = sys.stdout if result.success else sys.stderr
    printed_reasons: set[tuple[str, str, str | None]] = set()
    status_line = f"{result.node_name} completed" if result.success else f"{result.node_name} failed"
    print(status_line, file=stream)
    if result.plan_path is not None:
        print(f"Plan: {adapter.display_path(result.plan_path)}", file=stream)
    if result.spec_path is not None:
        print(f"Spec: {adapter.display_path(result.spec_path)}", file=stream)
    if result.readiness is not None:
        print(f"Readiness: {result.readiness.status.value}", file=stream)
    if result.validation is not None:
        print(f"Validation: {result.validation.status.value}", file=stream)
    if result.followup is not None:
        print(f"Follow-up: {result.followup.action.value}", file=stream)
        print(f"Why: {result.followup.explanation}", file=stream)
    if result.replay is not None:
        print(f"Replay: {result.replay.status.value}", file=stream)
        if result.replay.source_log_path is not None:
            print(f"Source Log: {adapter.display_path(result.replay.source_log_path)}", file=stream)
        if result.replay.ordered_at is not None:
            print(f"Ordered At: {result.replay.ordered_at.isoformat()}", file=stream)
        if result.replay.node_name is not None:
            print(f"Replayed Node: {result.replay.node_name}", file=stream)
        if result.replay.artifact_target is not None:
            print(
                f"Artifact Target: {result.replay.artifact_target.kind.value} {result.replay.artifact_target.path}",
                file=stream,
            )
        if result.replay.signal_kind is not None and result.replay.signal_value is not None:
            print(f"Signal: {result.replay.signal_kind.value}={result.replay.signal_value}", file=stream)
    if result.dispatch is not None:
        print(f"Dispatch: {result.dispatch.status.value}", file=stream)
        print(f"Executor: {result.dispatch.target.value}", file=stream)
        print(f"Mode: {result.dispatch.mode.value}", file=stream)
        if result.dispatch.payload is not None:
            print(f"Handoff: {result.dispatch.payload.title}", file=stream)
    if result.writeback is not None:
        print(f"Write-back: {result.writeback.destination.value}", file=stream)
        print(
            "Eligible: " + ("yes" if result.writeback.should_write_back else "no"),
            file=stream,
        )
        if result.writeback.candidate_kind is not None:
            print(f"Candidate Kind: {result.writeback.candidate_kind.value}", file=stream)
    print(f"State: {result.to_state.value}", file=stream)
    if result.output_path is not None:
        print(f"Spec: {adapter.display_path(result.output_path)}", file=stream)
    if result.log_path is not None:
        print(f"Run log: {adapter.display_path(result.log_path)}", file=stream)
    if result.validation is not None:
        for reason in result.validation.reasons:
            printed_reasons.add((reason.code, reason.message, reason.field))
            print(f"- {reason.code}: {reason.message}", file=stream)
    if result.followup is not None:
        for reason in result.followup.reasons:
            printed_reasons.add((reason.code, reason.message, reason.field))
            print(f"- {reason.code}: {reason.message}", file=stream)
    if result.replay is not None:
        for reason in result.replay.reasons:
            printed_reasons.add((reason.code, reason.message, reason.field))
            print(f"- {reason.code}: {reason.message}", file=stream)
    if result.dispatch is not None:
        for reason in result.dispatch.reasons:
            printed_reasons.add((reason.code, reason.message, reason.field))
            print(f"- {reason.code}: {reason.message}", file=stream)
    if result.writeback is not None:
        for reason in result.writeback.reasons:
            printed_reasons.add((reason.code, reason.message, reason.field))
            print(f"- {reason.code}: {reason.message}", file=stream)
    for issue in result.issues:
        identity = (issue.code, issue.message, issue.field)
        if identity in printed_reasons:
            continue
        print(f"- {issue.code}: {issue.message}", file=stream)
    if result.success and dry_run and result.rendered_output is not None:
        print("", file=stream)
        print(result.rendered_output.rstrip(), file=stream)


def _parse_writeback_kind(value: str | None) -> WritebackCandidateKind | None:
    if value is None:
        return None
    return WritebackCandidateKind(value)


def _parse_validation_status(value: str | None) -> ValidationEvidenceStatus | None:
    if value is None:
        return None
    return ValidationEvidenceStatus(value)


def _parse_readiness_status(value: str | None) -> ReadinessStatus | None:
    if value is None:
        return None
    return ReadinessStatus(value)


def _parse_aggregate_validation_status(value: str | None) -> ValidationStatus | None:
    if value is None:
        return None
    return ValidationStatus(value)


def _parse_writeback_destination(value: str | None) -> WritebackDestination | None:
    if value is None:
        return None
    return WritebackDestination(value)


def _parse_closeout_hint(value: str | None) -> CloseoutHint | None:
    if value is None:
        return None
    return CloseoutHint(value)


def _parse_executor_target(value: str | None) -> ExecutorTarget:
    return ExecutorTarget(value or ExecutorTarget.SHELL.value)


def _parse_dispatch_mode(value: str | None) -> DispatchMode:
    return DispatchMode(value or DispatchMode.PREVIEW.value)
