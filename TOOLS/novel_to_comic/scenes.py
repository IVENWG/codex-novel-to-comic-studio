"""single_scene schema: scene ids, narration scenes and storyboard validation.

`scene_id` is the single primary key of the whole video pipeline. It links
zh narration -> en narration -> storyboard -> director brief -> image -> QC ->
upscale -> TTS -> subtitles -> Jianying timeline. File-name ordering must
never be used to infer these relations.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


TARGET_FORMAT = "single_scene"

SCENE_ID_RE = re.compile(r"^scene_(\d{4,})$")

# Required fields of one narration scene (novel -> Chinese narration script).
REQUIRED_NARRATION_FIELDS = [
    "scene_id",
    "source_span",
    "zh_narration",
    "story_beat",
    "visual_beat",
    "setting_id",
    "emotion",
    "camera_intent",
]

LIST_NARRATION_FIELDS = ["characters", "character_states", "props"]

# Required fields of one single-scene storyboard entry.
REQUIRED_STORYBOARD_FIELDS = [
    "scene_id",
    "story_purpose",
    "visual_purpose",
    "shot_size",
    "angle",
    "setting_id",
    "action",
    "composition",
]

SHOT_SIZES = [
    "establishing",
    "extreme_wide",
    "wide",
    "medium",
    "medium_close_up",
    "close_up",
    "extreme_close_up",
    "insert",
]

CAMERA_ANGLES = [
    "eye_level",
    "low_angle",
    "high_angle",
    "top_down",
    "over_the_shoulder",
    "pov",
    "dutch",
]


def make_scene_id(index: int) -> str:
    """Return the canonical scene id for a 1-based index."""
    if index < 1:
        raise ValueError("scene index is 1-based")
    return f"scene_{index:04d}"


def parse_scene_id(scene_id: str) -> int:
    match = SCENE_ID_RE.match(scene_id or "")
    if not match:
        raise ValueError(f"invalid scene_id: {scene_id!r} (expected scene_NNNN)")
    return int(match.group(1))


def is_scene_id(value: Any) -> bool:
    return isinstance(value, str) and bool(SCENE_ID_RE.match(value))


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, data: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _check_scene_ids(doc: dict[str, Any], label: str) -> list[str]:
    """scene_id must be well-formed, unique and contiguous."""
    errors: list[str] = []
    scenes = doc.get("scenes", [])
    seen: set[str] = set()
    indices: list[int] = []
    for position, scene in enumerate(scenes):
        scene_id = scene.get("scene_id") if isinstance(scene, dict) else None
        if not is_scene_id(scene_id):
            errors.append(f"{label}[{position}].scene_id must match scene_NNNN")
            continue
        if scene_id in seen:
            errors.append(f"{label}: duplicate scene_id {scene_id}")
        seen.add(scene_id)
        indices.append(parse_scene_id(scene_id))
    if indices and indices != list(range(1, len(indices) + 1)):
        errors.append(f"{label}: scene ids must be contiguous from scene_0001, got {indices[:5]}...")
    return errors


def validate_narration_scenes(doc: dict[str, Any]) -> list[str]:
    """Validate chapters/chNN/narration/scenes.json (Chinese narration script)."""
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["narration document must be an object"]
    if doc.get("target_format") != TARGET_FORMAT:
        errors.append(f"target_format must be {TARGET_FORMAT}")
    if not doc.get("chapter"):
        errors.append("chapter is required")
    scenes = doc.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        return errors + ["scenes must be a non-empty list"]

    errors.extend(_check_scene_ids(doc, "narration"))

    for scene in scenes:
        if not isinstance(scene, dict):
            errors.append("every scene must be an object")
            continue
        scene_id = scene.get("scene_id", "?")
        for field in REQUIRED_NARRATION_FIELDS:
            value = scene.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{scene_id}.{field} is required")
        for field in LIST_NARRATION_FIELDS:
            if not isinstance(scene.get(field, []), list):
                errors.append(f"{scene_id}.{field} must be a list")
        for state in scene.get("character_states", []):
            # char-001@state-003 style references keep identity/version apart
            if isinstance(state, str) and "@" not in state and state.startswith("char-"):
                errors.append(f"{scene_id}.character_states should use char-xxx@state-yyy form, got {state}")
    return errors


def validate_storyboard_scenes(doc: dict[str, Any]) -> list[str]:
    """Validate chapters/chNN/single-scene-storyboard.json."""
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["storyboard document must be an object"]
    scenes = doc.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        return ["scenes must be a non-empty list"]

    errors.extend(_check_scene_ids(doc, "storyboard"))

    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        scene_id = scene.get("scene_id", "?")
        for field in REQUIRED_STORYBOARD_FIELDS:
            value = scene.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{scene_id}.{field} is required")
        shot = scene.get("shot_size")
        if isinstance(shot, str) and shot and shot not in SHOT_SIZES:
            errors.append(f"{scene_id}.shot_size {shot} not in {SHOT_SIZES}")
        angle = scene.get("angle")
        if isinstance(angle, str) and angle and angle not in CAMERA_ANGLES:
            errors.append(f"{scene_id}.angle {angle} not in {CAMERA_ANGLES}")
        if "panels" in scene or "grid" in scene:
            errors.append(f"{scene_id}: single_scene forbids panel grids; one beat = one image")
        for char in scene.get("characters", []):
            if isinstance(char, dict) and char.get("id") and not char.get("outfit_id"):
                errors.append(f"{scene_id}: character {char.get('id')} must pin an outfit_id")
    return errors


def load_narration_scenes(chapter_dir: str | Path) -> dict[str, Any]:
    path = Path(chapter_dir) / "narration" / "scenes.json"
    if not path.exists():
        raise FileNotFoundError(f"missing narration scenes: {path}")
    return load_json(path)


def scene_by_id(doc: dict[str, Any], scene_id: str) -> dict[str, Any] | None:
    for scene in doc.get("scenes", []):
        if isinstance(scene, dict) and scene.get("scene_id") == scene_id:
            return scene
    return None
