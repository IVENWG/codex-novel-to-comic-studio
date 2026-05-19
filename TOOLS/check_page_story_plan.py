#!/usr/bin/env python3
"""Validate reader-first manga page story plans before storyboard work."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from novel_to_comic.page_story_plan import check_page_story_plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a manga page story plan.")
    parser.add_argument("page_story_plan", help="Path to chapters/chNN/page-story-plan.json")
    args = parser.parse_args()

    result = check_page_story_plan(Path(args.page_story_plan))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
