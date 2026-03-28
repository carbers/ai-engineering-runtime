from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = ROOT / "tests"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))
from support import activate_repo_tempdir  # noqa: E402

activate_repo_tempdir(tempfile)
from ai_engineering_runtime.adapters import FileSystemAdapter  # noqa: E402
from ai_engineering_runtime.engine import RuntimeEngine  # noqa: E402
from ai_engineering_runtime.nodes.writeback_classifier import (  # noqa: E402
    WritebackClassifierNode,
    WritebackClassifierRequest,
)
from ai_engineering_runtime.state import WritebackCandidateKind, WritebackDestination  # noqa: E402
from ai_engineering_runtime.writeback_package import resolve_writeback_package_query  # noqa: E402


class WritebackPackageTests(unittest.TestCase):
    def test_builds_actionable_facts_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)

            result = engine.run(
                WritebackClassifierNode(
                    WritebackClassifierRequest(
                        text="Project-wide scope and boundary guidance should stay available later.",
                        candidate_kind=WritebackCandidateKind.PROJECT_CONTEXT,
                    )
                )
            )

            package, reasons = resolve_writeback_package_query(adapter, run_id=result.log_path.stem)

            self.assertEqual(reasons, ())
            self.assertIsNotNone(package)
            self.assertEqual(package.destination, WritebackDestination.FACTS)
            self.assertTrue(package.actionable)
            self.assertIn("ai/doc/facts", package.suggested_next_action)

    def test_builds_actionable_skills_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)

            result = engine.run(
                WritebackClassifierNode(
                    WritebackClassifierRequest(
                        text="This repeatable workflow should become a reusable skill.",
                        candidate_kind=WritebackCandidateKind.WORKFLOW_PATTERN,
                    )
                )
            )

            package, reasons = resolve_writeback_package_query(adapter, run_id=result.log_path.stem)

            self.assertEqual(reasons, ())
            self.assertIsNotNone(package)
            self.assertEqual(package.destination, WritebackDestination.SKILLS)
            self.assertTrue(package.actionable)
            self.assertIn("ai/skill/", package.suggested_next_action)

    def test_builds_non_actionable_change_summary_only_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)

            result = engine.run(
                WritebackClassifierNode(
                    WritebackClassifierRequest(
                        text="Task-local delivery detail for the closeout note only.",
                        candidate_kind=WritebackCandidateKind.DELIVERY_DETAIL,
                    )
                )
            )

            package, reasons = resolve_writeback_package_query(adapter, run_id=result.log_path.stem)

            self.assertEqual(reasons, ())
            self.assertIsNotNone(package)
            self.assertEqual(package.destination, WritebackDestination.CHANGE_SUMMARY_ONLY)
            self.assertFalse(package.actionable)

    def test_builds_non_actionable_ignore_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)

            result = engine.run(
                WritebackClassifierNode(
                    WritebackClassifierRequest(
                        text="Temporary scratch debugging detail.",
                        candidate_kind=WritebackCandidateKind.TRANSIENT_DETAIL,
                    )
                )
            )

            package, reasons = resolve_writeback_package_query(adapter, run_id=result.log_path.stem)

            self.assertEqual(reasons, ())
            self.assertIsNotNone(package)
            self.assertEqual(package.destination, WritebackDestination.IGNORE)
            self.assertFalse(package.actionable)
            self.assertIsNone(package.suggested_next_action)


if __name__ == "__main__":
    unittest.main()


