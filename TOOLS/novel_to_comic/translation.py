"""Scene-level Chinese -> English translation with terminology control.

Hard rule: translation is per scene (scene_0001.zh -> scene_0001.en). The
whole novel must never be translated in one pass and re-split afterwards,
because zh text / image / en text / TTS must keep pointing at the same
scene_id.

Actual translation is produced by the agent/LLM following the skill contract;
this module manages files, terminology enforcement and mapping validation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .scenes import load_json, write_json


TERMINOLOGY_RELPATH = Path("translation") / "terminology.json"
TRANSLATION_DIRNAME = "translation"

TERMINOLOGY_CATEGORIES = ["characters", "locations", "skills", "organizations", "props", "titles"]


def terminology_path(root: str | Path) -> Path:
    return Path(root) / TERMINOLOGY_RELPATH


def load_terminology(root: str | Path) -> dict[str, Any]:
    path = terminology_path(root)
    if not path.exists():
        return {category: {} for category in TERMINOLOGY_CATEGORIES}
    return load_json(path)


def save_terminology(root: str | Path, terminology: dict[str, Any]) -> None:
    write_json(terminology_path(root), terminology)


def validate_terminology(terminology: dict[str, Any]) -> list[str]:
    """One zh term must map to exactly one en rendering across the whole novel.

    Values are either a plain en string or an object `{"en": ..., "avoid": [...]}`.
    """
    errors: list[str] = []
    for category in TERMINOLOGY_CATEGORIES:
        bucket = terminology.get(category, {})
        if not isinstance(bucket, dict):
            errors.append(f"terminology.{category} must be an object")
            continue
        for zh_term, value in bucket.items():
            if isinstance(value, str):
                if not value.strip():
                    errors.append(f"terminology.{category}[{zh_term}] must be a non-empty string")
            elif isinstance(value, dict):
                if not isinstance(value.get("en"), str) or not value["en"].strip():
                    errors.append(f"terminology.{category}[{zh_term}].en must be a non-empty string")
            else:
                errors.append(f"terminology.{category}[{zh_term}] must be a string or object")
    return errors


def all_terms(terminology: dict[str, Any]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for category in TERMINOLOGY_CATEGORIES:
        bucket = terminology.get(category, {})
        if not isinstance(bucket, dict):
            continue
        for zh_term, value in bucket.items():
            if isinstance(value, str):
                merged[zh_term] = value
            elif isinstance(value, dict) and isinstance(value.get("en"), str):
                merged[zh_term] = value["en"]
    return merged


def check_terminology_applied(en_text: str, terminology: dict[str, Any]) -> list[str]:
    """Flag obvious wrong romanizations: known zh names rendered differently.

    Heuristic: if the zh source term appears nowhere in the terminology-based
    check, we cannot verify; when an en text contains an alternative spelling
    listed in terminology `aliases` (optional), flag it.
    """
    errors: list[str] = []
    lowered = en_text.lower()
    for zh_term, en_term in all_terms(terminology).items():
        aliases = []
        for category in TERMINOLOGY_CATEGORIES:
            bucket = terminology.get(category, {})
            if isinstance(bucket, dict) and isinstance(bucket.get(zh_term), dict):
                aliases = bucket[zh_term].get("avoid", [])
        for alias in aliases:
            if isinstance(alias, str) and alias.lower() in lowered and en_term.lower() not in lowered:
                errors.append(f"'{alias}' used but terminology requires '{en_term}' for {zh_term}")
    return errors


def translation_file(chapter_dir: str | Path, scene_id: str) -> Path:
    return Path(chapter_dir) / TRANSLATION_DIRNAME / f"{scene_id}.json"


def save_scene_translation(chapter_dir: str | Path, entry: dict[str, Any]) -> Path:
    scene_id = entry.get("scene_id")
    if not scene_id:
        raise ValueError("translation entry needs scene_id")
    path = translation_file(chapter_dir, scene_id)
    write_json(path, entry)
    return path


def load_scene_translation(chapter_dir: str | Path, scene_id: str) -> dict[str, Any] | None:
    path = translation_file(chapter_dir, scene_id)
    if not path.exists():
        return None
    return load_json(path)


def validate_translation_mapping(chapter_dir: str | Path, narration_doc: dict[str, Any]) -> list[str]:
    """Every narration scene must have a translation with matching zh text."""
    errors: list[str] = []
    for scene in narration_doc.get("scenes", []):
        scene_id = scene.get("scene_id")
        entry = load_scene_translation(chapter_dir, scene_id)
        if entry is None:
            errors.append(f"{scene_id}: missing translation file")
            continue
        if entry.get("scene_id") != scene_id:
            errors.append(f"{scene_id}: translation file scene_id mismatch")
        if entry.get("zh_text") != scene.get("zh_narration"):
            errors.append(f"{scene_id}: zh_text drifted from narration; retranslate this scene")
        if not (entry.get("en_text") or "").strip():
            errors.append(f"{scene_id}: en_text empty")
        if entry.get("status") not in {"PASS", "REVIEW"}:
            errors.append(f"{scene_id}: translation status is {entry.get('status')}, expected PASS")
    return errors
