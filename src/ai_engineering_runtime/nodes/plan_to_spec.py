from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from ai_engineering_runtime.adapters import FileSystemAdapter
from ai_engineering_runtime.artifacts import (
    FIRST_SLICE_FIELDS,
    LIST_FIELDS,
    REQUIRED_PLAN_SECTIONS,
    PlanArtifact,
    TaskSpecDraft,
    discover_artifacts,
    is_markdown_list_block,
    next_task_spec_path,
    parse_list_block,
)
from ai_engineering_runtime.engine import RunResult
from ai_engineering_runtime.state import ReadinessIssue, plan_to_spec_transition


@dataclass(frozen=True)
class PlanToSpecRequest:
    plan_path: Path
    dry_run: bool = False
    output_path: Path | None = None
    created_on: date = field(default_factory=date.today)


class PlanToSpecNode:
    name = "plan-to-spec"

    def __init__(self, request: PlanToSpecRequest):
        self.request = request

    def execute(self, adapter: FileSystemAdapter) -> RunResult:
        plan_path = adapter.resolve(self.request.plan_path)
        discovered = discover_artifacts(adapter.repo_root)
        issues: list[ReadinessIssue] = []
        rendered_output: str | None = None
        output_path: Path | None = None

        if not plan_path.exists():
            issues.append(
                ReadinessIssue(
                    code="missing-plan",
                    message=f"Plan not found: {adapter.display_path(plan_path)}",
                )
            )
        else:
            plan = PlanArtifact.from_markdown(plan_path, adapter.read_text(plan_path))
            issues.extend(self._validate_plan(plan))

            if not issues:
                draft = self._build_task_spec(plan)
                output_path = (
                    adapter.resolve(self.request.output_path)
                    if self.request.output_path is not None
                    else next_task_spec_path(
                        adapter.repo_root / "docs" / "specs",
                        self.request.created_on,
                        draft.slug,
                    )
                )
                if self.request.output_path is not None and output_path.exists() and not self.request.dry_run:
                    issues.append(
                        ReadinessIssue(
                            code="output-exists",
                            message=f"Output already exists: {adapter.display_path(output_path)}",
                        )
                    )
                else:
                    rendered_output = draft.render(adapter.display_path(plan.path))

        transition = plan_to_spec_transition(issues)
        success = not issues

        if success and rendered_output is not None and output_path is not None and not self.request.dry_run:
            adapter.write_text(output_path, rendered_output)

        result = RunResult(
            node_name=self.name,
            success=success,
            from_state=transition.from_state,
            to_state=transition.to_state,
            issues=transition.issues,
            plan_path=plan_path,
            output_path=output_path,
            rendered_output=rendered_output,
            metadata={
                "artifact_count": len(discovered),
                "dry_run": self.request.dry_run,
            },
        )
        log_path = adapter.build_run_log_path(self.name)
        result = result.with_log_path(log_path)
        adapter.write_json(log_path, result.to_log_record(adapter))
        return result

    def _validate_plan(self, plan: PlanArtifact) -> list[ReadinessIssue]:
        issues: list[ReadinessIssue] = []

        for section in REQUIRED_PLAN_SECTIONS:
            if not plan.sections.get(section, "").strip():
                issues.append(
                    ReadinessIssue(
                        code="missing-plan-section",
                        message=f"Missing required plan section: {section}",
                    )
                )

        for field_name in FIRST_SLICE_FIELDS:
            if not plan.first_slice_contract.get(field_name, "").strip():
                issues.append(
                    ReadinessIssue(
                        code="missing-first-slice-field",
                        message=f"Missing required First Slice field: {field_name}",
                    )
                )

        if issues:
            return issues

        for field_name in LIST_FIELDS:
            if not is_markdown_list_block(plan.first_slice_contract[field_name]):
                issues.append(
                    ReadinessIssue(
                        code="invalid-list-field",
                        message=f"First Slice field must use Markdown list items: {field_name}",
                    )
                )

        for field_name in ("White-box Needed", "Write-back Needed"):
            if not _starts_with_yes_or_no(plan.first_slice_contract[field_name]):
                issues.append(
                    ReadinessIssue(
                        code="invalid-choice-field",
                        message=f"First Slice field must start with Yes or No: {field_name}",
                    )
                )

        return issues

    def _build_task_spec(self, plan: PlanArtifact) -> TaskSpecDraft:
        contract = plan.first_slice_contract
        return TaskSpecDraft(
            title=contract["Spec Title"].strip(),
            source_plan_path=plan.path,
            goal=plan.sections["Goal"].strip(),
            in_scope=parse_list_block(contract["In Scope"]),
            out_of_scope=parse_list_block(contract["Out of Scope"]),
            affected_area=parse_list_block(contract["Affected Area"]),
            task_checklist=parse_list_block(contract["Task Checklist"]),
            done_when=contract["Done When"].strip(),
            black_box_checks=parse_list_block(contract["Black-box Checks"]),
            white_box_needed=contract["White-box Needed"].strip(),
            white_box_trigger=contract["White-box Trigger"].strip(),
            internal_logic_to_protect=contract["Internal Logic To Protect"].strip(),
            write_back_needed=contract["Write-back Needed"].strip(),
            risks_notes=contract["Risks / Notes"].strip(),
        )


def _starts_with_yes_or_no(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized.startswith("yes") or normalized.startswith("no")
