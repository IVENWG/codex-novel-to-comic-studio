#!/usr/bin/env python3
"""Print the current project phase as JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from novel_to_comic.state import detect_state


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect novel-to-comic project state.")
    parser.add_argument("root", nargs="?", default=".", help="Project root directory")
    args = parser.parse_args()

    state = detect_state(Path(args.root))
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
