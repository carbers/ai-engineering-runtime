from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import date
import io
from pathlib import Path
import shutil
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = ROOT / "tests"
RUN_LOG_FIXTURES = ROOT / "tests" / "fixtures" / "run_logs"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))
from support import activate_repo_tempdir  # noqa: E402

activate_repo_tempdir(tempfile)
from ai_engineering_runtime.adapters import FileSystemAdapter  # noqa: E402
from ai_engineering_runtime.cli import main  # noqa: E402
from ai_engineering_runtime.engine import RuntimeEngine  # noqa: E402
from ai_engineering_runtime.nodes.followup_suggester import (  # noqa: E402
    FollowupSuggesterNode,
    FollowupSuggesterRequest,
)
from ai_engineering_runtime.nodes.validation_collect import (  # noqa: E402
    ValidationCollectNode,
    ValidationCollectRequest,
)
from ai_engineering_runtime.nodes.writeback_classifier import (  # noqa: E402
    WritebackClassifierNode,
    WritebackClassifierRequest,
)
from ai_engineering_runtime.state import (  # noqa: E402
    CloseoutHint,
    ValidationEvidenceStatus,
)


VALID_ROADMAP = """
# Runtime Roadmap

## Problem
The repo still needs a runtime identity.

## Goal
Land the first runtime slice.

## Non-goals
- dashboards

## Constraints
- stay lightweight

## Proposed Approach
Use a CLI.

## Risks
- parser drift

## Phase Split
- phase 0

## First Slice
Compile this roadmap into a task spec.

### Spec Title
Runtime Plan To Spec Foundation

### In Scope
- align runtime docs
- implement the node

### Out of Scope
- executor dispatch

### Affected Area
- `src/ai_engineering_runtime/*`

### Task Checklist
- align the docs
- implement the node

### Done When
The CLI turns this roadmap into a draft spec.

### Black-box Checks
- the node writes the draft spec

### White-box Needed
Yes

### White-box Trigger
The parser and transition logic are stateful.

### Internal Logic To Protect
- section parsing

### Write-back Needed
No

### Risks / Notes
- keep it small
"""


def _write_repo_file(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


def _copy_run_log_fixture(root: Path, fixture_name: str) -> None:
    destination = root / ".runtime" / "runs" / fixture_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(RUN_LOG_FIXTURES / fixture_name, destination)


class CliTests(unittest.TestCase):
    def test_plan_readiness_check_reports_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "docs/runtime/roadmap.md", VALID_ROADMAP)

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    ["plan-readiness-check", "--plan", "docs/runtime/roadmap.md"],
                    repo_root=root,
                    today=date(2026, 3, 22),
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("plan-readiness-check completed", stdout.getvalue())
            self.assertIn("Readiness: ready", stdout.getvalue())
            self.assertIn("State: spec-ready", stdout.getvalue())

    def test_plan_readiness_check_reports_needs_clarification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            clarification_roadmap = VALID_ROADMAP.replace(
                "### Done When\nThe CLI turns this roadmap into a draft spec.\n\n",
                "### Done When\nTBD after the acceptance criteria are clarified.\n\n",
            )
            _write_repo_file(root, "docs/runtime/roadmap.md", clarification_roadmap)

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    ["plan-readiness-check", "--plan", "docs/runtime/roadmap.md"],
                    repo_root=root,
                    today=date(2026, 3, 22),
                )

            self.assertEqual(exit_code, 1)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("plan-readiness-check failed", stderr.getvalue())
            self.assertIn("Readiness: needs_clarification", stderr.getvalue())
            self.assertIn("placeholder-first-slice-field", stderr.getvalue())

    def test_task_spec_readiness_check_reports_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_spec = """
            # Sample Task Spec

            ## Metadata

            ### Source Plan / Request
            `docs/runtime/roadmap.md`

            ### Status
            `draft`

            ### Related Specs
            None.

            ## Goal
            Implement a narrow runtime slice.

            ## In Scope
            - add a readiness checker

            ## Out of Scope
            - executor dispatch

            ## Affected Area
            - `src/ai_engineering_runtime/*`

            ## Task Checklist
            - [ ] add the checker

            ## Done When
            The checker reports task-spec readiness.

            ## Validation

            ### Black-box Checks
            - checker returns ready

            ### White-box Needed
            Yes

            ### White-box Trigger
            The parser is contract-sensitive.

            ### Internal Logic To Protect
            - status mapping

            ## Write-back Needed
            No

            ## Risks / Notes
            - keep it small
            """
            _write_repo_file(root, "docs/specs/20260322-999-sample.md", task_spec)

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    ["task-spec-readiness-check", "--spec", "docs/specs/20260322-999-sample.md"],
                    repo_root=root,
                    today=date(2026, 3, 22),
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("task-spec-readiness-check completed", stdout.getvalue())
            self.assertIn("Spec: docs/specs/20260322-999-sample.md", stdout.getvalue())
            self.assertIn("Readiness: ready", stdout.getvalue())

    def test_validation_collect_reports_passed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_spec = """
            # Validation Sample

            ## Metadata

            ### Source Plan / Request
            `docs/runtime/roadmap.md`

            ### Status
            `done`

            ### Related Specs
            None.

            ## Goal
            Close out a runtime slice.

            ## In Scope
            - collect validation

            ## Out of Scope
            - follow-up generation

            ## Affected Area
            - `src/ai_engineering_runtime/*`

            ## Task Checklist
            - [x] collect evidence

            ## Done When
            Validation is aggregated cleanly.

            ## Validation

            ### Black-box Checks
            - validation returns passed

            ### White-box Needed
            Yes

            ### White-box Trigger
            The collector is branch-sensitive.

            ### Internal Logic To Protect
            - status derivation

            ## Write-back Needed
            No

            ## Risks / Notes
            - keep it small
            """
            _write_repo_file(root, "docs/specs/20260322-999-validation.md", task_spec)

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    [
                        "validation-collect",
                        "--spec",
                        "docs/specs/20260322-999-validation.md",
                        "--command-status",
                        "passed",
                        "--black-box-status",
                        "passed",
                        "--white-box-status",
                        "passed",
                    ],
                    repo_root=root,
                    today=date(2026, 3, 22),
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("validation-collect completed", stdout.getvalue())
            self.assertIn("Validation: passed", stdout.getvalue())
            self.assertIn("State: writeback-review", stdout.getvalue())

    def test_followup_suggester_reports_fix_validation_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    [
                        "followup-suggester",
                        "--validation-status",
                        "failed",
                    ],
                    repo_root=root,
                    today=date(2026, 3, 22),
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("followup-suggester completed", stdout.getvalue())
            self.assertIn("Follow-up: fix_validation_failure", stdout.getvalue())
            self.assertIn("Why: Prioritize a fix-oriented task before moving on.", stdout.getvalue())

    def test_executor_dispatch_reports_preview_for_ready_task_spec(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_spec = """
            # Dispatch Sample

            ## Metadata

            ### Source Plan / Request
            `docs/runtime/roadmap.md`

            ### Status
            `in-progress`

            ### Related Specs
            None.

            ## Goal
            Hand off a narrow task safely.

            ## In Scope
            - prepare a handoff payload

            ## Out of Scope
            - deep executor integration

            ## Affected Area
            - `src/ai_engineering_runtime/*`

            ## Task Checklist
            - [ ] prepare the handoff

            ## Done When
            The control plane can preview a handoff.

            ## Validation

            ### Black-box Checks
            - ready spec can dispatch

            ### White-box Needed
            Yes

            ### White-box Trigger
            The handoff gate is contract-sensitive.

            ### Internal Logic To Protect
            - readiness gating

            ## Write-back Needed
            No

            ## Risks / Notes
            - keep it small
            """
            _write_repo_file(root, "docs/specs/20260322-999-dispatch.md", task_spec)

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    [
                        "executor-dispatch",
                        "--spec",
                        "docs/specs/20260322-999-dispatch.md",
                        "--mode",
                        "preview",
                    ],
                    repo_root=root,
                    today=date(2026, 3, 22),
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("executor-dispatch completed", stdout.getvalue())
            self.assertIn("Dispatch: previewed", stdout.getvalue())
            self.assertIn("Executor: shell", stdout.getvalue())
            self.assertIn("Mode: preview", stdout.getvalue())

    def test_executor_dispatch_reports_codex_execution_for_ready_task_spec(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_spec = """
            # Codex Dispatch Sample

            ## Metadata

            ### Source Plan / Request
            `docs/runtime/roadmap.md`

            ### Status
            `in-progress`

            ### Related Specs
            None.

            ## Goal
            Hand off a narrow executor task safely.

            ## In Scope
            - prepare a codex handoff

            ## Out of Scope
            - live backend wiring

            ## Affected Area
            - `src/ai_engineering_runtime/nodes/executor_dispatch.py`

            ## Task Checklist
            - [ ] prepare the codex handoff

            ## Done When
            The control plane can submit a normalized executor task.

            ## Validation

            ### Black-box Checks
            - ready spec can dispatch

            ### White-box Needed
            Yes

            ### White-box Trigger
            Executor handoff and normalization are contract-sensitive.

            ### Internal Logic To Protect
            - adapter selection
            - execution result normalization

            ## Executor Requirements

            ### can_edit_files
            Yes

            ### can_open_repo_context
            Yes

            ## Write-back Needed
            No

            ## Risks / Notes
            - keep it small
            """
            _write_repo_file(root, "docs/specs/20260322-999-codex-dispatch.md", task_spec)

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    [
                        "executor-dispatch",
                        "--spec",
                        "docs/specs/20260322-999-codex-dispatch.md",
                        "--executor",
                        "codex",
                        "--mode",
                        "submit",
                    ],
                    repo_root=root,
                    today=date(2026, 3, 27),
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("Dispatch: dispatched", stdout.getvalue())
            self.assertIn("Executor: codex", stdout.getvalue())
            self.assertIn("Mode: submit", stdout.getvalue())
            self.assertIn("Execution: succeeded", stdout.getvalue())
            self.assertIn("Execution Summary:", stdout.getvalue())

    def test_executor_run_lifecycle_reports_polled_codex_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_spec = """
            # Codex Dispatch Sample

            ## Metadata

            ### Source Plan / Request
            `docs/runtime/roadmap.md`

            ### Status
            `in-progress`

            ### Related Specs
            None.

            ## Goal
            Hand off a narrow executor task safely.

            ## In Scope
            - prepare a codex handoff

            ## Out of Scope
            - live backend wiring

            ## Affected Area
            - `src/ai_engineering_runtime/nodes/executor_dispatch.py`

            ## Task Checklist
            - [ ] prepare the codex handoff

            ## Done When
            The control plane can submit a normalized executor task.

            ## Validation

            ### Black-box Checks
            - ready spec can dispatch

            ### White-box Needed
            Yes

            ### White-box Trigger
            Executor handoff and normalization are contract-sensitive.

            ### Internal Logic To Protect
            - adapter selection
            - execution result normalization

            ## Executor Requirements

            ### can_edit_files
            Yes

            ### can_open_repo_context
            Yes

            ## Write-back Needed
            No

            ## Risks / Notes
            - keep it small
            """
            _write_repo_file(root, "docs/specs/20260322-999-codex-dispatch.md", task_spec)

            dispatch_stdout = io.StringIO()
            dispatch_stderr = io.StringIO()
            with redirect_stdout(dispatch_stdout), redirect_stderr(dispatch_stderr):
                dispatch_exit = main(
                    [
                        "executor-dispatch",
                        "--spec",
                        "docs/specs/20260322-999-codex-dispatch.md",
                        "--executor",
                        "codex",
                        "--mode",
                        "submit",
                    ],
                    repo_root=root,
                    today=date(2026, 3, 27),
                )

            self.assertEqual(dispatch_exit, 0)
            dispatch_logs = sorted((root / ".runtime" / "runs").glob("*-executor-dispatch.json"))
            self.assertTrue(dispatch_logs)
            source_run_id = dispatch_logs[-1].stem

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    [
                        "executor-run-lifecycle",
                        "--run-id",
                        source_run_id,
                        "--action",
                        "poll",
                    ],
                    repo_root=root,
                    today=date(2026, 3, 27),
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("executor-run-lifecycle completed", stdout.getvalue())
            self.assertIn("Lifecycle Action: poll", stdout.getvalue())
            self.assertIn(f"Source Run: {source_run_id}", stdout.getvalue())
            self.assertIn("Execution: succeeded", stdout.getvalue())
            self.assertIn("State: validating", stdout.getvalue())

    def test_main_reports_success_and_writes_spec(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "docs/runtime/roadmap.md", VALID_ROADMAP)

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    ["plan-to-spec", "--plan", "docs/runtime/roadmap.md"],
                    repo_root=root,
                    today=date(2026, 3, 22),
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("plan-to-spec completed", stdout.getvalue())
            self.assertIn("Readiness: ready", stdout.getvalue())
            self.assertIn("State: spec-ready", stdout.getvalue())
            self.assertIn(
                "Spec: docs/specs/20260322-001-runtime-plan-to-spec-foundation.md",
                stdout.getvalue(),
            )

    def test_main_dry_run_prints_rendered_spec(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "docs/runtime/roadmap.md", VALID_ROADMAP)

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    ["plan-to-spec", "--plan", "docs/runtime/roadmap.md", "--dry-run"],
                    repo_root=root,
                    today=date(2026, 3, 22),
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("# Runtime Plan To Spec Foundation", stdout.getvalue())
            self.assertFalse(
                (root / "docs" / "specs" / "20260322-001-runtime-plan-to-spec-foundation.md").exists()
            )

    def test_main_reports_errors_to_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            invalid_roadmap = VALID_ROADMAP.replace("### Done When\nThe CLI turns this roadmap into a draft spec.\n\n", "")
            _write_repo_file(root, "docs/runtime/roadmap.md", invalid_roadmap)

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    ["plan-to-spec", "--plan", "docs/runtime/roadmap.md"],
                    repo_root=root,
                    today=date(2026, 3, 22),
                )

            self.assertEqual(exit_code, 1)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("plan-to-spec failed", stderr.getvalue())
            self.assertIn("Readiness: blocked", stderr.getvalue())
            self.assertIn("Missing required First Slice field: Done When", stderr.getvalue())

    def test_main_reports_runtime_io_errors_to_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "docs/runtime/roadmap.md", VALID_ROADMAP)

            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                patch("ai_engineering_runtime.cli.RuntimeEngine.run", side_effect=PermissionError("Access denied")),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                exit_code = main(
                    ["plan-readiness-check", "--plan", "docs/runtime/roadmap.md"],
                    repo_root=root,
                    today=date(2026, 3, 22),
                )

            self.assertEqual(exit_code, 1)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("plan-readiness-check failed", stderr.getvalue())
            self.assertIn("runtime-io-error", stderr.getvalue())

    def test_writeback_classifier_reports_destination_and_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    [
                        "writeback-classifier",
                        "--text",
                        "This repeatable workflow checklist should be reused later.",
                        "--kind",
                        "workflow_pattern",
                    ],
                    repo_root=root,
                    today=date(2026, 3, 22),
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("writeback-classifier completed", stdout.getvalue())
            self.assertIn("Write-back: skills", stdout.getvalue())
            self.assertIn("Eligible: yes", stdout.getvalue())
            self.assertIn("reusable-workflow-pattern", stdout.getvalue())

    def test_result_log_replay_reports_replayable_validation_signal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _copy_run_log_fixture(root, "20260322T191755447854-validation-collect.json")

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    [
                        "result-log-replay",
                        "--log",
                        ".runtime/runs/20260322T191755447854-validation-collect.json",
                    ],
                    repo_root=root,
                    today=date(2026, 3, 22),
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("result-log-replay completed", stdout.getvalue())
            self.assertIn("Replay: replayable", stdout.getvalue())
            self.assertIn("Replayed Node: validation-collect", stdout.getvalue())
            self.assertIn("Signal: validation=passed", stdout.getvalue())

    def test_result_log_replay_reports_rejected_malformed_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _copy_run_log_fixture(root, "20260322T193000000000-malformed.json")

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    [
                        "result-log-replay",
                        "--log",
                        ".runtime/runs/20260322T193000000000-malformed.json",
                    ],
                    repo_root=root,
                    today=date(2026, 3, 22),
                )

            self.assertEqual(exit_code, 1)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("result-log-replay failed", stderr.getvalue())
            self.assertIn("Replay: rejected", stderr.getvalue())
            self.assertIn("malformed-run-log-json", stderr.getvalue())

    def test_run_history_select_reports_selected_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _copy_run_log_fixture(root, "20260322T191727074753-validation-collect.json")
            _copy_run_log_fixture(root, "20260322T191755447854-validation-collect.json")

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    [
                        "run-history-select",
                        "--spec",
                        "docs/specs/20260322-005-validation-collect-foundation.md",
                        "--node",
                        "validation-collect",
                        "--limit",
                        "2",
                    ],
                    repo_root=root,
                    today=date(2026, 3, 22),
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("run-history-select completed", stdout.getvalue())
            self.assertIn("History: selected", stdout.getvalue())
            self.assertIn("Matches: 2", stdout.getvalue())
            self.assertIn("2026-03-22T19:17:55.447854", stdout.getvalue())

    def test_run_summary_reports_latest_human_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _copy_run_log_fixture(root, "20260322T191727074753-validation-collect.json")
            _copy_run_log_fixture(root, "20260322T191755447854-validation-collect.json")

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    [
                        "run-summary",
                        "--latest",
                        "--node",
                        "validation-collect",
                    ],
                    repo_root=root,
                    today=date(2026, 3, 22),
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("run-summary completed", stdout.getvalue())
            self.assertIn("Summary Node: validation-collect", stdout.getvalue())
            self.assertIn("Terminal: review", stdout.getvalue())
            self.assertIn("Summary Signal: validation=passed", stdout.getvalue())
            self.assertIn("History Matches: 1", stdout.getvalue())

    def test_run_summary_reports_json_view(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _copy_run_log_fixture(root, "20260322T180645808422-plan-to-spec.json")

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    [
                        "run-summary",
                        "--log",
                        ".runtime/runs/20260322T180645808422-plan-to-spec.json",
                        "--json",
                    ],
                    repo_root=root,
                    today=date(2026, 3, 22),
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("run-summary completed", stdout.getvalue())
            self.assertIn("\"run_id\": \"20260322T180645808422-plan-to-spec\"", stdout.getvalue())
            self.assertIn("\"status\": \"ready\"", stdout.getvalue())

    def test_validation_rollup_reports_latest_rollup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)
            engine.run(
                ValidationCollectNode(
                    ValidationCollectRequest(
                        command_status=ValidationEvidenceStatus.FAILED,
                        black_box_status=ValidationEvidenceStatus.PASSED,
                    )
                )
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    [
                        "validation-rollup",
                        "--latest",
                    ],
                    repo_root=root,
                    today=date(2026, 3, 23),
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("validation-rollup completed", stdout.getvalue())
            self.assertIn("Validation Rollup: blocking", stdout.getvalue())
            self.assertIn("Findings: 1", stdout.getvalue())

    def test_writeback_package_reports_materialized_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)
            result = engine.run(
                WritebackClassifierNode(
                    WritebackClassifierRequest(
                        text="Project-wide context should be written back later.",
                    )
                )
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    [
                        "writeback-package",
                        "--run-id",
                        result.log_path.stem,
                    ],
                    repo_root=root,
                    today=date(2026, 3, 23),
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("writeback-package completed", stdout.getvalue())
            self.assertIn("Write-back Package: facts", stdout.getvalue())
            self.assertIn("Actionable: yes", stdout.getvalue())

    def test_followup_package_reports_materialized_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)
            result = engine.run(
                FollowupSuggesterNode(
                    FollowupSuggesterRequest(closeout_hint=CloseoutHint.COMPLETE)
                )
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    [
                        "followup-package",
                        "--run-id",
                        result.log_path.stem,
                    ],
                    repo_root=root,
                    today=date(2026, 3, 23),
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("followup-package completed", stdout.getvalue())
            self.assertIn("Follow-up Package: no_followup_needed", stdout.getvalue())
            self.assertIn("Actionable: no", stdout.getvalue())

    def test_node_gate_reports_gate_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)
            result = engine.run(
                ValidationCollectNode(
                    ValidationCollectRequest(
                        command_status=ValidationEvidenceStatus.PASSED,
                        black_box_status=ValidationEvidenceStatus.PASSED,
                    )
                )
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    [
                        "node-gate",
                        "--node",
                        "validation-rollup",
                        "--run-id",
                        result.log_path.stem,
                    ],
                    repo_root=root,
                    today=date(2026, 3, 23),
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("node-gate completed", stdout.getvalue())
            self.assertIn("Gate Node: validation-rollup", stdout.getvalue())
            self.assertIn("Gate: eligible", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()

