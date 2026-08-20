"""TTS providers (Kokoro-82M by default, mock for tests)."""

from .base import (
    BaseTTS,
    TTSRequest,
    TTSResult,
    create_tts,
    load_audio_sidecar,
    validate_tts_mapping,
    wav_duration,
    DEFAULT_LANGUAGE,
    DEFAULT_MODEL,
    DEFAULT_VOICE,
)

__all__ = [
    "BaseTTS",
    "TTSRequest",
    "TTSResult",
    "create_tts",
    "load_audio_sidecar",
    "validate_tts_mapping",
    "wav_duration",
    "DEFAULT_LANGUAGE",
    "DEFAULT_MODEL",
    "DEFAULT_VOICE",
]
