"""Single Scene Director: one cinematic brief per scene, one image per beat.

Inputs: scene (narration + storyboard) + previous/next scene + continuity
ledger entry + asset registry + style. Outputs `director-brief.json` and
`director-brief.md` under `chapters/chNN/director-briefs/`.

Responsibilities:
- camera variation: avoid dozens of identical medium/frontal shots in a row;
- reference lock: identity / outfit / setting / prop / style references are
  resolved from the registry, never guessed from prose;
- targeted correction: after a QC failure, strengthen only the broken aspect
  instead of regenerating from a blank prompt.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import asset_registry
from .renderers.base import Reference
from .scenes import load_json, write_json


BRIEFS_DIRNAME = "director-briefs"

# Rotation pools keep consecutive shots varied (shot + angle + framing side).
SHOT_ROTATION = ["wide", "medium", "close_up", "medium_close_up", "extreme_wide", "establishing", "insert", "extreme_close_up"]
ANGLE_ROTATION = ["eye_level", "low_angle", "over_the_shoulder", "high_angle", "eye_level", "pov", "eye_level", "top_down"]

DEFAULT_MAX_REPEAT = 2

DEFAULT_NEGATIVE_CONSTRAINTS = [
    "panel grid",
    "multiple panels",
    "comic borders",
    "speech bubbles",
    "text and subtitles",
    "watermark",
    "extra limbs or malformed hands",
    "inconsistent face versus identity reference",
]


def plan_camera_sequence(scene_count: int, offset: int = 0) -> list[dict[str, str]]:
    """Deterministic varied camera plan; no N consecutive identical shots."""
    plan: list[dict[str, str]] = []
    for index in range(scene_count):
        slot = index + offset
        plan.append(
            {
                "shot_size": SHOT_ROTATION[slot % len(SHOT_ROTATION)],
                "angle": ANGLE_ROTATION[(slot * 3 + 1) % len(ANGLE_ROTATION)],
                "framing_side": "left" if slot % 2 == 0 else "right",
            }
        )
    return plan


def check_shot_repetition(storyboard: dict[str, Any], max_repeat: int = DEFAULT_MAX_REPEAT) -> list[str]:
    """Warn-level continuity check: repeated shot+angle runs beyond max_repeat."""
    warnings: list[str] = []
    run = 0
    previous_key = None
    for scene in storyboard.get("scenes", []):
        key = (scene.get("shot_size"), scene.get("angle"))
        if key == previous_key:
            run += 1
            if run > max_repeat:
                warnings.append(
                    f"{scene.get('scene_id')}: shot {key[0]}/{key[1]} repeated {run} times; vary the camera"
                )
        else:
            run = 1
        previous_key = key
    return warnings


def resolve_references(
    root: str | Path,
    registry: dict[str, Any],
    scene: dict[str, Any],
    ledger_entry: dict[str, Any] | None,
) -> list[Reference]:
    """Pick ordered references: 1 identity, 2 outfit, 3 setting, 4 style (+ props)."""
    root = Path(root)
    references: list[Reference] = []
    characters = (ledger_entry or {}).get("characters", []) if ledger_entry else []
    char_state = {char.get("character_id"): char for char in characters if isinstance(char, dict)}

    listed = scene.get("characters", []) or []
    for char in listed:
        char_id = char.get("id") if isinstance(char, dict) else char
        if not char_id:
            continue
        identity_path = asset_registry.identity_reference_path(root, char_id)
        references.append(Reference(path=str(identity_path), role="identity", asset_id=char_id))
        state = char_state.get(char_id) or {}
        outfit_id = (char.get("outfit_id") if isinstance(char, dict) else None) or state.get("outfit_id") or "default"
        outfit_path = asset_registry.outfit_reference_path(root, char_id, outfit_id)
        references.append(Reference(path=str(outfit_path), role="outfit", asset_id=f"{char_id}@{outfit_id}"))

    setting_id = scene.get("setting_id") or (ledger_entry or {}).get("setting_id")
    if setting_id:
        time_of_day = (ledger_entry or {}).get("time", "day") or "day"
        time_key = "night" if "night" in str(time_of_day).lower() else "day"
        setting_path = asset_registry.setting_reference_path(root, setting_id, time_of_day=time_key)
        references.append(Reference(path=str(setting_path), role="setting", asset_id=setting_id))

    for prop_id in scene.get("props", []) or []:
        prop_path = asset_registry.prop_reference_path(root, prop_id)
        references.append(Reference(path=str(prop_path), role="prop", asset_id=prop_id))

    style_path = asset_registry.style_reference_path(root)
    if style_path is not None:
        references.append(Reference(path=str(style_path), role="style", asset_id="style"))

    # Dedupe by path keeping first occurrence; hard cap keeps VRAM sane.
    seen: set[str] = set()
    unique: list[Reference] = []
    for reference in references:
        if reference.path in seen:
            continue
        seen.add(reference.path)
        unique.append(reference)
    return unique[:6]


def build_generation_prompt(
    scene: dict[str, Any],
    storyboard_scene: dict[str, Any] | None,
    ledger_entry: dict[str, Any] | None,
    style_notes: str,
    references: list[Reference],
    correction: dict[str, Any] | None = None,
) -> str:
    """Final copy-ready prompt. References are labeled so the model never guesses."""
    story = storyboard_scene or {}
    shot = story.get("shot_size", scene.get("camera_intent", "medium"))
    angle = story.get("angle", "eye_level")
    composition = story.get("composition", scene.get("visual_beat", ""))
    action = story.get("action", scene.get("story_beat", ""))
    emotion = scene.get("emotion", "")
    time_of_day = (ledger_entry or {}).get("time", "day")
    weather = (ledger_entry or {}).get("weather", "")

    characters: list[str] = []
    for char in (ledger_entry or {}).get("characters", []) or []:
        if not isinstance(char, dict):
            continue
        description = char.get("character_id", "")
        if char.get("injury"):
            description += f", visible injury: {char['injury']}"
        if char.get("weapon"):
            description += f", holding weapon {char['weapon']}"
        if char.get("expression"):
            description += f", expression {char['expression']}"
        characters.append(description)

    parts = [
        f"Single standalone cinematic illustration, no panel grid. {shot} shot, {angle} angle.",
        f"Scene: {action}",
        f"Composition: {composition}",
    ]
    if characters:
        parts.append("Characters: " + "; ".join(characters) + ".")
    parts.append(f"Emotion: {emotion}. Setting time: {time_of_day}" + (f", weather: {weather}." if weather else "."))
    if style_notes:
        parts.append(f"Visual style: {style_notes}.")
    if references:
        parts.append(
            "Reference images: " + "; ".join(reference.label(index) for index, reference in enumerate(references, start=1)) + "."
        )
        parts.append(
            "Strict consistency: face and hair follow the identity reference; clothing follows the outfit "
            "reference; location layout follows the environment reference; rendering style follows the style reference."
        )
    if correction:
        parts.append(f"Correction focus (previous attempt failed QC): {correction.get('correction_reason', '')}")
        if correction.get("emphasis"):
            parts.append("Strengthen: " + "; ".join(correction["emphasis"]) + ".")
    return " ".join(part for part in parts if part)


def build_director_brief(
    root: str | Path,
    scene: dict[str, Any],
    storyboard_scene: dict[str, Any] | None,
    ledger_entry: dict[str, Any] | None,
    registry: dict[str, Any],
    *,
    style_notes: str = "",
    previous_scene: dict[str, Any] | None = None,
    next_scene: dict[str, Any] | None,
    correction: dict[str, Any] | None = None,
    seed: int | None = None,
    attempt: int = 1,
) -> dict[str, Any]:
    """Assemble the full director brief dict for one scene."""
    root = Path(root)
    scene_id = scene["scene_id"]
    references = resolve_references(root, registry, scene, ledger_entry)
    prompt = build_generation_prompt(
        scene, storyboard_scene, ledger_entry, style_notes, references, correction=correction
    )
    brief = {
        "scene_id": scene_id,
        "target_format": "single_scene",
        "attempt": attempt,
        "scene_purpose": scene.get("story_beat", ""),
        "emotional_beat": scene.get("emotion", ""),
        "shot_size": (storyboard_scene or {}).get("shot_size", scene.get("camera_intent", "medium")),
        "camera_angle": (storyboard_scene or {}).get("angle", "eye_level"),
        "composition": (storyboard_scene or {}).get("composition", ""),
        "foreground": (storyboard_scene or {}).get("foreground", ""),
        "middle_ground": (storyboard_scene or {}).get("middle_ground", ""),
        "background": (storyboard_scene or {}).get("background", ""),
        "characters": (ledger_entry or {}).get("characters", []),
        "setting_lock": scene.get("setting_id") or (ledger_entry or {}).get("setting_id"),
        "prop_lock": scene.get("props", []),
        "lighting": (ledger_entry or {}).get("lighting", ""),
        "style": style_notes,
        "negative_constraints": DEFAULT_NEGATIVE_CONSTRAINTS,
        "references": [
            {"index": index, "role": reference.role, "asset_id": reference.asset_id, "path": reference.path}
            for index, reference in enumerate(references, start=1)
        ],
        "continuity": {
            "previous_scene_id": (previous_scene or {}).get("scene_id"),
            "next_scene_id": (next_scene or {}).get("scene_id"),
            "transition": scene.get("transition", ""),
        },
        "seed": seed,
        "correction": correction,
        "prompt": prompt,
    }
    return brief


def write_director_brief(chapter_dir: str | Path, brief: dict[str, Any]) -> tuple[Path, Path]:
    """Persist director-brief.json and a human-readable .md next to it."""
    directory = Path(chapter_dir) / BRIEFS_DIRNAME
    directory.mkdir(parents=True, exist_ok=True)
    scene_id = brief["scene_id"]
    json_path = directory / f"{scene_id}-director-brief.json"
    md_path = directory / f"{scene_id}-director-brief.md"
    write_json(json_path, brief)

    reference_lines = "\n".join(
        f"- image {ref['index']} = {ref['role']} ({ref['asset_id']}): `{ref['path']}`"
        for ref in brief["references"]
    ) or "- none"
    md = (
        f"# Director Brief {scene_id}\n\n"
        f"- Shot: {brief['shot_size']} / {brief['camera_angle']}\n"
        f"- Purpose: {brief['scene_purpose']}\n"
        f"- Emotion: {brief['emotional_beat']}\n"
        f"- Setting lock: {brief['setting_lock']}\n"
        f"- Prop lock: {', '.join(brief['prop_lock']) or 'none'}\n\n"
        f"## References\n\n{reference_lines}\n\n"
        f"## Negative constraints\n\n"
        + "\n".join(f"- {item}" for item in brief["negative_constraints"])
        + f"\n\n## Final prompt\n\n{brief['prompt']}\n"
    )
    md_path.write_text(md, encoding="utf-8")
    return json_path, md_path


def load_director_brief(chapter_dir: str | Path, scene_id: str) -> dict[str, Any] | None:
    path = Path(chapter_dir) / BRIEFS_DIRNAME / f"{scene_id}-director-brief.json"
    if not path.exists():
        return None
    return load_json(path)
