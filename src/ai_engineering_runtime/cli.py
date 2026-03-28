from __future__ import annotations

from datetime import date
import argparse
from pathlib import Path
import sys
from typing import Sequence

from ai_engineering_runtime.adapters import FileSystemAdapter
from ai_engineering_runtime.engine import RunResult, RuntimeEngine
from ai_engineering_runtime.handoffs import IntakeSourceKind, compile_handoff, load_handoff, validate_handoff
from ai_engineering_runtime.nodes.plan_readiness_check import (
    PlanReadinessCheckNode,
    PlanReadinessCheckRequest,
)
from ai_engineering_runtime.nodes.plan_to_spec import PlanToSpecNode, PlanToSpecRequest
from ai_engineering_runtime.nodes.result_log_replay import (
    ResultLogReplayNode,
    ResultLogReplayRequest,
)
from ai_engineering_runtime.nodes.node_gate import NodeGateNode, NodeGateRequest
from ai_engineering_runtime.nodes.run_history_select import (
    RunHistorySelectNode,
    RunHistorySelectRequest,
)
from ai_engineering_runtime.nodes.run_summary import RunSummaryNode, RunSummaryRequest
from ai_engineering_runtime.nodes.validation_rollup import (
    ValidationRollupNode,
    ValidationRollupRequest,
)
from ai_engineering_runtime.nodes.writeback_package import (
    WritebackPackageNode,
    WritebackPackageRequest,
)
from ai_engineering_runtime.nodes.followup_package import (
    FollowupPackageNode,
    FollowupPackageRequest,
)
from ai_engineering_runtime.nodes.executor_dispatch import (
    ExecutorDispatchNode,
    ExecutorDispatchRequest,
)
from ai_engineering_runtime.nodes.executor_run_lifecycle import (
    ExecutorRunLifecycleNode,
    ExecutorRunLifecycleRequest,
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
from ai_engineering_runtime.product_runtime import (
    close_run,
    inspect_run,
    preview_run_from_handoff,
    render_state_summary,
    resume_run,
    retry_run,
    run_from_handoff,
)
from ai_engineering_runtime.run_logs import ArtifactTargetKind, ReplaySignalKind
from ai_engineering_runtime.state import (
    CloseoutHint,
    DispatchMode,
    ExecutorLifecycleAction,
    ExecutorTarget,
    ReadinessStatus,
    RuntimeReason,
    ValidationEvidenceStatus,
    ValidationStatus,
    WritebackCandidateKind,
    WritebackDestination,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ae",
        description="AI workflow runtime control plane with product-oriented intake and orchestration paths.",
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser(
        "run",
        help="Run the product control plane from chat, prompt, or handoff input.",
    )
    run_source = run_parser.add_mutually_exclusive_group(required=True)
    run_source.add_argument("--from-chat", help="Path to a chat-style plain text input file.")
    run_source.add_argument("--from-prompt", help="Path to a prompt-style plain text input file.")
    run_source.add_argument("--from-handoff", help="Path to a normalized handoff JSON file.")
    run_parser.add_argument("--workflow", help="Optional workflow override.")
    run_parser.add_argument(
        "--preview-handoff",
        action="store_true",
        help="Compile and preview the handoff and run-state interpretation without creating or mutating a product run.",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the compiled handoff and next legal actions without dispatching or persisting the run.",
    )

    compile_handoff_parser = subparsers.add_parser(
        "compile-handoff",
        help="Compile chat, prompt, or handoff input into a normalized handoff document.",
    )
    compile_source = compile_handoff_parser.add_mutually_exclusive_group(required=True)
    compile_source.add_argument("--from-chat", help="Path to a chat-style plain text input file.")
    compile_source.add_argument("--from-prompt", help="Path to a prompt-style plain text input file.")
    compile_source.add_argument("--from-handoff", help="Path to an existing handoff JSON file.")
    compile_handoff_parser.add_argument("--workflow", help="Optional workflow hint or override.")
    compile_handoff_parser.add_argument("--out", help="Optional output path for the compiled handoff JSON.")
    compile_handoff_parser.add_argument(
        "--preview",
        action="store_true",
        help="Render a detailed compile preview with defaults, warnings, and candidate actions.",
    )

    validate_handoff_parser = subparsers.add_parser(
        "validate-handoff",
        help="Validate one normalized handoff JSON document.",
    )
    validate_handoff_parser.add_argument("--handoff", required=True, help="Path to a handoff JSON file.")

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect one product run and show current gates, lanes, and next-step decisions.",
    )
    inspect_parser.add_argument("run_id", help="Product run id.")

    resume_parser = subparsers.add_parser(
        "resume",
        help="Re-evaluate one product run and refresh its next-step decision.",
    )
    resume_parser.add_argument("run_id", help="Product run id.")

    retry_parser = subparsers.add_parser(
        "retry",
        help="Retry one product run node using retry and fallback policy.",
    )
    retry_parser.add_argument("run_id", help="Product run id.")
    retry_parser.add_argument("--node", required=True, help="Workflow node id to retry.")

    close_parser = subparsers.add_parser(
        "close",
        help="Attempt closeout for one product run.",
    )
    close_parser.add_argument("run_id", help="Product run id.")

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
        help="Prepare or dispatch a ready task spec through one executor adapter contract.",
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
        help="Dispatch mode: preview, shell echo proof, or adapter submit.",
    )

    executor_run_lifecycle = subparsers.add_parser(
        "executor-run-lifecycle",
        help="Revisit one previously dispatched executor run through poll or resume lifecycle actions.",
    )
    lifecycle_target = executor_run_lifecycle.add_mutually_exclusive_group(required=True)
    lifecycle_target.add_argument("--log", help="Explicit path to a prior executor run log JSON file.")
    lifecycle_target.add_argument("--run-id", help="Run id in <timestamp-node> form.")
    lifecycle_target.add_argument(
        "--latest",
        action="store_true",
        help="Select the latest matching run log under .runtime/runs/.",
    )
    executor_run_lifecycle.add_argument(
        "--node",
        help="Optional node-name filter when selecting with --latest.",
    )
    executor_run_lifecycle.add_argument(
        "--action",
        choices=[action.value for action in ExecutorLifecycleAction],
        default=ExecutorLifecycleAction.POLL.value,
        help="Lifecycle action to apply to the previously submitted executor run.",
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

    run_history_select = subparsers.add_parser(
        "run-history-select",
        help="Select replayable prior runs relevant to one explicit artifact target.",
    )
    history_target = run_history_select.add_mutually_exclusive_group(required=True)
    history_target.add_argument("--spec", help="Select history for one task spec path.")
    history_target.add_argument("--plan", help="Select history for one plan path.")
    history_target.add_argument("--output", help="Select history for one output path.")
    run_history_select.add_argument(
        "--node",
        help="Optional replayed node-name filter.",
    )
    run_history_select.add_argument(
        "--signal-kind",
        choices=[kind.value for kind in ReplaySignalKind],
        help="Optional replay signal kind filter.",
    )
    run_history_select.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of newest matches to return.",
    )

    run_summary = subparsers.add_parser(
        "run-summary",
        help="Load or materialize one stable run summary from current or historical run logs.",
    )
    summary_target = run_summary.add_mutually_exclusive_group(required=True)
    summary_target.add_argument("--log", help="Explicit path to a run log JSON file.")
    summary_target.add_argument("--run-id", help="Run id in <timestamp-node> form.")
    summary_target.add_argument(
        "--latest",
        action="store_true",
        help="Select the latest matching run log under .runtime/runs/.",
    )
    run_summary.add_argument(
        "--node",
        help="Optional node-name filter when selecting with --latest.",
    )
    run_summary.add_argument(
        "--json",
        action="store_true",
        help="Emit the materialized run summary as JSON after the status lines.",
    )

    node_gate = subparsers.add_parser(
        "node-gate",
        help="Evaluate whether one declared node is eligible, blocked, skipped, not-applicable, or unknown for one run context.",
    )
    node_gate.add_argument(
        "--node",
        required=True,
        help="Declared node name to evaluate.",
    )
    gate_target = node_gate.add_mutually_exclusive_group(required=True)
    gate_target.add_argument("--log", help="Explicit path to a source run log JSON file.")
    gate_target.add_argument("--run-id", help="Run id in <timestamp-node> form.")
    gate_target.add_argument(
        "--latest",
        action="store_true",
        help="Select the latest matching run log under .runtime/runs/.",
    )
    node_gate.add_argument(
        "--summary-node",
        help="Optional node-name filter when selecting with --latest.",
    )
    node_gate.add_argument(
        "--json",
        action="store_true",
        help="Emit the gate result as JSON after the status lines.",
    )

    validation_rollup = subparsers.add_parser(
        "validation-rollup",
        help="Load or materialize one validation rollup artifact from a validation run.",
    )
    rollup_target = validation_rollup.add_mutually_exclusive_group(required=True)
    rollup_target.add_argument("--log", help="Explicit path to a validation run log JSON file.")
    rollup_target.add_argument("--run-id", help="Run id in <timestamp-node> form.")
    rollup_target.add_argument(
        "--latest",
        action="store_true",
        help="Select the latest validation run log under .runtime/runs/.",
    )
    validation_rollup.add_argument(
        "--node",
        help="Optional node-name filter when selecting with --latest.",
    )
    validation_rollup.add_argument(
        "--json",
        action="store_true",
        help="Emit the validation rollup as JSON after the status lines.",
    )

    writeback_package = subparsers.add_parser(
        "writeback-package",
        help="Load or materialize one write-back package artifact from a classifier run.",
    )
    writeback_target = writeback_package.add_mutually_exclusive_group(required=True)
    writeback_target.add_argument("--log", help="Explicit path to a write-back classifier run log JSON file.")
    writeback_target.add_argument("--run-id", help="Run id in <timestamp-node> form.")
    writeback_target.add_argument(
        "--latest",
        action="store_true",
        help="Select the latest write-back classifier run log under .runtime/runs/.",
    )
    writeback_package.add_argument(
        "--node",
        help="Optional node-name filter when selecting with --latest.",
    )
    writeback_package.add_argument(
        "--json",
        action="store_true",
        help="Emit the write-back package as JSON after the status lines.",
    )

    followup_package = subparsers.add_parser(
        "followup-package",
        help="Load or materialize one follow-up package artifact from a follow-up run.",
    )
    followup_target = followup_package.add_mutually_exclusive_group(required=True)
    followup_target.add_argument("--log", help="Explicit path to a follow-up run log JSON file.")
    followup_target.add_argument("--run-id", help="Run id in <timestamp-node> form.")
    followup_target.add_argument(
        "--latest",
        action="store_true",
        help="Select the latest follow-up run log under .runtime/runs/.",
    )
    followup_package.add_argument(
        "--node",
        help="Optional node-name filter when selecting with --latest.",
    )
    followup_package.add_argument(
        "--json",
        action="store_true",
        help="Emit the follow-up package as JSON after the status lines.",
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
        "run",
        "compile-handoff",
        "validate-handoff",
        "inspect",
        "resume",
        "retry",
        "close",
        "plan-readiness-check",
        "task-spec-readiness-check",
        "validation-collect",
        "followup-suggester",
        "executor-dispatch",
        "executor-run-lifecycle",
        "plan-to-spec",
        "writeback-classifier",
        "result-log-replay",
        "run-history-select",
        "run-summary",
        "node-gate",
        "validation-rollup",
        "writeback-package",
        "followup-package",
    }:
        parser.print_help()
        return 1

    adapter = FileSystemAdapter(repo_root or Path.cwd())
    if args.command in {"run", "compile-handoff", "validate-handoff", "inspect", "resume", "retry", "close"}:
        return _run_product_command(args, adapter)

    engine = RuntimeEngine(adapter)
    dry_run = False
    try:
        if args.command == "plan-readiness-check":
            result = engine.run(
                PlanReadinessCheckNode(
                    PlanReadinessCheckRequest(
                        plan_path=Path(args.plan),
                    )
                )
            )
        elif args.command == "task-spec-readiness-check":
            result = engine.run(
                TaskSpecReadinessCheckNode(
                    TaskSpecReadinessCheckRequest(
                        spec_path=Path(args.spec),
                    )
                )
            )
        elif args.command == "validation-collect":
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
        elif args.command == "followup-suggester":
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
        elif args.command == "executor-dispatch":
            result = engine.run(
                ExecutorDispatchNode(
                    ExecutorDispatchRequest(
                        spec_path=Path(args.spec),
                        target=_parse_executor_target(args.executor),
                        mode=_parse_dispatch_mode(args.mode),
                    )
                )
            )
        elif args.command == "executor-run-lifecycle":
            result = engine.run(
                ExecutorRunLifecycleNode(
                    ExecutorRunLifecycleRequest(
                        log_path=Path(args.log) if args.log else None,
                        run_id=args.run_id,
                        latest=bool(args.latest),
                        node_name=args.node,
                        action=_parse_executor_lifecycle_action(args.action),
                    )
                )
            )
        elif args.command == "writeback-classifier":
            result = engine.run(
                WritebackClassifierNode(
                    WritebackClassifierRequest(
                        text=args.text,
                        candidate_kind=_parse_writeback_kind(args.kind),
                    )
                )
            )
        elif args.command == "result-log-replay":
            result = engine.run(
                ResultLogReplayNode(
                    ResultLogReplayRequest(
                        log_path=Path(args.log) if args.log else None,
                        latest=bool(args.latest),
                        node_name=args.node,
                    )
                )
            )
        elif args.command == "run-history-select":
            artifact_kind, artifact_path = _parse_history_target(args)
            result = engine.run(
                RunHistorySelectNode(
                    RunHistorySelectRequest(
                        artifact_kind=artifact_kind,
                        artifact_path=artifact_path,
                        node_name=args.node,
                        signal_kind=_parse_replay_signal_kind(args.signal_kind),
                        limit=args.limit,
                    )
                )
            )
        elif args.command == "run-summary":
            result = engine.run(
                RunSummaryNode(
                    RunSummaryRequest(
                        log_path=Path(args.log) if args.log else None,
                        run_id=args.run_id,
                        latest=bool(args.latest),
                        node_name=args.node,
                        json_output=bool(args.json),
                    )
                )
            )
        elif args.command == "node-gate":
            result = engine.run(
                NodeGateNode(
                    NodeGateRequest(
                        node_name=args.node,
                        log_path=Path(args.log) if args.log else None,
                        run_id=args.run_id,
                        latest=bool(args.latest),
                        summary_node_name=args.summary_node,
                        json_output=bool(args.json),
                    )
                )
            )
        elif args.command == "validation-rollup":
            result = engine.run(
                ValidationRollupNode(
                    ValidationRollupRequest(
                        log_path=Path(args.log) if args.log else None,
                        run_id=args.run_id,
                        latest=bool(args.latest),
                        node_name=args.node,
                        json_output=bool(args.json),
                    )
                )
            )
        elif args.command == "writeback-package":
            result = engine.run(
                WritebackPackageNode(
                    WritebackPackageRequest(
                        log_path=Path(args.log) if args.log else None,
                        run_id=args.run_id,
                        latest=bool(args.latest),
                        node_name=args.node,
                        json_output=bool(args.json),
                    )
                )
            )
        elif args.command == "followup-package":
            result = engine.run(
                FollowupPackageNode(
                    FollowupPackageRequest(
                        log_path=Path(args.log) if args.log else None,
                        run_id=args.run_id,
                        latest=bool(args.latest),
                        node_name=args.node,
                        json_output=bool(args.json),
                    )
                )
            )
        else:
            dry_run = bool(args.dry_run)
            request = PlanToSpecRequest(
                plan_path=Path(args.plan),
                dry_run=dry_run,
                output_path=Path(args.output) if args.output else None,
                created_on=today or date.today(),
            )
            result = engine.run(PlanToSpecNode(request))
    except OSError as error:
        _emit_runtime_error(args.command or "ae-runtime", error)
        return 1

    _emit_result(result, adapter, dry_run=dry_run)
    return 0 if result.success else 1


def _run_product_command(args: argparse.Namespace, adapter: FileSystemAdapter) -> int:
    if args.command == "compile-handoff":
        handoff, reasons = _resolve_handoff_from_args(adapter, args)
        if handoff is None:
            _emit_runtime_reasons("compile-handoff failed", reasons)
            return 1
        preview_state = None
        if args.preview:
            preview_result = preview_run_from_handoff(adapter, handoff, force_workflow_id=args.workflow)
            preview_state = preview_result.state
        if args.out:
            output_path = adapter.resolve(Path(args.out))
            adapter.write_json(output_path, handoff.to_record())
        _emit_handoff_summary(
            handoff,
            adapter,
            output_path=Path(args.out) if args.out else None,
            preview=args.preview,
            preview_state=preview_state,
        )
        return 0

    if args.command == "validate-handoff":
        handoff_path = adapter.resolve(Path(args.handoff))
        try:
            handoff = load_handoff(handoff_path)
        except (OSError, ValueError) as error:
            _emit_runtime_error("validate-handoff", error)
            return 1
        reasons = validate_handoff(handoff)
        if reasons:
            _emit_runtime_reasons("validate-handoff failed", reasons)
            return 1
        preview_result = preview_run_from_handoff(adapter, handoff)
        _emit_handoff_summary(handoff, adapter, output_path=handoff_path, preview=True, preview_state=preview_result.state)
        return 0

    if args.command == "run":
        handoff, reasons = _resolve_handoff_from_args(adapter, args)
        if handoff is None:
            _emit_runtime_reasons("run failed", reasons)
            return 1
        if args.preview_handoff or args.dry_run:
            preview_result = preview_run_from_handoff(adapter, handoff, force_workflow_id=args.workflow)
            _emit_handoff_summary(handoff, adapter, output_path=None, preview=True, preview_state=preview_result.state)
            if preview_result.state is not None:
                print("")
                print("run preview")
                print(render_state_summary(preview_result.state))
            return 0 if preview_result.success else 1
        result = run_from_handoff(adapter, handoff, force_workflow_id=args.workflow)
        _emit_product_result("run", result)
        return 0 if result.success else 1

    if args.command == "inspect":
        result = inspect_run(adapter, args.run_id)
        _emit_product_result("inspect", result)
        return 0 if result.success else 1

    if args.command == "resume":
        result = resume_run(adapter, args.run_id)
        _emit_product_result("resume", result)
        return 0 if result.success else 1

    if args.command == "retry":
        result = retry_run(adapter, args.run_id, args.node)
        _emit_product_result("retry", result)
        return 0 if result.success else 1

    result = close_run(adapter, args.run_id)
    _emit_product_result("close", result)
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
    if result.history_selection is not None:
        print(f"History: {result.history_selection.status.value}", file=stream)
        if result.history_selection.selection_basis:
            print(f"Basis: {', '.join(result.history_selection.selection_basis)}", file=stream)
        print(f"Matches: {len(result.history_selection.matches)}", file=stream)
        for match in result.history_selection.matches:
            ordered_at = match.ordered_at.isoformat() if match.ordered_at is not None else "unknown"
            signal = (
                f"{match.signal_kind.value}={match.signal_value}"
                if match.signal_kind is not None and match.signal_value is not None
                else "no-signal"
            )
            target = (
                f"{match.artifact_target.kind.value} {match.artifact_target.path}"
                if match.artifact_target is not None
                else "no-target"
            )
            print(f"- {ordered_at} {match.node_name}: {signal} ({target})", file=stream)
    if result.summary is not None and result.metadata.get("summary_output_format") != "json":
        print(f"Summary Run: {result.summary.run_id}", file=stream)
        print(f"Summary Node: {result.summary.node_name}", file=stream)
        print(f"Summary Source Log: {adapter.display_path(result.summary.source_log_path)}", file=stream)
        if result.summary.ordered_at is not None:
            print(f"Summary Ordered At: {result.summary.ordered_at.isoformat()}", file=stream)
        print(f"Terminal: {result.summary.terminal_state.status.value}", file=stream)
        if result.summary.terminal_state.workflow_state is not None:
            print(f"Workflow State: {result.summary.terminal_state.workflow_state}", file=stream)
        if (
            result.summary.terminal_state.signal_kind is not None
            and result.summary.terminal_state.signal_value is not None
        ):
            print(
                "Summary Signal: "
                f"{result.summary.terminal_state.signal_kind}={result.summary.terminal_state.signal_value}",
                file=stream,
            )
        if result.summary.terminal_state.stop_reason_code is not None:
            print(
                "Summary Reason: "
                f"{result.summary.terminal_state.stop_reason_code} {result.summary.terminal_state.stop_reason_message}",
                file=stream,
            )
        if result.summary.history is not None:
            print(f"History Matches: {result.summary.history.match_count}", file=stream)
    if result.gate is not None:
        print(f"Gate Node: {result.gate.node_name}", file=stream)
        print(f"Gate: {result.gate.status.value}", file=stream)
        if result.gate.summary_run_id is not None:
            print(f"Summary Run: {result.gate.summary_run_id}", file=stream)
    if result.validation_rollup is not None and result.metadata.get("summary_output_format") != "json":
        print(f"Validation Rollup: {result.validation_rollup.status.value}", file=stream)
        print(f"Validation Source: {result.validation_rollup.source_log_ref.path}", file=stream)
        print(f"Findings: {len(result.validation_rollup.findings)}", file=stream)
    if result.writeback_package is not None and result.metadata.get("summary_output_format") != "json":
        print(f"Write-back Package: {result.writeback_package.destination.value}", file=stream)
        print("Actionable: " + ("yes" if result.writeback_package.actionable else "no"), file=stream)
        if result.writeback_package.suggested_next_action is not None:
            print(f"Next Action: {result.writeback_package.suggested_next_action}", file=stream)
    if result.followup_package is not None and result.metadata.get("summary_output_format") != "json":
        print(f"Follow-up Package: {result.followup_package.action.value}", file=stream)
        print("Actionable: " + ("yes" if result.followup_package.actionable else "no"), file=stream)
        if result.followup_package.suggested_next_step is not None:
            print(f"Next Step: {result.followup_package.suggested_next_step}", file=stream)
    if result.dispatch is not None:
        print(f"Dispatch: {result.dispatch.status.value}", file=stream)
        print(f"Executor: {result.dispatch.target.value}", file=stream)
        print(f"Mode: {result.dispatch.mode.value}", file=stream)
        if result.dispatch.payload is not None:
            print(f"Handoff: {result.dispatch.payload.title}", file=stream)
    if result.metadata.get("executor_lifecycle_action") is not None:
        print(f"Lifecycle Action: {result.metadata['executor_lifecycle_action']}", file=stream)
        if result.metadata.get("source_run_id") is not None:
            print(f"Source Run: {result.metadata['source_run_id']}", file=stream)
        if result.metadata.get("source_log_path") is not None:
            print(f"Source Log: {result.metadata['source_log_path']}", file=stream)
    if result.execution is not None:
        print(f"Execution: {result.execution.final_status.value}", file=stream)
        print(f"Execution Summary: {result.execution.summary}", file=stream)
        if result.execution.changed_files:
            print(f"Changed Files: {len(result.execution.changed_files)}", file=stream)
        if result.execution.repair_spec_candidate is not None:
            print(f"Repair Seed: {result.execution.repair_spec_candidate.title}", file=stream)
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
    if result.history_selection is not None:
        for reason in result.history_selection.reasons:
            printed_reasons.add((reason.code, reason.message, reason.field))
            print(f"- {reason.code}: {reason.message}", file=stream)
    if result.dispatch is not None:
        for reason in result.dispatch.reasons:
            printed_reasons.add((reason.code, reason.message, reason.field))
            print(f"- {reason.code}: {reason.message}", file=stream)
    if result.execution is not None:
        for finding in result.execution.findings:
            identity = (finding.code, finding.message, finding.field)
            printed_reasons.add(identity)
            print(f"- {finding.severity.value}: {finding.code}: {finding.message}", file=stream)
    if result.writeback is not None:
        for reason in result.writeback.reasons:
            printed_reasons.add((reason.code, reason.message, reason.field))
            print(f"- {reason.code}: {reason.message}", file=stream)
    if result.gate is not None:
        for reason in result.gate.blocking_reasons:
            printed_reasons.add((reason.code, reason.message, reason.field))
            print(f"- {reason.code}: {reason.message}", file=stream)
        for reason in result.gate.advisory_reasons:
            printed_reasons.add((reason.code, reason.message, reason.field))
            print(f"- {reason.code}: {reason.message}", file=stream)
    if result.validation_rollup is not None:
        for finding in result.validation_rollup.findings:
            identity = (finding.code, finding.message, finding.field)
            printed_reasons.add(identity)
            print(f"- {finding.severity.value}: {finding.code}: {finding.message}", file=stream)
    if result.writeback_package is not None:
        for reason in result.writeback_package.reasons:
            printed_reasons.add((reason.code, reason.message, reason.field))
            print(f"- {reason.code}: {reason.message}", file=stream)
    if result.followup_package is not None:
        for reason in result.followup_package.blockers:
            printed_reasons.add((reason.code, reason.message, reason.field))
            print(f"- {reason.code}: {reason.message}", file=stream)
    for issue in result.issues:
        identity = (issue.code, issue.message, issue.field)
        if identity in printed_reasons:
            continue
        print(f"- {issue.code}: {issue.message}", file=stream)
    render_always = result.metadata.get("summary_output_format") == "json"
    if result.success and result.rendered_output is not None and (dry_run or render_always):
        print("", file=stream)
        print(result.rendered_output.rstrip(), file=stream)


def _emit_runtime_error(command_name: str, error: OSError) -> None:
    print(f"{command_name} failed", file=sys.stderr)
    print(f"- runtime-io-error: {_format_os_error(error)}", file=sys.stderr)


def _emit_runtime_reasons(status_line: str, reasons: tuple[RuntimeReason, ...]) -> None:
    print(status_line, file=sys.stderr)
    for reason in reasons:
        print(f"- {reason.code}: {reason.message}", file=sys.stderr)


def _emit_handoff_summary(
    handoff,
    adapter: FileSystemAdapter,
    *,
    output_path: Path | None,
    preview: bool = False,
    preview_state=None,
) -> None:
    print("handoff ready")
    print(f"Workflow: {handoff.workflow_id}")
    print(f"Intake Profile: {handoff.intake_profile.value}")
    print(f"Request: {handoff.request_summary}")
    print(f"Normalized Objective: {handoff.normalized_objective.splitlines()[0]}")
    print(f"Lanes: {len(handoff.lanes)}")
    if handoff.phase_hint is not None:
        print(f"Phase Hint: {handoff.phase_hint}")
    if handoff.lane_hint is not None:
        print(f"Lane Hint: {handoff.lane_hint}")
    if handoff.required_artifacts:
        print("Required Artifacts: " + ", ".join(artifact.name for artifact in handoff.required_artifacts))
    if handoff.defaults_applied:
        print("Defaults Applied: " + "; ".join(handoff.defaults_applied))
    if handoff.warnings:
        print("Warnings: " + "; ".join(handoff.warnings))
    if handoff.constraints:
        print("Constraints: " + "; ".join(handoff.constraints))
    if output_path is not None:
        print(f"Handoff: {adapter.display_path(adapter.resolve(output_path))}")
    if preview and preview_state is not None:
        print("Candidate Actions: " + ", ".join(preview_state.decision.next_legal_actions))
        print(f"Default Action: {preview_state.decision.default_action}")
        if preview_state.decision.why_not_auto_advance is not None:
            print(f"Why Not Auto Advance: {preview_state.decision.why_not_auto_advance}")


def _emit_product_result(command_name: str, result) -> None:
    stream = sys.stdout if result.success else sys.stderr
    if result.state is None:
        _emit_runtime_reasons(f"{command_name} failed", result.reasons)
        return
    print(f"{command_name} completed" if result.success else f"{command_name} failed", file=stream)
    print(render_state_summary(result.state), file=stream)
    print(f"Product Run: {result.state.run_id}", file=stream)
    if command_name in {"retry", "resume", "close"} and result.state.decision.why_not_auto_advance is not None:
        print(f"Action Context: {result.state.decision.why_not_auto_advance}", file=stream)
    for reason in result.reasons:
        print(f"- {reason.code}: {reason.message}", file=stream)


def _resolve_handoff_from_args(
    adapter: FileSystemAdapter,
    args: argparse.Namespace,
):
    try:
        if getattr(args, "from_handoff", None):
            handoff = load_handoff(adapter.resolve(Path(args.from_handoff)))
            reasons = validate_handoff(handoff)
            if reasons:
                return None, reasons
            return handoff, ()
        source_kind, source_path = _parse_intake_source(args)
        resolved_path = adapter.resolve(source_path)
        raw_text = adapter.read_text(resolved_path)
        handoff = compile_handoff(
            text=raw_text,
            source_kind=source_kind,
            repo_root=adapter.repo_root,
            source_path=resolved_path,
            workflow_hint=getattr(args, "workflow", None),
        )
        reasons = validate_handoff(handoff)
        if reasons:
            return None, reasons
        return handoff, ()
    except (OSError, ValueError) as error:
        return None, (RuntimeReason(code="handoff-resolution-failed", message=str(error)),)


def _parse_intake_source(args: argparse.Namespace) -> tuple[IntakeSourceKind, Path]:
    if getattr(args, "from_chat", None):
        return IntakeSourceKind.CHAT, Path(args.from_chat)
    if getattr(args, "from_prompt", None):
        return IntakeSourceKind.PROMPT, Path(args.from_prompt)
    raise ValueError("One intake source is required.")


def _format_os_error(error: OSError) -> str:
    details = str(error).strip() or error.__class__.__name__
    filename = getattr(error, "filename", None)
    if filename is not None and str(filename) not in details:
        return f"{details}: {filename}"
    return details


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


def _parse_executor_lifecycle_action(value: str | None) -> ExecutorLifecycleAction:
    return ExecutorLifecycleAction(value or ExecutorLifecycleAction.POLL.value)


def _parse_replay_signal_kind(value: str | None) -> ReplaySignalKind | None:
    if value is None:
        return None
    return ReplaySignalKind(value)


def _parse_history_target(args: argparse.Namespace) -> tuple[ArtifactTargetKind, Path]:
    if args.spec:
        return ArtifactTargetKind.SPEC, Path(args.spec)
    if args.plan:
        return ArtifactTargetKind.PLAN, Path(args.plan)
    return ArtifactTargetKind.OUTPUT, Path(args.output)
