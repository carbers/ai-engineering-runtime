from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ai_engineering_runtime.artifacts import (  # noqa: E402
    ArtifactKind,
    PlanArtifact,
    discover_artifacts,
    next_task_spec_path,
)


def _write_file(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


class ArtifactProtocolTests(unittest.TestCase):
    def test_plan_artifact_parses_nested_first_slice_contract(self) -> None:
        plan = PlanArtifact.from_markdown(
            Path("docs/runtime/roadmap.md"),
            textwrap.dedent(
                """
                # Runtime Roadmap

                ## Problem
                The repo needs a runtime.

                ## Goal
                Ship the first runtime slice.

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
                Initial slice text.

                ### Spec Title
                Runtime Plan To Spec Foundation

                ### In Scope
                - parse the roadmap

                ### Out of Scope
                - executor dispatch

                ### Affected Area
                - `src/ai_engineering_runtime/*`

                ### Task Checklist
                - implement the node

                ### Done When
                The command emits a spec.

                ### Black-box Checks
                - command succeeds

                ### White-box Needed
                Yes

                ### White-box Trigger
                The parser is stateful.

                ### Internal Logic To Protect
                - section parsing

                ### Write-back Needed
                No

                ### Risks / Notes
                - keep it small
                """
            ),
        )

        self.assertEqual(plan.sections["Goal"], "Ship the first runtime slice.")
        self.assertEqual(plan.first_slice_contract["Spec Title"], "Runtime Plan To Spec Foundation")
        self.assertIn("- implement the node", plan.first_slice_contract["Task Checklist"])

    def test_discover_artifacts_reads_canonical_locations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_file(root, "docs/runtime/roadmap.md", "# Runtime Roadmap")
            _write_file(root, "docs/specs/20260322-001-sample.md", "# Sample Spec")
            _write_file(root, "docs/facts/project-scope.md", "# Project Scope")
            _write_file(root, "skills/plan-to-spec.md", "# Skill")

            refs = discover_artifacts(root)
            kinds = [(ref.kind, ref.path.name) for ref in refs]

            self.assertIn((ArtifactKind.PLAN, "roadmap.md"), kinds)
            self.assertIn((ArtifactKind.TASK_SPEC, "20260322-001-sample.md"), kinds)
            self.assertIn((ArtifactKind.FACT, "project-scope.md"), kinds)
            self.assertIn((ArtifactKind.SKILL, "plan-to-spec.md"), kinds)

    def test_next_task_spec_path_skips_existing_same_day_sequences(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            specs_dir = Path(temp_dir) / "docs" / "specs"
            specs_dir.mkdir(parents=True, exist_ok=True)
            (specs_dir / "20260322-001-existing.md").write_text("# Existing\n", encoding="utf-8")
            (specs_dir / "20260322-003-another.md").write_text("# Another\n", encoding="utf-8")

            next_path = next_task_spec_path(
                specs_dir,
                date(2026, 3, 22),
                "runtime-plan-to-spec-foundation",
            )

            self.assertEqual(
                next_path.name,
                "20260322-004-runtime-plan-to-spec-foundation.md",
            )


if __name__ == "__main__":
    unittest.main()
