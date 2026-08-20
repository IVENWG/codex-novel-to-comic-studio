"""Image QC for single_scene drafts: PASS / RETRY / MANUAL_REVIEW.

Rule-based checks run everywhere (size, blank image, reference metadata).
Semantic checks (identity drift, outfit, setting, hands, style drift, beat
match, continuity) are delegated to an optional VLM provider; without one the
corresponding checks are marked `unverified` and, in strict mode, force
MANUAL_REVIEW instead of silently passing.

QC results drive Targeted Regeneration: only the broken aspect is corrected.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from .scenes import write_json


VERDICTS = ["PASS", "RETRY", "MANUAL_REVIEW"]

QC_RELPATH_TEMPLATE = "qc/{scene_id}.qc.json"

DEFAULT_MAX_RETRY = 3

# QC check categories mapped to targeted correction emphasis.
CORRECTION_MAP = {
    "identity": {"emphasis": ["identity reference weight", "face and hair match"], "lock": "identity"},
    "outfit": {"emphasis": ["outfit reference match"], "lock": "outfit"},
    "setting": {"emphasis": ["environment reference match", "location layout"], "lock": "setting"},
    "prop": {"emphasis": ["prop reference match"], "lock": "prop"},
    "hands": {"emphasis": ["clean hands and fingers"], "lock": None},
    "style_drift": {"emphasis": ["style reference match"], "lock": "style"},
    "beat": {"emphasis": ["scene action match"], "lock": None},
    "continuity": {"emphasis": ["continuity with adjacent scenes"], "lock": None},
    "composition": {"emphasis": ["composition and character count"], "lock": None},
}

SEMANTIC_CHECKS = [
    "identity",
    "face",
    "hair",
    "age",
    "body_proportions",
    "outfit",
    "weapon",
    "injury",
    "setting",
    "character_count",
    "action",
    "expression",
    "props",
    "hands_feet",
    "style_drift",
    "story_beat",
    "continuity",
]


def qc_scene_image(
    image_path: str | Path,
    brief: dict[str, Any],
    *,
    expected_size: tuple[int, int] = (1024, 1536),
    vlm: Any = None,
    strict: bool = False,
) -> dict[str, Any]:
    """Run QC for one generated draft image against its director brief."""
    image_path = Path(image_path)
    checks: list[dict[str, Any]] = []

    if not image_path.exists():
        checks.append({"check": "file_exists", "status": "fail", "detail": f"missing {image_path}"})
        return _verdict(brief.get("scene_id", "?"), checks, retries_hint=True)

    with Image.open(image_path) as image:
        if image.size != tuple(expected_size):
            checks.append(
                {
                    "check": "size",
                    "status": "fail",
                    "detail": f"{image.size[0]}x{image.size[1]}, expected {expected_size[0]}x{expected_size[1]}",
                }
            )
        else:
            checks.append({"check": "size", "status": "pass"})

        coverage = _content_coverage(image.convert("RGB"))
        if coverage < 0.35:
            checks.append({"check": "blank_image", "status": "fail", "detail": f"coverage {coverage:.2f}"})
        else:
            checks.append({"check": "blank_image", "status": "pass", "detail": f"coverage {coverage:.2f}"})

    # Reference lock: the renderer must have received the brief's references.
    references = brief.get("references", [])
    metadata = _read_png_metadata(image_path)
    if references:
        recorded = metadata.get("ntc:references", "")
        missing = [ref["role"] for ref in references if ref["role"] not in recorded]
        if missing:
            checks.append({"check": "references_applied", "status": "fail", "detail": f"missing {missing}"})
        else:
            checks.append({"check": "references_applied", "status": "pass"})

    if vlm is not None:
        checks.extend(vlm.review(image_path, brief, SEMANTIC_CHECKS))
    else:
        for check_name in ("identity", "outfit", "setting", "hands_feet", "style_drift", "story_beat", "continuity"):
            checks.append({"check": check_name, "status": "unverified", "detail": "no VLM provider configured"})

    result = _verdict(brief.get("scene_id", "?"), checks, retries_hint=True, strict=strict)
    return result


def save_qc_report(chapter_dir: str | Path, report: dict[str, Any]) -> Path:
    scene_id = report["scene_id"]
    path = Path(chapter_dir) / QC_RELPATH_TEMPLATE.format(scene_id=scene_id)
    write_json(path, report)
    return path


def load_qc_report(chapter_dir: str | Path, scene_id: str) -> dict[str, Any] | None:
    path = Path(chapter_dir) / QC_RELPATH_TEMPLATE.format(scene_id=scene_id)
    if not path.exists():
        return None
    from .scenes import load_json

    return load_json(path)


def plan_targeted_regeneration(qc_report: dict[str, Any]) -> dict[str, Any]:
    """Turn QC failures into a correction reason + targeted emphasis.

    Never rebuild the prompt from scratch: keep the previous brief and only
    strengthen the failing aspect (outfit wrong -> re-lock outfit, face drift
    -> raise identity weight, ...).
    """
    failed = [
        check for check in qc_report.get("checks", [])
        if check.get("status") == "fail"
    ]
    if not failed:
        return {"needed": False, "correction_reason": "", "emphasis": []}

    emphasis: list[str] = []
    locks: list[str] = []
    reasons: list[str] = []
    for check in failed:
        category = _categorize(check.get("check", ""))
        plan = CORRECTION_MAP.get(category)
        if plan:
            emphasis.extend(plan["emphasis"])
            if plan["lock"]:
                locks.append(plan["lock"])
        reasons.append(f"{check.get('check')}: {check.get('detail', '')}")

    return {
        "needed": True,
        "correction_reason": "; ".join(reasons),
        "emphasis": _dedupe(emphasis),
        "relock": _dedupe(locks),
    }


def decide_verdict(retry_count: int, max_retry: int, qc_report: dict[str, Any]) -> str:
    """Enforce bounded retries: exceed max_retry -> MANUAL_REVIEW, never loop."""
    if qc_report.get("verdict") == "PASS":
        return "PASS"
    if retry_count >= max_retry:
        return "MANUAL_REVIEW"
    return "RETRY"


def _verdict(scene_id: str, checks: list[dict[str, Any]], *, retries_hint: bool = True, strict: bool = False) -> dict[str, Any]:
    failures = [check for check in checks if check.get("status") == "fail"]
    unverified = [check for check in checks if check.get("status") == "unverified"]
    if failures:
        verdict = "RETRY"
    elif unverified and strict:
        verdict = "MANUAL_REVIEW"
    else:
        verdict = "PASS"
    return {"scene_id": scene_id, "verdict": verdict, "checks": checks, "retry_hint": retries_hint}


def _categorize(check_name: str) -> str:
    if check_name in {"identity", "face", "hair", "age", "body_proportions"}:
        return "identity"
    if check_name in {"outfit",}:
        return "outfit"
    if check_name in {"setting",}:
        return "setting"
    if check_name in {"weapon", "props"}:
        return "prop"
    if check_name in {"hands_feet",}:
        return "hands"
    if check_name in {"style_drift",}:
        return "style_drift"
    if check_name in {"story_beat", "action", "expression"}:
        return "beat"
    if check_name in {"continuity",}:
        return "continuity"
    if check_name in {"character_count", "composition", "size", "blank_image", "references_applied"}:
        return "composition"
    return "composition"


def _content_coverage(image: Image.Image) -> float:
    gray = image.convert("L")
    histogram = gray.histogram()
    total = sum(histogram)
    if not total:
        return 0.0
    extremes = histogram[0] + histogram[-1]
    return 1.0 - extremes / total


def _read_png_metadata(image_path: Path) -> dict[str, str]:
    try:
        with Image.open(image_path) as image:
            return dict(image.text) if getattr(image, "text", None) else {}
    except Exception:
        return {}


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique
