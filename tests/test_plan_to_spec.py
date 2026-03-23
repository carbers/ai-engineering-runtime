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
TESTS = ROOT / "tests"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))
from support import activate_repo_tempdir  # noqa: E402

activate_repo_tempdir(tempfile)
from ai_engineering_runtime.adapters import FileSystemAdapter  # noqa: E402
from ai_engineering_runtime.engine import RuntimeEngine  # noqa: E402
from ai_engineering_runtime.nodes.plan_to_spec import PlanToSpecNode, PlanToSpecRequest  # noqa: E402
from ai_engineering_runtime.state import ReadinessStatus, WorkflowState  # noqa: E402


VALID_ROADMAP = """
# Runtime Roadmap

## Problem
The repo still needs a runtime identity.

## Goal
Land the first runtime slice.

## Non-goals
- dashboards

## Constraints
- stay lightweight
- keep the SOP starter in place

## Proposed Approach
Add a CLI and one real node.

## Risks
- parser drift

## Phase Split
- phase 0 alignment
- phase 1 implementation

## First Slice
Compile this roadmap into a task spec.

### Spec Title
Runtime Plan To Spec Foundation

### In Scope
- align runtime docs
- implement the plan-to-spec node

### Out of Scope
- executor dispatch

### Affected Area
- `docs/runtime/*`
- `src/ai_engineering_runtime/*`

### Task Checklist
- align the docs
- implement the node

### Done When
The CLI turns this roadmap into a draft spec.

### Black-box Checks
- the node writes the draft spec
- dry-run prints the draft spec

### White-box Needed
Yes

### White-box Trigger
The parser and transition logic are stateful.

### Internal Logic To Protect
- section parsing
- state transitions

### Write-back Needed
No

### Risks / Notes
- keep the parser limited to the documented contract
"""


def _write_repo_file(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


class PlanToSpecNodeTests(unittest.TestCase):
    def test_execute_writes_spec_and_run_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "docs/runtime/roadmap.md", VALID_ROADMAP)
            _write_repo_file(root, "docs/facts/project-scope.md", "# Scope")
            _write_repo_file(root, "skills/plan-to-spec.md", "# Skill")

            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)
            result = engine.run(
                PlanToSpecNode(
                    PlanToSpecRequest(
                        plan_path=Path("docs/runtime/roadmap.md"),
                        created_on=date(2026, 3, 22),
                    )
                )
            )

            self.assertTrue(result.success)
            self.assertEqual(result.to_state, WorkflowState.SPEC_READY)
            self.assertIsNotNone(result.readiness)
            self.assertEqual(result.readiness.status, ReadinessStatus.READY)
            self.assertIsNotNone(result.output_path)
            self.assertTrue(result.output_path.exists())
            self.assertIsNotNone(result.log_path)
            self.assertTrue(result.log_path.exists())
            self.assertIn("`draft`", result.output_path.read_text(encoding="utf-8"))

            payload = json.loads(result.log_path.read_text(encoding="utf-8"))
            self.assertTrue(payload["success"])
            self.assertEqual(payload["to_state"], "spec-ready")
            self.assertEqual(payload["log_path"], ".runtime/runs/" + result.log_path.name)
            self.assertEqual(payload["readiness"]["status"], "ready")

    def test_dry_run_emits_spec_without_writing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "docs/runtime/roadmap.md", VALID_ROADMAP)

            adapter = FileSystemAdapter(root)
            engine = RuntimeEngine(adapter)
            result = engine.run(
                PlanToSpecNode(
                    PlanToSpecRequest(
                        plan_path=Path("docs/runtime/roadmap.md"),
                        dry_run=True,
                        created_on=date(2026, 3, 22),
                    )
                )
            )

            self.assertTrue(result.success)
            self.assertIsNotNone(result.readiness)
            self.assertEqual(result.readiness.status, ReadinessStatus.READY)
            self.assertIsNotNone(result.output_path)
            self.assertFalse(result.output_path.exists())
            self.assertIsNotNone(result.rendered_output)
            self.assertIn("# Runtime Plan To Spec Foundation", result.rendered_output)
            self.assertTrue(result.log_path.exists())

    def test_missing_first_slice_field_blocks_without_writing_spec(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            invalid_roadmap = VALID_ROADMAP.replace("### Done When\nThe CLI turns this roadmap into a draft spec.\n\n", "")
            _write_repo_file(root, "docs/runtime/roadmap.md", invalid_roadmap)

            adapter = FileSystemAdapter(root)
            result = PlanToSpecNode(
                PlanToSpecRequest(
                    plan_path=Path("docs/runtime/roadmap.md"),
                    created_on=date(2026, 3, 22),
                )
            ).execute(adapter)

            self.assertFalse(result.success)
            self.assertEqual(result.to_state, WorkflowState.BLOCKED)
            self.assertIsNotNone(result.readiness)
            self.assertEqual(result.readiness.status, ReadinessStatus.BLOCKED)
            self.assertFalse((root / "docs" / "specs").exists())
            self.assertTrue(any("Done When" in issue.message for issue in result.issues))
            self.assertTrue(result.log_path.exists())

    def test_plain_text_list_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            invalid_roadmap = VALID_ROADMAP.replace(
                "### In Scope\n- align runtime docs\n- implement the plan-to-spec node\n",
                "### In Scope\nalign runtime docs without bullet markers\n",
            )
            _write_repo_file(root, "docs/runtime/roadmap.md", invalid_roadmap)

            adapter = FileSystemAdapter(root)
            result = PlanToSpecNode(
                PlanToSpecRequest(
                    plan_path=Path("docs/runtime/roadmap.md"),
                    created_on=date(2026, 3, 22),
                )
            ).execute(adapter)

            self.assertFalse(result.success)
            self.assertEqual(result.to_state, WorkflowState.BLOCKED)
            self.assertIsNotNone(result.readiness)
            self.assertEqual(result.readiness.status, ReadinessStatus.BLOCKED)
            self.assertTrue(any("Markdown list items" in issue.message for issue in result.issues))


if __name__ == "__main__":
    unittest.main()


