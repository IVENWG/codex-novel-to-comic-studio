"""IndexTTS-2.5 local TTS provider (Bilibili IndexTeam).

Zero-shot voice cloning: the narrator timbre comes from ONE locked reference
clip (3-10s) at `tts.reference_audio` (default `audio-voice/narrator-reference.wav`),
so every scene of the whole novel keeps the exact same narrator voice.
Per-scene emotion is injected from the narration scene's `emotion` field via
text-driven emotion control (`use_emo_text` / `emo_alpha`).

Setup on the rendering machine:

    git clone https://github.com/index-tts/index-tts
    pip install -e index-tts            # or follow its README
    # download IndexTeam/IndexTTS-2.5 weights into checkpoints/ (hf download)

`indextts` is imported lazily; the rest of the pipeline runs without it.
VRAM note: the pipeline releases the image renderer before warming this
provider so FLUX and IndexTTS never share the GPU at the same time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import BaseTTS, TTSRequest, TTSResult, DEFAULT_LANGUAGE, wav_duration


DEFAULT_MODEL = "IndexTeam/IndexTTS-2.5"

LANGUAGE_MAP = {
    "en": "en",
    "en-us": "en",
    "zh": "zh",
    "ja": "ja",
    "es": "es",
    "ar": "ar",
}


class IndexTTSTTS(BaseTTS):
    name = "indextts"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        reference_audio: str | None = None,
        model_dir: str = "checkpoints",
        cfg_path: str | None = None,
        language: str = DEFAULT_LANGUAGE,
        speed: float = 1.0,
        device: str | None = None,
        use_fp16: bool = True,
        use_scene_emotion: bool = True,
        emo_alpha: float = 0.6,
        sample_rate: int = 24000,
        **_: object,
    ) -> None:
        self.model = model
        self.reference_audio = reference_audio
        self.model_dir = model_dir
        self.cfg_path = cfg_path
        self.default_language = language
        self.default_speed = speed
        self.device = device
        self.use_fp16 = use_fp16
        self.use_scene_emotion = use_scene_emotion
        self.emo_alpha = emo_alpha
        self.sample_rate = sample_rate
        self._pipeline: Any = None

    # -- lifecycle ----------------------------------------------------------
    def warm(self) -> None:
        if self._pipeline is not None:
            return
        if not self.reference_audio or not Path(self.reference_audio).exists():
            raise RuntimeError(
                "indextts needs a narrator reference clip: set tts.reference_audio in "
                "config/user-preferences.json (default audio-voice/narrator-reference.wav). "
                "Create one with `python3 -m novel_to_comic make-voice-samples` or see "
                "audio-voice/README.md."
            )
        try:
            from indextts.infer import IndexTTS2
        except ImportError as error:  # pragma: no cover - GPU machine only
            raise RuntimeError(
                "indextts provider needs the index-tts package. Install: "
                "git clone https://github.com/index-tts/index-tts && pip install -e index-tts, "
                "then download IndexTeam/IndexTTS-2.5 weights into checkpoints/."
            ) from error
        kwargs: dict[str, Any] = {"model_dir": self.model_dir, "use_fp16": self.use_fp16}
        if self.cfg_path:
            kwargs["cfg_path"] = self.cfg_path
        if self.device:
            kwargs["device"] = self.device
        self._pipeline = IndexTTS2(**kwargs)

    def release(self) -> None:
        self._pipeline = None

    # -- synthesis -----------------------------------------------------------
    def _synthesize(self, request: TTSRequest) -> TTSResult:
        self.warm()
        output_path = Path(request.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # duration_factor is IndexTTS speed control (0.5x - 2.0x).
        duration_factor = float(request.speed or self.default_speed or 1.0)
        duration_factor = min(2.0, max(0.5, duration_factor))

        kwargs: dict[str, Any] = {
            "spk_audio_prompt": str(self.reference_audio),
            "text": request.text,
            "output_path": str(output_path),
            "duration_factor": duration_factor,
            "lang": LANGUAGE_MAP.get((request.language or self.default_language or "").lower(), "auto"),
        }
        emotion = str((request.metadata or {}).get("emotion") or "").strip()
        if self.use_scene_emotion and emotion:
            kwargs.update({"use_emo_text": True, "emo_text": emotion, "emo_alpha": self.emo_alpha})

        try:
            self._pipeline.infer(**kwargs)
        except TypeError:
            # Older/newer infer() signatures: retry with the minimal contract.
            self._pipeline.infer(
                spk_audio_prompt=kwargs["spk_audio_prompt"],
                text=request.text,
                output_path=str(output_path),
            )

        duration = wav_duration(output_path) or 0.0
        return TTSResult(
            scene_id=request.scene_id,
            audio_path=str(output_path),
            duration=round(duration, 3),
            sample_rate=self.sample_rate,
            voice=f"clone:{Path(str(self.reference_audio)).stem}",
            speed=duration_factor,
            word_timestamps=None,
        )
