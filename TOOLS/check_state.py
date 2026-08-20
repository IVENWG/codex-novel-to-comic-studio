#!/usr/bin/env python3
"""Print the current project phase as JSON.

For `single_scene` projects the output additionally carries a `video_pipeline`
section (per-chapter sections, per-scene PASS/IN_PROGRESS, next scene, stale).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from novel_to_comic.state import detect_state


def _target_format(root: Path) -> str | None:
    config_path = root / "config" / "user-preferences.json"
    if not config_path.exists():
        return None
    try:
        preferences = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return (preferences.get("project") or {}).get("target_format")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect novel-to-comic project state.")
    parser.add_argument("root", nargs="?", default=".", help="Project root directory")
    parser.add_argument("--chapter", default=None, help="Limit video pipeline status to one chapter")
    args = parser.parse_args()

    root = Path(args.root)
    state = detect_state(root)
    if _target_format(root) == "single_scene":
        from novel_to_comic.video_state import detect_video_state

        state["video_pipeline"] = detect_video_state(root, chapter=args.chapter)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
