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
from ai_engineering_runtime.gate_evaluator import GateStatus, evaluate_node_gate  # noqa: E402
from ai_engineering_runtime.nodes.validation_collect import (  # noqa: E402
    ValidationCollectNode,
    ValidationCollectRequest,
)
from ai_engineering_runtime.run_summary import resolve_summary_query  # noqa: E402
from ai_engineering_runtime.state import ValidationEvidenceStatus  # noqa: E402
from ai_engineering_runtime.validation_rollup import resolve_validation_rollup_query  # noqa: E402


class GateEvaluatorTests(unittest.TestCase):
    def test_reports_eligible_when_required_summary_and_signal_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)

            result = engine.run(
                ValidationCollectNode(
                    ValidationCollectRequest(
                        command_status=ValidationEvidenceStatus.PASSED,
                        black_box_status=ValidationEvidenceStatus.PASSED,
                    )
                )
            )
            summary, reasons = resolve_summary_query(adapter, run_id=result.log_path.stem)

            self.assertEqual(reasons, ())
            gate = evaluate_node_gate(adapter, node_name="validation-rollup", summary=summary)

            self.assertEqual(gate.status, GateStatus.ELIGIBLE)

    def test_reports_blocked_when_required_signal_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)

            result = engine.run(
                ValidationCollectNode(
                    ValidationCollectRequest(
                        command_status=ValidationEvidenceStatus.PASSED,
                        black_box_status=ValidationEvidenceStatus.PASSED,
                    )
                )
            )
            summary, _ = resolve_summary_query(adapter, run_id=result.log_path.stem)

            gate = evaluate_node_gate(adapter, node_name="writeback-package", summary=summary)

            self.assertEqual(gate.status, GateStatus.BLOCKED)
            self.assertEqual(gate.blocking_reasons[0].code, "missing-required-signal")

    def test_reports_skipped_when_primary_output_already_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)

            result = engine.run(
                ValidationCollectNode(
                    ValidationCollectRequest(
                        command_status=ValidationEvidenceStatus.PASSED,
                        black_box_status=ValidationEvidenceStatus.PASSED,
                    )
                )
            )
            summary, _ = resolve_summary_query(adapter, run_id=result.log_path.stem)
            rollup, reasons = resolve_validation_rollup_query(adapter, run_id=result.log_path.stem)

            self.assertEqual(reasons, ())
            self.assertIsNotNone(rollup)
            gate = evaluate_node_gate(adapter, node_name="validation-rollup", summary=summary)

            self.assertEqual(gate.status, GateStatus.SKIPPED)
            self.assertEqual(gate.advisory_reasons[0].code, "primary-output-already-exists")

    def test_reports_not_applicable_for_terminal_status_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)

            result = engine.run(
                ValidationCollectNode(
                    ValidationCollectRequest(
                        command_status=ValidationEvidenceStatus.PASSED,
                        black_box_status=ValidationEvidenceStatus.PASSED,
                    )
                )
            )
            summary, _ = resolve_summary_query(adapter, run_id=result.log_path.stem)

            gate = evaluate_node_gate(adapter, node_name="executor-dispatch", summary=summary)

            self.assertEqual(gate.status, GateStatus.NOT_APPLICABLE)
            self.assertEqual(gate.blocking_reasons[0].code, "terminal-status-not-applicable")

    def test_reports_unknown_for_undeclared_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)

            result = engine.run(
                ValidationCollectNode(
                    ValidationCollectRequest(
                        command_status=ValidationEvidenceStatus.PASSED,
                        black_box_status=ValidationEvidenceStatus.PASSED,
                    )
                )
            )
            summary, _ = resolve_summary_query(adapter, run_id=result.log_path.stem)

            gate = evaluate_node_gate(adapter, node_name="imaginary-node", summary=summary)

            self.assertEqual(gate.status, GateStatus.UNKNOWN)
            self.assertEqual(gate.blocking_reasons[0].code, "unknown-node-contract")


if __name__ == "__main__":
    unittest.main()


