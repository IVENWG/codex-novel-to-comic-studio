#!/usr/bin/env python3
"""Bind composed page images into PDF and CBZ files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from novel_to_comic.bind import bind_pages


def main() -> int:
    parser = argparse.ArgumentParser(description="Bind page directories into PDF and CBZ.")
    parser.add_argument("page_dirs", nargs="+", help="One or more directories containing finished readable page images, usually chapters/chNN/finished-pages")
    parser.add_argument("--out", default="output", help="Output directory")
    parser.add_argument("--book-slug", required=True, help="Output file slug without extension")
    args = parser.parse_args()

    result = bind_pages([Path(path) for path in args.page_dirs], Path(args.out), args.book_slug)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
