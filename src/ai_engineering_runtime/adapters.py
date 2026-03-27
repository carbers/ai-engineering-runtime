from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
import json
import os
from pathlib import Path
import shlex
import subprocess
from typing import Protocol
from uuid import uuid4

from ai_engineering_runtime.artifacts import TaskSpecArtifact, normalize_inline_code, parse_list_block, parse_markdown_sections
from ai_engineering_runtime.state import (
    DispatchMode,
    DispatchPayload,
    DispatchResult,
    ExecutionArtifactRef,
    ExecutionResult,
    ExecutionStatus,
    ExecutorCapabilityProfile,
    ExecutorDescriptor,
    ExecutorRequirements,
    ExecutorTarget,
    ReviewFinding,
    ReviewFindingSeverity,
    RuntimeReason,
    derive_repair_spec_candidate,
)


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

    def build_validation_rollup_path(self, run_id: str) -> Path:
        rollup_dir = self.repo_root / ".runtime" / "rollups" / "validation"
        rollup_dir.mkdir(parents=True, exist_ok=True)
        return rollup_dir / f"{run_id}.json"

    def build_writeback_package_path(self, run_id: str) -> Path:
        package_dir = self.repo_root / ".runtime" / "packages" / "writeback"
        package_dir.mkdir(parents=True, exist_ok=True)
        return package_dir / f"{run_id}.json"

    def build_followup_package_path(self, run_id: str) -> Path:
        package_dir = self.repo_root / ".runtime" / "packages" / "followup"
        package_dir.mkdir(parents=True, exist_ok=True)
        return package_dir / f"{run_id}.json"

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


@dataclass(frozen=True)
class ExecutorDispatchContext:
    repo_root: Path
    spec_path: Path
    repo_label: str


@dataclass(frozen=True)
class PreparedDispatch:
    target: ExecutorTarget
    mode: DispatchMode
    spec_identity: str
    executor: ExecutorDescriptor
    requirements: ExecutorRequirements
    payload_summary: DispatchPayload
    payload_body: dict[str, object]
    context_summary: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutorRunHandle:
    run_id: str
    target: ExecutorTarget
    mode: DispatchMode
    submitted_at: datetime
    status_hint: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutorPollResult:
    status: str
    is_terminal: bool
    summary: str | None = None


class ExecutorAdapter(Protocol):
    descriptor: ExecutorDescriptor
    supported_modes: tuple[DispatchMode, ...]

    def prepare(self, spec: TaskSpecArtifact, context: ExecutorDispatchContext) -> PreparedDispatch:
        ...

    def dispatch(self, prepared: PreparedDispatch) -> ExecutorRunHandle:
        ...

    def poll(self, handle: ExecutorRunHandle) -> ExecutorPollResult:
        ...

    def resume(self, handle: ExecutorRunHandle) -> ExecutorPollResult:
        ...

    def collect(self, handle: ExecutorRunHandle) -> object:
        ...

    def restore_handle(self, dispatch: DispatchResult) -> ExecutorRunHandle | None:
        ...

    def normalize(
        self,
        prepared: PreparedDispatch,
        handle: ExecutorRunHandle,
        poll_result: ExecutorPollResult,
        collected: object,
    ) -> ExecutionResult:
        ...


def build_dispatch_payload(task_spec: TaskSpecArtifact) -> DispatchPayload:
    return DispatchPayload(
        title=task_spec.title,
        goal=task_spec.sections["Goal"].strip(),
        in_scope=tuple(parse_list_block(task_spec.sections["In Scope"])),
        done_when=task_spec.sections["Done When"].strip(),
    )


def extract_executor_requirements(task_spec: TaskSpecArtifact) -> ExecutorRequirements:
    requirements_block = parse_markdown_sections(task_spec.sections.get("Executor Requirements", ""), level=3)
    return ExecutorRequirements(
        can_edit_files=_as_requirement(requirements_block.get("can_edit_files")),
        can_run_shell=_as_requirement(requirements_block.get("can_run_shell")),
        can_open_repo_context=_as_requirement(requirements_block.get("can_open_repo_context")),
        can_return_patch=_as_requirement(requirements_block.get("can_return_patch")),
        can_return_commit=_as_requirement(requirements_block.get("can_return_commit")),
        can_run_tests=_as_requirement(requirements_block.get("can_run_tests")),
        can_do_review_only=_as_requirement(requirements_block.get("can_do_review_only")),
        supports_noninteractive=_as_requirement(requirements_block.get("supports_noninteractive")),
        supports_resume=_as_requirement(requirements_block.get("supports_resume")),
    )


def evaluate_executor_compatibility(
    *,
    requirements: ExecutorRequirements,
    executor: ExecutorDescriptor,
    mode: DispatchMode,
    supported_modes: tuple[DispatchMode, ...],
) -> tuple[RuntimeReason, ...]:
    reasons: list[RuntimeReason] = []
    if mode not in supported_modes:
        reasons.append(
            RuntimeReason(
                code="unsupported-dispatch-mode",
                message=f"Executor {executor.name} does not support dispatch mode {mode.value}.",
                field="mode",
            )
        )

    capability_record = executor.capabilities.to_record()
    for capability_name in requirements.required_capabilities():
        if capability_record.get(capability_name):
            continue
        reasons.append(
            RuntimeReason(
                code="executor-capability-mismatch",
                message=f"Executor {executor.name} does not satisfy required capability {capability_name}.",
                field=capability_name,
            )
        )
    return tuple(reasons)


def build_executor_adapter(target: ExecutorTarget) -> ExecutorAdapter:
    if target is ExecutorTarget.SHELL:
        return ShellExecutorAdapter()
    if target is ExecutorTarget.CODEX:
        return CodexExecutorAdapter()
    raise ValueError(f"Unsupported executor target: {target.value}")


class ShellExecutorAdapter:
    descriptor = ExecutorDescriptor(
        name="shell",
        executor_type="local-shell",
        version="v1",
        capabilities=ExecutorCapabilityProfile(
            can_run_shell=True,
            supports_noninteractive=True,
        ),
    )
    supported_modes = (DispatchMode.PREVIEW, DispatchMode.ECHO)

    def __init__(self) -> None:
        self._receipts: dict[str, ShellDispatchReceipt] = {}

    def prepare(self, spec: TaskSpecArtifact, context: ExecutorDispatchContext) -> PreparedDispatch:
        payload_summary = build_dispatch_payload(spec)
        requirements = extract_executor_requirements(spec)
        return PreparedDispatch(
            target=ExecutorTarget.SHELL,
            mode=DispatchMode.ECHO,
            spec_identity=context.spec_path.as_posix(),
            executor=self.descriptor,
            requirements=requirements,
            payload_summary=payload_summary,
            payload_body={
                "command_text": f"ae-runtime dispatch {payload_summary.title}",
                "affected_area": parse_list_block(spec.sections.get("Affected Area", "")),
                "validation_checks": parse_list_block(spec.validation.get("Black-box Checks", "")),
            },
            context_summary={
                "repo_root": context.repo_root.as_posix(),
                "repo_label": context.repo_label,
            },
        )

    def dispatch(self, prepared: PreparedDispatch) -> ExecutorRunHandle:
        safe_text = str(prepared.payload_body.get("command_text", "ae-runtime dispatch"))
        receipt = self.dispatch_echo(safe_text)
        run_id = f"shell-{uuid4().hex[:12]}"
        self._receipts[run_id] = receipt
        return ExecutorRunHandle(
            run_id=run_id,
            target=ExecutorTarget.SHELL,
            mode=DispatchMode.ECHO,
            submitted_at=datetime.now(),
            status_hint="completed" if receipt.returncode == 0 else "failed",
            metadata={
                "command": list(receipt.command),
                "receipt": _shell_receipt_to_record(receipt),
            },
        )

    def poll(self, handle: ExecutorRunHandle) -> ExecutorPollResult:
        receipt = self._load_receipt(handle)
        if receipt is None:
            return ExecutorPollResult(status="missing", is_terminal=True, summary="No shell receipt was recorded.")
        status = "completed" if receipt.returncode == 0 else "failed"
        return ExecutorPollResult(status=status, is_terminal=True, summary=_summarize_text(receipt.stdout))

    def resume(self, handle: ExecutorRunHandle) -> ExecutorPollResult:
        return self.poll(handle)

    def collect(self, handle: ExecutorRunHandle) -> ShellDispatchReceipt | None:
        return self._load_receipt(handle)

    def restore_handle(self, dispatch: DispatchResult) -> ExecutorRunHandle | None:
        return _restore_handle_from_dispatch(dispatch)

    def _load_receipt(self, handle: ExecutorRunHandle) -> ShellDispatchReceipt | None:
        receipt = self._receipts.get(handle.run_id)
        if receipt is not None:
            return receipt
        receipt = _shell_receipt_from_record(handle.metadata.get("receipt"))
        if receipt is not None:
            self._receipts[handle.run_id] = receipt
        return receipt

    def normalize(
        self,
        prepared: PreparedDispatch,
        handle: ExecutorRunHandle,
        poll_result: ExecutorPollResult,
        collected: object,
    ) -> ExecutionResult:
        receipt = collected if isinstance(collected, ShellDispatchReceipt) else None
        if receipt is None:
            findings = (
                ReviewFinding(
                    code="missing-shell-receipt",
                    message="The shell adapter could not recover the dispatch receipt.",
                    severity=ReviewFindingSeverity.BLOCKING,
                ),
            )
            repair_spec = derive_repair_spec_candidate(
                spec_title=prepared.payload_summary.title,
                findings=findings,
                uncovered_items=("Re-run the shell dispatch proof path.",),
                validations_claimed=(),
            )
            return ExecutionResult(
                executor=self.descriptor,
                spec_identity=prepared.spec_identity,
                dispatch_summary=prepared.payload_summary.to_record(),
                final_status=ExecutionStatus.BLOCKED,
                summary="Shell dispatch receipt was unavailable.",
                uncovered_items=("No shell dispatch receipt was captured.",),
                findings=findings,
                repair_spec_candidate=repair_spec,
            )

        final_status = ExecutionStatus.SUCCEEDED if receipt.returncode == 0 else ExecutionStatus.FAILED
        findings: tuple[ReviewFinding, ...] = ()
        uncovered_items: tuple[str, ...] = ()
        if receipt.returncode != 0:
            findings = (
                ReviewFinding(
                    code="shell-dispatch-failed",
                    message="The local shell dispatch proof path returned a non-zero exit status.",
                    severity=ReviewFindingSeverity.BLOCKING,
                ),
            )
            uncovered_items = ("Inspect local shell availability and retry the dispatch proof path.",)

        repair_spec = derive_repair_spec_candidate(
            spec_title=prepared.payload_summary.title,
            findings=findings,
            uncovered_items=uncovered_items,
            validations_claimed=(),
        )
        return ExecutionResult(
            executor=self.descriptor,
            spec_identity=prepared.spec_identity,
            dispatch_summary=prepared.payload_summary.to_record(),
            final_status=final_status,
            summary="Shell adapter executed the local echo proof path.",
            stdout_summary=_summarize_text(receipt.stdout),
            stderr_summary=_summarize_text(receipt.stderr),
            log_summary=poll_result.summary,
            raw_artifact_refs=(ExecutionArtifactRef(kind="command", value=" ".join(receipt.command)),),
            findings=findings,
            uncovered_items=uncovered_items,
            repair_spec_candidate=repair_spec,
        )

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


@dataclass(frozen=True)
class CodexBackendRunResult:
    success: bool
    summary: str
    changed_files: tuple[str, ...] = ()
    stdout: str = ""
    stderr: str = ""
    validations_claimed: tuple[str, ...] = ()
    uncovered_items: tuple[str, ...] = ()
    suggested_followups: tuple[str, ...] = ()
    findings: tuple[ReviewFinding, ...] = ()
    patch_ref: str | None = None
    branch_ref: str | None = None
    commit_ref: str | None = None
    artifact_refs: tuple[ExecutionArtifactRef, ...] = ()

    def to_record(self) -> dict[str, object]:
        return {
            "success": self.success,
            "summary": self.summary,
            "changed_files": list(self.changed_files),
            "stdout": self.stdout,
            "stderr": self.stderr,
            "validations_claimed": list(self.validations_claimed),
            "uncovered_items": list(self.uncovered_items),
            "suggested_followups": list(self.suggested_followups),
            "findings": [finding.to_record() for finding in self.findings],
            "patch_ref": self.patch_ref,
            "branch_ref": self.branch_ref,
            "commit_ref": self.commit_ref,
            "artifact_refs": [reference.to_record() for reference in self.artifact_refs],
        }

    @classmethod
    def from_record(cls, value: object) -> "CodexBackendRunResult" | None:
        if not isinstance(value, dict):
            return None
        success = value.get("success")
        summary = value.get("summary")
        changed_files = value.get("changed_files", [])
        stdout = value.get("stdout", "")
        stderr = value.get("stderr", "")
        validations_claimed = value.get("validations_claimed", [])
        uncovered_items = value.get("uncovered_items", [])
        suggested_followups = value.get("suggested_followups", [])
        findings = value.get("findings", [])
        artifact_refs = value.get("artifact_refs", [])
        patch_ref = value.get("patch_ref")
        branch_ref = value.get("branch_ref")
        commit_ref = value.get("commit_ref")
        if not isinstance(success, bool) or not isinstance(summary, str):
            return None
        if not _is_list_of_strings(changed_files):
            return None
        if not all(isinstance(item, str) for item in (stdout, stderr)):
            return None
        if not _is_list_of_strings(validations_claimed):
            return None
        if not _is_list_of_strings(uncovered_items):
            return None
        if not _is_list_of_strings(suggested_followups):
            return None
        for item in (patch_ref, branch_ref, commit_ref):
            if item is not None and not isinstance(item, str):
                return None

        parsed_findings: list[ReviewFinding] = []
        for item in findings:
            parsed = _parse_review_finding_record(item)
            if parsed is None:
                return None
            parsed_findings.append(parsed)

        parsed_refs: list[ExecutionArtifactRef] = []
        for item in artifact_refs:
            parsed = _parse_execution_artifact_ref_record(item)
            if parsed is None:
                return None
            parsed_refs.append(parsed)

        return cls(
            success=success,
            summary=summary,
            changed_files=tuple(changed_files),
            stdout=stdout,
            stderr=stderr,
            validations_claimed=tuple(validations_claimed),
            uncovered_items=tuple(uncovered_items),
            suggested_followups=tuple(suggested_followups),
            findings=tuple(parsed_findings),
            patch_ref=patch_ref,
            branch_ref=branch_ref,
            commit_ref=commit_ref,
            artifact_refs=tuple(parsed_refs),
        )


class CodexBackend(Protocol):
    supports_resume: bool

    def run(self, prepared: PreparedDispatch, handle: ExecutorRunHandle) -> CodexBackendRunResult:
        ...

    def poll(self, handle: ExecutorRunHandle) -> ExecutorPollResult:
        ...

    def resume(self, handle: ExecutorRunHandle) -> ExecutorPollResult:
        ...

    def collect(self, handle: ExecutorRunHandle) -> CodexBackendRunResult | None:
        ...


class MockCodexBackend:
    supports_resume = False

    def run(self, prepared: PreparedDispatch, handle: ExecutorRunHandle) -> CodexBackendRunResult:
        affected_area = prepared.payload_body.get("affected_area", ())
        changed_files = tuple(
            item for item in affected_area if isinstance(item, str) and ("/" in item or "." in item)
        )
        validation_checks = prepared.payload_body.get("validation_checks", ())
        findings = (
            ReviewFinding(
                code="manual-closeout-review",
                message="Executor output should still be reviewed for residual repository hygiene and closeout gaps.",
                severity=ReviewFindingSeverity.WARNING,
                source="codex-mock",
            ),
        )
        run_label = prepared.payload_summary.title.lower().replace(" ", "-")
        run_result = CodexBackendRunResult(
            success=True,
            summary=f"Mock Codex backend completed the narrow task handoff for {prepared.payload_summary.title}.",
            changed_files=changed_files,
            stdout="codex mock execution completed",
            validations_claimed=tuple(validation_checks)[:3] if isinstance(validation_checks, tuple) else (),
            suggested_followups=(
                "Run validation-collect with executor-reported evidence before closeout.",
                "Review normalized findings for residual cleanup items.",
            ),
            findings=findings,
            patch_ref=f"mock://codex/patch/{run_label}",
            artifact_refs=(ExecutionArtifactRef(kind="backend_run", value=f"mock://codex/run/{run_label}"),),
        )
        _write_mock_codex_payload(handle, run_result)
        return run_result

    def poll(self, handle: ExecutorRunHandle) -> ExecutorPollResult:
        run_result = self.collect(handle)
        if run_result is None:
            return ExecutorPollResult(status="missing", is_terminal=True, summary="No Codex run was recorded.")
        return ExecutorPollResult(
            status="completed" if run_result.success else "failed",
            is_terminal=True,
            summary=run_result.summary,
        )

    def resume(self, handle: ExecutorRunHandle) -> ExecutorPollResult:
        return self.poll(handle)

    def collect(self, handle: ExecutorRunHandle) -> CodexBackendRunResult | None:
        payload = _load_mock_codex_payload(handle)
        if payload is None:
            return None
        return CodexBackendRunResult.from_record(payload)


class CodexExecutorAdapter:
    descriptor = ExecutorDescriptor(
        name="codex",
        executor_type="external-coding-agent",
        version="v1",
        capabilities=ExecutorCapabilityProfile(
            can_edit_files=True,
            can_run_shell=True,
            can_open_repo_context=True,
            can_return_patch=True,
            can_run_tests=True,
            can_do_review_only=True,
            supports_noninteractive=True,
        ),
    )
    supported_modes = (DispatchMode.PREVIEW, DispatchMode.SUBMIT)

    def __init__(self, backend: CodexBackend | None = None) -> None:
        self.backend = backend or MockCodexBackend()
        self.descriptor = replace(
            type(self).descriptor,
            capabilities=replace(
                type(self).descriptor.capabilities,
                supports_resume=_backend_supports_resume(self.backend),
            ),
        )
        self._runs: dict[str, CodexBackendRunResult] = {}
    def prepare(self, spec: TaskSpecArtifact, context: ExecutorDispatchContext) -> PreparedDispatch:
        payload_summary = build_dispatch_payload(spec)
        requirements = extract_executor_requirements(spec)
        return PreparedDispatch(
            target=ExecutorTarget.CODEX,
            mode=DispatchMode.SUBMIT,
            spec_identity=context.spec_path.as_posix(),
            executor=self.descriptor,
            requirements=requirements,
            payload_summary=payload_summary,
            payload_body={
                "title": spec.title,
                "goal": spec.sections.get("Goal", "").strip(),
                "in_scope": tuple(parse_list_block(spec.sections.get("In Scope", ""))),
                "out_of_scope": tuple(parse_list_block(spec.sections.get("Out of Scope", ""))),
                "affected_area": tuple(parse_list_block(spec.sections.get("Affected Area", ""))),
                "done_when": spec.sections.get("Done When", "").strip(),
                "validation_checks": tuple(parse_list_block(spec.validation.get("Black-box Checks", ""))),
                "risks_notes": spec.sections.get("Risks / Notes", "").strip(),
            },
            context_summary={
                "repo_root": context.repo_root.as_posix(),
                "repo_label": context.repo_label,
                "spec_path": context.spec_path.as_posix(),
            },
        )

    def dispatch(self, prepared: PreparedDispatch) -> ExecutorRunHandle:
        run_id = f"codex-{uuid4().hex[:12]}"
        base_metadata = {"repo_root": prepared.context_summary.get("repo_root")}
        handle = ExecutorRunHandle(
            run_id=run_id,
            target=ExecutorTarget.CODEX,
            mode=DispatchMode.SUBMIT,
            submitted_at=datetime.now(),
            status_hint="submitted",
            metadata=base_metadata,
        )
        try:
            run_result = self.backend.run(prepared, handle)
        except TypeError:
            run_result = self.backend.run(prepared)
        self._runs[run_id] = run_result
        return ExecutorRunHandle(
            run_id=run_id,
            target=ExecutorTarget.CODEX,
            mode=DispatchMode.SUBMIT,
            submitted_at=handle.submitted_at,
            status_hint="completed" if run_result.success else "failed",
            metadata={
                **base_metadata,
                "changed_files": list(run_result.changed_files),
                "patch_ref": run_result.patch_ref,
                "branch_ref": run_result.branch_ref,
                "commit_ref": run_result.commit_ref,
            },
        )

    def poll(self, handle: ExecutorRunHandle) -> ExecutorPollResult:
        if not hasattr(self.backend, "poll"):
            run_result = self._runs.get(handle.run_id)
            if run_result is None:
                return ExecutorPollResult(status="missing", is_terminal=True, summary="No Codex run was recorded.")
            return ExecutorPollResult(
                status="completed" if run_result.success else "failed",
                is_terminal=True,
                summary=run_result.summary,
            )
        return self.backend.poll(handle)

    def resume(self, handle: ExecutorRunHandle) -> ExecutorPollResult:
        if not hasattr(self.backend, "resume"):
            return self.poll(handle)
        return self.backend.resume(handle)

    def collect(self, handle: ExecutorRunHandle) -> CodexBackendRunResult | None:
        if not hasattr(self.backend, "collect"):
            return self._runs.get(handle.run_id)
        return self.backend.collect(handle)

    def restore_handle(self, dispatch: DispatchResult) -> ExecutorRunHandle | None:
        return _restore_handle_from_dispatch(dispatch)

    def normalize(
        self,
        prepared: PreparedDispatch,
        handle: ExecutorRunHandle,
        poll_result: ExecutorPollResult,
        collected: object,
    ) -> ExecutionResult:
        run_result = collected if isinstance(collected, CodexBackendRunResult) else None
        if run_result is None:
            findings = (
                ReviewFinding(
                    code="missing-codex-result",
                    message="The Codex adapter could not collect a backend result for the submitted run.",
                    severity=ReviewFindingSeverity.BLOCKING,
                ),
            )
            repair_spec = derive_repair_spec_candidate(
                spec_title=prepared.payload_summary.title,
                findings=findings,
                uncovered_items=("Re-submit the Codex task after verifying backend connectivity.",),
                validations_claimed=(),
            )
            return ExecutionResult(
                executor=self.descriptor,
                spec_identity=prepared.spec_identity,
                dispatch_summary=prepared.payload_summary.to_record(),
                final_status=ExecutionStatus.BLOCKED,
                summary="Codex backend result was unavailable.",
                uncovered_items=("No Codex backend result was captured.",),
                findings=findings,
                repair_spec_candidate=repair_spec,
            )

        final_status = ExecutionStatus.SUCCEEDED if run_result.success else ExecutionStatus.FAILED
        repair_spec = derive_repair_spec_candidate(
            spec_title=prepared.payload_summary.title,
            findings=run_result.findings,
            uncovered_items=run_result.uncovered_items,
            validations_claimed=run_result.validations_claimed,
        )
        return ExecutionResult(
            executor=self.descriptor,
            spec_identity=prepared.spec_identity,
            dispatch_summary=prepared.payload_summary.to_record(),
            final_status=final_status,
            summary=run_result.summary,
            changed_files=run_result.changed_files,
            patch_ref=run_result.patch_ref,
            branch_ref=run_result.branch_ref,
            commit_ref=run_result.commit_ref,
            stdout_summary=_summarize_text(run_result.stdout),
            stderr_summary=_summarize_text(run_result.stderr),
            log_summary=poll_result.summary,
            validations_claimed=run_result.validations_claimed,
            uncovered_items=run_result.uncovered_items,
            suggested_followups=run_result.suggested_followups,
            raw_artifact_refs=run_result.artifact_refs,
            findings=run_result.findings,
            repair_spec_candidate=repair_spec,
        )


def _as_requirement(text: str | None) -> bool:
    if text is None:
        return False
    normalized = normalize_inline_code(text).strip().lower()
    return normalized in {"yes", "true", "required", "1"}


def _restore_handle_from_dispatch(dispatch: DispatchResult) -> ExecutorRunHandle | None:
    run_id = dispatch.execution_metadata.get("run_id")
    submitted_at = dispatch.execution_metadata.get("submitted_at")
    handle_metadata = dispatch.execution_metadata.get("handle_metadata", {})
    if not isinstance(run_id, str) or not run_id.strip():
        return None
    if not isinstance(submitted_at, str):
        return None
    if not isinstance(handle_metadata, dict):
        return None
    try:
        parsed_submitted_at = datetime.fromisoformat(submitted_at)
    except ValueError:
        return None
    status_hint = dispatch.execution_metadata.get("execution_final_status") or dispatch.execution_metadata.get("poll_status")
    if not isinstance(status_hint, str) or not status_hint.strip():
        status_hint = "unknown"
    return ExecutorRunHandle(
        run_id=run_id,
        target=dispatch.target,
        mode=dispatch.mode,
        submitted_at=parsed_submitted_at,
        status_hint=status_hint,
        metadata=handle_metadata,
    )


def _shell_receipt_to_record(receipt: ShellDispatchReceipt) -> dict[str, object]:
    return {
        "command": list(receipt.command),
        "returncode": receipt.returncode,
        "stdout": receipt.stdout,
        "stderr": receipt.stderr,
    }


def _shell_receipt_from_record(value: object) -> ShellDispatchReceipt | None:
    if not isinstance(value, dict):
        return None
    command = value.get("command")
    returncode = value.get("returncode")
    stdout = value.get("stdout")
    stderr = value.get("stderr")
    if not isinstance(command, list) or not all(isinstance(entry, str) for entry in command):
        return None
    if not isinstance(returncode, int):
        return None
    if not isinstance(stdout, str) or not isinstance(stderr, str):
        return None
    return ShellDispatchReceipt(
        command=tuple(command),
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _backend_supports_resume(backend: object) -> bool:
    return bool(getattr(backend, "supports_resume", False))


def _mock_codex_run_path(handle: ExecutorRunHandle) -> Path | None:
    repo_root = handle.metadata.get("repo_root")
    if not isinstance(repo_root, str) or not repo_root.strip():
        return None
    path = Path(repo_root) / ".runtime" / "executors" / "codex" / f"{handle.run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _write_mock_codex_payload(handle: ExecutorRunHandle, run_result: CodexBackendRunResult) -> None:
    path = _mock_codex_run_path(handle)
    if path is None:
        return
    path.write_text(json.dumps(run_result.to_record(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_mock_codex_payload(handle: ExecutorRunHandle) -> dict[str, object] | None:
    path = _mock_codex_run_path(handle)
    if path is None or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _parse_review_finding_record(value: object) -> ReviewFinding | None:
    if not isinstance(value, dict):
        return None
    code = value.get("code")
    message = value.get("message")
    severity = value.get("severity")
    field_name = value.get("field")
    source = value.get("source")
    if not isinstance(code, str) or not isinstance(message, str) or not isinstance(severity, str):
        return None
    if field_name is not None and not isinstance(field_name, str):
        return None
    if source is not None and not isinstance(source, str):
        return None
    try:
        return ReviewFinding(
            code=code,
            message=message,
            severity=ReviewFindingSeverity(severity),
            field=field_name,
            source=source,
        )
    except ValueError:
        return None


def _parse_execution_artifact_ref_record(value: object) -> ExecutionArtifactRef | None:
    if not isinstance(value, dict):
        return None
    kind = value.get("kind")
    raw_value = value.get("value")
    if not isinstance(kind, str) or not isinstance(raw_value, str):
        return None
    return ExecutionArtifactRef(kind=kind, value=raw_value)


def _is_list_of_strings(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _summarize_text(text: str) -> str | None:
    cleaned = " ".join(text.split())
    if not cleaned:
        return None
    if len(cleaned) <= 160:
        return cleaned
    return cleaned[:157] + "..."
