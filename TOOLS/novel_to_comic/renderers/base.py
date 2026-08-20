"""Renderer abstraction for single_scene image generation.

Unified interface (no ComfyUI dependency):

    render(prompt, references, width, height, seed, output_path, metadata)

Heavy model dependencies (torch/diffusers) are imported lazily by concrete
renderers so state/validation tooling runs on machines without a GPU.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REFERENCE_ROLES = ["identity", "outfit", "setting", "style", "prop", "expression"]


@dataclass(frozen=True)
class Reference:
    path: str
    role: str
    asset_id: str = ""
    weight: float = 1.0

    def label(self, index: int) -> str:
        """Human/model-facing label: image 1 = identity, image 2 = outfit, ..."""
        return f"image {index} = {self.role}" + (f" ({self.asset_id})" if self.asset_id else "")


@dataclass
class RenderRequest:
    prompt: str
    output_path: str
    references: list[Reference] = field(default_factory=list)
    width: int = 1024
    height: int = 1536
    seed: int | None = None
    negative_prompt: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.prompt or not self.prompt.strip():
            errors.append("prompt is required")
        if self.width < 256 or self.height < 256:
            errors.append("width/height must be >= 256")
        for reference in self.references:
            if reference.role not in REFERENCE_ROLES:
                errors.append(f"reference role {reference.role} not in {REFERENCE_ROLES}")
        return errors


@dataclass
class RenderResult:
    path: str
    width: int
    height: int
    seed: int
    renderer: str
    duration_seconds: float
    metadata: dict[str, Any] = field(default_factory=dict)


def deterministic_seed(scene_id: str, salt: str = "", attempt: int = 0) -> int:
    """Stable per-scene seed so reruns are reproducible (seed_policy: deterministic_by_scene)."""
    material = f"{scene_id}|{salt}|{attempt}".encode("utf-8")
    return int(hashlib.sha256(material).hexdigest()[:12], 16)


class BaseRenderer:
    """Base class; concrete renderers keep the model resident across a batch."""

    name = "base"

    def warm(self) -> None:  # pragma: no cover - trivial
        """Load model once before a batch."""

    def release(self) -> None:  # pragma: no cover - trivial
        """Free model memory after a batch."""

    def render(self, request: RenderRequest) -> RenderResult:
        """Public entry point: validates, times and delegates to `_render`."""
        errors = request.validate()
        if errors:
            raise ValueError("; ".join(errors))
        start = time.time()
        result = self._render(request)
        result.duration_seconds = round(time.time() - start, 3)
        result.renderer = self.name
        return result

    def _render(self, request: RenderRequest) -> RenderResult:
        raise NotImplementedError


def create_renderer(name: str, options: dict[str, Any] | None = None) -> BaseRenderer:
    """Factory keyed by config `image_generation.renderer`."""
    options = options or {}
    if name == "mock":
        from .mock import MockRenderer

        return MockRenderer(**options)
    if name == "flux2_klein":
        from .flux2_klein import Flux2KleinRenderer

        return Flux2KleinRenderer(**options)
    raise ValueError(f"unknown renderer: {name} (expected flux2_klein or mock)")
