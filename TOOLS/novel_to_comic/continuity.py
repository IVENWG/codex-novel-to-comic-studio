"""Continuity Ledger: resolved per-scene world state, computed before rendering.

The ledger lives at `chapters/chNN/continuity-ledger.json`. The Director reads
character states, outfits, injuries, weapons, weather and story state from the
ledger instead of asking the image model to "remember" the story.

State changes (injury, outfit change, gained weapon) persist forward until an
explicit `cleared` entry removes them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .scenes import is_scene_id, load_json, parse_scene_id, write_json


LEDGER_RELPATH = "continuity-ledger.json"

REQUIRED_ENTRY_FIELDS = ["scene_id", "setting_id", "time"]


def ledger_path(chapter_dir: str | Path) -> Path:
    return Path(chapter_dir) / LEDGER_RELPATH


def load_ledger(chapter_dir: str | Path) -> dict[str, Any]:
    path = ledger_path(chapter_dir)
    if not path.exists():
        return {"chapter": Path(chapter_dir).name, "entries": []}
    return load_json(path)


def save_ledger(chapter_dir: str | Path, ledger: dict[str, Any]) -> None:
    write_json(ledger_path(chapter_dir), ledger)


def validate_ledger(ledger: dict[str, Any], narration_doc: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    entries = ledger.get("entries")
    if not isinstance(entries, list) or not entries:
        return ["ledger entries must be a non-empty list"]

    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("ledger entry must be an object")
            continue
        scene_id = entry.get("scene_id", "?")
        if not is_scene_id(scene_id):
            errors.append(f"ledger entry scene_id invalid: {scene_id}")
            continue
        if scene_id in seen:
            errors.append(f"duplicate ledger entry for {scene_id}")
        seen.add(scene_id)
        for field in REQUIRED_ENTRY_FIELDS:
            if not entry.get(field):
                errors.append(f"{scene_id}: ledger entry missing {field}")
        for char in entry.get("characters", []):
            if not isinstance(char, dict) or not char.get("character_id"):
                errors.append(f"{scene_id}: ledger character needs character_id")
                continue
            if not char.get("outfit_id"):
                errors.append(f"{scene_id}: character {char.get('character_id')} must pin outfit_id")

    if narration_doc is not None:
        narration_ids = {
            scene.get("scene_id") for scene in narration_doc.get("scenes", []) if isinstance(scene, dict)
        }
        missing = narration_ids - seen
        for scene_id in sorted(missing or []):
            errors.append(f"no continuity entry for {scene_id}")
    return errors


def resolve_state_for_scene(ledger: dict[str, Any], scene_id: str) -> dict[str, Any] | None:
    for entry in ledger.get("entries", []):
        if isinstance(entry, dict) and entry.get("scene_id") == scene_id:
            return entry
    return None


def character_state_at(ledger: dict[str, Any], scene_id: str, character_id: str) -> dict[str, Any] | None:
    entry = resolve_state_for_scene(ledger, scene_id)
    if not entry:
        return None
    for char in entry.get("characters", []):
        if isinstance(char, dict) and char.get("character_id") == character_id:
            return char
    return None


def check_state_persistence(ledger: dict[str, Any]) -> list[str]:
    """Flag continuity drift: an injury/outfit/weapon must not silently vanish.

    For every character, walk scenes in order. Once an `injury` or `weapon`
    appears it must stay until a later entry lists it in `cleared`. Outfit
    changes are legitimate but must be recorded explicitly (different outfit_id
    without `outfit_change: true` on the first differing entry is suspicious).
    """
    errors: list[str] = []
    entries = sorted(
        (entry for entry in ledger.get("entries", []) if isinstance(entry, dict)),
        key=lambda entry: parse_scene_id(entry["scene_id"]) if is_scene_id(entry.get("scene_id", "")) else 0,
    )

    active_injuries: dict[str, str] = {}
    active_weapons: dict[str, str] = {}
    current_outfit: dict[str, str] = {}

    for entry in entries:
        scene_id = entry.get("scene_id", "?")
        present: set[str] = set()
        for char in entry.get("characters", []):
            if not isinstance(char, dict):
                continue
            char_id = char.get("character_id", "?")
            present.add(char_id)

            injury = char.get("injury") or ""
            cleared = set(char.get("cleared", []) or [])
            if injury:
                active_injuries[char_id] = injury
            elif char_id in active_injuries and "injury" not in cleared:
                errors.append(
                    f"{scene_id}: {char_id} injury {active_injuries[char_id]} disappeared without explicit clear"
                )
            if "injury" in cleared:
                active_injuries.pop(char_id, None)

            weapon = char.get("weapon") or ""
            if weapon:
                active_weapons[char_id] = weapon
            elif char_id in active_weapons and "weapon" not in cleared:
                errors.append(
                    f"{scene_id}: {char_id} weapon {active_weapons[char_id]} disappeared without explicit clear"
                )
            if "weapon" in cleared:
                active_weapons.pop(char_id, None)

            outfit_id = char.get("outfit_id")
            if outfit_id:
                previous = current_outfit.get(char_id)
                if previous and previous != outfit_id and not char.get("outfit_change"):
                    errors.append(
                        f"{scene_id}: {char_id} outfit changed {previous} -> {outfit_id} without outfit_change marker"
                    )
                current_outfit[char_id] = outfit_id

    return errors
