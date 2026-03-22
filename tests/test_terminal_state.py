from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ai_engineering_runtime.engine import RunResult  # noqa: E402
from ai_engineering_runtime.run_logs import (  # noqa: E402
    ReplaySignalKind,
    RunRecord,
    RunRecordStatus,
)
from ai_engineering_runtime.state import (  # noqa: E402
    RuntimeReason,
    ValidationResult,
    ValidationStatus,
    WorkflowState,
)
from ai_engineering_runtime.terminal_state import (  # noqa: E402
    TerminalStatus,
    resolve_terminal_state_for_record,
    resolve_terminal_state_for_result,
)


class TerminalStateTests(unittest.TestCase):
    def test_resolve_terminal_state_for_result_uses_primary_issue_first(self) -> None:
        result = RunResult(
            node_name="validation-collect",
            success=False,
            from_state=WorkflowState.VALIDATING,
            to_state=WorkflowState.BLOCKED,
            issues=(
                RuntimeReason(
                    code="command-failed",
                    message="command validation failed.",
                ),
            ),
            validation=ValidationResult(
                status=ValidationStatus.FAILED,
                reasons=(
                    RuntimeReason(
                        code="command-failed",
                        message="command validation failed.",
                    ),
                ),
            ),
        )

        terminal = resolve_terminal_state_for_result(result)

        self.assertEqual(terminal.status, TerminalStatus.BLOCKED)
        self.assertEqual(terminal.stop_reason_code, "command-failed")
        self.assertEqual(terminal.signal_kind, "validation")
        self.assertEqual(terminal.signal_value, "failed")

    def test_resolve_terminal_state_for_record_falls_back_to_signal_reason(self) -> None:
        record = RunRecord(
            status=RunRecordStatus.LOADABLE,
            source_log_path=Path(".runtime/runs/20260322T190929590964-writeback-classifier.json"),
            node_name="writeback-classifier",
            success=True,
            from_state="writeback-review",
            to_state="writeback-review",
            signal_kind=ReplaySignalKind.WRITEBACK,
            signal_value="skills",
            signal_reasons=(
                RuntimeReason(
                    code="reusable-workflow-pattern",
                    message="Candidate captures a reusable workflow pattern.",
                ),
            ),
        )

        terminal = resolve_terminal_state_for_record(record)

        self.assertEqual(terminal.status, TerminalStatus.REVIEW)
        self.assertEqual(terminal.stop_reason_code, "reusable-workflow-pattern")
        self.assertEqual(terminal.signal_kind, "writeback")
        self.assertEqual(terminal.signal_value, "skills")


if __name__ == "__main__":
    unittest.main()
