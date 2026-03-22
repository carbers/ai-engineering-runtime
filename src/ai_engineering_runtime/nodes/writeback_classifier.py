from __future__ import annotations

from dataclasses import dataclass
import re

from ai_engineering_runtime.adapters import FileSystemAdapter
from ai_engineering_runtime.engine import RunResult
from ai_engineering_runtime.state import (
    RuntimeReason,
    WorkflowState,
    WritebackCandidateKind,
    WritebackDestination,
    WritebackResult,
)

_SKILLS_PATTERN = re.compile(r"\b(reusable|repeatable|workflow|playbook|checklist|routine|skill)\b")
_FACTS_PATTERN = re.compile(r"\b(scope|boundary|policy|contract|canonical|default|project-wide)\b")
_IGNORE_PATTERN = re.compile(r"\b(debug|temporary|transient|one-off|scratch|investigation)\b")

_KIND_MAP: dict[WritebackCandidateKind, tuple[WritebackDestination, RuntimeReason]] = {
    WritebackCandidateKind.PROJECT_CONTEXT: (
        WritebackDestination.FACTS,
        RuntimeReason(
            code="stable-project-context",
            message="Candidate is stable reusable project context suited for facts.",
        ),
    ),
    WritebackCandidateKind.WORKFLOW_PATTERN: (
        WritebackDestination.SKILLS,
        RuntimeReason(
            code="reusable-workflow-pattern",
            message="Candidate captures a repeatable workflow pattern suited for skills.",
        ),
    ),
    WritebackCandidateKind.DELIVERY_DETAIL: (
        WritebackDestination.CHANGE_SUMMARY_ONLY,
        RuntimeReason(
            code="task-local-delivery-detail",
            message="Candidate is useful for task closeout but not durable enough for facts or skills.",
        ),
    ),
    WritebackCandidateKind.TRANSIENT_DETAIL: (
        WritebackDestination.IGNORE,
        RuntimeReason(
            code="transient-detail",
            message="Candidate is one-off or transient detail that should not be written back.",
        ),
    ),
}


@dataclass(frozen=True)
class WritebackClassifierRequest:
    text: str
    candidate_kind: WritebackCandidateKind | None = None


class WritebackClassifierNode:
    name = "writeback-classifier"

    def __init__(self, request: WritebackClassifierRequest):
        self.request = request

    def execute(self, adapter: FileSystemAdapter) -> RunResult:
        candidate_text = self.request.text.strip()
        if not candidate_text:
            result = RunResult(
                node_name=self.name,
                success=False,
                from_state=WorkflowState.WRITEBACK_REVIEW,
                to_state=WorkflowState.WRITEBACK_REVIEW,
                issues=(
                    RuntimeReason(
                        code="missing-candidate-text",
                        message="Candidate closeout text is required for write-back classification.",
                        field="text",
                    ),
                ),
            )
            log_path = adapter.build_run_log_path(self.name)
            result = result.with_log_path(log_path)
            adapter.write_json(log_path, result.to_log_record(adapter))
            return result

        writeback = classify_writeback(candidate_text, self.request.candidate_kind)
        result = RunResult(
            node_name=self.name,
            success=True,
            from_state=WorkflowState.WRITEBACK_REVIEW,
            to_state=WorkflowState.WRITEBACK_REVIEW,
            writeback=writeback,
            metadata={"text_length": len(candidate_text)},
        )
        log_path = adapter.build_run_log_path(self.name)
        result = result.with_log_path(log_path)
        adapter.write_json(log_path, result.to_log_record(adapter))
        return result


def classify_writeback(
    candidate_text: str,
    candidate_kind: WritebackCandidateKind | None = None,
) -> WritebackResult:
    normalized = candidate_text.strip()
    resolved_kind = candidate_kind or _infer_kind(normalized)
    destination, reason = _KIND_MAP[resolved_kind]
    return WritebackResult(
        destination=destination,
        should_write_back=destination in {WritebackDestination.FACTS, WritebackDestination.SKILLS},
        reasons=(reason,),
        candidate_kind=resolved_kind,
    )


def _infer_kind(candidate_text: str) -> WritebackCandidateKind:
    normalized = candidate_text.lower()
    if _SKILLS_PATTERN.search(normalized):
        return WritebackCandidateKind.WORKFLOW_PATTERN
    if _FACTS_PATTERN.search(normalized):
        return WritebackCandidateKind.PROJECT_CONTEXT
    if _IGNORE_PATTERN.search(normalized):
        return WritebackCandidateKind.TRANSIENT_DETAIL
    return WritebackCandidateKind.DELIVERY_DETAIL
