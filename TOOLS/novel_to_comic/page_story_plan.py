"""Validation helpers for reader-first manga page story plans."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_PLAN_FIELDS = [
    "chapter",
    "status",
    "page_count_policy",
    "actual_page_count",
    "reader_promise",
    "must_include",
    "asset_gaps_before_director_briefs",
    "pages",
]

REQUIRED_PAGE_FIELDS = [
    "page",
    "source_span",
    "story_job",
    "reader_enters_with",
    "reader_leaves_with",
    "beats",
    "tone",
    "info_density",
    "handoff",
]


def check_page_story_plan(path: str | Path) -> dict[str, Any]:
    plan_path = Path(path)
    issues: list[dict[str, str]] = []
    plan = _read_plan(plan_path, issues)
    if plan is None:
        return _result(plan_path, {}, issues)

    for field in REQUIRED_PLAN_FIELDS:
        if field not in plan:
            issues.append({"file": str(plan_path), "issue": f"missing plan field: {field}"})

    if plan.get("page_count_policy") != "story_first_variable":
        issues.append({"file": str(plan_path), "issue": "page_count_policy must be story_first_variable"})

    pages = plan.get("pages")
    if not isinstance(pages, list) or not pages:
        issues.append({"file": str(plan_path), "issue": "pages must be a non-empty list"})
        pages = []

    declared_count = plan.get("actual_page_count")
    if declared_count != len(pages):
        issues.append(
            {
                "file": str(plan_path),
                "issue": f"actual_page_count must equal pages length ({declared_count!r} != {len(pages)})",
            }
        )

    if not isinstance(plan.get("must_include"), list) or not plan.get("must_include"):
        issues.append({"file": str(plan_path), "issue": "must_include must list source beats that cannot be dropped"})

    asset_gaps = plan.get("asset_gaps_before_director_briefs")
    if not isinstance(asset_gaps, list):
        issues.append({"file": str(plan_path), "issue": "asset_gaps_before_director_briefs must be a list"})
    else:
        for index, gap in enumerate(asset_gaps, start=1):
            if not isinstance(gap, dict):
                issues.append({"file": str(plan_path), "issue": f"asset gap {index} must be an object"})
                continue
            for field in ("id", "need", "risk"):
                if not _has_text(gap.get(field)):
                    issues.append({"file": str(plan_path), "issue": f"asset gap {index} missing {field}"})

    _check_pages(plan_path, pages, issues)
    return _result(plan_path, plan, issues)


def _read_plan(path: Path, issues: list[dict[str, str]]) -> dict[str, Any] | None:
    if not path.exists():
        issues.append({"file": str(path), "issue": "page story plan not found"})
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        issues.append({"file": str(path), "issue": f"invalid JSON: {error.msg}"})
        return None
    if not isinstance(data, dict):
        issues.append({"file": str(path), "issue": "page story plan must be a JSON object"})
        return None
    return data


def _check_pages(path: Path, pages: list[Any], issues: list[dict[str, str]]) -> None:
    seen_numbers: set[int] = set()
    for index, page in enumerate(pages, start=1):
        page_label = f"page {index}"
        if not isinstance(page, dict):
            issues.append({"file": str(path), "issue": f"{page_label} must be an object"})
            continue
        for field in REQUIRED_PAGE_FIELDS:
            value = page.get(field)
            if field == "beats":
                if not isinstance(value, list) or not value or not all(_has_text(item) for item in value):
                    issues.append({"file": str(path), "issue": f"{page_label} missing useful beats"})
            elif field == "page":
                if not isinstance(value, int):
                    issues.append({"file": str(path), "issue": f"{page_label} missing numeric page"})
            elif not _has_text(value):
                issues.append({"file": str(path), "issue": f"{page_label} missing {field}"})

        page_number = page.get("page")
        if isinstance(page_number, int):
            if page_number in seen_numbers:
                issues.append({"file": str(path), "issue": f"duplicate page number: {page_number}"})
            seen_numbers.add(page_number)
            if page_number != index:
                issues.append({"file": str(path), "issue": f"page numbers must be sequential; expected {index}, got {page_number}"})

        if _looks_like_vague_summary(page.get("story_job")):
            issues.append({"file": str(path), "issue": f"{page_label} story_job is too vague for manga adaptation"})


def _looks_like_vague_summary(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower()
    vague_jobs = {
        "introduce everything quickly",
        "tell the story",
        "explain the chapter",
        "show what happens",
        "lore montage",
    }
    return normalized in vague_jobs


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _result(path: Path, plan: dict[str, Any], issues: list[dict[str, str]]) -> dict[str, Any]:
    pages = plan.get("pages") if isinstance(plan.get("pages"), list) else []
    return {
        "path": str(path),
        "status": "pass" if not issues else "needs_fix",
        "actual_page_count": len(pages),
        "declared_page_count": plan.get("actual_page_count"),
        "issues": issues,
    }
