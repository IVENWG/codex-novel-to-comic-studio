"""Optional fallback for composing separate panel images into page images.

The production v0 flow asks image2 for complete pages. This module is useful
for layout previews, tests, or recovery when a page must be rebuilt from
separate panels.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


DEFAULT_PAGE_SIZE = (2480, 3508)


def compose_chapter_pages(
    storyboard_path: str | Path,
    finals_dir: str | Path,
    output_dir: str | Path,
    page_size: tuple[int, int] = DEFAULT_PAGE_SIZE,
    gutter: int = 8,
) -> list[Path]:
    storyboard = json.loads(Path(storyboard_path).read_text(encoding="utf-8"))
    finals = Path(finals_dir)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    page_paths: list[Path] = []

    for page in storyboard.get("pages", []):
        page_number = int(page["page"])
        canvas = Image.new("RGB", page_size, "white")
        boxes = _layout_boxes(page.get("layout", "2x2"), page_size, gutter, len(page.get("panels", [])))
        for panel, box in zip(page.get("panels", []), boxes, strict=False):
            panel_number = int(panel["panel"])
            panel_image = _load_panel_image(finals / f"p{page_number:03d}-{panel_number:02d}.png", box)
            canvas.paste(panel_image, box[:2])
        page_path = target / f"page-{page_number:03d}.png"
        canvas.save(page_path)
        page_paths.append(page_path)

    return page_paths


def _layout_boxes(layout: str, page_size: tuple[int, int], gutter: int, panel_count: int) -> list[tuple[int, int, int, int]]:
    width, height = page_size
    if layout == "splash":
        return [(0, 0, width, height)]
    if layout == "3x2":
        rows, cols = 3, 2
    elif layout == "2x2":
        rows, cols = 2, 2
    else:
        cols = 2
        rows = max(1, (panel_count + 1) // 2)

    cell_width = (width - gutter * (cols - 1)) // cols
    cell_height = (height - gutter * (rows - 1)) // rows
    boxes: list[tuple[int, int, int, int]] = []
    for row in range(rows):
        for col in range(cols):
            x0 = col * (cell_width + gutter)
            y0 = row * (cell_height + gutter)
            boxes.append((x0, y0, x0 + cell_width, y0 + cell_height))
    return boxes[:panel_count]


def _load_panel_image(path: Path, box: tuple[int, int, int, int]) -> Image.Image:
    width = box[2] - box[0]
    height = box[3] - box[1]
    if not path.exists():
        placeholder = Image.new("RGB", (width, height), (245, 245, 245))
        draw = ImageDraw.Draw(placeholder)
        draw.rectangle((0, 0, width - 1, height - 1), outline=(180, 180, 180), width=2)
        draw.text((12, 12), path.name, fill=(80, 80, 80))
        return placeholder

    with Image.open(path) as image:
        rgb = image.convert("RGB")
        rgb.thumbnail((width, height))
        panel = Image.new("RGB", (width, height), "white")
        x = (width - rgb.width) // 2
        y = (height - rgb.height) // 2
        panel.paste(rgb, (x, y))
        return panel
