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
from ai_engineering_runtime.nodes.writeback_classifier import (  # noqa: E402
    WritebackClassifierNode,
    WritebackClassifierRequest,
    classify_writeback,
)
from ai_engineering_runtime.state import (  # noqa: E402
    WorkflowState,
    WritebackCandidateKind,
    WritebackDestination,
)


class WritebackClassifierNodeTests(unittest.TestCase):
    def test_execute_classifies_facts_for_project_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = FileSystemAdapter(Path(temp_dir))
            engine = RuntimeEngine(adapter)

            result = engine.run(
                WritebackClassifierNode(
                    WritebackClassifierRequest(
                        text="Project scope and repository boundary language changed in a stable way.",
                        candidate_kind=WritebackCandidateKind.PROJECT_CONTEXT,
                    )
                )
            )

            self.assertTrue(result.success)
            self.assertEqual(result.from_state, WorkflowState.WRITEBACK_REVIEW)
            self.assertEqual(result.to_state, WorkflowState.WRITEBACK_REVIEW)
            self.assertIsNotNone(result.writeback)
            self.assertEqual(result.writeback.destination, WritebackDestination.FACTS)
            self.assertTrue(result.writeback.should_write_back)
            self.assertEqual(result.writeback.reasons[0].code, "stable-project-context")
            self.assertTrue(result.log_path.exists())

            payload = json.loads(result.log_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["writeback"]["destination"], "facts")
            self.assertTrue(payload["writeback"]["should_write_back"])

    def test_execute_classifies_skills_for_reusable_workflow_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = FileSystemAdapter(Path(temp_dir))
            result = WritebackClassifierNode(
                WritebackClassifierRequest(
                    text="This repeatable closeout workflow should become a runtime skill.",
                    candidate_kind=WritebackCandidateKind.WORKFLOW_PATTERN,
                )
            ).execute(adapter)

            self.assertTrue(result.success)
            self.assertIsNotNone(result.writeback)
            self.assertEqual(result.writeback.destination, WritebackDestination.SKILLS)
            self.assertEqual(result.writeback.reasons[0].code, "reusable-workflow-pattern")

    def test_execute_defaults_to_change_summary_only_for_delivery_detail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = FileSystemAdapter(Path(temp_dir))
            result = WritebackClassifierNode(
                WritebackClassifierRequest(
                    text="Adjusted the CLI output and added targeted tests for this slice.",
                )
            ).execute(adapter)

            self.assertTrue(result.success)
            self.assertIsNotNone(result.writeback)
            self.assertEqual(result.writeback.destination, WritebackDestination.CHANGE_SUMMARY_ONLY)
            self.assertFalse(result.writeback.should_write_back)
            self.assertEqual(result.writeback.candidate_kind, WritebackCandidateKind.DELIVERY_DETAIL)

    def test_execute_classifies_ignore_for_transient_detail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = FileSystemAdapter(Path(temp_dir))
            result = WritebackClassifierNode(
                WritebackClassifierRequest(
                    text="Temporary debug output from this one-off investigation is not reusable.",
                    candidate_kind=WritebackCandidateKind.TRANSIENT_DETAIL,
                )
            ).execute(adapter)

            self.assertTrue(result.success)
            self.assertIsNotNone(result.writeback)
            self.assertEqual(result.writeback.destination, WritebackDestination.IGNORE)
            self.assertFalse(result.writeback.should_write_back)
            self.assertEqual(result.writeback.reasons[0].code, "transient-detail")

    def test_missing_candidate_text_returns_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = FileSystemAdapter(Path(temp_dir))
            result = WritebackClassifierNode(
                WritebackClassifierRequest(text="   ")
            ).execute(adapter)

            self.assertFalse(result.success)
            self.assertEqual(result.to_state, WorkflowState.WRITEBACK_REVIEW)
            self.assertEqual(result.issues[0].code, "missing-candidate-text")
            self.assertEqual(result.issues[0].field, "text")


class WritebackClassifierInferenceTests(unittest.TestCase):
    def test_classify_writeback_uses_keyword_inference_when_hint_missing(self) -> None:
        result = classify_writeback("This reusable workflow checklist should be kept for later.")

        self.assertEqual(result.destination, WritebackDestination.SKILLS)
        self.assertEqual(result.candidate_kind, WritebackCandidateKind.WORKFLOW_PATTERN)


if __name__ == "__main__":
    unittest.main()
