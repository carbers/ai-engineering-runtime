from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ai_engineering_runtime.adapters import FileSystemAdapter  # noqa: E402
from ai_engineering_runtime.engine import RuntimeEngine  # noqa: E402
from ai_engineering_runtime.nodes.followup_suggester import (  # noqa: E402
    FollowupSuggesterNode,
    FollowupSuggesterRequest,
    suggest_followup,
)
from ai_engineering_runtime.state import (  # noqa: E402
    CloseoutHint,
    FollowupAction,
    ReadinessStatus,
    ValidationStatus,
    WorkflowState,
    WritebackDestination,
)


class FollowupSuggesterNodeTests(unittest.TestCase):
    def test_execute_suggests_clarify_plan_for_non_ready_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = FileSystemAdapter(Path(temp_dir))
            engine = RuntimeEngine(adapter)
            result = engine.run(
                FollowupSuggesterNode(
                    FollowupSuggesterRequest(
                        readiness_status=ReadinessStatus.NEEDS_CLARIFICATION,
                    )
                )
            )

            self.assertTrue(result.success)
            self.assertEqual(result.from_state, WorkflowState.WRITEBACK_REVIEW)
            self.assertEqual(result.to_state, WorkflowState.PLANNING)
            self.assertIsNotNone(result.followup)
            self.assertEqual(result.followup.action, FollowupAction.CLARIFY_PLAN)
            self.assertEqual(result.followup.reasons[0].code, "readiness-needs-clarification")

    def test_execute_suggests_fix_validation_failure_for_failed_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = FileSystemAdapter(Path(temp_dir))
            result = FollowupSuggesterNode(
                FollowupSuggesterRequest(
                    validation_status=ValidationStatus.FAILED,
                )
            ).execute(adapter)

            self.assertTrue(result.success)
            self.assertEqual(result.to_state, WorkflowState.BLOCKED)
            self.assertIsNotNone(result.followup)
            self.assertEqual(result.followup.action, FollowupAction.FIX_VALIDATION_FAILURE)
            self.assertEqual(result.followup.reasons[0].code, "validation-failed")

    def test_execute_suggests_writeback_for_facts_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = FileSystemAdapter(Path(temp_dir))
            result = FollowupSuggesterNode(
                FollowupSuggesterRequest(
                    writeback_destination=WritebackDestination.FACTS,
                )
            ).execute(adapter)

            self.assertTrue(result.success)
            self.assertEqual(result.to_state, WorkflowState.WRITEBACK_REVIEW)
            self.assertIsNotNone(result.followup)
            self.assertEqual(result.followup.action, FollowupAction.WRITE_BACK_STABLE_CONTEXT)

    def test_execute_suggests_no_followup_needed_when_closeout_is_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = FileSystemAdapter(Path(temp_dir))
            result = FollowupSuggesterNode(
                FollowupSuggesterRequest(
                    validation_status=ValidationStatus.PASSED,
                    closeout_hint=CloseoutHint.COMPLETE,
                )
            ).execute(adapter)

            self.assertTrue(result.success)
            self.assertEqual(result.to_state, WorkflowState.COMPLETE)
            self.assertIsNotNone(result.followup)
            self.assertEqual(result.followup.action, FollowupAction.NO_FOLLOWUP_NEEDED)
            self.assertTrue(result.log_path.exists())

            payload = json.loads(result.log_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["followup"]["action"], "no_followup_needed")

    def test_missing_signals_returns_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = FileSystemAdapter(Path(temp_dir))
            result = FollowupSuggesterNode(FollowupSuggesterRequest()).execute(adapter)

            self.assertFalse(result.success)
            self.assertEqual(result.to_state, WorkflowState.BLOCKED)
            self.assertEqual(result.issues[0].code, "missing-followup-signal")


class FollowupSuggestionPriorityTests(unittest.TestCase):
    def test_suggest_followup_prioritizes_validation_over_writeback(self) -> None:
        result = suggest_followup(
            FollowupSuggesterRequest(
                validation_status=ValidationStatus.FAILED,
                writeback_destination=WritebackDestination.FACTS,
            )
        )

        self.assertEqual(result.action, FollowupAction.FIX_VALIDATION_FAILURE)


if __name__ == "__main__":
    unittest.main()
