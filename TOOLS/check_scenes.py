#!/usr/bin/env python3
"""Validate single_scene narration scenes or a single-scene storyboard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from novel_to_comic.scenes import validate_narration_scenes, validate_storyboard_scenes


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate single_scene scene documents.")
    parser.add_argument("path", help="narration/scenes.json or single-scene-storyboard.json")
    args = parser.parse_args()

    path = Path(args.path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    if "storyboard" in path.name:
        errors = validate_storyboard_scenes(doc)
    else:
        errors = validate_narration_scenes(doc)

    result = {"status": "pass" if not errors else "needs_fix", "errors": errors}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
