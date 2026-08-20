"""Upscaler abstraction: only QC-PASS drafts get 4x upscaled."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_MODEL = "RealESRGAN_x4plus_anime_6B"


class UpscaleGateError(RuntimeError):
    """Raised when an upscale is attempted on a non-PASS image."""


@dataclass
class UpscaleResult:
    path: str
    width: int
    height: int
    scale: int
    provider: str
    model: str


def should_upscale(qc_status: str, *, only_after_qc_pass: bool = True) -> bool:
    if only_after_qc_pass:
        return qc_status == "PASS"
    return qc_status in {"PASS", "RETRY", "MANUAL_REVIEW"}


class BaseUpscaler:
    name = "base"
    model = ""

    def warm(self) -> None:  # pragma: no cover - trivial
        pass

    def release(self) -> None:  # pragma: no cover - trivial
        pass

    def upscale(self, src: str | Path, dst: str | Path, scale: int = 4, qc_status: str = "PASS") -> UpscaleResult:
        if not should_upscale(qc_status):
            raise UpscaleGateError(f"refusing to upscale {src}: QC status is {qc_status}, not PASS")
        src_path = Path(src)
        if not src_path.exists():
            raise FileNotFoundError(f"source image missing: {src}")
        dst_path = Path(dst)
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        return self._upscale(src_path, dst_path, scale)

    def _upscale(self, src: Path, dst: Path, scale: int) -> UpscaleResult:
        raise NotImplementedError


def create_upscaler(name: str, options: dict[str, Any] | None = None) -> BaseUpscaler:
    options = options or {}
    if name == "realesrgan":
        from .realesrgan import RealEsrganUpscaler

        return RealEsrganUpscaler(**options)
    if name == "mock":
        from .mock import MockUpscaler

        return MockUpscaler(**options)
    raise ValueError(f"unknown upscaler provider: {name}")
