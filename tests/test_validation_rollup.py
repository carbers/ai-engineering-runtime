from __future__ import annotations
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
from ai_engineering_runtime.nodes.validation_collect import (  # noqa: E402
    ValidationCollectNode,
    ValidationCollectRequest,
)
from ai_engineering_runtime.state import ValidationEvidenceStatus  # noqa: E402
from ai_engineering_runtime.validation_rollup import (  # noqa: E402
    ValidationFindingSeverity,
    ValidationRollupStatus,
    resolve_validation_rollup_query,
)


class ValidationRollupTests(unittest.TestCase):
    def test_rollup_marks_failed_validation_as_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)

            result = engine.run(
                ValidationCollectNode(
                    ValidationCollectRequest(
                        command_status=ValidationEvidenceStatus.FAILED,
                        black_box_status=ValidationEvidenceStatus.PASSED,
                    )
                )
            )

            rollup, reasons = resolve_validation_rollup_query(adapter, run_id=result.log_path.stem)

            self.assertEqual(reasons, ())
            self.assertIsNotNone(rollup)
            self.assertEqual(rollup.status, ValidationRollupStatus.BLOCKING)
            self.assertEqual(rollup.findings[0].severity, ValidationFindingSeverity.BLOCKING)
            self.assertTrue((root / ".runtime" / "rollups" / "validation" / f"{result.log_path.stem}.json").exists())

    def test_rollup_can_materialize_advisory_findings_from_structured_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter = FileSystemAdapter(root)
            run_id = "20260323T120000000000-validation-collect"
            log_path = root / ".runtime" / "runs" / f"{run_id}.json"
            payload = {
                "node": "validation-collect",
                "success": True,
                "from_state": "validating",
                "to_state": "writeback-review",
                "plan_path": None,
                "spec_path": "docs/specs/20260322-999-advisory.md",
                "output_path": None,
                "log_path": f".runtime/runs/{run_id}.json",
                "issues": [],
                "validation": {
                    "status": "passed",
                    "evidence": [],
                    "reasons": [
                        {
                            "code": "advisory-warning",
                            "message": "Validation passed with a review note that should remain visible.",
                        }
                    ],
                },
                "writeback": None,
                "followup": None,
                "dispatch": None,
                "replay": None,
                "history_selection": None,
                "summary": None,
                "metadata": {},
                "rendered_output": None,
            }
            adapter.write_json(log_path, payload)

            rollup, reasons = resolve_validation_rollup_query(adapter, run_id=run_id)

            self.assertEqual(reasons, ())
            self.assertIsNotNone(rollup)
            self.assertEqual(rollup.status, ValidationRollupStatus.ADVISORY)
            self.assertEqual(rollup.findings[0].code, "advisory-warning")
            self.assertEqual(rollup.findings[0].severity, ValidationFindingSeverity.ADVISORY)

    def test_rollup_keeps_manual_notes_as_info_without_blocking_clean_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)

            result = engine.run(
                ValidationCollectNode(
                    ValidationCollectRequest(
                        command_status=ValidationEvidenceStatus.PASSED,
                        black_box_status=ValidationEvidenceStatus.PASSED,
                        notes=("Captured an observation for the closeout note.",),
                    )
                )
            )

            rollup, reasons = resolve_validation_rollup_query(adapter, run_id=result.log_path.stem)

            self.assertEqual(reasons, ())
            self.assertIsNotNone(rollup)
            self.assertEqual(rollup.status, ValidationRollupStatus.CLEAN)
            self.assertEqual(len(rollup.findings), 1)
            self.assertEqual(rollup.findings[0].severity, ValidationFindingSeverity.INFO)
            self.assertEqual(rollup.findings[0].code, "manual-note")


if __name__ == "__main__":
    unittest.main()
