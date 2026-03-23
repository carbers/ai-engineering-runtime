from __future__ import annotations

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
from ai_engineering_runtime.nodes.result_log_replay import (  # noqa: E402
    ResultLogReplayNode,
    ResultLogReplayRequest,
)
from ai_engineering_runtime.run_logs import (  # noqa: E402
    ArtifactTargetKind,
    ReplaySignalKind,
    ReplayStatus,
    load_replay_result,
    select_latest_run_log,
)
from ai_engineering_runtime.state import WorkflowState  # noqa: E402


def _copy_fixture(root: Path, fixture_name: str) -> Path:
    source = FIXTURES / fixture_name
    destination = root / ".runtime" / "runs" / fixture_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return destination


class ResultLogReplayNodeTests(unittest.TestCase):
    def test_execute_replays_validation_log_from_explicit_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            replay_path = _copy_fixture(root, "20260322T191755447854-validation-collect.json")

            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)
            result = engine.run(
                ResultLogReplayNode(
                    ResultLogReplayRequest(
                        log_path=Path(".runtime/runs") / replay_path.name,
                    )
                )
            )

            self.assertTrue(result.success)
            self.assertEqual(result.from_state, WorkflowState.COMPLETE)
            self.assertEqual(result.to_state, WorkflowState.COMPLETE)
            self.assertIsNotNone(result.replay)
            self.assertEqual(result.replay.status, ReplayStatus.REPLAYABLE)
            self.assertEqual(result.replay.node_name, "validation-collect")
            self.assertEqual(result.replay.signal_kind, ReplaySignalKind.VALIDATION)
            self.assertEqual(result.replay.signal_value, "passed")
            self.assertEqual(result.replay.artifact_target.kind, ArtifactTargetKind.SPEC)
            self.assertEqual(
                result.replay.artifact_target.path,
                "docs/specs/20260322-005-validation-collect-foundation.md",
            )
            self.assertEqual(result.replay.ordered_at.isoformat(), "2026-03-22T19:17:55.447854")
            self.assertTrue(result.log_path.exists())

    def test_execute_rejects_legacy_plan_to_spec_log_without_replay_signal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _copy_fixture(root, "20260322T180645808422-plan-to-spec.json")

            adapter = FileSystemAdapter(root)
            result = ResultLogReplayNode(
                ResultLogReplayRequest(
                    log_path=Path(".runtime/runs/20260322T180645808422-plan-to-spec.json"),
                )
            ).execute(adapter)

            self.assertFalse(result.success)
            self.assertEqual(result.to_state, WorkflowState.BLOCKED)
            self.assertIsNotNone(result.replay)
            self.assertEqual(result.replay.status, ReplayStatus.REJECTED)
            self.assertEqual(result.replay.node_name, "plan-to-spec")
            self.assertEqual(result.replay.reasons[0].code, "missing-replayable-signal")

    def test_execute_selects_latest_matching_log_for_node_filter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _copy_fixture(root, "20260322T191727074753-validation-collect.json")
            _copy_fixture(root, "20260322T191755447854-validation-collect.json")
            _copy_fixture(root, "20260322T192114699084-followup-suggester.json")

            adapter = FileSystemAdapter(root)
            result = ResultLogReplayNode(
                ResultLogReplayRequest(
                    latest=True,
                    node_name="validation-collect",
                )
            ).execute(adapter)

            self.assertTrue(result.success)
            self.assertIsNotNone(result.replay)
            self.assertEqual(
                result.replay.source_log_path.name,
                "20260322T191755447854-validation-collect.json",
            )
            self.assertEqual(result.replay.signal_value, "passed")

    def test_execute_reports_missing_selection_when_no_logs_match(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter = FileSystemAdapter(root)

            result = ResultLogReplayNode(
                ResultLogReplayRequest(
                    latest=True,
                    node_name="validation-collect",
                )
            ).execute(adapter)

            self.assertFalse(result.success)
            self.assertIsNotNone(result.replay)
            self.assertEqual(result.replay.status, ReplayStatus.REJECTED)
            self.assertEqual(result.replay.reasons[0].code, "missing-run-log-selection")


class RunLogReplayParsingTests(unittest.TestCase):
    def test_load_replay_result_rejects_malformed_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            malformed_path = _copy_fixture(root, "20260322T193000000000-malformed.json")

            replay = load_replay_result(malformed_path)

            self.assertEqual(replay.status, ReplayStatus.REJECTED)
            self.assertEqual(replay.reasons[0].code, "malformed-run-log-json")

    def test_load_replay_result_rejects_ambiguous_signal_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ambiguous_path = _copy_fixture(root, "20260322T193100000000-validation-collect.json")

            replay = load_replay_result(ambiguous_path)

            self.assertEqual(replay.status, ReplayStatus.REJECTED)
            self.assertEqual(replay.reasons[0].code, "ambiguous-replayable-signal")

    def test_load_replay_result_rejects_invalid_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            invalid_path = _copy_fixture(root, "20260322T193200000000-invalid-envelope.json")

            replay = load_replay_result(invalid_path)

            self.assertEqual(replay.status, ReplayStatus.REJECTED)
            self.assertEqual(replay.reasons[0].code, "invalid-run-log-envelope")

    def test_select_latest_run_log_returns_newest_by_filename_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _copy_fixture(root, "20260322T191727074753-validation-collect.json")
            _copy_fixture(root, "20260322T191755447854-validation-collect.json")
            _copy_fixture(root, "20260322T192114699084-followup-suggester.json")

            selected = select_latest_run_log(root, node_name="validation-collect")

            self.assertIsNotNone(selected)
            self.assertEqual(selected.name, "20260322T191755447854-validation-collect.json")


if __name__ == "__main__":
    unittest.main()


