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
from ai_engineering_runtime.artifact_refs import (  # noqa: E402
    ArtifactRefKind,
    artifact_ref_from_artifact_target,
    artifact_ref_from_path,
    build_runtime_artifact_ref,
    resolve_artifact_ref,
)
from ai_engineering_runtime.run_logs import ArtifactTarget, ArtifactTargetKind  # noqa: E402


class ArtifactRefTests(unittest.TestCase):
    def test_infers_repo_artifact_kinds_from_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            plan_ref = artifact_ref_from_path(root, Path("docs/runtime/roadmap.md"))
            spec_ref = artifact_ref_from_path(root, Path("docs/specs/20260322-999-sample.md"))
            fact_ref = artifact_ref_from_path(root, Path("docs/facts/current-scope.md"))
            skill_ref = artifact_ref_from_path(root, Path("skills/spec-normalization/SKILL.md"))

            self.assertEqual(plan_ref.kind, ArtifactRefKind.PLAN)
            self.assertEqual(spec_ref.kind, ArtifactRefKind.TASK_SPEC)
            self.assertEqual(fact_ref.kind, ArtifactRefKind.FACT)
            self.assertEqual(skill_ref.kind, ArtifactRefKind.SKILL)

    def test_builds_runtime_artifact_refs_and_resolves_them(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            summary_ref = build_runtime_artifact_ref(
                root,
                kind=ArtifactRefKind.RUN_SUMMARY,
                run_id="20260323T010203000000-validation-collect",
            )
            package_ref = build_runtime_artifact_ref(
                root,
                kind=ArtifactRefKind.WRITEBACK_PACKAGE,
                run_id="20260323T010203000000-writeback-classifier",
            )

            self.assertEqual(summary_ref.path, ".runtime/summaries/20260323T010203000000-validation-collect.json")
            self.assertEqual(
                resolve_artifact_ref(root, package_ref),
                root / ".runtime" / "packages" / "writeback" / "20260323T010203000000-writeback-classifier.json",
            )

    def test_converts_artifact_target_to_artifact_ref(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            ref = artifact_ref_from_artifact_target(
                root,
                ArtifactTarget(
                    kind=ArtifactTargetKind.SPEC,
                    path="docs/specs/20260322-005-validation-collect-foundation.md",
                ),
            )

            self.assertEqual(ref.kind, ArtifactRefKind.TASK_SPEC)
            self.assertEqual(ref.path, "docs/specs/20260322-005-validation-collect-foundation.md")


if __name__ == "__main__":
    unittest.main()


