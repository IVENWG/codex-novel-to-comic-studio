"""TTS abstraction: scene-level English audio (one WAV per scene, never one
chapter-long WAV). Durations are always measured from the real WAV file.
"""

from __future__ import annotations

import json
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_VOICE = "af_heart"
DEFAULT_LANGUAGE = "en-us"
DEFAULT_MODEL = "hexgrad/Kokoro-82M"


@dataclass
class TTSRequest:
    scene_id: str
    text: str
    output_path: str
    voice: str = DEFAULT_VOICE
    speed: float = 1.0
    language: str = DEFAULT_LANGUAGE
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TTSResult:
    scene_id: str
    audio_path: str
    duration: float
    sample_rate: int
    voice: str
    speed: float
    word_timestamps: list[dict[str, Any]] | None = None


def wav_duration(path: str | Path) -> float | None:
    """Real WAV duration via stdlib; subtitle timing depends on this."""
    try:
        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            rate = handle.getframerate()
            if rate <= 0:
                return None
            return frames / rate
    except (wave.Error, OSError, EOFError):
        return None


class BaseTTS:
    name = "base"

    def warm(self) -> None:  # pragma: no cover - trivial
        pass

    def release(self) -> None:  # pragma: no cover - trivial
        pass

    def synthesize(self, request: TTSRequest) -> TTSResult:
        if not request.text or not request.text.strip():
            raise ValueError(f"{request.scene_id}: TTS text is empty")
        result = self._synthesize(request)
        self._write_sidecar(request, result)
        return result

    def _synthesize(self, request: TTSRequest) -> TTSResult:
        raise NotImplementedError

    def _write_sidecar(self, request: TTSRequest, result: TTSResult) -> None:
        """Persist per-scene audio metadata next to the WAV."""
        sidecar = Path(result.audio_path).with_suffix(".json")
        payload = {
            "scene_id": result.scene_id,
            "en_text": request.text,
            "voice": result.voice,
            "speed": result.speed,
            "language": request.language,
            "duration": result.duration,
            "audio_path": result.audio_path,
            "sample_rate": result.sample_rate,
        }
        if result.word_timestamps:
            payload["word_timestamps"] = result.word_timestamps
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_audio_sidecar(chapter_dir: str | Path, scene_id: str) -> dict[str, Any] | None:
    path = Path(chapter_dir) / "audio" / f"{scene_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def validate_tts_mapping(chapter_dir: str | Path, narration_doc: dict[str, Any]) -> list[str]:
    """Every scene must have its own WAV + sidecar keyed by scene_id."""
    errors: list[str] = []
    root = Path(chapter_dir)
    for scene in narration_doc.get("scenes", []):
        scene_id = scene.get("scene_id")
        wav = root / "audio" / f"{scene_id}.wav"
        if not wav.exists():
            errors.append(f"{scene_id}: missing audio/{scene_id}.wav")
            continue
        duration = wav_duration(wav)
        if duration is None or duration <= 0:
            errors.append(f"{scene_id}: unreadable or empty WAV")
        sidecar = load_audio_sidecar(chapter_dir, scene_id)
        if sidecar is None:
            errors.append(f"{scene_id}: missing audio sidecar json")
        elif sidecar.get("scene_id") != scene_id:
            errors.append(f"{scene_id}: sidecar scene_id mismatch")
    return errors


def create_tts(name: str, options: dict[str, Any] | None = None) -> BaseTTS:
    options = options or {}
    if name == "kokoro":
        from .kokoro import KokoroTTS

        return KokoroTTS(**options)
    if name == "indextts":
        from .indextts import IndexTTSTTS

        return IndexTTSTTS(**options)
    if name == "mock":
        from .mock import MockTTS

        return MockTTS(**options)
    raise ValueError(f"unknown tts provider: {name}")
