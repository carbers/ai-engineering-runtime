from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import shutil
import tempfile as stdlib_tempfile
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SCRATCH_ROOT = ROOT / ".tmp" / "tests"


class RepoTemporaryDirectory:
    """A repo-local replacement for tempfile.TemporaryDirectory in constrained runs."""

    def __init__(
        self,
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | Path | None = None,
        ignore_cleanup_errors: bool = False,
    ) -> None:
        base_dir = Path(dir) if dir is not None else SCRATCH_ROOT
        base_dir.mkdir(parents=True, exist_ok=True)
        token = uuid4().hex
        resolved_prefix = prefix or "tmp"
        resolved_suffix = suffix or ""
        self.path = base_dir / f"{resolved_prefix}{token}{resolved_suffix}"
        self.path.mkdir(parents=True, exist_ok=False)
        self.name = str(self.path)
        self.ignore_cleanup_errors = ignore_cleanup_errors

    def __enter__(self) -> str:
        return self.name

    def __exit__(self, exc_type, exc, tb) -> None:
        self.cleanup()

    def cleanup(self) -> None:
        shutil.rmtree(self.path, ignore_errors=self.ignore_cleanup_errors)


def activate_repo_tempdir(tempfile_module: object = stdlib_tempfile) -> None:
    """Redirect tempfile.TemporaryDirectory into the repository scratch area."""

    setattr(tempfile_module, "tempdir", str(SCRATCH_ROOT))
    setattr(tempfile_module, "TemporaryDirectory", RepoTemporaryDirectory)


@contextmanager
def repo_temp_dir() -> str:
    """Create one repo-local temporary directory for constrained test runs."""

    SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
    temp_dir = SCRATCH_ROOT / uuid4().hex
    temp_dir.mkdir(parents=True, exist_ok=False)
    try:
        yield str(temp_dir)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
