#!/usr/bin/env python3
"""Validate manga page scripts before storyboard and director brief work."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from novel_to_comic.page_script import check_page_script


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a manga page script.")
    parser.add_argument("page_script", help="Path to chapters/chNN/page-script.json")
    args = parser.parse_args()

    result = check_page_script(Path(args.page_script))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
