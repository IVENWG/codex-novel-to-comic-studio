"""Scene Manifest: the single source of truth for the video half of the pipeline.

One manifest per chapter lives at `chapters/chNN/video/scene-manifest.json`.
Every entry is keyed by `scene_id`; correspondence between zh text, en text,
image, audio and subtitles is always resolved through the manifest, never via
filename sorting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .scenes import is_scene_id, load_json, write_json


MANIFEST_RELPATH = Path("video") / "scene-manifest.json"

STEP_KEYS = ["image_qc", "translation_status", "tts_status", "upscale_status"]

REQUIRED_ENTRY_FIELDS = [
    "scene_id",
    "zh_text",
    "en_text",
    "draft_image",
    "final_image",
    "audio",
    "duration",
    "zh_subtitle",
    "en_subtitle",
]


def manifest_path(chapter_dir: str | Path) -> Path:
    return Path(chapter_dir) / MANIFEST_RELPATH


def load_manifest(chapter_dir: str | Path) -> dict[str, Any]:
    path = manifest_path(chapter_dir)
    if not path.exists():
        return {"chapter": Path(chapter_dir).name, "target_format": "single_scene", "scenes": {}}
    return load_json(path)


def save_manifest(chapter_dir: str | Path, manifest: dict[str, Any]) -> None:
    write_json(manifest_path(chapter_dir), manifest)


def upsert_scene(manifest: dict[str, Any], entry: dict[str, Any]) -> None:
    """Merge a scene entry into the manifest keyed by scene_id."""
    scene_id = entry.get("scene_id")
    if not is_scene_id(scene_id):
        raise ValueError(f"manifest entry needs a valid scene_id, got {scene_id!r}")
    scenes = manifest.setdefault("scenes", {})
    existing = scenes.get(scene_id, {})
    existing.update(entry)
    scenes[scene_id] = existing


def get_scene(manifest: dict[str, Any], scene_id: str) -> dict[str, Any] | None:
    return manifest.get("scenes", {}).get(scene_id)


def ordered_scene_ids(manifest: dict[str, Any]) -> list[str]:
    """Deterministic ordering by numeric scene id, never by dict insertion order."""
    return sorted(manifest.get("scenes", {}), key=lambda sid: int(sid.split("_")[1]))


def scene_is_pass(entry: dict[str, Any]) -> bool:
    """A scene is production-ready when every tracked step reports PASS."""
    if not all(entry.get(key) == "PASS" for key in STEP_KEYS):
        return False
    duration = entry.get("duration")
    if not isinstance(duration, (int, float)) or duration <= 0:
        return False
    for field in ("final_image", "audio"):
        if not entry.get(field):
            return False
    return True


def validate_manifest(manifest: dict[str, Any], chapter_dir: str | Path) -> list[str]:
    """Cross-check manifest entries against the filesystem.

    All referenced artifacts must exist and the numeric duration must match the
    real audio file when it is a readable WAV.
    """
    errors: list[str] = []
    root = Path(chapter_dir)
    scenes = manifest.get("scenes", {})
    if not isinstance(scenes, dict) or not scenes:
        return ["manifest has no scenes"]

    for scene_id, entry in scenes.items():
        if not is_scene_id(scene_id):
            errors.append(f"invalid scene_id key: {scene_id}")
            continue
        if entry.get("scene_id") != scene_id:
            errors.append(f"{scene_id}: entry.scene_id mismatch")
        for field in REQUIRED_ENTRY_FIELDS:
            if field not in entry:
                errors.append(f"{scene_id}: missing field {field}")
        for field in ("draft_image", "final_image", "audio"):
            rel = entry.get(field)
            if rel and not (root / rel).exists():
                errors.append(f"{scene_id}: {field} not found at {rel}")
        duration = entry.get("duration")
        if isinstance(duration, (int, float)) and duration <= 0:
            errors.append(f"{scene_id}: duration must be positive")
        audio_rel = entry.get("audio")
        if audio_rel and (root / audio_rel).exists() and audio_rel.endswith(".wav"):
            from .tts.base import wav_duration

            actual = wav_duration(root / audio_rel)
            if actual and abs(actual - float(duration)) > 0.25:
                errors.append(
                    f"{scene_id}: manifest duration {duration:.2f}s differs from wav {actual:.2f}s"
                )
    return errors
