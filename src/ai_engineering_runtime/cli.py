from __future__ import annotations

from datetime import date
import argparse
from pathlib import Path
import sys
from typing import Sequence

from ai_engineering_runtime.adapters import FileSystemAdapter
from ai_engineering_runtime.engine import RunResult, RuntimeEngine
from ai_engineering_runtime.nodes.plan_to_spec import PlanToSpecNode, PlanToSpecRequest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ae-runtime",
        description="CLI-first workflow runtime for SOP artifacts.",
    )
    subparsers = parser.add_subparsers(dest="command")

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

    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    repo_root: Path | None = None,
    today: date | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command != "plan-to-spec":
        parser.print_help()
        return 1

    adapter = FileSystemAdapter(repo_root or Path.cwd())
    engine = RuntimeEngine(adapter)
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
    status_line = "plan-to-spec completed" if result.success else "plan-to-spec failed"
    print(status_line, file=stream)
    print(f"Plan: {adapter.display_path(result.plan_path)}", file=stream)
    print(f"State: {result.to_state.value}", file=stream)
    if result.output_path is not None:
        print(f"Spec: {adapter.display_path(result.output_path)}", file=stream)
    if result.log_path is not None:
        print(f"Run log: {adapter.display_path(result.log_path)}", file=stream)
    for issue in result.issues:
        print(f"- {issue.message}", file=stream)
    if result.success and dry_run and result.rendered_output is not None:
        print("", file=stream)
        print(result.rendered_output.rstrip(), file=stream)
