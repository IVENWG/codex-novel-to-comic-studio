#!/usr/bin/env python3
"""Add dialogue, captions, and SFX to page art for one chapter."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from novel_to_comic.lettering import A4_PAGE_SIZE, letter_chapter_pages


def main() -> int:
    parser = argparse.ArgumentParser(description="Create finished readable comic pages from page art and storyboard text.")
    parser.add_argument("storyboard", help="Path to chapters/chNN/storyboard.json")
    parser.add_argument("--page-art", required=True, help="Directory containing page-art/page-001.png etc.")
    parser.add_argument("--out", required=True, help="Output finished-pages directory")
    parser.add_argument("--width", type=int, default=A4_PAGE_SIZE[0])
    parser.add_argument("--height", type=int, default=A4_PAGE_SIZE[1])
    args = parser.parse_args()

    pages = letter_chapter_pages(
        Path(args.storyboard),
        Path(args.page_art),
        Path(args.out),
        page_size=(args.width, args.height),
    )
    print(json.dumps({"pages": len(pages), "out": args.out, "size": [args.width, args.height]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
