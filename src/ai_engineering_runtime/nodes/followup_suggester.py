from __future__ import annotations

from dataclasses import dataclass

from ai_engineering_runtime.adapters import FileSystemAdapter
from ai_engineering_runtime.engine import RunResult
from ai_engineering_runtime.state import (
    CloseoutHint,
    FollowupAction,
    FollowupResult,
    ReadinessStatus,
    RuntimeReason,
    ValidationStatus,
    WritebackDestination,
    followup_transition,
)


@dataclass(frozen=True)
class FollowupSuggesterRequest:
    readiness_status: ReadinessStatus | None = None
    validation_status: ValidationStatus | None = None
    writeback_destination: WritebackDestination | None = None
    closeout_hint: CloseoutHint | None = None


class FollowupSuggesterNode:
    name = "followup-suggester"

    def __init__(self, request: FollowupSuggesterRequest):
        self.request = request

    def execute(self, adapter: FileSystemAdapter) -> RunResult:
        if (
            self.request.readiness_status is None
            and self.request.validation_status is None
            and self.request.writeback_destination is None
            and self.request.closeout_hint is None
        ):
            result = RunResult(
                node_name=self.name,
                success=False,
                from_state=followup_transition(
                    FollowupResult(
                        action=FollowupAction.IMPLEMENT_NEXT_TASK,
                        explanation="placeholder",
                    )
                ).from_state,
                to_state=followup_transition(
                    FollowupResult(
                        action=FollowupAction.FIX_VALIDATION_FAILURE,
                        explanation="placeholder",
                    )
                ).to_state,
                issues=(
                    RuntimeReason(
                        code="missing-followup-signal",
                        message="At least one readiness, validation, write-back, or closeout signal is required.",
                    ),
                ),
            )
            log_path = adapter.build_run_log_path(self.name)
            result = result.with_log_path(log_path)
            adapter.write_json(log_path, result.to_log_record(adapter))
            return result

        followup = suggest_followup(self.request)
        transition = followup_transition(followup)
        result = RunResult(
            node_name=self.name,
            success=True,
            from_state=transition.from_state,
            to_state=transition.to_state,
            issues=transition.issues,
            followup=followup,
        )
        log_path = adapter.build_run_log_path(self.name)
        result = result.with_log_path(log_path)
        adapter.write_json(log_path, result.to_log_record(adapter))
        return result


def suggest_followup(request: FollowupSuggesterRequest) -> FollowupResult:
    if request.readiness_status in {
        ReadinessStatus.BLOCKED,
        ReadinessStatus.NEEDS_CLARIFICATION,
    }:
        if request.readiness_status is ReadinessStatus.BLOCKED:
            reason = RuntimeReason(
                code="readiness-blocked",
                message="Readiness signals indicate a blocking issue that must be clarified before execution can continue.",
            )
        else:
            reason = RuntimeReason(
                code="readiness-needs-clarification",
                message="Readiness signals indicate the plan or spec still needs clarification before execution can continue.",
            )
        return FollowupResult(
            action=FollowupAction.CLARIFY_PLAN,
            explanation="Clarify the plan or spec before continuing.",
            reasons=(reason,),
        )

    if request.validation_status in {
        ValidationStatus.FAILED,
        ValidationStatus.INCOMPLETE,
    }:
        code = (
            "validation-failed"
            if request.validation_status is ValidationStatus.FAILED
            else "validation-incomplete"
        )
        message = (
            "Validation failed and needs a fix-oriented next task."
            if request.validation_status is ValidationStatus.FAILED
            else "Validation is incomplete and needs a fix-oriented next task."
        )
        return FollowupResult(
            action=FollowupAction.FIX_VALIDATION_FAILURE,
            explanation="Prioritize a fix-oriented task before moving on.",
            reasons=(RuntimeReason(code=code, message=message),),
        )

    if request.writeback_destination is WritebackDestination.FACTS:
        return FollowupResult(
            action=FollowupAction.WRITE_BACK_STABLE_CONTEXT,
            explanation="Persist the stable project context before closing out.",
            reasons=(
                RuntimeReason(
                    code="writeback-facts",
                    message="Write-back classification indicates durable project context.",
                ),
            ),
        )

    if request.writeback_destination is WritebackDestination.SKILLS:
        return FollowupResult(
            action=FollowupAction.PROMOTE_SKILL_CANDIDATE,
            explanation="Capture the reusable workflow pattern as a skill candidate.",
            reasons=(
                RuntimeReason(
                    code="writeback-skills",
                    message="Write-back classification indicates a reusable workflow pattern.",
                ),
            ),
        )

    if request.closeout_hint is CloseoutHint.COMPLETE:
        return FollowupResult(
            action=FollowupAction.NO_FOLLOWUP_NEEDED,
            explanation="The supplied closeout hint supports a clean stop with no immediate next action.",
            reasons=(
                RuntimeReason(
                    code="closeout-complete",
                    message="Explicit closeout hint indicates no immediate follow-up is needed.",
                ),
            ),
        )

    return FollowupResult(
        action=FollowupAction.IMPLEMENT_NEXT_TASK,
        explanation="Continue with the next narrow task.",
        reasons=(
            RuntimeReason(
                code="default-next-task",
                message="No higher-priority clarification, validation, or write-back signal was supplied.",
            ),
        ),
    )
