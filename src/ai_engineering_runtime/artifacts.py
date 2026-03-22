from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
import re

REQUIRED_PLAN_SECTIONS = (
    "Problem",
    "Goal",
    "Non-goals",
    "Constraints",
    "Proposed Approach",
    "Risks",
    "Phase Split",
    "First Slice",
)

FIRST_SLICE_FIELDS = (
    "Spec Title",
    "In Scope",
    "Out of Scope",
    "Affected Area",
    "Task Checklist",
    "Done When",
    "Black-box Checks",
    "White-box Needed",
    "White-box Trigger",
    "Internal Logic To Protect",
    "Write-back Needed",
    "Risks / Notes",
)

LIST_FIELDS = frozenset(
    {
        "In Scope",
        "Out of Scope",
        "Affected Area",
        "Task Checklist",
        "Black-box Checks",
    }
)

REQUIRED_TASK_SPEC_SECTIONS = (
    "Metadata",
    "Goal",
    "In Scope",
    "Out of Scope",
    "Affected Area",
    "Task Checklist",
    "Done When",
    "Validation",
    "Write-back Needed",
    "Risks / Notes",
)

TASK_SPEC_METADATA_FIELDS = (
    "Source Plan / Request",
    "Status",
)

TASK_SPEC_VALIDATION_FIELDS = (
    "Black-box Checks",
    "White-box Needed",
    "White-box Trigger",
    "Internal Logic To Protect",
)

TASK_SPEC_LIST_FIELDS = frozenset(
    {
        "In Scope",
        "Out of Scope",
        "Affected Area",
        "Task Checklist",
        "Black-box Checks",
    }
)

ALLOWED_TASK_SPEC_STATUSES = frozenset({"draft", "in-progress", "blocked", "done"})
EXECUTABLE_TASK_SPEC_STATUSES = frozenset({"draft", "in-progress"})

_HEADING_RE = re.compile(r"^(#{2,6})\s+(.*?)\s*$")
_BULLET_RE = re.compile(r"^[-*]\s+")
_CHECKBOX_RE = re.compile(r"^[-*]\s+\[[ xX]\]\s+")
_ORDERED_RE = re.compile(r"^\d+\.\s+")
_SPEC_NAME_RE = re.compile(r"^(?P<date>\d{8})-(?P<seq>\d{3})-(?P<slug>.+)\.md$")


class ArtifactKind(str, Enum):
    PLAN = "plan"
    TASK_SPEC = "task-spec"
    FACT = "fact"
    SKILL = "skill"
    CHANGE_SUMMARY = "change-summary"


@dataclass(frozen=True)
class ArtifactRef:
    kind: ArtifactKind
    path: Path


@dataclass(frozen=True)
class PlanArtifact:
    path: Path
    title: str
    sections: dict[str, str]
    first_slice_contract: dict[str, str]
    raw_text: str = ""

    @classmethod
    def from_markdown(cls, path: Path, text: str) -> "PlanArtifact":
        sections = parse_markdown_sections(text, level=2)
        first_slice = parse_markdown_sections(sections.get("First Slice", ""), level=3)
        return cls(
            path=path.resolve(),
            title=extract_markdown_title(text, fallback=path.stem.replace("-", " ").title()),
            sections=sections,
            first_slice_contract=first_slice,
            raw_text=text,
        )


@dataclass(frozen=True)
class TaskSpecDraft:
    title: str
    source_plan_path: Path
    goal: str
    in_scope: list[str]
    out_of_scope: list[str]
    affected_area: list[str]
    task_checklist: list[str]
    done_when: str
    black_box_checks: list[str]
    white_box_needed: str
    white_box_trigger: str
    internal_logic_to_protect: str
    write_back_needed: str
    risks_notes: str
    status: str = "draft"
    related_specs: list[str] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return slugify(self.title)

    def render(self, source_plan_label: str) -> str:
        lines = [
            f"# {self.title}",
            "",
            "## Metadata",
            "",
            "### Source Plan / Request",
            f"`{source_plan_label}`",
            "",
            "### Status",
            f"`{self.status}`",
            "",
            "### Related Specs",
        ]

        if self.related_specs:
            lines.extend(f"- {item}" for item in self.related_specs)
        else:
            lines.append("None.")

        lines.extend(
            [
                "",
                "## Goal",
                self.goal,
                "",
                "## In Scope",
                *_render_list(self.in_scope),
                "",
                "## Out of Scope",
                *_render_list(self.out_of_scope),
                "",
                "## Affected Area",
                *_render_list(self.affected_area),
                "",
                "## Task Checklist",
                *_render_list(self.task_checklist, checkbox=True),
                "",
                "## Done When",
                self.done_when,
                "",
                "## Validation",
                "",
                "### Black-box Checks",
                *_render_list(self.black_box_checks),
                "",
                "### White-box Needed",
                self.white_box_needed,
                "",
                "### White-box Trigger",
                self.white_box_trigger,
                "",
                "### Internal Logic To Protect",
                self.internal_logic_to_protect,
                "",
                "## Write-back Needed",
                self.write_back_needed,
                "",
                "## Risks / Notes",
                self.risks_notes,
                "",
            ]
        )
        return "\n".join(lines)


@dataclass(frozen=True)
class TaskSpecArtifact:
    path: Path
    title: str
    sections: dict[str, str]
    metadata: dict[str, str]
    validation: dict[str, str]
    raw_text: str = ""

    @classmethod
    def from_markdown(cls, path: Path, text: str) -> "TaskSpecArtifact":
        sections = parse_markdown_sections(text, level=2)
        metadata = parse_markdown_sections(sections.get("Metadata", ""), level=3)
        validation = parse_markdown_sections(sections.get("Validation", ""), level=3)
        return cls(
            path=path.resolve(),
            title=extract_markdown_title(text, fallback=path.stem.replace("-", " ").title()),
            sections=sections,
            metadata=metadata,
            validation=validation,
            raw_text=text,
        )

    @property
    def status(self) -> str:
        return normalize_inline_code(self.metadata.get("Status", ""))


def discover_artifacts(repo_root: Path) -> list[ArtifactRef]:
    root = repo_root.resolve()
    artifacts: list[ArtifactRef] = []

    roadmap = root / "docs" / "runtime" / "roadmap.md"
    if roadmap.exists():
        artifacts.append(ArtifactRef(kind=ArtifactKind.PLAN, path=roadmap))

    artifacts.extend(_discover_glob(root / "docs" / "specs", "*.md", ArtifactKind.TASK_SPEC))
    artifacts.extend(_discover_glob(root / "docs" / "facts", "*.md", ArtifactKind.FACT))
    artifacts.extend(_discover_glob(root / "skills", "*.md", ArtifactKind.SKILL))

    for summary_dir in (root / "docs" / "change-summaries", root / "docs" / "summaries"):
        artifacts.extend(_discover_glob(summary_dir, "*.md", ArtifactKind.CHANGE_SUMMARY))

    return artifacts


def extract_markdown_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def parse_markdown_sections(text: str, level: int) -> dict[str, str]:
    sections: dict[str, str] = {}
    current_title: str | None = None
    buffer: list[str] = []

    for line in text.splitlines():
        match = _HEADING_RE.match(line)
        if match and len(match.group(1)) == level:
            if current_title is not None:
                sections[current_title] = "\n".join(buffer).strip()
            current_title = match.group(2).strip()
            buffer = []
            continue

        if current_title is not None:
            buffer.append(line)

    if current_title is not None:
        sections[current_title] = "\n".join(buffer).strip()

    return sections


def parse_list_block(text: str) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not _is_markdown_list_item(stripped):
            continue
        stripped = _strip_list_marker(stripped)
        items.append(stripped)
    return items


def is_markdown_list_block(text: str) -> bool:
    saw_item = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not _is_markdown_list_item(stripped):
            return False
        saw_item = True
    return saw_item


def next_task_spec_path(specs_dir: Path, created_on: date, slug: str) -> Path:
    specs_dir.mkdir(parents=True, exist_ok=True)
    day_prefix = created_on.strftime("%Y%m%d")
    highest = 0

    for path in specs_dir.glob(f"{day_prefix}-*.md"):
        match = _SPEC_NAME_RE.match(path.name)
        if not match:
            continue
        highest = max(highest, int(match.group("seq")))

    return specs_dir / f"{day_prefix}-{highest + 1:03d}-{slug}.md"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "task"


def normalize_inline_code(text: str) -> str:
    normalized = text.strip()
    if normalized.startswith("`") and normalized.endswith("`") and len(normalized) >= 2:
        return normalized[1:-1].strip()
    return normalized


def _discover_glob(directory: Path, pattern: str, kind: ArtifactKind) -> list[ArtifactRef]:
    if not directory.exists():
        return []
    return [ArtifactRef(kind=kind, path=path.resolve()) for path in sorted(directory.glob(pattern))]


def _render_list(items: list[str], *, checkbox: bool = False) -> list[str]:
    prefix = "- [ ] " if checkbox else "- "
    return [f"{prefix}{item}" for item in items]


def _is_markdown_list_item(text: str) -> bool:
    return bool(_CHECKBOX_RE.match(text) or _BULLET_RE.match(text) or _ORDERED_RE.match(text))


def _strip_list_marker(text: str) -> str:
    text = _CHECKBOX_RE.sub("", text)
    text = _BULLET_RE.sub("", text)
    text = _ORDERED_RE.sub("", text)
    return text
