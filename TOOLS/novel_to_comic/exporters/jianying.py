"""Jianying (剪映 / CapCut desktop) draft exporter.

Builds an editable draft from the scene manifest:

- Video track: one image segment per scene, duration = real TTS duration.
- Audio track: the scene WAVs back to back.
- Text track: English subtitles by default; the Chinese SRT is always kept in
  the export folder (and optionally added as a muted second text track).

Times are in microseconds, ids are stable UUIDs, and ordering comes from the
manifest (scene_id), never from filename sorting. First version keeps effects
off: image fills the canvas with correct aspect; camera variety comes from
Director + generation, not from editor effects.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from ..scene_manifest import ordered_scene_ids
from ..subtitles import build_timeline, split_into_cues


MICRO = 1_000_000

DEFAULT_CANVAS = {"width": 1080, "height": 1920, "ratio": "9:16"}


def _uuid() -> str:
    return str(uuid.uuid4()).upper()


def _microseconds(seconds: float) -> int:
    return int(round(seconds * MICRO))


def export_jianying_draft(
    manifest: dict[str, Any],
    chapter_dir: str | Path,
    output_root: str | Path,
    *,
    project_name: str = "novel-comic-video",
    canvas: dict[str, Any] | None = None,
    include_chinese_track: bool = False,
) -> dict[str, Any]:
    """Write `exports/jianying/<project>/draft_content.json` + meta + report."""
    chapter_dir = Path(chapter_dir)
    canvas = canvas or DEFAULT_CANVAS
    draft_dir = Path(output_root) / "jianying" / project_name
    draft_dir.mkdir(parents=True, exist_ok=True)

    timeline = build_timeline(manifest)
    scene_ids = ordered_scene_ids(manifest)
    total_seconds = sum(timeline[scene_id]["duration"] for scene_id in scene_ids)

    video_materials: list[dict[str, Any]] = []
    audio_materials: list[dict[str, Any]] = []
    text_materials: list[dict[str, Any]] = []
    video_segments: list[dict[str, Any]] = []
    audio_segments: list[dict[str, Any]] = []
    text_segments: list[dict[str, Any]] = []
    zh_text_segments: list[dict[str, Any]] = []
    missing_assets: list[str] = []

    for scene_id in scene_ids:
        entry = manifest["scenes"][scene_id]
        span = timeline[scene_id]
        duration_us = _microseconds(span["duration"])
        start_us = _microseconds(span["start"])

        image_path = chapter_dir / (entry.get("final_image") or entry.get("draft_image") or "")
        audio_path = chapter_dir / (entry.get("audio") or "")
        if not image_path.exists():
            missing_assets.append(f"{scene_id}: image {image_path}")
        if not audio_path.exists():
            missing_assets.append(f"{scene_id}: audio {audio_path}")

        video_material_id = _uuid()
        video_materials.append(
            {
                "id": video_material_id,
                "type": "photo",
                "path": str(image_path.resolve()),
                "duration": duration_us,
                "width": canvas["width"],
                "height": canvas["height"],
                "scene_id": scene_id,
            }
        )
        video_segments.append(
            {
                "id": _uuid(),
                "material_id": video_material_id,
                "target_timerange": {"start": start_us, "duration": duration_us},
                "source_timerange": {"start": 0, "duration": duration_us},
                "extra_material_refs": [],
                "scene_id": scene_id,
            }
        )

        audio_material_id = _uuid()
        audio_materials.append(
            {
                "id": audio_material_id,
                "type": "extract_music",
                "path": str(audio_path.resolve()),
                "duration": duration_us,
                "scene_id": scene_id,
            }
        )
        audio_segments.append(
            {
                "id": _uuid(),
                "material_id": audio_material_id,
                "target_timerange": {"start": start_us, "duration": duration_us},
                "source_timerange": {"start": 0, "duration": duration_us},
                "scene_id": scene_id,
            }
        )

        for cue in split_into_cues(entry.get("en_subtitle") or entry.get("en_text"), span["start"], span["duration"]):
            text_material_id = _uuid()
            text_materials.append(
                {
                    "id": text_material_id,
                    "content": cue["text"],
                    "language": "en",
                    "typesetting": 0,
                }
            )
            text_segments.append(
                {
                    "id": _uuid(),
                    "material_id": text_material_id,
                    "target_timerange": {
                        "start": _microseconds(cue["start"]),
                        "duration": _microseconds(cue["end"] - cue["start"]),
                    },
                    "scene_id": scene_id,
                }
            )

        if include_chinese_track:
            for cue in split_into_cues(entry.get("zh_subtitle") or entry.get("zh_text"), span["start"], span["duration"]):
                zh_material_id = _uuid()
                text_materials.append(
                    {
                        "id": zh_material_id,
                        "content": cue["text"],
                        "language": "zh",
                        "typesetting": 0,
                    }
                )
                zh_text_segments.append(
                    {
                        "id": _uuid(),
                        "material_id": zh_material_id,
                        "target_timerange": {
                            "start": _microseconds(cue["start"]),
                            "duration": _microseconds(cue["end"] - cue["start"]),
                        },
                        "scene_id": scene_id,
                        "visible": False,
                    }
                )

    tracks = [
        {"id": _uuid(), "type": "video", "segments": video_segments},
        {"id": _uuid(), "type": "audio", "segments": audio_segments},
        {"id": _uuid(), "type": "text", "segments": text_segments},
    ]
    if include_chinese_track and zh_text_segments:
        tracks.append({"id": _uuid(), "type": "text", "segments": zh_text_segments, "disabled": True})

    draft_id = _uuid()
    draft_content = {
        "id": draft_id,
        "canvas_config": {"width": canvas["width"], "height": canvas["height"], "ratio": canvas.get("ratio", "9:16")},
        "duration": _microseconds(total_seconds),
        "materials": {
            "videos": video_materials,
            "audios": audio_materials,
            "texts": text_materials,
        },
        "tracks": tracks,
        "platform": {"os": "novel-to-comic-studio"},
    }
    (draft_dir / "draft_content.json").write_text(
        json.dumps(draft_content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    draft_meta = {
        "draft_id": draft_id,
        "draft_name": project_name,
        "draft_root_path": str(draft_dir.parent),
        "draft_timeline_range": _microseconds(total_seconds),
        "draft_materials_count": len(video_materials) + len(audio_materials) + len(text_materials),
        "tm_draft_modified": str(int(time.time() * 1000)),
    }
    (draft_dir / "draft_meta_info.json").write_text(
        json.dumps(draft_meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    report = {
        "project_name": project_name,
        "draft_dir": str(draft_dir),
        "scene_count": len(scene_ids),
        "total_duration_seconds": round(total_seconds, 3),
        "image_tracks": 1,
        "audio_tracks": 1,
        "subtitle_tracks": 2 if include_chinese_track and zh_text_segments else 1,
        "missing_assets": missing_assets,
        "errors": [],
        "warnings": [
            "Chinese SRT is kept in subtitles/; enable include_chinese_track to embed it as a disabled track."
        ] if not include_chinese_track else [],
    }
    (draft_dir / "export-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report
