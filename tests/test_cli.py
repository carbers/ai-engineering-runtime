from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import date
import io
from pathlib import Path
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ai_engineering_runtime.cli import main  # noqa: E402


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

## Proposed Approach
Use a CLI.

## Risks
- parser drift

## Phase Split
- phase 0

## First Slice
Compile this roadmap into a task spec.

### Spec Title
Runtime Plan To Spec Foundation

### In Scope
- align runtime docs
- implement the node

### Out of Scope
- executor dispatch

### Affected Area
- `src/ai_engineering_runtime/*`

### Task Checklist
- align the docs
- implement the node

### Done When
The CLI turns this roadmap into a draft spec.

### Black-box Checks
- the node writes the draft spec

### White-box Needed
Yes

### White-box Trigger
The parser and transition logic are stateful.

### Internal Logic To Protect
- section parsing

### Write-back Needed
No

### Risks / Notes
- keep it small
"""


def _write_repo_file(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


class CliTests(unittest.TestCase):
    def test_main_reports_success_and_writes_spec(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "docs/runtime/roadmap.md", VALID_ROADMAP)

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    ["plan-to-spec", "--plan", "docs/runtime/roadmap.md"],
                    repo_root=root,
                    today=date(2026, 3, 22),
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("plan-to-spec completed", stdout.getvalue())
            self.assertIn("State: spec-ready", stdout.getvalue())
            self.assertIn(
                "Spec: docs/specs/20260322-001-runtime-plan-to-spec-foundation.md",
                stdout.getvalue(),
            )

    def test_main_dry_run_prints_rendered_spec(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_repo_file(root, "docs/runtime/roadmap.md", VALID_ROADMAP)

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    ["plan-to-spec", "--plan", "docs/runtime/roadmap.md", "--dry-run"],
                    repo_root=root,
                    today=date(2026, 3, 22),
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("# Runtime Plan To Spec Foundation", stdout.getvalue())
            self.assertFalse(
                (root / "docs" / "specs" / "20260322-001-runtime-plan-to-spec-foundation.md").exists()
            )

    def test_main_reports_errors_to_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            invalid_roadmap = VALID_ROADMAP.replace("### Done When\nThe CLI turns this roadmap into a draft spec.\n\n", "")
            _write_repo_file(root, "docs/runtime/roadmap.md", invalid_roadmap)

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    ["plan-to-spec", "--plan", "docs/runtime/roadmap.md"],
                    repo_root=root,
                    today=date(2026, 3, 22),
                )

            self.assertEqual(exit_code, 1)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("plan-to-spec failed", stderr.getvalue())
            self.assertIn("Missing required First Slice field: Done When", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
