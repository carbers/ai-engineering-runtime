from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import textwrap
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
from ai_engineering_runtime.state import (  # noqa: E402
    ValidationEvidenceStatus,
    ValidationStatus,
    WorkflowState,
)


WHITE_BOX_TASK_SPEC = """
# Validation Sample

## Metadata

### Source Plan / Request
`docs/runtime/roadmap.md`

### Status
`done`

### Related Specs
None.

## Goal
Close out a narrow runtime slice.

## In Scope
- validate the slice

## Out of Scope
- broader redesign

## Affected Area
- `src/ai_engineering_runtime/*`

## Task Checklist
- [x] run validation

## Done When
Validation evidence is collected cleanly.

## Validation

### Black-box Checks
- validation result is aggregated

### White-box Needed
Yes

### White-box Trigger
The aggregation logic is branch-sensitive.

### Internal Logic To Protect
- failed vs incomplete mapping

## Write-back Needed
No

## Risks / Notes
- keep it small
"""


def _write_repo_file(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


class ValidationCollectNodeTests(unittest.TestCase):
    def test_execute_reports_passed_for_complete_validation_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "docs/specs/20260322-999-validation.md", WHITE_BOX_TASK_SPEC)

            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)
            result = engine.run(
                ValidationCollectNode(
                    ValidationCollectRequest(
                        spec_path=Path("docs/specs/20260322-999-validation.md"),
                        command_status=ValidationEvidenceStatus.PASSED,
                        black_box_status=ValidationEvidenceStatus.PASSED,
                        white_box_status=ValidationEvidenceStatus.PASSED,
                        notes=("Manual smoke test reviewed.",),
                    )
                )
            )

            self.assertTrue(result.success)
            self.assertEqual(result.from_state, WorkflowState.VALIDATING)
            self.assertEqual(result.to_state, WorkflowState.WRITEBACK_REVIEW)
            self.assertIsNotNone(result.validation)
            self.assertEqual(result.validation.status, ValidationStatus.PASSED)
            self.assertEqual(len(result.validation.evidence), 4)
            self.assertTrue(result.log_path.exists())

            payload = json.loads(result.log_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["validation"]["status"], "passed")

    def test_execute_reports_failed_for_failing_command_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "docs/specs/20260322-999-validation.md", WHITE_BOX_TASK_SPEC)

            adapter = FileSystemAdapter(root)
            result = ValidationCollectNode(
                ValidationCollectRequest(
                    spec_path=Path("docs/specs/20260322-999-validation.md"),
                    command_status=ValidationEvidenceStatus.FAILED,
                    black_box_status=ValidationEvidenceStatus.PASSED,
                    white_box_status=ValidationEvidenceStatus.PASSED,
                )
            ).execute(adapter)

            self.assertFalse(result.success)
            self.assertEqual(result.to_state, WorkflowState.BLOCKED)
            self.assertIsNotNone(result.validation)
            self.assertEqual(result.validation.status, ValidationStatus.FAILED)
            self.assertEqual(result.validation.reasons[0].code, "command-failed")

    def test_execute_reports_incomplete_when_required_white_box_evidence_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "docs/specs/20260322-999-validation.md", WHITE_BOX_TASK_SPEC)

            adapter = FileSystemAdapter(root)
            result = ValidationCollectNode(
                ValidationCollectRequest(
                    spec_path=Path("docs/specs/20260322-999-validation.md"),
                    command_status=ValidationEvidenceStatus.PASSED,
                    black_box_status=ValidationEvidenceStatus.PASSED,
                )
            ).execute(adapter)

            self.assertFalse(result.success)
            self.assertEqual(result.to_state, WorkflowState.BLOCKED)
            self.assertIsNotNone(result.validation)
            self.assertEqual(result.validation.status, ValidationStatus.INCOMPLETE)
            self.assertEqual(result.validation.reasons[0].code, "missing-white-box-evidence")

    def test_missing_task_spec_path_returns_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            adapter = FileSystemAdapter(root)
            result = ValidationCollectNode(
                ValidationCollectRequest(
                    spec_path=Path("docs/specs/missing.md"),
                    command_status=ValidationEvidenceStatus.PASSED,
                )
            ).execute(adapter)

            self.assertFalse(result.success)
            self.assertEqual(result.to_state, WorkflowState.BLOCKED)
            self.assertEqual(result.issues[0].code, "missing-task-spec")


if __name__ == "__main__":
    unittest.main()
