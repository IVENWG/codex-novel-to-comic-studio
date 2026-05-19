"""Deterministic lettering for page-level comic art."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont, ImageOps


A4_PAGE_SIZE = (2480, 3508)
DEFAULT_FONT_PATHS = [
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
]


def normalize_page_image(
    input_path: str | Path,
    output_path: str | Path,
    page_size: tuple[int, int] = A4_PAGE_SIZE,
    background: tuple[int, int, int] = (255, 255, 255),
) -> Path:
    source = Path(input_path)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        rgb = image.convert("RGB")
        rgb = ImageOps.contain(rgb, page_size, method=Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", page_size, background)
        x = (page_size[0] - rgb.width) // 2
        y = (page_size[1] - rgb.height) // 2
        canvas.paste(rgb, (x, y))
        canvas.save(target)
    return target


def normalize_directory(
    page_dir: str | Path,
    page_size: tuple[int, int] = A4_PAGE_SIZE,
    suffixes: tuple[str, ...] = (".png", ".jpg", ".jpeg"),
) -> list[Path]:
    root = Path(page_dir)
    outputs: list[Path] = []
    for page_path in sorted(path for path in root.iterdir() if path.suffix.lower() in suffixes):
        outputs.append(normalize_page_image(page_path, page_path, page_size=page_size))
    return outputs


def letter_chapter_pages(
    storyboard_path: str | Path,
    page_art_dir: str | Path,
    output_dir: str | Path,
    page_size: tuple[int, int] = A4_PAGE_SIZE,
) -> list[Path]:
    storyboard = json.loads(Path(storyboard_path).read_text(encoding="utf-8"))
    art_root = Path(page_art_dir)
    target_root = Path(output_dir)
    target_root.mkdir(parents=True, exist_ok=True)

    text_font = _load_font(46)
    caption_font = _load_font(42)
    sfx_font = _load_font(128)
    outputs: list[Path] = []

    for page in storyboard.get("pages", []):
        page_number = int(page["page"])
        source = art_root / f"page-{page_number:03d}.png"
        target = target_root / f"page-{page_number:03d}.png"
        if not source.exists():
            continue
        normalize_page_image(source, target, page_size=page_size)
        with Image.open(target) as image:
            canvas = image.convert("RGBA")
        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        panel_boxes = _layout_boxes(page.get("layout", "2x2"), page_size, 34, len(page.get("panels", [])))
        for panel, box in zip(page.get("panels", []), panel_boxes, strict=False):
            _draw_panel_lettering(draw, panel, box, text_font, caption_font, sfx_font)
        composed = Image.alpha_composite(canvas, overlay).convert("RGB")
        composed.save(target)
        outputs.append(target)

    return outputs


def _draw_panel_lettering(
    draw: ImageDraw.ImageDraw,
    panel: dict[str, Any],
    box: tuple[int, int, int, int],
    text_font: ImageFont.FreeTypeFont,
    caption_font: ImageFont.FreeTypeFont,
    sfx_font: ImageFont.FreeTypeFont,
) -> None:
    slots: list[tuple[str, dict[str, Any]]] = []
    for caption in panel.get("captions", []):
        slots.append(("caption", caption))
    for dialogue in panel.get("dialogue", []):
        slots.append(("speech", dialogue))
    for sfx in panel.get("sfx", []):
        slots.append(("sfx", sfx))

    used: dict[str, int] = {}
    for kind, item in slots:
        anchor = item.get("anchor", "upper-left")
        index = used.get(anchor, 0)
        used[anchor] = index + 1
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        if kind == "sfx":
            _draw_sfx(draw, box, anchor, text, sfx_font, index)
        elif kind == "caption":
            _draw_caption(draw, box, anchor, text, caption_font, index)
        else:
            _draw_speech(draw, box, anchor, text, text_font, index)


def _draw_caption(
    draw: ImageDraw.ImageDraw,
    panel_box: tuple[int, int, int, int],
    anchor: str,
    text: str,
    font: ImageFont.FreeTypeFont,
    index: int,
) -> None:
    rect = _anchored_rect(panel_box, anchor, index, width_ratio=0.58, height=160)
    lines = _wrap_text(text, font, rect[2] - rect[0] - 48, max_lines=3)
    rect = _fit_rect_height(draw, rect, lines, font, padding=24)
    draw.rounded_rectangle(rect, radius=18, fill=(20, 20, 22, 218), outline=(255, 255, 255, 235), width=3)
    _draw_multiline_centered(draw, rect, lines, font, fill=(255, 255, 255, 255), padding=24)


def _draw_speech(
    draw: ImageDraw.ImageDraw,
    panel_box: tuple[int, int, int, int],
    anchor: str,
    text: str,
    font: ImageFont.FreeTypeFont,
    index: int,
) -> None:
    rect = _anchored_rect(panel_box, anchor, index, width_ratio=0.54, height=170)
    lines = _wrap_text(text, font, rect[2] - rect[0] - 54, max_lines=4)
    rect = _fit_rect_height(draw, rect, lines, font, padding=26)
    draw.rounded_rectangle(rect, radius=54, fill=(255, 255, 255, 238), outline=(20, 20, 22, 245), width=4)
    _draw_tail(draw, rect, panel_box, anchor)
    _draw_multiline_centered(draw, rect, lines, font, fill=(20, 20, 22, 255), padding=28)


def _draw_sfx(
    draw: ImageDraw.ImageDraw,
    panel_box: tuple[int, int, int, int],
    anchor: str,
    text: str,
    font: ImageFont.FreeTypeFont,
    index: int,
) -> None:
    x0, y0, x1, y1 = _anchored_rect(panel_box, anchor, index, width_ratio=0.36, height=170)
    draw.text(
        (x0 + 20, y0),
        text,
        font=font,
        fill=(228, 47, 45, 235),
        stroke_width=8,
        stroke_fill=(255, 246, 222, 245),
    )


def _layout_boxes(layout: str, page_size: tuple[int, int], gutter: int, panel_count: int) -> list[tuple[int, int, int, int]]:
    width, height = page_size
    margin = 82
    content = (margin, margin, width - margin, height - margin)
    x0, y0, x1, y1 = content
    content_width = x1 - x0
    content_height = y1 - y0
    if layout == "splash":
        return [content]
    if layout == "3x2":
        rows, cols = 3, 2
    elif layout == "2x2":
        rows, cols = 2, 2
    else:
        cols = 2
        rows = max(1, (panel_count + 1) // 2)
    cell_width = (content_width - gutter * (cols - 1)) // cols
    cell_height = (content_height - gutter * (rows - 1)) // rows
    boxes: list[tuple[int, int, int, int]] = []
    for row in range(rows):
        for col in range(cols):
            px0 = x0 + col * (cell_width + gutter)
            py0 = y0 + row * (cell_height + gutter)
            boxes.append((px0, py0, px0 + cell_width, py0 + cell_height))
    return boxes[:panel_count]


def _anchored_rect(
    panel_box: tuple[int, int, int, int],
    anchor: str,
    index: int,
    width_ratio: float,
    height: int,
) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = panel_box
    panel_width = x1 - x0
    panel_height = y1 - y0
    width = max(420, int(panel_width * width_ratio))
    offset = index * (height + 18)
    pad = 28

    if "right" in anchor:
        left = x1 - width - pad
    elif "center" in anchor:
        left = x0 + (panel_width - width) // 2
    else:
        left = x0 + pad

    if anchor.startswith("lower"):
        top = y1 - height - pad - offset
    elif anchor.endswith("center") or anchor == "center":
        top = y0 + (panel_height - height) // 2 + offset
    else:
        top = y0 + pad + offset

    return (left, top, left + width, top + height)


def _fit_rect_height(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    lines: list[str],
    font: ImageFont.FreeTypeFont,
    padding: int,
) -> tuple[int, int, int, int]:
    line_height = _line_height(draw, font)
    needed = line_height * len(lines) + padding * 2 + max(0, len(lines) - 1) * 10
    x0, y0, x1, y1 = rect
    if needed <= y1 - y0:
        return rect
    return (x0, y0, x1, y0 + needed)


def _draw_multiline_centered(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    lines: list[str],
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int, int],
    padding: int,
) -> None:
    x0, y0, x1, y1 = rect
    line_height = _line_height(draw, font)
    total_height = line_height * len(lines) + max(0, len(lines) - 1) * 10
    y = y0 + max(padding, (y1 - y0 - total_height) // 2)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        width = bbox[2] - bbox[0]
        draw.text((x0 + (x1 - x0 - width) // 2, y), line, font=font, fill=fill)
        y += line_height + 10


def _draw_tail(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    panel_box: tuple[int, int, int, int],
    anchor: str,
) -> None:
    x0, y0, x1, y1 = rect
    px0, py0, px1, py1 = panel_box
    if "right" in anchor:
        points = [(x1 - 80, y1 - 8), (x1 - 20, y1 - 18), (min(px1 - 70, x1 + 70), min(py1 - 80, y1 + 105))]
    else:
        points = [(x0 + 80, y1 - 8), (x0 + 20, y1 - 18), (max(px0 + 70, x0 - 70), min(py1 - 80, y1 + 105))]
    draw.polygon(points, fill=(255, 255, 255, 238), outline=(20, 20, 22, 245))


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, max_lines: int) -> list[str]:
    chunks = _semantic_chunks(text)
    lines: list[str] = []
    current = ""
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox
    for chunk in chunks:
        candidate = current + chunk
        bbox = measure((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = chunk
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and "".join(lines) != text:
        lines[-1] = lines[-1].rstrip("，。！？、") + "…"
    return lines or [textwrap.shorten(text, width=12, placeholder="…")]


def _semantic_chunks(text: str) -> Iterable[str]:
    if " " in text:
        for token in text.split(" "):
            yield token + " "
        return
    for char in text:
        yield char


def _line_height(draw: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont) -> int:
    bbox = draw.textbbox((0, 0), "漫画", font=font)
    return bbox[3] - bbox[1] + 8


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for font_path in DEFAULT_FONT_PATHS:
        path = Path(font_path)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()
