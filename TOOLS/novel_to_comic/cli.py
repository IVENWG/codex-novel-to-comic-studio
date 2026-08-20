"""Unified CLI for the single_scene video pipeline.

    python -m novel_to_comic ingest novel.txt
    python -m novel_to_comic status
    python -m novel_to_comic prepare-assets --chapter ch001
    python -m novel_to_comic approve-assets
    python -m novel_to_comic pilot --chapter ch001
    python -m novel_to_comic approve-pilot
    python -m novel_to_comic run --chapter ch001
    python -m novel_to_comic regenerate scene_0021 --image
    python -m novel_to_comic export-jianying --chapter ch001
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import pipeline, video_state
from .scenes import validate_narration_scenes
from .source import parse_source_file, write_parsed_source


def _print(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_ingest(args: argparse.Namespace) -> int:
    parsed = parse_source_file(args.source)
    write_parsed_source(parsed, Path(args.root) / "source")
    _print({"title": parsed.title, "chapters": len(parsed.chapters), "out": str(Path(args.root) / "source")})
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    _print(video_state.detect_video_state(args.root, chapter=args.chapter))
    return 0


def cmd_validate_narration(args: argparse.Namespace) -> int:
    from .scenes import load_narration_scenes

    chapter_dir = pipeline.chapter_path(args.root, args.chapter)
    doc = load_narration_scenes(chapter_dir)
    errors = validate_narration_scenes(doc)
    _print({"status": "pass" if not errors else "needs_fix", "errors": errors})
    return 0 if not errors else 1


def cmd_prepare_assets(args: argparse.Namespace) -> int:
    """Asset generation itself is driven by the asset skills (FLUX render of
    identity/outfit/setting/prop cards); this command verifies the registry and
    reports the production gate status so nothing is generated without approval.
    """
    from . import asset_registry

    registry = asset_registry.load_registry(args.root)
    gates = asset_registry.check_production_gates(args.root, registry)
    _print(
        {
            "registered_assets": len(registry.get("assets", {})),
            "gates": "open" if gates else "cleared",
            "blocking": gates,
            "hint": "Generate visual assets with the asset skills, register them in "
            "visual-bible/asset-registry.json, review, then run `approve-assets`.",
        }
    )
    return 0


def cmd_approve_assets(args: argparse.Namespace) -> int:
    path = pipeline.mark_approved(args.root, "assets")
    _print({"approved": str(path)})
    return 0


def cmd_pilot(args: argparse.Namespace) -> int:
    summary = pipeline.run_pilot(args.root, args.chapter, scene_count=args.scene_count)
    _print(summary)
    return 0


def cmd_approve_pilot(args: argparse.Namespace) -> int:
    path = pipeline.mark_approved(args.root, "pilot")
    _print({"approved": str(path)})
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    summary = pipeline.run_batch(args.root, args.chapter)
    _print(summary)
    return 0


def cmd_regenerate(args: argparse.Namespace) -> int:
    scopes = [name for name, enabled in (
        ("image", args.image),
        ("translation", args.translation),
        ("tts", args.tts),
        ("subtitle", args.subtitle),
    ) if enabled]
    scope = scopes[0] if len(scopes) == 1 else "all"
    summary = pipeline.regenerate_scene(args.root, args.chapter, args.scene_id, scope=scope)
    _print(summary)
    return 0


def cmd_export_jianying(args: argparse.Namespace) -> int:
    report = pipeline.export_jianying(args.root, args.chapter, project_name=args.project_name)
    _print(report)
    return 0 if not report.get("manifest_errors") else 1


DEFAULT_VOICE_CANDIDATES = ["af_heart", "af_nicole", "af_bella", "af_sarah", "am_michael", "am_echo"]

DEFAULT_SAMPLE_TEXT = (
    "Rain hammered the old town as the stranger pushed open the tea house door. "
    "Nobody knew his name, but everyone remembered the long bundle wrapped in cloth at his side. "
    "That night, the story of the sword began."
)


def cmd_make_voice_samples(args: argparse.Namespace) -> int:
    """Generate narrator voice candidates (via Kokoro) to pick an IndexTTS
    reference clip from. Listen, choose one, trim 5-10s and save it as
    audio-voice/narrator-reference.wav (see audio-voice/README.md)."""
    from .tts.base import TTSRequest, create_tts

    voices = [voice.strip() for voice in args.voices.split(",") if voice.strip()] or DEFAULT_VOICE_CANDIDATES
    out_dir = Path(args.root) / "audio-voice" / "candidates"
    tts = create_tts("kokoro", {})
    written: list[str] = []
    for voice in voices:
        out_path = out_dir / f"{voice}.wav"
        tts.synthesize(
            TTSRequest(
                scene_id=f"voice-{voice}",
                text=args.text,
                output_path=str(out_path),
                voice=voice,
            )
        )
        written.append(str(out_path))
    _print(
        {
            "samples": written,
            "next_steps": [
                "Listen to audio-voice/candidates/*.wav and pick the best storyteller voice.",
                "Trim a clean 5-10s segment (no music/noise) and save it as audio-voice/narrator-reference.wav.",
                "IndexTTS-2.5 will clone that timbre for every scene of the whole novel.",
            ],
        }
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="novel_to_comic", description="Novel -> English comic explainer video pipeline")
    parser.add_argument("--root", default=".", help="Project root directory")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Parse TXT/EPUB into source/")
    ingest.add_argument("source", help="Path to the .txt or .epub novel")
    ingest.set_defaults(func=cmd_ingest)

    status = sub.add_parser("status", help="Show single_scene pipeline state")
    status.add_argument("--chapter", default=None)
    status.set_defaults(func=cmd_status)

    validate = sub.add_parser("validate-narration", help="Validate chapter narration scenes")
    validate.add_argument("--chapter", required=True)
    validate.set_defaults(func=cmd_validate_narration)

    prepare = sub.add_parser("prepare-assets", help="Check asset registry and gate status")
    prepare.add_argument("--chapter", default=None)
    prepare.set_defaults(func=cmd_prepare_assets)

    approve_assets = sub.add_parser("approve-assets", help="Gate 1: lock approved visual assets")
    approve_assets.set_defaults(func=cmd_approve_assets)

    pilot = sub.add_parser("pilot", help="Run 10-20 pilot scenes end to end")
    pilot.add_argument("--chapter", required=True)
    pilot.add_argument("--scene-count", type=int, default=None)
    pilot.set_defaults(func=cmd_pilot)

    approve_pilot = sub.add_parser("approve-pilot", help="Gate 2: allow whole-book production")
    approve_pilot.set_defaults(func=cmd_approve_pilot)

    run = sub.add_parser("run", help="Unattended batch production (needs PILOT_APPROVED)")
    run.add_argument("--chapter", required=True)
    run.set_defaults(func=cmd_run)

    regenerate = sub.add_parser("regenerate", help="Regenerate one scene only")
    regenerate.add_argument("scene_id")
    regenerate.add_argument("--chapter", required=True)
    regenerate.add_argument("--image", action="store_true")
    regenerate.add_argument("--translation", action="store_true")
    regenerate.add_argument("--tts", action="store_true")
    regenerate.add_argument("--subtitle", action="store_true")
    regenerate.set_defaults(func=cmd_regenerate)

    export = sub.add_parser("export-jianying", help="Build a Jianying draft from the manifest")
    export.add_argument("--chapter", required=True)
    export.add_argument("--project-name", default=None)
    export.set_defaults(func=cmd_export_jianying)

    voices = sub.add_parser("make-voice-samples", help="Generate narrator voice candidates (Kokoro)")
    voices.add_argument("--voices", default=",".join(DEFAULT_VOICE_CANDIDATES), help="Comma-separated Kokoro voice ids")
    voices.add_argument("--text", default=DEFAULT_SAMPLE_TEXT, help="Storytelling sample sentence")
    voices.set_defaults(func=cmd_make_voice_samples)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as error:  # surface gate errors clearly for unattended runs
        _print({"error": str(error), "command": args.command})
        return 1


if __name__ == "__main__":
    sys.exit(main())
