from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import shlex
import subprocess


class FileSystemAdapter:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve()

    def resolve(self, path: Path) -> Path:
        candidate = path if path.is_absolute() else self.repo_root / path
        return candidate.resolve()

    def display_path(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.repo_root).as_posix()
        except ValueError:
            return path.resolve().as_posix()

    def read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def write_text(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text.rstrip() + "\n", encoding="utf-8")

    def build_run_log_path(self, node_name: str) -> Path:
        run_dir = self.repo_root / ".runtime" / "runs"
        run_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
        return run_dir / f"{timestamp}-{node_name}.json"

    def build_run_summary_path(self, run_id: str) -> Path:
        summary_dir = self.repo_root / ".runtime" / "summaries"
        summary_dir.mkdir(parents=True, exist_ok=True)
        return summary_dir / f"{run_id}.json"

    def write_json(self, path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def write_run_log(self, node_name: str, payload: dict[str, object]) -> Path:
        log_path = self.build_run_log_path(node_name)
        self.write_json(log_path, payload)
        return log_path


@dataclass(frozen=True)
class ShellDispatchReceipt:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class ShellExecutorAdapter:
    def dispatch_echo(self, text: str) -> ShellDispatchReceipt:
        safe_text = self._sanitize_echo_text(text)
        command = self._build_echo_command(safe_text)
        completed = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            check=False,
        )
        return ShellDispatchReceipt(
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def _build_echo_command(self, text: str) -> tuple[str, ...]:
        if os.name == "nt":
            return ("cmd", "/c", "echo", text)
        return ("sh", "-lc", f"printf '%s\\n' {shlex.quote(text)}")

    def _sanitize_echo_text(self, text: str) -> str:
        cleaned = " ".join(text.splitlines()).strip()
        for char in "&|<>^":
            cleaned = cleaned.replace(char, " ")
        return cleaned or "ae-runtime dispatch"
