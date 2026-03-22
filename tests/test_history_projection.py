from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ai_engineering_runtime.history_projection import (  # noqa: E402
    ProjectedSignalKey,
    project_history_signals,
)
from ai_engineering_runtime.run_logs import (  # noqa: E402
    ArtifactTarget,
    ArtifactTargetKind,
    ReplayResult,
    ReplaySignalKind,
    ReplayStatus,
)


class HistoryProjectionTests(unittest.TestCase):
    def test_project_history_signals_uses_newest_value_per_key(self) -> None:
        projection = project_history_signals(
            [
                ReplayResult(
                    status=ReplayStatus.REPLAYABLE,
                    source_log_path=Path(".runtime/runs/new.json"),
                    ordered_at=datetime(2026, 3, 22, 19, 17, 55, 447854),
                    node_name="validation-collect",
                    artifact_target=ArtifactTarget(
                        ArtifactTargetKind.SPEC,
                        "docs/specs/20260322-005-validation-collect-foundation.md",
                    ),
                    signal_kind=ReplaySignalKind.VALIDATION,
                    signal_value="passed",
                ),
                ReplayResult(
                    status=ReplayStatus.REPLAYABLE,
                    source_log_path=Path(".runtime/runs/old.json"),
                    ordered_at=datetime(2026, 3, 22, 19, 17, 27, 74753),
                    node_name="validation-collect",
                    artifact_target=ArtifactTarget(
                        ArtifactTargetKind.SPEC,
                        "docs/specs/20260322-005-validation-collect-foundation.md",
                    ),
                    signal_kind=ReplaySignalKind.VALIDATION,
                    signal_value="incomplete",
                ),
            ]
        )

        self.assertEqual(projection.source_count, 2)
        self.assertEqual(projection.get(ProjectedSignalKey.VALIDATION_STATUS).value, "passed")

    def test_project_history_signals_keeps_multiple_compact_keys(self) -> None:
        projection = project_history_signals(
            [
                ReplayResult(
                    status=ReplayStatus.REPLAYABLE,
                    source_log_path=Path(".runtime/runs/followup.json"),
                    ordered_at=datetime(2026, 3, 22, 19, 21, 14, 699084),
                    node_name="followup-suggester",
                    signal_kind=ReplaySignalKind.FOLLOWUP,
                    signal_value="fix_validation_failure",
                ),
                ReplayResult(
                    status=ReplayStatus.REPLAYABLE,
                    source_log_path=Path(".runtime/runs/validation.json"),
                    ordered_at=datetime(2026, 3, 22, 19, 17, 55, 447854),
                    node_name="validation-collect",
                    signal_kind=ReplaySignalKind.VALIDATION,
                    signal_value="passed",
                ),
            ]
        )

        self.assertEqual(projection.get(ProjectedSignalKey.VALIDATION_STATUS).value, "passed")
        self.assertEqual(projection.get(ProjectedSignalKey.FOLLOWUP_ACTION).value, "fix_validation_failure")


if __name__ == "__main__":
    unittest.main()
