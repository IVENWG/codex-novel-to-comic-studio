#!/usr/bin/env python3
"""Optional fallback: compose separate panel images into draft page images."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from novel_to_comic.compose import compose_chapter_pages


def main() -> int:
    parser = argparse.ArgumentParser(description="Optional fallback: compose separate panel images into draft pages.")
    parser.add_argument("storyboard", help="Path to chapters/chNN/storyboard.json")
    parser.add_argument("--finals", required=True, help="Directory containing separate panel images")
    parser.add_argument("--out", required=True, help="Output pages directory")
    parser.add_argument("--width", type=int, default=2480)
    parser.add_argument("--height", type=int, default=3508)
    parser.add_argument("--gutter", type=int, default=8)
    args = parser.parse_args()

    pages = compose_chapter_pages(
        Path(args.storyboard),
        Path(args.finals),
        Path(args.out),
        page_size=(args.width, args.height),
        gutter=args.gutter,
    )
    print(json.dumps({"pages": len(pages), "out": args.out}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
