"""Asset Registry, Asset Lock and canonical asset directory conventions.

Layout under `visual-bible/`:

    asset-registry.json
    characters/char-001/
        bio.md
        identity/{face.png,full-body.png,reference-sheet.png}
        expressions/{neutral.png,happy.png,...}
        wardrobe/{default,outfit-001,...}/reference.png
        states/state-001.json
        signature/description.md
    settings/set-001/{location-card.md,wide-day.png,...,details/}
    props/prop-sword-001/reference.png

Statuses: DRAFT -> APPROVED -> LOCKED (DEPRECATED for retired assets).
LOCKED canonical assets must never be overwritten by the normal pipeline.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .scenes import load_json, write_json


REGISTRY_RELPATH = Path("visual-bible") / "asset-registry.json"

ASSET_TYPES = ["character_identity", "outfit", "expression", "setting", "prop", "style_reference"]
ASSET_STATUSES = ["DRAFT", "APPROVED", "LOCKED", "DEPRECATED"]
USABLE_STATUSES = {"APPROVED", "LOCKED"}

# Approval gate marker files (hard gates, not warnings).
STYLE_APPROVED_RELPATH = Path("visual-bible") / "STYLE_APPROVED"
REFERENCE_ASSETS_APPROVED_RELPATH = Path("visual-bible") / "REFERENCE_ASSETS_APPROVED"
PILOT_APPROVED_RELPATH = Path("visual-bible") / "PILOT_APPROVED"

CHARACTER_ID_RE = re.compile(r"^char-\d{3,}$")
SETTING_ID_RE = re.compile(r"^set-\d{3,}$")
PROP_ID_RE = re.compile(r"^prop-[\w-]+$")


class AssetLockError(RuntimeError):
    """Raised when a gate blocks production or a locked asset would be overwritten."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hash_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_registry(root: str | Path) -> dict[str, Any]:
    path = Path(root) / REGISTRY_RELPATH
    if not path.exists():
        return {"assets": {}, "updated_at": None}
    return load_json(path)


def save_registry(root: str | Path, registry: dict[str, Any]) -> None:
    registry["updated_at"] = _now()
    write_json(Path(root) / REGISTRY_RELPATH, registry)


def get_asset(registry: dict[str, Any], asset_id: str) -> dict[str, Any] | None:
    return registry.get("assets", {}).get(asset_id)


def register_asset(
    root: str | Path,
    registry: dict[str, Any],
    *,
    asset_id: str,
    asset_type: str,
    path: str,
    version: str = "v1",
    status: str = "DRAFT",
    notes: str = "",
) -> dict[str, Any]:
    """Insert or update one canonical asset. Locked assets cannot be overwritten."""
    if asset_type not in ASSET_TYPES:
        raise ValueError(f"unknown asset type: {asset_type}")
    if status not in ASSET_STATUSES:
        raise ValueError(f"unknown asset status: {status}")
    existing = get_asset(registry, asset_id)
    if existing and existing.get("status") == "LOCKED" and status != "LOCKED":
        raise AssetLockError(
            f"asset {asset_id} is LOCKED; normal pipeline cannot overwrite canonical assets"
        )
    asset_path = Path(root) / path
    entry = {
        "id": asset_id,
        "type": asset_type,
        "version": version,
        "path": path,
        "status": status,
        "hash": hash_file(asset_path) if asset_path.exists() else "",
        "created_at": existing.get("created_at", _now()) if existing else _now(),
        "approved_at": existing.get("approved_at") if existing else None,
        "notes": notes,
    }
    registry.setdefault("assets", {})[asset_id] = entry
    return entry


def set_asset_status(registry: dict[str, Any], asset_id: str, status: str) -> dict[str, Any]:
    if status not in ASSET_STATUSES:
        raise ValueError(f"unknown asset status: {status}")
    asset = get_asset(registry, asset_id)
    if asset is None:
        raise KeyError(f"asset not registered: {asset_id}")
    asset["status"] = status
    if status in USABLE_STATUSES and not asset.get("approved_at"):
        asset["approved_at"] = _now()
    return asset


def verify_asset_hash(root: str | Path, registry: dict[str, Any], asset_id: str) -> bool:
    asset = get_asset(registry, asset_id)
    if not asset or not asset.get("hash"):
        return False
    path = Path(root) / asset["path"]
    return path.exists() and hash_file(path) == asset["hash"]


# ---------------------------------------------------------------------------
# Canonical asset path conventions
# ---------------------------------------------------------------------------

def character_dir(root: str | Path, character_id: str) -> Path:
    return Path(root) / "visual-bible" / "characters" / character_id


def identity_reference_path(root: str | Path, character_id: str) -> Path:
    base = character_dir(root, character_id) / "identity"
    for name in ("reference-sheet.png", "face.png", "full-body.png"):
        candidate = base / name
        if candidate.exists():
            return candidate
    return base / "reference-sheet.png"


def outfit_reference_path(root: str | Path, character_id: str, outfit_id: str) -> Path:
    return character_dir(root, character_id) / "wardrobe" / outfit_id / "reference.png"


def expression_reference_path(root: str | Path, character_id: str, expression: str) -> Path:
    return character_dir(root, character_id) / "expressions" / f"{expression}.png"


def setting_reference_path(root: str | Path, setting_id: str, time_of_day: str = "day", shot: str = "wide") -> Path:
    return Path(root) / "visual-bible" / "settings" / setting_id / f"{shot}-{time_of_day}.png"


def prop_reference_path(root: str | Path, prop_id: str) -> Path:
    return Path(root) / "visual-bible" / "props" / prop_id / "reference.png"


def style_reference_path(root: str | Path) -> Path | None:
    samples = Path(root) / "visual-bible" / "style-samples"
    if not samples.exists():
        return None
    for candidate in sorted(samples.glob("*.png")):
        return candidate
    return None


def character_state_path(root: str | Path, character_id: str, state_id: str) -> Path:
    return character_dir(root, character_id) / "states" / f"{state_id}.json"


# ---------------------------------------------------------------------------
# Hard gates
# ---------------------------------------------------------------------------

def check_production_gates(root: str | Path, registry: dict[str, Any] | None = None) -> list[str]:
    """Return blocking reasons for batch image generation (empty list = go)."""
    root = Path(root)
    errors: list[str] = []
    if not (root / STYLE_APPROVED_RELPATH).exists():
        errors.append("missing STYLE_APPROVED: visual-bible/STYLE_APPROVED")
    if not (root / REFERENCE_ASSETS_APPROVED_RELPATH).exists():
        errors.append("missing REFERENCE_ASSETS_APPROVED: visual-bible/REFERENCE_ASSETS_APPROVED")
    if registry is not None:
        identities = [
            asset for asset in registry.get("assets", {}).values() if asset.get("type") == "character_identity"
        ]
        if not any(asset.get("status") in USABLE_STATUSES for asset in identities):
            errors.append("no APPROVED/LOCKED character identity assets in registry")
    return errors


def check_scene_assets(
    root: str | Path,
    registry: dict[str, Any],
    scene: dict[str, Any],
) -> list[str]:
    """Every character/setting/prop a scene uses must have an approved asset."""
    errors: list[str] = []
    assets = registry.get("assets", {})

    def usable(asset_id: str, wanted_type: str) -> bool:
        asset = assets.get(asset_id)
        return bool(asset and asset.get("type") == wanted_type and asset.get("status") in USABLE_STATUSES)

    for char in scene.get("characters", []) or []:
        char_id = char.get("id") if isinstance(char, dict) else char
        if char_id and not usable(char_id, "character_identity"):
            errors.append(f"scene {scene.get('scene_id')}: character {char_id} identity not APPROVED/LOCKED")
        if isinstance(char, dict) and char.get("outfit_id"):
            outfit_key = f"{char_id}@{char['outfit_id']}"
            if not usable(outfit_key, "outfit"):
                errors.append(f"scene {scene.get('scene_id')}: outfit {outfit_key} not APPROVED/LOCKED")
    setting_id = scene.get("setting_id")
    if setting_id and not usable(setting_id, "setting"):
        errors.append(f"scene {scene.get('scene_id')}: setting {setting_id} not APPROVED/LOCKED")
    for prop_id in scene.get("props", []) or []:
        if prop_id and not usable(prop_id, "prop"):
            errors.append(f"scene {scene.get('scene_id')}: prop {prop_id} not APPROVED/LOCKED")
    return errors


def assert_writable(registry: dict[str, Any], asset_id: str) -> None:
    """Guard before regenerating any canonical asset file."""
    asset = get_asset(registry, asset_id)
    if asset and asset.get("status") == "LOCKED":
        raise AssetLockError(f"asset {asset_id} is LOCKED and cannot be regenerated by the pipeline")
