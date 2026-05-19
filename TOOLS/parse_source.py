#!/usr/bin/env python3
"""Parse a TXT or EPUB source file into source/novel.txt and chapter files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from novel_to_comic.source import parse_source_file, write_parsed_source


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse a TXT or EPUB novel source.")
    parser.add_argument("input", help="Path to .txt or .epub")
    parser.add_argument("--out", default="source", help="Output source directory")
    args = parser.parse_args()

    parsed = parse_source_file(Path(args.input))
    write_parsed_source(parsed, Path(args.out))
    print(json.dumps({"title": parsed.title, "chapters": len(parsed.chapters), "out": args.out}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
