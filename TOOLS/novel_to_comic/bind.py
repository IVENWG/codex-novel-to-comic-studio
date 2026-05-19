"""Bind composed page images into PDF and CBZ outputs."""

from __future__ import annotations

from pathlib import Path
import zipfile

from PIL import Image


def bind_pages(page_dirs: list[str | Path], output_dir: str | Path, book_slug: str) -> dict[str, str]:
    pages = _collect_pages(page_dirs)
    if not pages:
        raise ValueError("No page images found to bind")

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    pdf_path = target / f"{book_slug}.pdf"
    cbz_path = target / f"{book_slug}.cbz"

    _write_pdf(pages, pdf_path)
    _write_cbz(pages, cbz_path)

    return {"pdf": str(pdf_path), "cbz": str(cbz_path), "page_count": str(len(pages))}


def _collect_pages(page_dirs: list[str | Path]) -> list[Path]:
    pages: list[Path] = []
    for page_dir in page_dirs:
        root = Path(page_dir)
        pages.extend(sorted(root.glob("page-*.png")))
        pages.extend(sorted(root.glob("page-*.jpg")))
        pages.extend(sorted(root.glob("page-*.jpeg")))
    return sorted(pages)


def _write_pdf(pages: list[Path], pdf_path: Path) -> None:
    images: list[Image.Image] = []
    for page in pages:
        with Image.open(page) as image:
            images.append(image.convert("RGB").copy())
    first, rest = images[0], images[1:]
    first.save(pdf_path, save_all=True, append_images=rest)
    for image in images:
        image.close()


def _write_cbz(pages: list[Path], cbz_path: Path) -> None:
    with zipfile.ZipFile(cbz_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, page in enumerate(pages, start=1):
            archive.write(page, arcname=f"page-{index:03d}{page.suffix.lower()}")
