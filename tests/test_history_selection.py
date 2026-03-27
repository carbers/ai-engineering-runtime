from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = ROOT / "tests"
FIXTURES = ROOT / "tests" / "fixtures" / "run_logs"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))
from support import activate_repo_tempdir  # noqa: E402

activate_repo_tempdir(tempfile)
from ai_engineering_runtime.adapters import FileSystemAdapter  # noqa: E402
from ai_engineering_runtime.engine import RuntimeEngine  # noqa: E402
from ai_engineering_runtime.history_selection import (  # noqa: E402
    HistorySelectionStatus,
    select_correlated_history,
)
from ai_engineering_runtime.nodes.run_history_select import (  # noqa: E402
    RunHistorySelectNode,
    RunHistorySelectRequest,
)
from ai_engineering_runtime.run_logs import ArtifactTargetKind, ReplaySignalKind  # noqa: E402
from ai_engineering_runtime.state import WorkflowState  # noqa: E402


def _copy_fixture(root: Path, fixture_name: str) -> Path:
    source = FIXTURES / fixture_name
    destination = root / ".runtime" / "runs" / fixture_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return destination


def _write_run_log(root: Path, log_name: str, payload: dict[str, object]) -> Path:
    destination = root / ".runtime" / "runs" / log_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


class HistorySelectionTests(unittest.TestCase):
    def test_select_correlated_history_returns_newest_exact_matches_first(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _copy_fixture(root, "20260322T191727074753-validation-collect.json")
            _copy_fixture(root, "20260322T191755447854-validation-collect.json")
            _copy_fixture(root, "20260322T192114699084-followup-suggester.json")

            selection = select_correlated_history(
                root,
                artifact_kind=ArtifactTargetKind.SPEC,
                artifact_path=Path("docs/specs/20260322-005-validation-collect-foundation.md"),
                node_name="validation-collect",
                limit=2,
            )

            self.assertEqual(selection.status, HistorySelectionStatus.SELECTED)
            self.assertEqual(len(selection.matches), 2)
            self.assertEqual(
                selection.matches[0].source_log_path.name,
                "20260322T191755447854-validation-collect.json",
            )
            self.assertEqual(
                selection.matches[1].source_log_path.name,
                "20260322T191727074753-validation-collect.json",
            )

    def test_select_correlated_history_respects_signal_kind_filter_and_reports_no_match(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _copy_fixture(root, "20260322T191755447854-validation-collect.json")

            selection = select_correlated_history(
                root,
                artifact_kind=ArtifactTargetKind.SPEC,
                artifact_path=Path("docs/specs/20260322-005-validation-collect-foundation.md"),
                signal_kind=ReplaySignalKind.FOLLOWUP,
            )

            self.assertEqual(selection.status, HistorySelectionStatus.NO_MATCH)
            self.assertEqual(selection.reasons[0].code, "no-correlated-history-match")

    def test_node_execute_reports_no_match_as_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)

            result = engine.run(
                RunHistorySelectNode(
                    RunHistorySelectRequest(
                        artifact_kind=ArtifactTargetKind.SPEC,
                        artifact_path=Path("docs/specs/20260322-005-validation-collect-foundation.md"),
                        node_name="validation-collect",
                        limit=1,
                    )
                )
            )

            self.assertFalse(result.success)
            self.assertEqual(result.to_state, WorkflowState.BLOCKED)
            self.assertIsNotNone(result.history_selection)
            self.assertEqual(result.history_selection.status, HistorySelectionStatus.NO_MATCH)

    def test_select_correlated_history_skips_logs_with_invalid_execution_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_run_log(
                root,
                "20260327T120000000001-executor-dispatch.json",
                {
                    "node": "executor-dispatch",
                    "success": True,
                    "from_state": "spec-ready",
                    "to_state": "executing",
                    "plan_path": None,
                    "spec_path": "docs/specs/20260327-001-executor-adapter-codex-v1.md",
                    "output_path": None,
                    "log_path": ".runtime/runs/20260327T120000000001-executor-dispatch.json",
                    "rendered_output": None,
                    "metadata": {},
                    "issues": [],
                    "readiness": None,
                    "validation": None,
                    "writeback": None,
                    "followup": None,
                    "dispatch": {
                        "target": "codex",
                        "status": "dispatched",
                        "mode": "submit",
                        "payload": {
                            "title": "Dispatch Sample",
                            "goal": "Hand off a narrow task safely.",
                            "in_scope": ["prepare a handoff payload"],
                            "done_when": "The control plane can prepare or echo a narrow task handoff.",
                        },
                        "reasons": [],
                        "executor": None,
                        "requirements": None,
                        "execution_metadata": {},
                    },
                    "execution": {
                        "summary": "missing required execution fields"
                    },
                },
            )
            valid_path = _write_run_log(
                root,
                "20260327T115900000000-executor-dispatch.json",
                {
                    "node": "executor-dispatch",
                    "success": True,
                    "from_state": "spec-ready",
                    "to_state": "executing",
                    "plan_path": None,
                    "spec_path": "docs/specs/20260327-001-executor-adapter-codex-v1.md",
                    "output_path": None,
                    "log_path": ".runtime/runs/20260327T115900000000-executor-dispatch.json",
                    "rendered_output": None,
                    "metadata": {},
                    "issues": [],
                    "readiness": None,
                    "validation": None,
                    "writeback": None,
                    "followup": None,
                    "dispatch": {
                        "target": "codex",
                        "status": "dispatched",
                        "mode": "submit",
                        "payload": {
                            "title": "Dispatch Sample",
                            "goal": "Hand off a narrow task safely.",
                            "in_scope": ["prepare a handoff payload"],
                            "done_when": "The control plane can prepare or echo a narrow task handoff.",
                        },
                        "reasons": [],
                        "executor": None,
                        "requirements": None,
                        "execution_metadata": {},
                    },
                    "execution": {
                        "executor": {
                            "name": "codex",
                            "type": "external-coding-agent",
                            "version": "v1",
                            "capabilities": {
                                "can_edit_files": True,
                                "can_run_shell": True,
                                "can_open_repo_context": True,
                                "can_return_patch": True,
                                "can_return_commit": False,
                                "can_run_tests": True,
                                "can_do_review_only": True,
                                "supports_noninteractive": True,
                                "supports_resume": False,
                            },
                        },
                        "spec_identity": "docs/specs/20260327-001-executor-adapter-codex-v1.md",
                        "dispatch_summary": {
                            "title": "Dispatch Sample",
                            "goal": "Hand off a narrow task safely.",
                            "in_scope": ["prepare a handoff payload"],
                            "done_when": "The control plane can prepare or echo a narrow task handoff.",
                        },
                        "final_status": "running",
                        "summary": "Executor run is still in progress.",
                        "changed_files": [],
                        "patch_ref": None,
                        "branch_ref": None,
                        "commit_ref": None,
                        "stdout_summary": None,
                        "stderr_summary": None,
                        "log_summary": "Executor run is still in progress.",
                        "validations_claimed": [],
                        "uncovered_items": [],
                        "suggested_followups": [],
                        "raw_artifact_refs": [],
                        "findings": [],
                        "repair_spec_candidate": None,
                    },
                },
            )

            selection = select_correlated_history(
                root,
                artifact_kind=ArtifactTargetKind.SPEC,
                artifact_path=Path("docs/specs/20260327-001-executor-adapter-codex-v1.md"),
                node_name="executor-dispatch",
                limit=2,
            )

            self.assertEqual(selection.status, HistorySelectionStatus.SELECTED)
            self.assertEqual(len(selection.matches), 1)
            self.assertEqual(selection.matches[0].source_log_path, valid_path.resolve())

    def test_select_correlated_history_skips_logs_with_invalid_dispatch_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_run_log(
                root,
                "20260327T120000000002-executor-dispatch.json",
                {
                    "node": "executor-dispatch",
                    "success": True,
                    "from_state": "spec-ready",
                    "to_state": "executing",
                    "plan_path": None,
                    "spec_path": "docs/specs/20260327-001-executor-adapter-codex-v1.md",
                    "output_path": None,
                    "log_path": ".runtime/runs/20260327T120000000002-executor-dispatch.json",
                    "rendered_output": None,
                    "metadata": {},
                    "issues": [],
                    "readiness": None,
                    "validation": None,
                    "writeback": None,
                    "followup": None,
                    "dispatch": {
                        "status": "dispatched",
                    },
                    "execution": {
                        "executor": {
                            "name": "codex",
                            "type": "external-coding-agent",
                            "version": "v1",
                            "capabilities": {
                                "can_edit_files": True,
                                "can_run_shell": True,
                                "can_open_repo_context": True,
                                "can_return_patch": True,
                                "can_return_commit": False,
                                "can_run_tests": True,
                                "can_do_review_only": True,
                                "supports_noninteractive": True,
                                "supports_resume": False,
                            },
                        },
                        "spec_identity": "docs/specs/20260327-001-executor-adapter-codex-v1.md",
                        "dispatch_summary": {
                            "title": "Dispatch Sample",
                            "goal": "Hand off a narrow task safely.",
                            "in_scope": ["prepare a handoff payload"],
                            "done_when": "The control plane can prepare or echo a narrow task handoff.",
                        },
                        "final_status": "running",
                        "summary": "Executor run is still in progress.",
                        "changed_files": [],
                        "patch_ref": None,
                        "branch_ref": None,
                        "commit_ref": None,
                        "stdout_summary": None,
                        "stderr_summary": None,
                        "log_summary": "Executor run is still in progress.",
                        "validations_claimed": [],
                        "uncovered_items": [],
                        "suggested_followups": [],
                        "raw_artifact_refs": [],
                        "findings": [],
                        "repair_spec_candidate": None,
                    },
                },
            )
            valid_path = _write_run_log(
                root,
                "20260327T115900000001-executor-dispatch.json",
                {
                    "node": "executor-dispatch",
                    "success": True,
                    "from_state": "spec-ready",
                    "to_state": "executing",
                    "plan_path": None,
                    "spec_path": "docs/specs/20260327-001-executor-adapter-codex-v1.md",
                    "output_path": None,
                    "log_path": ".runtime/runs/20260327T115900000001-executor-dispatch.json",
                    "rendered_output": None,
                    "metadata": {},
                    "issues": [],
                    "readiness": None,
                    "validation": None,
                    "writeback": None,
                    "followup": None,
                    "dispatch": {
                        "target": "codex",
                        "status": "dispatched",
                        "mode": "submit",
                        "payload": {
                            "title": "Dispatch Sample",
                            "goal": "Hand off a narrow task safely.",
                            "in_scope": ["prepare a handoff payload"],
                            "done_when": "The control plane can prepare or echo a narrow task handoff.",
                        },
                        "reasons": [],
                        "executor": None,
                        "requirements": None,
                        "execution_metadata": {},
                    },
                    "execution": {
                        "executor": {
                            "name": "codex",
                            "type": "external-coding-agent",
                            "version": "v1",
                            "capabilities": {
                                "can_edit_files": True,
                                "can_run_shell": True,
                                "can_open_repo_context": True,
                                "can_return_patch": True,
                                "can_return_commit": False,
                                "can_run_tests": True,
                                "can_do_review_only": True,
                                "supports_noninteractive": True,
                                "supports_resume": False,
                            },
                        },
                        "spec_identity": "docs/specs/20260327-001-executor-adapter-codex-v1.md",
                        "dispatch_summary": {
                            "title": "Dispatch Sample",
                            "goal": "Hand off a narrow task safely.",
                            "in_scope": ["prepare a handoff payload"],
                            "done_when": "The control plane can prepare or echo a narrow task handoff.",
                        },
                        "final_status": "running",
                        "summary": "Executor run is still in progress.",
                        "changed_files": [],
                        "patch_ref": None,
                        "branch_ref": None,
                        "commit_ref": None,
                        "stdout_summary": None,
                        "stderr_summary": None,
                        "log_summary": "Executor run is still in progress.",
                        "validations_claimed": [],
                        "uncovered_items": [],
                        "suggested_followups": [],
                        "raw_artifact_refs": [],
                        "findings": [],
                        "repair_spec_candidate": None,
                    },
                },
            )

            selection = select_correlated_history(
                root,
                artifact_kind=ArtifactTargetKind.SPEC,
                artifact_path=Path("docs/specs/20260327-001-executor-adapter-codex-v1.md"),
                node_name="executor-dispatch",
                limit=2,
            )

            self.assertEqual(selection.status, HistorySelectionStatus.SELECTED)
            self.assertEqual(len(selection.matches), 1)
            self.assertEqual(selection.matches[0].source_log_path, valid_path.resolve())


if __name__ == "__main__":
    unittest.main()
