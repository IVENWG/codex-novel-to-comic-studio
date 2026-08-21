"""Mock upscaler: LANCZOS resize, keeps the upscale gate and file contract testable."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from .base import BaseUpscaler, UpscaleResult, DEFAULT_MODEL


class MockUpscaler(BaseUpscaler):
    name = "mock"

    def __init__(self, model: str = DEFAULT_MODEL, **_: object) -> None:
        self.model = model

    def _upscale(self, src: Path, dst: Path, scale: int) -> UpscaleResult:
        with Image.open(src) as image:
            resized = image.resize((image.width * scale, image.height * scale), Image.LANCZOS)
            dst_format = "WEBP" if dst.suffix.lower() == ".webp" else "PNG"
            resized.save(dst, format=dst_format)
            width, height = resized.size
        return UpscaleResult(path=str(dst), width=width, height=height, scale=scale, provider=self.name, model=self.model)
