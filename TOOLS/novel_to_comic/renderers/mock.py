"""Deterministic mock renderer for tests and GPU-less machines.

Produces a real PNG (seeded pattern) and records the prompt, seed and
reference roles into PNG text metadata, so downstream QC/manifest logic can be
exercised end-to-end without FLUX.
"""

from __future__ import annotations

import hashlib
import json
import random

from PIL import Image, ImageDraw
from PIL.PngImagePlugin import PngInfo

from .base import BaseRenderer, RenderRequest, RenderResult, deterministic_seed


class MockRenderer(BaseRenderer):
    name = "mock"

    def __init__(self, fail_scenes: list[str] | None = None, **_: object) -> None:
        # fail_scenes lets tests simulate generation failures for resume checks
        self.fail_scenes = set(fail_scenes or [])

    def _render(self, request: RenderRequest) -> RenderResult:
        scene_id = str(request.metadata.get("scene_id", ""))
        if scene_id in self.fail_scenes:
            raise RuntimeError(f"mock renderer simulated failure for {scene_id}")

        seed = request.seed if request.seed is not None else deterministic_seed(scene_id or request.prompt)
        rng = random.Random(seed)

        image = Image.new("RGB", (request.width, request.height))
        draw = ImageDraw.Draw(image)
        base_color = (rng.randrange(40, 200), rng.randrange(40, 200), rng.randrange(40, 200))
        draw.rectangle([0, 0, request.width, request.height], fill=base_color)
        # A few seeded shapes so the image is not blank (QC coverage check).
        for _ in range(24):
            x0 = rng.randrange(0, request.width)
            y0 = rng.randrange(0, request.height)
            size = rng.randrange(16, max(32, request.width // 8))
            color = (rng.randrange(0, 255), rng.randrange(0, 255), rng.randrange(0, 255))
            draw.ellipse([x0, y0, x0 + size, y0 + size], fill=color)

        info = PngInfo()
        info.add_text("ntc:prompt", request.prompt[:2000])
        info.add_text("ntc:seed", str(seed))
        info.add_text("ntc:references", json.dumps(
            [{"role": reference.role, "asset_id": reference.asset_id, "path": reference.path}
             for reference in request.references],
            ensure_ascii=False,
        )[:2000])
        info.add_text("ntc:content-hash", hashlib.sha256(request.prompt.encode("utf-8")).hexdigest()[:32])

        from pathlib import Path

        output_path = Path(request.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, format="PNG", pnginfo=info)

        return RenderResult(
            path=str(output_path),
            width=request.width,
            height=request.height,
            seed=seed,
            renderer=self.name,
            duration_seconds=0.0,
            metadata={"references": len(request.references)},
        )
