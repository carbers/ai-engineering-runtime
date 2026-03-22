from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ai_engineering_runtime.artifact_refs import ArtifactRefKind  # noqa: E402
from ai_engineering_runtime.node_contracts import get_node_contract, list_node_contracts  # noqa: E402
from ai_engineering_runtime.run_logs import ReplaySignalKind  # noqa: E402
from ai_engineering_runtime.terminal_state import TerminalStatus  # noqa: E402


class NodeContractTests(unittest.TestCase):
    def test_registry_covers_current_runtime_nodes(self) -> None:
        contracts = {contract.node_name for contract in list_node_contracts()}
        self.assertIn("plan-to-spec", contracts)
        self.assertIn("run-summary", contracts)
        self.assertIn("validation-rollup", contracts)
        self.assertIn("writeback-package", contracts)
        self.assertIn("followup-package", contracts)

    def test_validation_rollup_contract_declares_summary_and_validation_inputs(self) -> None:
        contract = get_node_contract("validation-rollup")
        self.assertIsNotNone(contract)
        self.assertEqual(contract.required_ref_kinds, (ArtifactRefKind.RUN_SUMMARY,))
        self.assertEqual(contract.required_signal_kinds, (ReplaySignalKind.VALIDATION,))
        self.assertEqual(contract.primary_output_kind, ArtifactRefKind.VALIDATION_ROLLUP)

    def test_executor_dispatch_contract_is_ready_only(self) -> None:
        contract = get_node_contract("executor-dispatch")
        self.assertIsNotNone(contract)
        self.assertEqual(contract.required_ref_kinds, (ArtifactRefKind.TASK_SPEC,))
        self.assertEqual(contract.required_signal_kinds, (ReplaySignalKind.READINESS,))
        self.assertEqual(contract.applicable_terminal_statuses, (TerminalStatus.READY,))


if __name__ == "__main__":
    unittest.main()
