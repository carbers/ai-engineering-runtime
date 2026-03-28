from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from ai_engineering_runtime.run_logs import ArtifactTarget


class ArtifactRefKind(str, Enum):
    PLAN = "plan"
    TASK_SPEC = "task_spec"
    FACT = "fact"
    SKILL = "skill"
    CHANGE_SUMMARY = "change_summary"
    OUTPUT = "output"
    RUN_LOG = "run_log"
    RUN_SUMMARY = "run_summary"
    VALIDATION_ROLLUP = "validation_rollup"
    WRITEBACK_PACKAGE = "writeback_package"
    FOLLOWUP_PACKAGE = "followup_package"


@dataclass(frozen=True)
class ArtifactRef:
    kind: ArtifactRefKind
    path: str

    def to_record(self) -> dict[str, str]:
        return {
            "kind": self.kind.value,
            "path": self.path,
        }

    @classmethod
    def from_record(cls, payload: object) -> "ArtifactRef" | None:
        if not isinstance(payload, dict):
            return None
        kind = payload.get("kind")
        path = payload.get("path")
        if not isinstance(kind, str) or not isinstance(path, str):
            return None
        try:
            return cls(kind=ArtifactRefKind(kind), path=path)
        except ValueError:
            return None


def artifact_ref_from_path(
    repo_root: Path,
    path: Path | str,
    *,
    kind: ArtifactRefKind | None = None,
) -> ArtifactRef:
    normalized_path = normalize_repo_relative_path(repo_root, path)
    return ArtifactRef(
        kind=kind or infer_artifact_ref_kind(normalized_path),
        path=normalized_path,
    )


def artifact_ref_from_artifact_target(repo_root: Path, artifact_target: ArtifactTarget) -> ArtifactRef:
    kind_map = {
        "spec": ArtifactRefKind.TASK_SPEC,
        "plan": ArtifactRefKind.PLAN,
        "output": ArtifactRefKind.OUTPUT,
    }
    return ArtifactRef(
        kind=kind_map[artifact_target.kind.value],
        path=normalize_repo_relative_path(repo_root, artifact_target.path),
    )


def resolve_artifact_ref(repo_root: Path, artifact_ref: ArtifactRef) -> Path:
    path = Path(artifact_ref.path)
    if path.is_absolute():
        return path.resolve()
    return (repo_root.resolve() / path).resolve()


def artifact_ref_exists(repo_root: Path, artifact_ref: ArtifactRef) -> bool:
    return resolve_artifact_ref(repo_root, artifact_ref).exists()


def build_runtime_artifact_ref(
    repo_root: Path,
    *,
    kind: ArtifactRefKind,
    run_id: str,
) -> ArtifactRef:
    return artifact_ref_from_path(
        repo_root,
        build_runtime_artifact_path(repo_root, kind=kind, run_id=run_id),
        kind=kind,
    )


def build_runtime_artifact_path(
    repo_root: Path,
    *,
    kind: ArtifactRefKind,
    run_id: str,
) -> Path:
    root = repo_root.resolve()
    if kind is ArtifactRefKind.RUN_LOG:
        return root / ".runtime" / "runs" / f"{run_id}.json"
    if kind is ArtifactRefKind.RUN_SUMMARY:
        return root / ".runtime" / "summaries" / f"{run_id}.json"
    if kind is ArtifactRefKind.VALIDATION_ROLLUP:
        return root / ".runtime" / "rollups" / "validation" / f"{run_id}.json"
    if kind is ArtifactRefKind.WRITEBACK_PACKAGE:
        return root / ".runtime" / "packages" / "writeback" / f"{run_id}.json"
    if kind is ArtifactRefKind.FOLLOWUP_PACKAGE:
        return root / ".runtime" / "packages" / "followup" / f"{run_id}.json"
    raise ValueError(f"Artifact kind does not have a runtime path family: {kind.value}")


def normalize_repo_relative_path(repo_root: Path, path: Path | str) -> str:
    raw_path = Path(path)
    resolved = raw_path.resolve() if raw_path.is_absolute() else (repo_root.resolve() / raw_path).resolve()
    try:
        return resolved.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def infer_artifact_ref_kind(path: str) -> ArtifactRefKind:
    normalized = path.replace("\\", "/")
    if normalized.startswith("ai/doc/runtime/"):
        return ArtifactRefKind.PLAN
    if normalized.startswith("ai/doc/specs/"):
        return ArtifactRefKind.TASK_SPEC
    if normalized.startswith("ai/doc/facts/"):
        return ArtifactRefKind.FACT
    if normalized.startswith("ai/skill/"):
        return ArtifactRefKind.SKILL
    if normalized.startswith("ai/doc/change-summaries/") or normalized.startswith("docs/summaries/"):
        return ArtifactRefKind.CHANGE_SUMMARY
    if normalized.startswith(".runtime/runs/"):
        return ArtifactRefKind.RUN_LOG
    if normalized.startswith(".runtime/summaries/"):
        return ArtifactRefKind.RUN_SUMMARY
    if normalized.startswith(".runtime/rollups/validation/"):
        return ArtifactRefKind.VALIDATION_ROLLUP
    if normalized.startswith(".runtime/packages/writeback/"):
        return ArtifactRefKind.WRITEBACK_PACKAGE
    if normalized.startswith(".runtime/packages/followup/"):
        return ArtifactRefKind.FOLLOWUP_PACKAGE
    return ArtifactRefKind.OUTPUT
