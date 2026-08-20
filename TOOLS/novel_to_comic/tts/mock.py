"""Mock TTS: writes a real silent WAV with a deterministic, text-proportional
duration so subtitle timing and Jianying timeline logic can be tested without
Kokoro installed.
"""

from __future__ import annotations

import re
import wave
from pathlib import Path

from .base import BaseTTS, TTSRequest, TTSResult, DEFAULT_VOICE


WORDS_PER_SECOND = 2.6
MIN_SECONDS = 1.2


class MockTTS(BaseTTS):
    name = "mock"

    def __init__(self, voice: str = DEFAULT_VOICE, sample_rate: int = 24000, **_: object) -> None:
        self.default_voice = voice
        self.sample_rate = sample_rate

    def _synthesize(self, request: TTSRequest) -> TTSResult:
        words = re.findall(r"[A-Za-z0-9']+", request.text)
        seconds = max(MIN_SECONDS, len(words) / WORDS_PER_SECOND)
        seconds /= request.speed or 1.0

        output_path = Path(request.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frames = int(seconds * self.sample_rate)
        with wave.open(str(output_path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(self.sample_rate)
            handle.writeframes(b"\x00\x00" * frames)

        return TTSResult(
            scene_id=request.scene_id,
            audio_path=str(output_path),
            duration=round(frames / self.sample_rate, 3),
            sample_rate=self.sample_rate,
            voice=request.voice or self.default_voice,
            speed=request.speed or 1.0,
        )
