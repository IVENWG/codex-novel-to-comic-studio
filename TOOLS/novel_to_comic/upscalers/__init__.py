"""Upscaler providers (Real-ESRGAN by default, mock for tests)."""

from .base import BaseUpscaler, UpscaleGateError, UpscaleResult, create_upscaler, should_upscale

__all__ = ["BaseUpscaler", "UpscaleGateError", "UpscaleResult", "create_upscaler", "should_upscale"]
