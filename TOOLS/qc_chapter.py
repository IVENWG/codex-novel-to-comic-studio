#!/usr/bin/env python3
"""Run basic QC for a chapter's page art and finished pages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from novel_to_comic.qc import qc_chapter


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a chapter QC report.")
    parser.add_argument("storyboard", help="Path to chapters/chNN/storyboard.json")
    parser.add_argument("--page-art", required=True, help="Page art directory")
    parser.add_argument("--finished-pages", required=True, help="Finished pages directory")
    parser.add_argument("--out", required=True, help="QC report path")
    parser.add_argument("--width", type=int, default=2480)
    parser.add_argument("--height", type=int, default=3508)
    args = parser.parse_args()

    report = qc_chapter(
        Path(args.storyboard),
        Path(args.page_art),
        Path(args.finished_pages),
        Path(args.out),
        expected_size=(args.width, args.height),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
