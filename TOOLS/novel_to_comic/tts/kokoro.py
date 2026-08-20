"""Kokoro-82M local TTS provider.

Default voice is `af_heart` (American English narration). The voice is
configurable but the project default stays af_heart. The pipeline stays
resident during a batch; `kokoro` + `soundfile` are imported lazily.

Install on the target machine:

    pip install kokoro soundfile
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import BaseTTS, TTSRequest, TTSResult, DEFAULT_LANGUAGE, DEFAULT_MODEL, DEFAULT_VOICE, wav_duration


class KokoroTTS(BaseTTS):
    name = "kokoro"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        voice: str = DEFAULT_VOICE,
        language: str = DEFAULT_LANGUAGE,
        speed: float = 1.0,
        device: str = "auto",
        sample_rate: int = 24000,
        **_: object,
    ) -> None:
        self.model = model
        self.default_voice = voice
        self.default_language = language
        self.default_speed = speed
        self.device = device
        self.sample_rate = sample_rate
        self._pipeline: Any = None

    def warm(self) -> None:
        if self._pipeline is not None:
            return
        try:
            from kokoro import KPipeline
        except ImportError as error:  # pragma: no cover - needs kokoro installed
            raise RuntimeError(
                "kokoro provider needs the kokoro package: pip install kokoro soundfile"
            ) from error
        lang_code = self.default_language.split("-")[0] if self.default_language else "e"
        # Kokoro lang codes: 'e' = American English
        self._pipeline = KPipeline(lang_code="e" if lang_code == "en" else lang_code)

    def release(self) -> None:
        self._pipeline = None

    def _synthesize(self, request: TTSRequest) -> TTSResult:
        self.warm()
        import soundfile as sf

        voice = request.voice or self.default_voice
        speed = request.speed or self.default_speed

        audio = None
        word_timestamps: list[dict[str, Any]] = []
        for _graphemes, _phonemes, chunk in self._pipeline(request.text, voice=voice, speed=speed):
            audio = chunk.audio if audio is None else _concat(audio, chunk.audio)
            for word in getattr(chunk, "words", []) or []:
                word_timestamps.append(
                    {
                        "text": getattr(word, "text", ""),
                        "start_ts": float(getattr(word, "start_ts", 0.0)),
                        "end_ts": float(getattr(word, "end_ts", 0.0)),
                    }
                )
        if audio is None:
            raise RuntimeError(f"kokoro produced no audio for {request.scene_id}")

        output_path = Path(request.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), audio, self.sample_rate)

        duration = wav_duration(output_path) or 0.0
        return TTSResult(
            scene_id=request.scene_id,
            audio_path=str(output_path),
            duration=round(duration, 3),
            sample_rate=self.sample_rate,
            voice=voice,
            speed=speed,
            word_timestamps=word_timestamps or None,
        )


def _concat(previous: Any, current: Any) -> Any:
    import numpy as np

    return np.concatenate([previous, current])
