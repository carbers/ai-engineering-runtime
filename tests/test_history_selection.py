from __future__ import annotations

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
FIXTURES = ROOT / "tests" / "fixtures" / "run_logs"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

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


if __name__ == "__main__":
    unittest.main()
