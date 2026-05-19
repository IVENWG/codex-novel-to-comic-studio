#!/usr/bin/env python3
"""Normalize comic page images to the configured A4 production canvas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from novel_to_comic.lettering import A4_PAGE_SIZE, normalize_directory


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize page images to A4 portrait 2480x3508 by default.")
    parser.add_argument("page_dir", help="Directory containing page images")
    parser.add_argument("--width", type=int, default=A4_PAGE_SIZE[0])
    parser.add_argument("--height", type=int, default=A4_PAGE_SIZE[1])
    args = parser.parse_args()

    outputs = normalize_directory(Path(args.page_dir), page_size=(args.width, args.height))
    print(json.dumps({"normalized": len(outputs), "page_dir": args.page_dir, "size": [args.width, args.height]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
