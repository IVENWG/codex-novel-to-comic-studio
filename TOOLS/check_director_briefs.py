#!/usr/bin/env python3
"""Validate whole-page manga director briefs before image2 generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_MARKERS = [
    "Page purpose",
    "Source trace",
    "Reference lock",
    "Page layout",
    "Panel directives",
    "Text directives",
    "Image2 prompt",
    "QC checklist",
    "finished-pages/page-",
]


def check_briefs(root: str | Path) -> dict[str, object]:
    directory = Path(root)
    files = sorted(directory.glob("page-*-director-brief.md"))
    issues: list[dict[str, str]] = []
    if not files:
        issues.append({"file": str(directory), "issue": "no director brief files found"})
    for path in files:
        text = path.read_text(encoding="utf-8")
        for marker in REQUIRED_MARKERS:
            if marker not in text:
                issues.append({"file": str(path), "issue": f"missing marker: {marker}"})
        if "visual-bible/characters/" not in text and "No character reference required" not in text:
            issues.append({"file": str(path), "issue": "missing character reference lock or explicit no-character statement"})
        if "2x2" in text or "3x2" in text:
            issues.append({"file": str(path), "issue": "mechanical grid token found; describe manga panel geometry instead"})
        if "Do not draw text" in text or "no text" in text.lower():
            issues.append({"file": str(path), "issue": "finished-page brief must include exact readable text, not forbid all text"})
    return {"briefs": len(files), "issues": issues, "status": "pass" if not issues else "needs_fix"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate manga page director briefs.")
    parser.add_argument("director_briefs", help="Directory containing page-NNN-director-brief.md files")
    args = parser.parse_args()
    result = check_briefs(Path(args.director_briefs))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
