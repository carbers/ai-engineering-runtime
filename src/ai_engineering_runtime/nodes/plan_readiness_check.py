from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from ai_engineering_runtime.adapters import FileSystemAdapter
from ai_engineering_runtime.artifacts import (
    FIRST_SLICE_FIELDS,
    LIST_FIELDS,
    REQUIRED_PLAN_SECTIONS,
    PlanArtifact,
    discover_artifacts,
    is_markdown_list_block,
)
from ai_engineering_runtime.engine import RunResult
from ai_engineering_runtime.state import (
    ReadinessIssue,
    ReadinessResult,
    ReadinessStatus,
    plan_to_spec_transition,
)

_PLACEHOLDER_PATTERNS = (
    re.compile(r"\btbd\b", re.IGNORECASE),
    re.compile(r"\btodo\b", re.IGNORECASE),
    re.compile(r"\bto be decided\b", re.IGNORECASE),
    re.compile(r"\bto be determined\b", re.IGNORECASE),
)


@dataclass(frozen=True)
class PlanReadinessCheckRequest:
    plan_path: Path


@dataclass(frozen=True)
class CheckedPlan:
    plan_path: Path
    plan: PlanArtifact | None
    readiness: ReadinessResult


class PlanReadinessCheckNode:
    name = "plan-readiness-check"

    def __init__(self, request: PlanReadinessCheckRequest):
        self.request = request

    def execute(self, adapter: FileSystemAdapter) -> RunResult:
        discovered = discover_artifacts(adapter.repo_root)
        checked_plan = check_plan_readiness(adapter, self.request.plan_path)
        transition = plan_to_spec_transition(checked_plan.readiness)
        result = RunResult(
            node_name=self.name,
            success=checked_plan.readiness.is_ready,
            from_state=transition.from_state,
            to_state=transition.to_state,
            issues=transition.issues,
            readiness=checked_plan.readiness,
            plan_path=checked_plan.plan_path,
            metadata={"artifact_count": len(discovered)},
        )
        log_path = adapter.build_run_log_path(self.name)
        result = result.with_log_path(log_path)
        adapter.write_json(log_path, result.to_log_record(adapter))
        return result


def check_plan_readiness(adapter: FileSystemAdapter, plan_path: Path) -> CheckedPlan:
    resolved_plan_path = adapter.resolve(plan_path)
    if not resolved_plan_path.exists():
        return CheckedPlan(
            plan_path=resolved_plan_path,
            plan=None,
            readiness=ReadinessResult(
                status=ReadinessStatus.BLOCKED,
                reasons=(
                    ReadinessIssue(
                        code="missing-plan",
                        message=f"Plan not found: {adapter.display_path(resolved_plan_path)}",
                        field="plan_path",
                    ),
                ),
            ),
        )

    plan = PlanArtifact.from_markdown(resolved_plan_path, adapter.read_text(resolved_plan_path))
    return CheckedPlan(
        plan_path=resolved_plan_path,
        plan=plan,
        readiness=assess_plan_readiness(plan),
    )


def assess_plan_readiness(plan: PlanArtifact) -> ReadinessResult:
    blocked_reasons: list[ReadinessIssue] = []

    for section in REQUIRED_PLAN_SECTIONS:
        if not plan.sections.get(section, "").strip():
            blocked_reasons.append(
                ReadinessIssue(
                    code="missing-plan-section",
                    message=f"Missing required plan section: {section}",
                    field=section,
                )
            )

    for field_name in FIRST_SLICE_FIELDS:
        if not plan.first_slice_contract.get(field_name, "").strip():
            blocked_reasons.append(
                ReadinessIssue(
                    code="missing-first-slice-field",
                    message=f"Missing required First Slice field: {field_name}",
                    field=field_name,
                )
            )

    if blocked_reasons:
        return ReadinessResult(
            status=ReadinessStatus.BLOCKED,
            reasons=tuple(blocked_reasons),
        )

    for field_name in LIST_FIELDS:
        if not is_markdown_list_block(plan.first_slice_contract[field_name]):
            blocked_reasons.append(
                ReadinessIssue(
                    code="invalid-list-field",
                    message=f"First Slice field must use Markdown list items: {field_name}",
                    field=field_name,
                )
            )

    for field_name in ("White-box Needed", "Write-back Needed"):
        if not _starts_with_yes_or_no(plan.first_slice_contract[field_name]):
            blocked_reasons.append(
                ReadinessIssue(
                    code="invalid-choice-field",
                    message=f"First Slice field must start with Yes or No: {field_name}",
                    field=field_name,
                )
            )

    if blocked_reasons:
        return ReadinessResult(
            status=ReadinessStatus.BLOCKED,
            reasons=tuple(blocked_reasons),
        )

    clarification_reasons: list[ReadinessIssue] = []
    for section_name in REQUIRED_PLAN_SECTIONS:
        if section_name == "First Slice":
            continue
        if _contains_placeholder_text(plan.sections[section_name]):
            clarification_reasons.append(
                ReadinessIssue(
                    code="placeholder-plan-section",
                    message=f"Plan section needs clarification before spec compilation: {section_name}",
                    field=section_name,
                )
            )

    for field_name in FIRST_SLICE_FIELDS:
        if _contains_placeholder_text(plan.first_slice_contract[field_name]):
            clarification_reasons.append(
                ReadinessIssue(
                    code="placeholder-first-slice-field",
                    message=f"First Slice field needs clarification before spec compilation: {field_name}",
                    field=field_name,
                )
            )

    if clarification_reasons:
        return ReadinessResult(
            status=ReadinessStatus.NEEDS_CLARIFICATION,
            reasons=tuple(clarification_reasons),
        )

    return ReadinessResult(status=ReadinessStatus.READY)


def _contains_placeholder_text(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return False
    return any(pattern.search(normalized) for pattern in _PLACEHOLDER_PATTERNS)


def _starts_with_yes_or_no(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized.startswith("yes") or normalized.startswith("no")
