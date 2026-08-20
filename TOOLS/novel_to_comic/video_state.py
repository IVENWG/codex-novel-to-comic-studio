"""Video pipeline state: per-scene step status, stale detection, resume and
single-scene regeneration planning.

Statuses: MISSING, READY, RUNNING, PASS, STALE, FAILED, MANUAL_REVIEW.

Everything is derived from the filesystem (filesystem-first), so a rerun can
always answer "what is the next unfinished scene?" without hidden state.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .scene_manifest import load_manifest, scene_is_pass
from .scenes import load_json, load_narration_scenes


STATUSES = ["MISSING", "READY", "RUNNING", "PASS", "STALE", "FAILED", "MANUAL_REVIEW"]

SCENE_STEPS = [
    "director",
    "draft_image",
    "image_qc",
    "upscale",
    "translation",
    "tts",
]

CHAPTER_STEPS = ["narration", "continuity", "storyboard", "subtitles", "manifest", "jianying"]

# Regeneration scopes -> which per-scene artifacts must be redone.
REGENERATE_SCOPES = {
    "image": ["director", "draft_image", "image_qc", "upscale"],
    "translation": ["translation", "tts", "subtitles"],
    "tts": ["tts", "subtitles"],
    "subtitle": ["subtitles"],
    "all": ["director", "draft_image", "image_qc", "upscale", "translation", "tts", "subtitles"],
}


def _mtime(path: Path) -> float | None:
    return path.stat().st_mtime if path.exists() else None


def scene_artifacts(chapter_dir: str | Path, scene_id: str) -> dict[str, Path]:
    chapter_dir = Path(chapter_dir)
    return {
        "director": chapter_dir / "director-briefs" / f"{scene_id}-director-brief.json",
        "draft_image": chapter_dir / "images" / "draft" / f"{scene_id}.png",
        "image_qc": chapter_dir / "qc" / f"{scene_id}.qc.json",
        "upscale": chapter_dir / "images" / "final" / f"{scene_id}.png",
        "translation": chapter_dir / "translation" / f"{scene_id}.json",
        "tts": chapter_dir / "audio" / f"{scene_id}.wav",
        "tts_meta": chapter_dir / "audio" / f"{scene_id}.json",
    }


def chapter_artifacts(chapter_dir: str | Path) -> dict[str, Path]:
    chapter_dir = Path(chapter_dir)
    return {
        "narration": chapter_dir / "narration" / "scenes.json",
        "continuity": chapter_dir / "continuity-ledger.json",
        "storyboard": chapter_dir / "single-scene-storyboard.json",
        "subtitles": chapter_dir / "subtitles" / "subtitles.en.srt",
        "manifest": chapter_dir / "video" / "scene-manifest.json",
    }


def step_status(chapter_dir: str | Path, scene_id: str, step: str) -> str:
    """Status of one per-scene step, read straight from disk."""
    artifacts = scene_artifacts(chapter_dir, scene_id)

    if step == "image_qc":
        qc_path = artifacts["image_qc"]
        if not qc_path.exists():
            return "MISSING"
        report = load_json(qc_path)
        verdict = report.get("verdict")
        if verdict == "PASS":
            return "PASS"
        if verdict == "MANUAL_REVIEW":
            return "MANUAL_REVIEW"
        return "FAILED"

    if step == "translation":
        path = artifacts["translation"]
        if not path.exists():
            return "MISSING"
        entry = load_json(path)
        status = entry.get("status")
        if status == "PASS":
            return "PASS"
        return "FAILED" if status == "FAILED" else "RUNNING"

    path = artifacts.get(step)
    if path is None:
        return "MISSING"
    if not path.exists():
        return "MISSING"
    if step == "draft_image" and artifacts["image_qc"].exists():
        qc_verdict = load_json(artifacts["image_qc"]).get("verdict")
        if qc_verdict in {"RETRY", "MANUAL_REVIEW"}:
            return "FAILED" if qc_verdict == "RETRY" else "MANUAL_REVIEW"
    return "PASS"


def scene_status(chapter_dir: str | Path, scene_id: str) -> dict[str, str]:
    return {step: step_status(chapter_dir, scene_id, step) for step in SCENE_STEPS}


def scene_complete(manifest_entry: dict[str, Any] | None) -> bool:
    """Resume rule: a fully PASS scene is never regenerated."""
    return bool(manifest_entry) and scene_is_pass(manifest_entry)


def next_pending_scene(chapter_dir: str | Path) -> str | None:
    """First scene (by numeric id) that is not fully PASS in the manifest."""
    try:
        narration = load_narration_scenes(chapter_dir)
    except FileNotFoundError:
        return None
    manifest = load_manifest(chapter_dir)
    for scene in narration.get("scenes", []):
        scene_id = scene.get("scene_id")
        if not scene_complete(manifest.get("scenes", {}).get(scene_id)):
            return scene_id
    return None


def detect_stale(chapter_dir: str | Path, root: str | Path | None = None) -> dict[str, list[str]]:
    """Precise dependency staleness.

    - narration edited -> translation/tts/subtitles stale (image untouched
      unless the visual beat changed, which is a manual decision);
    - director brief newer than draft -> image stale;
    - canonical identity asset newer than draft -> image stale.
    """
    chapter_dir = Path(chapter_dir)
    stale: dict[str, list[str]] = {}
    narration_path = chapter_artifacts(chapter_dir)["narration"]
    narration_mtime = _mtime(narration_path)

    try:
        narration = load_narration_scenes(chapter_dir)
    except FileNotFoundError:
        return stale

    identity_mtimes: list[float] = []
    if root is not None:
        characters_dir = Path(root) / "visual-bible" / "characters"
        if characters_dir.exists():
            for identity in characters_dir.glob("*/identity/*.png"):
                identity_mtimes.append(identity.stat().st_mtime)
    newest_identity = max(identity_mtimes) if identity_mtimes else None

    for scene in narration.get("scenes", []):
        scene_id = scene.get("scene_id")
        if not scene_id:
            continue
        artifacts = scene_artifacts(chapter_dir, scene_id)
        reasons: list[str] = []

        translation_mtime = _mtime(artifacts["translation"])
        if narration_mtime and translation_mtime and narration_mtime > translation_mtime:
            reasons.append("narration newer than translation")

        tts_mtime = _mtime(artifacts["tts"])
        if translation_mtime and tts_mtime and translation_mtime > tts_mtime:
            reasons.append("translation newer than tts")

        brief_mtime = _mtime(artifacts["director"])
        draft_mtime = _mtime(artifacts["draft_image"])
        if brief_mtime and draft_mtime and brief_mtime > draft_mtime:
            reasons.append("director brief newer than draft image")
        if newest_identity and draft_mtime and newest_identity > draft_mtime:
            reasons.append("character identity asset newer than draft image")

        if reasons:
            stale[scene_id] = reasons
    return stale


def regenerate_plan(scope: str) -> list[str]:
    if scope not in REGENERATE_SCOPES:
        raise ValueError(f"unknown regenerate scope: {scope} (expected one of {sorted(REGENERATE_SCOPES)})")
    return list(REGENERATE_SCOPES[scope])


def clear_scene_artifacts(chapter_dir: str | Path, scene_id: str, steps: list[str]) -> list[str]:
    """Delete artifacts of the steps being regenerated; returns removed paths."""
    artifacts = scene_artifacts(chapter_dir, scene_id)
    removed: list[str] = []
    for step in steps:
        for key in (step, f"{step}_meta"):
            path = artifacts.get(key)
            if path and path.exists():
                path.unlink()
                removed.append(str(path))
    if "subtitles" in steps:
        for srt in Path(chapter_dir, "subtitles").glob("subtitles.*.srt"):
            srt.unlink()
            removed.append(str(srt))
    return removed


def detect_video_state(root: str | Path, chapter: str | None = None) -> dict[str, Any]:
    """Summary used by `check_state.py` for single_scene projects."""
    root = Path(root)
    chapters_dir = root / "chapters"
    chapter_dirs = sorted(path for path in chapters_dir.glob("ch*") if path.is_dir()) if chapters_dir.exists() else []
    if chapter:
        chapter_dirs = [path for path in chapter_dirs if path.name == chapter]

    sections: dict[str, Any] = {"target_format": "single_scene", "chapters": {}}
    for chapter_dir in chapter_dirs:
        chapter_sections: dict[str, str] = {}
        chapter_files = chapter_artifacts(chapter_dir)
        for name, path in chapter_files.items():
            chapter_sections[name] = "READY" if path.exists() else "MISSING"

        scene_summary: dict[str, str] = {}
        try:
            narration = load_narration_scenes(chapter_dir)
            manifest = load_manifest(chapter_dir)
            for scene in narration.get("scenes", []):
                scene_id = scene.get("scene_id")
                entry = manifest.get("scenes", {}).get(scene_id)
                scene_summary[scene_id] = "PASS" if scene_complete(entry) else "IN_PROGRESS"
        except FileNotFoundError:
            pass

        sections["chapters"][chapter_dir.name] = {
            "sections": chapter_sections,
            "scenes": scene_summary,
            "next_scene": next_pending_scene(chapter_dir),
            "stale": detect_stale(chapter_dir, root),
        }
    return sections
