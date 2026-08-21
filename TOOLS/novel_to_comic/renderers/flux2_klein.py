"""Local FLUX.2 Klein 4B renderer (diffusers, no ComfyUI, no cloud API).

Target hardware: RTX 3090 24GB VRAM / 32GB RAM. Draft resolution for
single_scene is 1024x1536; only QC-PASS images are later 4x upscaled.

The pipeline stays resident for the whole batch (`warm()` once). torch and
diffusers are imported lazily so the rest of the tooling runs without a GPU.

Multi-reference handling: FLUX text+image conditioning varies by release; this
renderer composites the approved references into an init image (identity /
outfit / setting / style slots) and labels them explicitly in the prompt so
the model is never left guessing which reference is which.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image

from .base import BaseRenderer, RenderRequest, RenderResult, deterministic_seed


DEFAULT_MODEL = "black-forest-labs/FLUX.2-klein-4B"

DEFAULT_NEGATIVE = (
    "extra limbs, malformed hands, extra fingers, fused fingers, watermark, signature, "
    "text, subtitles, logo, panel grid, multiple panels, comic grid, borders, blurry face"
)


class Flux2KleinRenderer(BaseRenderer):
    name = "flux2_klein"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        device: str = "cuda",
        dtype: str = "bfloat16",
        steps: int = 28,
        guidance_scale: float = 3.5,
        reference_composite: bool = True,
        **_: object,
    ) -> None:
        self.model = model
        self.device = device
        self.dtype = dtype
        self.steps = steps
        self.guidance_scale = guidance_scale
        self.reference_composite = reference_composite
        self._pipeline: Any = None
        self._torch: Any = None

    # -- lifecycle ----------------------------------------------------------
    def warm(self) -> None:
        """Load the model once; batches must not reload FLUX per image."""
        if self._pipeline is not None:
            return
        try:
            import torch
            from diffusers import DiffusionPipeline
        except ImportError as error:  # pragma: no cover - requires GPU box
            raise RuntimeError(
                "flux2_klein renderer needs torch + diffusers. "
                "Install: pip install torch diffusers transformers accelerate sentencepiece protobuf"
            ) from error
        self._torch = torch
        dtype = torch.bfloat16 if self.dtype == "bfloat16" else torch.float16

        model_path = self.model
        for candidate in [
            self.model,
            f"models/flux/{Path(self.model).name}",
            f"../models/flux/{Path(self.model).name}",
            f"models/{Path(self.model).name}",
            f"../models/{Path(self.model).name}",
        ]:
            if Path(candidate).exists():
                model_path = str(Path(candidate).resolve())
                break

        self._pipeline = DiffusionPipeline.from_pretrained(
            model_path,
            torch_dtype=dtype,
        ).to(self.device)

    def release(self) -> None:
        self._pipeline = None
        if self._torch is not None and self.device.startswith("cuda"):
            self._torch.cuda.empty_cache()

    # -- render --------------------------------------------------------------
    def _render(self, request: RenderRequest) -> RenderResult:
        self.warm()
        seed = request.seed if request.seed is not None else deterministic_seed(
            str(request.metadata.get("scene_id", "")) or request.prompt
        )

        prompt = self._prompt_with_reference_labels(request)
        generator = self._torch.Generator(device=self.device).manual_seed(seed)

        kwargs: dict[str, Any] = {
            "prompt": prompt,
            "width": request.width,
            "height": request.height,
            "num_inference_steps": self.steps,
            "guidance_scale": self.guidance_scale,
            "generator": generator,
        }
        init_image = self._compose_reference_init(request)
        if init_image is not None:
            kwargs["image"] = init_image
            kwargs["strength"] = 0.85

        output = self._pipeline(**kwargs)
        image = output.images[0]

        output_path = Path(request.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, format="PNG")

        return RenderResult(
            path=str(output_path),
            width=image.width,
            height=image.height,
            seed=seed,
            renderer=self.name,
            duration_seconds=0.0,
            metadata={"model": self.model, "steps": self.steps},
        )

    # -- reference handling ----------------------------------------------------
    def _prompt_with_reference_labels(self, request: RenderRequest) -> str:
        """Tell the model exactly what each reference image is (image 1 = identity...)."""
        labels = [reference.label(index) for index, reference in enumerate(request.references, start=1)]
        negative = request.negative_prompt or DEFAULT_NEGATIVE
        parts = [request.prompt.strip()]
        if labels:
            parts.append("Reference images provided: " + "; ".join(labels) + ".")
            parts.append(
                "Match identity face/hair from the identity reference exactly; use the outfit reference "
                "for clothing, the environment reference for the location, and the style reference only "
                "for visual style. Do not invent new faces or outfits."
            )
        parts.append(f"Avoid: {negative}.")
        return " ".join(parts)

    def _compose_reference_init(self, request: RenderRequest) -> Image.Image | None:
        """Best-effort reference conditioning: tile existing references into an init canvas."""
        if not self.reference_composite or not request.references:
            return None
        available: list[Image.Image] = []
        for reference in request.references:
            path = Path(reference.path)
            if path.exists():
                available.append(Image.open(path).convert("RGB"))
        if not available:
            return None
        # Weight identity/outfit highest: they appear first and largest.
        ordered = sorted(
            zip(request.references, available),
            key=lambda pair: 0 if pair[0].role in ("identity", "outfit") else 1,
        )
        canvas = Image.new("RGB", (request.width, request.height), (128, 128, 128))
        columns = min(len(ordered), 2)
        rows = (len(ordered) + columns - 1) // columns
        cell_w, cell_h = request.width // columns, request.height // rows
        for index, (_reference, image) in enumerate(ordered):
            resized = image.resize((cell_w, cell_h))
            canvas.paste(resized, ((index % columns) * cell_w, (index // columns) * cell_h))
        return canvas
