from __future__ import annotations

import json
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
from ai_engineering_runtime.nodes.writeback_classifier import (  # noqa: E402
    WritebackClassifierNode,
    WritebackClassifierRequest,
)
from ai_engineering_runtime.run_summary import (  # noqa: E402
    materialize_summary_for_log,
    resolve_summary_query,
)


def _copy_fixture(root: Path, fixture_name: str) -> Path:
    source = FIXTURES / fixture_name
    destination = root / ".runtime" / "runs" / fixture_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return destination


class RunSummaryTests(unittest.TestCase):
    def test_engine_run_materializes_summary_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)

            result = engine.run(
                WritebackClassifierNode(
                    WritebackClassifierRequest(
                        text="This repeatable workflow checklist should be reused later.",
                    )
                )
            )

            summary_path = root / ".runtime" / "summaries" / f"{result.log_path.stem}.json"
            self.assertTrue(summary_path.exists())

            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["node"], "writeback-classifier")
            self.assertEqual(payload["terminal_state"]["status"], "review")
            self.assertEqual(payload["terminal_state"]["signal_kind"], "writeback")

    def test_materialize_summary_for_historical_validation_log_includes_prior_history_signal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            latest_log = _copy_fixture(root, "20260322T191755447854-validation-collect.json")
            _copy_fixture(root, "20260322T191727074753-validation-collect.json")

            adapter = FileSystemAdapter(root)
            summary, reasons = materialize_summary_for_log(adapter, latest_log)

            self.assertEqual(reasons, ())
            self.assertIsNotNone(summary)
            self.assertEqual(summary.terminal_state.status.value, "review")
            self.assertEqual(summary.terminal_state.signal_kind, "validation")
            self.assertEqual(summary.terminal_state.signal_value, "passed")
            self.assertIsNotNone(summary.history)
            self.assertEqual(summary.history.match_count, 1)
            self.assertEqual(summary.history.signals[0].key.value, "validation_status")
            self.assertEqual(summary.history.signals[0].value, "incomplete")

    def test_materialize_summary_for_non_replayable_plan_to_spec_log_still_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plan_log = _copy_fixture(root, "20260322T180645808422-plan-to-spec.json")

            adapter = FileSystemAdapter(root)
            summary, reasons = materialize_summary_for_log(adapter, plan_log)

            self.assertEqual(reasons, ())
            self.assertIsNotNone(summary)
            self.assertEqual(summary.terminal_state.status.value, "ready")
            self.assertEqual(summary.history.match_count, 0)

    def test_resolve_summary_query_latest_returns_materialized_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _copy_fixture(root, "20260322T191755447854-validation-collect.json")

            adapter = FileSystemAdapter(root)
            summary, reasons = resolve_summary_query(
                adapter,
                latest=True,
                node_name="validation-collect",
            )

            self.assertEqual(reasons, ())
            self.assertIsNotNone(summary)
            self.assertEqual(summary.node_name, "validation-collect")


if __name__ == "__main__":
    unittest.main()
