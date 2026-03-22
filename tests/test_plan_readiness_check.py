from __future__ import annotations

from datetime import date
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
from ai_engineering_runtime.nodes.plan_readiness_check import (  # noqa: E402
    PlanReadinessCheckNode,
    PlanReadinessCheckRequest,
)
from ai_engineering_runtime.nodes.plan_to_spec import PlanToSpecNode, PlanToSpecRequest  # noqa: E402
from ai_engineering_runtime.state import (  # noqa: E402
    ReadinessIssue,
    ReadinessResult,
    ReadinessStatus,
    WorkflowState,
    plan_to_spec_transition,
)


READY_ROADMAP = """
# Runtime Roadmap

## Problem
The repo still needs a runtime identity.

## Goal
Land the first runtime slice.

## Non-goals
- dashboards

## Constraints
- stay lightweight

## Proposed Approach
Use a CLI.

## Risks
- parser drift

## Phase Split
- phase 0

## First Slice
Compile this roadmap into a task spec.

### Spec Title
Runtime Plan Readiness Check

### In Scope
- add a readiness-check node
- wire the CLI

### Out of Scope
- executor dispatch

### Affected Area
- `src/ai_engineering_runtime/*`

### Task Checklist
- add the readiness checker
- add the CLI command

### Done When
The readiness check reports whether this plan can compile into a draft spec.

### Black-box Checks
- the readiness command reports a stable status

### White-box Needed
Yes

### White-box Trigger
The classification logic gates the workflow.

### Internal Logic To Protect
- readiness status mapping

### Write-back Needed
No

### Risks / Notes
- keep it small
"""

NEEDS_CLARIFICATION_ROADMAP = READY_ROADMAP.replace(
    "### Done When\nThe readiness check reports whether this plan can compile into a draft spec.\n",
    "### Done When\nTBD after the acceptance signal is clarified.\n",
)

BLOCKED_ROADMAP = READY_ROADMAP.replace(
    "## Goal\nLand the first runtime slice.\n\n",
    "",
)


def _write_repo_file(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


class PlanReadinessCheckNodeTests(unittest.TestCase):
    def test_execute_reports_ready_for_compilable_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "docs/runtime/roadmap.md", READY_ROADMAP)

            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)
            result = engine.run(
                PlanReadinessCheckNode(
                    PlanReadinessCheckRequest(plan_path=Path("docs/runtime/roadmap.md"))
                )
            )

            self.assertTrue(result.success)
            self.assertEqual(result.to_state, WorkflowState.SPEC_READY)
            self.assertIsNotNone(result.readiness)
            self.assertEqual(result.readiness.status, ReadinessStatus.READY)
            self.assertEqual(result.readiness.reasons, ())
            self.assertTrue(result.log_path.exists())

            payload = json.loads(result.log_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["readiness"]["status"], "ready")
            self.assertTrue(payload["readiness"]["eligible_for_plan_to_spec"])

    def test_execute_reports_needs_clarification_for_placeholder_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "docs/runtime/roadmap.md", NEEDS_CLARIFICATION_ROADMAP)

            adapter = FileSystemAdapter(root)
            result = PlanReadinessCheckNode(
                PlanReadinessCheckRequest(plan_path=Path("docs/runtime/roadmap.md"))
            ).execute(adapter)

            self.assertFalse(result.success)
            self.assertEqual(result.to_state, WorkflowState.PLANNING)
            self.assertIsNotNone(result.readiness)
            self.assertEqual(result.readiness.status, ReadinessStatus.NEEDS_CLARIFICATION)
            self.assertEqual([issue.code for issue in result.issues], ["placeholder-first-slice-field"])
            self.assertEqual(result.issues[0].field, "Done When")
            self.assertTrue(result.log_path.exists())

    def test_execute_reports_blocked_for_missing_required_structure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "docs/runtime/roadmap.md", BLOCKED_ROADMAP)

            adapter = FileSystemAdapter(root)
            result = PlanReadinessCheckNode(
                PlanReadinessCheckRequest(plan_path=Path("docs/runtime/roadmap.md"))
            ).execute(adapter)

            self.assertFalse(result.success)
            self.assertEqual(result.to_state, WorkflowState.BLOCKED)
            self.assertIsNotNone(result.readiness)
            self.assertEqual(result.readiness.status, ReadinessStatus.BLOCKED)
            self.assertEqual([issue.code for issue in result.issues], ["missing-plan-section"])
            self.assertEqual(result.issues[0].field, "Goal")

    def test_missing_plan_path_returns_blocked_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            adapter = FileSystemAdapter(root)
            result = PlanReadinessCheckNode(
                PlanReadinessCheckRequest(plan_path=Path("docs/runtime/missing.md"))
            ).execute(adapter)

            self.assertFalse(result.success)
            self.assertEqual(result.to_state, WorkflowState.BLOCKED)
            self.assertEqual(result.issues[0].code, "missing-plan")
            self.assertEqual(result.issues[0].field, "plan_path")

    def test_plan_to_spec_stops_when_readiness_needs_clarification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "docs/runtime/roadmap.md", NEEDS_CLARIFICATION_ROADMAP)

            adapter = FileSystemAdapter(root)
            result = PlanToSpecNode(
                PlanToSpecRequest(
                    plan_path=Path("docs/runtime/roadmap.md"),
                    dry_run=True,
                    created_on=date(2026, 3, 22),
                )
            ).execute(adapter)

            self.assertFalse(result.success)
            self.assertEqual(result.to_state, WorkflowState.PLANNING)
            self.assertIsNotNone(result.readiness)
            self.assertEqual(result.readiness.status, ReadinessStatus.NEEDS_CLARIFICATION)
            self.assertIsNone(result.output_path)
            self.assertIsNone(result.rendered_output)


class PlanReadinessTransitionTests(unittest.TestCase):
    def test_plan_to_spec_transition_maps_all_readiness_statuses(self) -> None:
        ready = plan_to_spec_transition(ReadinessResult(status=ReadinessStatus.READY))
        needs_clarification = plan_to_spec_transition(
            ReadinessResult(
                status=ReadinessStatus.NEEDS_CLARIFICATION,
                reasons=(ReadinessIssue(code="placeholder-first-slice-field", message="x"),),
            )
        )
        blocked = plan_to_spec_transition(
            ReadinessResult(
                status=ReadinessStatus.BLOCKED,
                reasons=(ReadinessIssue(code="missing-plan-section", message="x"),),
            )
        )

        self.assertEqual(ready.to_state, WorkflowState.SPEC_READY)
        self.assertEqual(needs_clarification.to_state, WorkflowState.PLANNING)
        self.assertEqual(blocked.to_state, WorkflowState.BLOCKED)


if __name__ == "__main__":
    unittest.main()
