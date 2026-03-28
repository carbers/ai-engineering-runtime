from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime
import io
import json
from pathlib import Path
import sys
import textwrap
import unittest
from unittest.mock import patch
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = ROOT / "tests"
FIXTURES = TESTS / "fixtures" / "product"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from support import repo_temp_dir  # noqa: E402

from ai_engineering_runtime.cli import main  # noqa: E402


def _write_repo_file(root: Path, relative_path: str, content: str) -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return path


def _copy_fixture(root: Path, fixture_name: str, destination: str) -> Path:
    content = (FIXTURES / fixture_name).read_text(encoding="utf-8")
    return _write_repo_file(root, destination, content)


def _run_cli(root: Path, argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(argv, repo_root=root)
    return exit_code, stdout.getvalue(), stderr.getvalue()


def _extract_run_id(output: str) -> str:
    for line in output.splitlines():
        if line.startswith("Product Run: "):
            return line.split(": ", 1)[1].strip()
    raise AssertionError(f"No Product Run line found in output:\n{output}")


class ProductCliTests(unittest.TestCase):
    def test_compile_handoff_preview_reports_defaults_warnings_and_candidate_actions(self) -> None:
        with repo_temp_dir() as temp_dir:
            root = Path(temp_dir)
            _copy_fixture(root, "short-prompt.txt", "inputs/short-prompt.txt")

            exit_code, stdout, stderr = _run_cli(
                root,
                [
                    "compile-handoff",
                    "--from-prompt",
                    "inputs/short-prompt.txt",
                    "--preview",
                ],
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr, "")
            self.assertIn("handoff ready", stdout)
            self.assertIn("Intake Profile: single_prompt", stdout)
            self.assertIn("Defaults Applied:", stdout)
            self.assertIn("Warnings:", stdout)
            self.assertIn("Candidate Actions:", stdout)
            self.assertIn("Why Not Auto Advance:", stdout)

    def test_compile_handoff_from_prompt_and_validate(self) -> None:
        with repo_temp_dir() as temp_dir:
            root = Path(temp_dir)
            _copy_fixture(root, "review-loop-prompt.txt", "inputs/review-loop-prompt.txt")

            exit_code, stdout, stderr = _run_cli(
                root,
                [
                    "compile-handoff",
                    "--from-prompt",
                    "inputs/review-loop-prompt.txt",
                    "--out",
                    ".runtime/compiled/review-loop.json",
                ],
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr, "")
            self.assertIn("handoff ready", stdout)
            self.assertIn("Workflow: repo-coding-task", stdout)
            self.assertIn("Intake Profile: task_request", stdout)

            compiled_path = root / ".runtime" / "compiled" / "review-loop.json"
            self.assertTrue(compiled_path.exists())

            exit_code, stdout, stderr = _run_cli(
                root,
                ["validate-handoff", "--handoff", ".runtime/compiled/review-loop.json"],
            )
            self.assertEqual(exit_code, 0)
            self.assertNotIn("validate-handoff failed", stderr)
            self.assertIn("handoff ready", stdout)

            payload = json.loads(compiled_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["workflow_id"], "repo-coding-task")

    def test_run_from_chat_holds_with_active_and_parked_lanes(self) -> None:
        with repo_temp_dir() as temp_dir:
            root = Path(temp_dir)
            _copy_fixture(root, "jx3-chat.txt", "inputs/jx3-chat.txt")

            exit_code, stdout, stderr = _run_cli(
                root,
                ["run", "--from-chat", "inputs/jx3-chat.txt"],
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr, "")
            self.assertIn("run completed", stdout)
            self.assertIn("Workflow Phases:", stdout)
            self.assertIn("Workflow Nodes:", stdout)
            self.assertIn("Suggested Node: executor-dispatch", stdout)
            self.assertIn("Current Phase: M2-prepared", stdout)
            self.assertIn("Active Lane: mvp-lore-4b (M2-prepared)", stdout)
            self.assertIn("Parked Lanes: productlib-data-pipeline", stdout)
            self.assertIn("Default Action: hold-for-review", stdout)
            self.assertIn("dispatch-baseline-eval", stdout)
            self.assertIn("dispatch-teacher-expand", stdout)
            self.assertIn("Planning Artifacts Present:", stdout)
            self.assertIn("Execution Artifacts Missing:", stdout)
            self.assertIn("Open Findings Summary: blocking=0, non-blocking=0", stdout)
            self.assertIn("Timeline:", stdout)
            self.assertIn("Missing Artifacts: real baseline run, teacher expansion result, sft run result", stdout)
            self.assertIn("Why Not Auto Advance: The lane is ready for executor dispatch", stdout)
            self.assertIn("execution_gate: needs_review", stdout)
            self.assertNotIn("compile-planning-artifacts", stdout)

            run_id = _extract_run_id(stdout)
            exit_code, inspect_stdout, inspect_stderr = _run_cli(root, ["inspect", run_id])
            self.assertEqual(exit_code, 0)
            self.assertEqual(inspect_stderr, "")
            self.assertIn("Stop Reason: execution_gate_pending", inspect_stdout)
            self.assertIn("Parked Lanes: productlib-data-pipeline", inspect_stdout)
            self.assertIn("Closeout Summary: validation_pending", inspect_stdout)

    def test_run_preview_handoff_shows_candidate_actions_without_persisting_run(self) -> None:
        with repo_temp_dir() as temp_dir:
            root = Path(temp_dir)
            _copy_fixture(root, "ambiguous-chat.txt", "inputs/ambiguous-chat.txt")

            exit_code, stdout, stderr = _run_cli(
                root,
                ["run", "--from-chat", "inputs/ambiguous-chat.txt", "--preview-handoff"],
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr, "")
            self.assertIn("handoff ready", stdout)
            self.assertIn("Candidate Actions:", stdout)
            self.assertIn("run preview", stdout)
            self.assertFalse((root / ".runtime" / "product-runs").exists())

    def test_review_findings_flow_into_retry_and_closeout(self) -> None:
        with repo_temp_dir() as temp_dir:
            root = Path(temp_dir)
            _copy_fixture(root, "review-loop-prompt.txt", "inputs/review-loop-prompt.txt")

            compile_exit, compile_stdout, compile_stderr = _run_cli(
                root,
                [
                    "compile-handoff",
                    "--from-prompt",
                    "inputs/review-loop-prompt.txt",
                    "--out",
                    ".runtime/compiled/review-loop.json",
                ],
            )
            self.assertEqual(compile_exit, 0)
            self.assertEqual(compile_stderr, "")
            self.assertIn("handoff ready", compile_stdout)

            exit_code, stdout, stderr = _run_cli(
                root,
                ["run", "--from-handoff", ".runtime/compiled/review-loop.json"],
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("Open Findings:", stdout)
            self.assertIn("review-executor/review-1: update the closeout-facing documentation before closeout", stdout)
            self.assertIn("validation/not-passed", stdout)
            self.assertIn("Default Action: repair-dispatch", stdout)
            self.assertIn("repair-dispatch", stdout)
            self.assertIn("Closeout Summary: needs_repair", stdout)
            run_id = _extract_run_id(stdout)

            exit_code, retry_stdout, retry_stderr = _run_cli(
                root,
                ["retry", run_id, "--node", "repair-dispatch"],
            )
            self.assertEqual(exit_code, 0)
            self.assertIn("validation_gate: pass", retry_stdout)
            self.assertIn("closeout_gate: pass", retry_stdout)
            self.assertIn("Repair Rounds: 1/2", retry_stdout)
            self.assertIn("Last Node: repair-dispatch", retry_stdout)
            self.assertIn("Last Executor: codex-coder", retry_stdout)
            self.assertNotIn("Open Findings:", retry_stdout)

            exit_code, close_stdout, close_stderr = _run_cli(root, ["close", run_id])
            self.assertEqual(exit_code, 0)
            self.assertIn("Status: complete", close_stdout)
            self.assertIn("Default Action: close-run", close_stdout)
            self.assertIn("Closeable: yes", close_stdout)

    def test_runs_lists_product_runs_with_key_state(self) -> None:
        with repo_temp_dir() as temp_dir:
            root = Path(temp_dir)
            _copy_fixture(root, "jx3-chat.txt", "inputs/jx3-chat.txt")
            _copy_fixture(root, "review-loop-prompt.txt", "inputs/review-loop-prompt.txt")

            first_exit, first_stdout, first_stderr = _run_cli(root, ["run", "--from-chat", "inputs/jx3-chat.txt"])
            second_exit, second_stdout, second_stderr = _run_cli(
                root,
                ["run", "--from-prompt", "inputs/review-loop-prompt.txt"],
            )

            self.assertEqual(first_exit, 0)
            self.assertEqual(second_exit, 0)
            self.assertEqual(first_stderr, "")
            self.assertEqual(second_stderr, "")

            first_run_id = _extract_run_id(first_stdout)
            second_run_id = _extract_run_id(second_stdout)

            exit_code, runs_stdout, runs_stderr = _run_cli(root, ["runs", "--limit", "10"])

            self.assertEqual(exit_code, 0)
            self.assertEqual(runs_stderr, "")
            self.assertIn("Product Runs: 2", runs_stdout)
            self.assertIn(first_run_id, runs_stdout)
            self.assertIn(second_run_id, runs_stdout)
            self.assertIn("action=hold-for-review", runs_stdout)
            self.assertIn("phase=", runs_stdout)

    def test_runs_skips_invalid_product_run_files(self) -> None:
        with repo_temp_dir() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, ".runtime/product-runs/bad.json", "{not valid json")

            exit_code, stdout, stderr = _run_cli(root, ["runs"])

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr, "")
            self.assertIn("Product Runs: 0", stdout)
            self.assertIn("Skipped Invalid Runs: bad.json", stdout)

    def test_inspect_reports_invalid_product_run_payload(self) -> None:
        with repo_temp_dir() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, ".runtime/product-runs/corrupt-run.json", "{not valid json")

            exit_code, stdout, stderr = _run_cli(root, ["inspect", "corrupt-run"])

            self.assertEqual(exit_code, 1)
            self.assertEqual(stdout, "")
            self.assertIn("inspect failed", stderr)
            self.assertIn("runtime-data-error", stderr)
            self.assertIn("Invalid product run JSON", stderr)

    def test_run_ids_stay_unique_within_same_second(self) -> None:
        with repo_temp_dir() as temp_dir:
            root = Path(temp_dir)
            _copy_fixture(root, "jx3-chat.txt", "inputs/jx3-chat.txt")

            fixed_time = datetime(2026, 3, 28, 12, 34, 56, tzinfo=UTC)
            generated_ids = [
                UUID("11111111-0000-0000-0000-000000000001"),
                UUID("22222222-0000-0000-0000-000000000002"),
            ]

            with patch("ai_engineering_runtime.product_runtime._utc_now", return_value=fixed_time), patch(
                "ai_engineering_runtime.product_runtime.uuid4",
                side_effect=generated_ids,
            ):
                first_exit, first_stdout, first_stderr = _run_cli(
                    root,
                    ["run", "--from-chat", "inputs/jx3-chat.txt"],
                )
                second_exit, second_stdout, second_stderr = _run_cli(
                    root,
                    ["run", "--from-chat", "inputs/jx3-chat.txt"],
                )

            self.assertEqual(first_exit, 0)
            self.assertEqual(second_exit, 0)
            self.assertEqual(first_stderr, "")
            self.assertEqual(second_stderr, "")

            first_run_id = _extract_run_id(first_stdout)
            second_run_id = _extract_run_id(second_stdout)

            self.assertEqual(first_run_id, "20260328T123456-repo-coding-task-11111111")
            self.assertEqual(second_run_id, "20260328T123456-repo-coding-task-22222222")
            self.assertNotEqual(first_run_id, second_run_id)
            self.assertTrue((root / ".runtime" / "product-runs" / f"{first_run_id}.json").exists())
            self.assertTrue((root / ".runtime" / "product-runs" / f"{second_run_id}.json").exists())


if __name__ == "__main__":
    unittest.main()
