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
from ai_engineering_runtime.nodes.followup_suggester import (  # noqa: E402
    FollowupSuggesterNode,
    FollowupSuggesterRequest,
)
from ai_engineering_runtime.state import (  # noqa: E402
    CloseoutHint,
    FollowupAction,
    ReadinessStatus,
    ValidationStatus,
    WritebackDestination,
)
from ai_engineering_runtime.followup_package import resolve_followup_package_query  # noqa: E402


class FollowupPackageTests(unittest.TestCase):
    def test_builds_clarify_plan_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)

            result = engine.run(
                FollowupSuggesterNode(
                    FollowupSuggesterRequest(readiness_status=ReadinessStatus.NEEDS_CLARIFICATION)
                )
            )

            package, reasons = resolve_followup_package_query(adapter, run_id=result.log_path.stem)

            self.assertEqual(reasons, ())
            self.assertIsNotNone(package)
            self.assertEqual(package.action, FollowupAction.CLARIFY_PLAN)
            self.assertTrue(package.actionable)
            self.assertIn("Clarify the plan", package.suggested_next_step)

    def test_builds_fix_validation_failure_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)

            result = engine.run(
                FollowupSuggesterNode(
                    FollowupSuggesterRequest(validation_status=ValidationStatus.FAILED)
                )
            )

            package, reasons = resolve_followup_package_query(adapter, run_id=result.log_path.stem)

            self.assertEqual(reasons, ())
            self.assertIsNotNone(package)
            self.assertEqual(package.action, FollowupAction.FIX_VALIDATION_FAILURE)
            self.assertTrue(package.actionable)
            self.assertIn("fix-focused task", package.suggested_next_step)

    def test_builds_writeback_and_skill_followup_packages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)

            writeback_result = engine.run(
                FollowupSuggesterNode(
                    FollowupSuggesterRequest(writeback_destination=WritebackDestination.FACTS)
                )
            )
            skill_result = engine.run(
                FollowupSuggesterNode(
                    FollowupSuggesterRequest(writeback_destination=WritebackDestination.SKILLS)
                )
            )

            writeback_package, _ = resolve_followup_package_query(adapter, run_id=writeback_result.log_path.stem)
            skill_package, _ = resolve_followup_package_query(adapter, run_id=skill_result.log_path.stem)

            self.assertEqual(writeback_package.action, FollowupAction.WRITE_BACK_STABLE_CONTEXT)
            self.assertIn("ai/doc/facts", writeback_package.suggested_next_step)
            self.assertEqual(skill_package.action, FollowupAction.PROMOTE_SKILL_CANDIDATE)
            self.assertIn("ai/skill/", skill_package.suggested_next_step)

    def test_builds_non_actionable_no_followup_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)

            result = engine.run(
                FollowupSuggesterNode(
                    FollowupSuggesterRequest(closeout_hint=CloseoutHint.COMPLETE)
                )
            )

            package, reasons = resolve_followup_package_query(adapter, run_id=result.log_path.stem)

            self.assertEqual(reasons, ())
            self.assertIsNotNone(package)
            self.assertEqual(package.action, FollowupAction.NO_FOLLOWUP_NEEDED)
            self.assertFalse(package.actionable)
            self.assertIsNone(package.suggested_next_step)


if __name__ == "__main__":
    unittest.main()


