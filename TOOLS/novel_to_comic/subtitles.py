"""Subtitle generation: English (default), Chinese (kept), bilingual.

Timing always comes from the real Kokoro WAV durations recorded in the scene
manifest (word timestamps are used when available). Character-count guessing
is forbidden. Chinese subtitles map to the same scene time span as English.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .scene_manifest import ordered_scene_ids


SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")


def format_srt_timestamp(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    millis = int(round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def split_into_cues(text: str, start: float, duration: float, word_timestamps: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Split one scene's text into timed cues.

    Prefer word timestamps; otherwise distribute the measured duration over
    semantic sentences weighted by word count.
    """
    text = (text or "").strip()
    if not text or duration <= 0:
        return []
    end = start + duration

    if word_timestamps:
        cue = {"start": word_timestamps[0].get("start_ts", start), "end": end, "text": text}
        return [cue]

    sentences = [sentence.strip() for sentence in SENTENCE_SPLIT_RE.split(text) if sentence.strip()]
    if not sentences:
        sentences = [text]
    weights = [max(1, len(sentence.split())) for sentence in sentences]
    total = sum(weights)

    cues: list[dict[str, Any]] = []
    cursor = start
    for sentence, weight in zip(sentences, weights):
        portion = duration * weight / total
        cue_end = min(end, cursor + portion)
        cues.append({"start": cursor, "end": cue_end, "text": sentence})
        cursor = cue_end
    if cues:
        cues[-1]["end"] = end
    return cues


def build_timeline(manifest: dict[str, Any]) -> dict[str, Any]:
    """Assign each scene a [start, end] span from real audio durations."""
    timeline: dict[str, Any] = {}
    cursor = 0.0
    for scene_id in ordered_scene_ids(manifest):
        entry = manifest["scenes"][scene_id]
        duration = float(entry.get("duration") or 0.0)
        timeline[scene_id] = {"start": cursor, "end": cursor + duration, "duration": duration}
        cursor += duration
    return timeline


def render_srt(cues: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for index, cue in enumerate(cues, start=1):
        lines.append(str(index))
        lines.append(f"{format_srt_timestamp(cue['start'])} --> {format_srt_timestamp(cue['end'])}")
        lines.append(cue["text"])
        lines.append("")
    return "\n".join(lines)


def generate_subtitles(
    manifest: dict[str, Any],
    output_dir: str | Path,
    *,
    default_language: str = "en",
    keep_chinese: bool = True,
    generate_bilingual: bool = True,
    bilingual_order: list[str] | None = None,
) -> dict[str, str]:
    """Write subtitles.en.srt / subtitles.zh.srt / subtitles.bilingual.srt."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    bilingual_order = bilingual_order or ["en", "zh"]
    timeline = build_timeline(manifest)

    en_cues: list[dict[str, Any]] = []
    zh_cues: list[dict[str, Any]] = []
    for scene_id in ordered_scene_ids(manifest):
        entry = manifest["scenes"][scene_id]
        span = timeline[scene_id]
        en_cues.extend(split_into_cues(entry.get("en_subtitle") or entry.get("en_text"), span["start"], span["duration"]))
        zh_cues.extend(split_into_cues(entry.get("zh_subtitle") or entry.get("zh_text"), span["start"], span["duration"]))

    written: dict[str, str] = {}
    en_path = output_dir / "subtitles.en.srt"
    en_path.write_text(render_srt(en_cues), encoding="utf-8")
    written["en"] = str(en_path)

    if keep_chinese:
        zh_path = output_dir / "subtitles.zh.srt"
        zh_path.write_text(render_srt(zh_cues), encoding="utf-8")
        written["zh"] = str(zh_path)

    if generate_bilingual:
        bilingual_cues: list[dict[str, Any]] = []
        for en_cue, zh_cue in zip(en_cues, zh_cues):
            first, second = (en_cue, zh_cue) if bilingual_order[0] == "en" else (zh_cue, en_cue)
            bilingual_cues.append(
                {
                    "start": en_cue["start"],
                    "end": en_cue["end"],
                    "text": f"{first['text']}\n{second['text']}",
                }
            )
        # Fall back to remaining single-side cues when lengths differ.
        if len(en_cues) != len(zh_cues):
            longer, shorter = (en_cues, zh_cues) if len(en_cues) > len(zh_cues) else (zh_cues, en_cues)
            for cue in longer[len(shorter):]:
                bilingual_cues.append(cue)
        bilingual_path = output_dir / "subtitles.bilingual.srt"
        bilingual_path.write_text(render_srt(bilingual_cues), encoding="utf-8")
        written["bilingual"] = str(bilingual_path)

    written["default"] = written.get(default_language, written.get("en", ""))
    return written
