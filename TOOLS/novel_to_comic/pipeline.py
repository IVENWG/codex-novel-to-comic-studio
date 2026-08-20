"""single_scene production pipeline orchestration.

Wires: director -> render -> QC (bounded targeted retries) -> upscale ->
translation -> TTS -> subtitles -> scene manifest -> Jianying export, with
hard approval gates, resume (skip fully-PASS scenes) and per-scene logs.

Providers (renderer/upscaler/tts/translator) come from
`config/user-preferences.json`; heavy ones (flux2_klein / realesrgan / kokoro)
are only constructed when configured, so mock-only runs work anywhere.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import asset_registry, continuity, director, image_qc, scene_manifest, subtitles, translation, video_state
from .asset_registry import AssetLockError
from .renderers.base import Reference, RenderRequest, deterministic_seed
from .scenes import load_json, load_narration_scenes, scene_by_id, write_json
from .tts.base import TTSRequest


PILOT_MARKER_RELPATH = asset_registry.PILOT_APPROVED_RELPATH


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_preferences(root: str | Path) -> dict[str, Any]:
    path = Path(root) / "config" / "user-preferences.json"
    if not path.exists():
        return {}
    return load_json(path)


def chapter_path(root: str | Path, chapter: str) -> Path:
    path = Path(root) / "chapters" / chapter
    if not path.exists():
        raise FileNotFoundError(f"chapter directory missing: {path}")
    return path


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------

def require_visual_asset_gate(root: str | Path) -> None:
    errors = asset_registry.check_production_gates(root, asset_registry.load_registry(root))
    if errors:
        raise AssetLockError("batch generation blocked: " + "; ".join(errors))


def require_pilot_gate(root: str | Path) -> None:
    if not (Path(root) / PILOT_MARKER_RELPATH).exists():
        raise AssetLockError(
            "whole-book production blocked: missing PILOT_APPROVED "
            "(run the pilot, review it, then `approve-pilot`)"
        )


def mark_approved(root: str | Path, marker: str) -> Path:
    allowed = {
        "assets": asset_registry.REFERENCE_ASSETS_APPROVED_RELPATH,
        "pilot": PILOT_MARKER_RELPATH,
    }
    if marker not in allowed:
        raise ValueError(f"unknown approval marker: {marker}")
    path = Path(root) / allowed[marker]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"approved {_now()}\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

def build_providers(preferences: dict[str, Any]) -> dict[str, Any]:
    """Instantiate renderer/upscaler/tts once per batch (models stay resident)."""
    from .renderers.base import create_renderer
    from .tts.base import create_tts
    from .upscalers.base import create_upscaler

    image_config = preferences.get("image_generation", {})
    upscale_config = preferences.get("upscale", {})
    tts_config = preferences.get("tts", {})

    renderer = create_renderer(
        image_config.get("renderer", "mock"),
        {"model": image_config.get("model"), "device": image_config.get("device"), "steps": image_config.get("steps")},
    )
    upscaler = create_upscaler(
        upscale_config.get("provider", "mock"),
        {"model": upscale_config.get("model"), "scale": upscale_config.get("scale", 4)},
    )
    tts = create_tts(
        tts_config.get("provider", "mock"),
        {key: value for key, value in tts_config.items() if key != "provider"},
    )
    return {"renderer": renderer, "upscaler": upscaler, "tts": tts}


# ---------------------------------------------------------------------------
# Scene processing
# ---------------------------------------------------------------------------

def mock_translate(zh_text: str) -> str:
    """Deterministic stand-in translation for mock/test pipelines only."""
    return f"[en narration] {zh_text.strip()}"


def process_scene(
    root: str | Path,
    chapter_dir: str | Path,
    scene: dict[str, Any],
    *,
    narration_doc: dict[str, Any],
    storyboard_doc: dict[str, Any] | None,
    ledger: dict[str, Any],
    registry: dict[str, Any],
    preferences: dict[str, Any],
    providers: dict[str, Any],
) -> dict[str, Any]:
    """Run every pipeline step for one scene (image phase + audio phase).

    Batch runs should call `run_scenes`, which splits the two phases so the
    image renderer and the TTS model never occupy the GPU at the same time.
    """
    process_scene_image(
        root, chapter_dir, scene,
        narration_doc=narration_doc, storyboard_doc=storyboard_doc,
        ledger=ledger, registry=registry, preferences=preferences, providers=providers,
    )
    return process_scene_audio(root, chapter_dir, scene, preferences=preferences, providers=providers)


def _update_scene_log(chapter_dir: str | Path, scene_id: str, step: str, value: Any) -> None:
    path = Path(chapter_dir) / "logs" / f"{scene_id}.json"
    log = load_json(path) if path.exists() else {"scene_id": scene_id, "started_at": _now(), "steps": {}}
    log.setdefault("steps", {})[step] = value
    write_json(path, log)


def process_scene_image(
    root: str | Path,
    chapter_dir: str | Path,
    scene: dict[str, Any],
    *,
    narration_doc: dict[str, Any],
    storyboard_doc: dict[str, Any] | None,
    ledger: dict[str, Any],
    registry: dict[str, Any],
    preferences: dict[str, Any],
    providers: dict[str, Any],
) -> dict[str, Any]:
    """Image phase: director brief -> render -> QC retry loop -> upscale."""
    root = Path(root)
    chapter_dir = Path(chapter_dir)
    scene_id = scene["scene_id"]
    manifest = scene_manifest.load_manifest(chapter_dir)
    entry = scene_manifest.get_scene(manifest, scene_id) or {}

    image_config = preferences.get("image_generation", {})
    width = int(image_config.get("width", 1024))
    height = int(image_config.get("height", 1536))
    max_retry = int(preferences.get("qc", {}).get("max_retry", image_qc.DEFAULT_MAX_RETRY))
    expected_size = (width, height)

    scenes = narration_doc.get("scenes", [])
    index = next((i for i, item in enumerate(scenes) if item.get("scene_id") == scene_id), 0)
    previous_scene = scenes[index - 1] if index > 0 else None
    next_scene = scenes[index + 1] if index + 1 < len(scenes) else None
    storyboard_scene = scene_by_id(storyboard_doc or {}, scene_id) if storyboard_doc else None
    ledger_entry = continuity.resolve_state_for_scene(ledger, scene_id)
    style_notes = preferences.get("visuals", {}).get("style_family", "")

    # -- 1. director brief ----------------------------------------------------
    brief = director.load_director_brief(chapter_dir, scene_id)
    if brief is None:
        brief = director.build_director_brief(
            root, scene, storyboard_scene, ledger_entry, registry,
            style_notes=style_notes, previous_scene=previous_scene, next_scene=next_scene,
            seed=deterministic_seed(scene_id),
        )
        director.write_director_brief(chapter_dir, brief)
    _update_scene_log(chapter_dir, scene_id, "director", "ok")

    # -- 2. render draft + QC with bounded targeted retries --------------------
    draft_path = chapter_dir / "images" / "draft" / f"{scene_id}.png"
    qc_report = image_qc.load_qc_report(chapter_dir, scene_id)
    attempt = int((qc_report or {}).get("attempt", 1)) if qc_report else 1

    while True:
        needs_render = not draft_path.exists() or (qc_report and qc_report.get("verdict") != "PASS")
        if needs_render:
            request = RenderRequest(
                prompt=brief["prompt"],
                output_path=str(draft_path),
                references=[
                    Reference(path=ref["path"], role=ref["role"], asset_id=ref["asset_id"])
                    for ref in brief.get("references", [])
                ],
                width=width,
                height=height,
                seed=deterministic_seed(scene_id, attempt=attempt),
                metadata={"scene_id": scene_id, "attempt": attempt},
            )
            result = providers["renderer"].render(request)
            _update_scene_log(chapter_dir, scene_id, "render", {"seed": result.seed, "seconds": result.duration_seconds, "attempt": attempt})

        qc_report = image_qc.qc_scene_image(draft_path, brief, expected_size=expected_size)
        qc_report["attempt"] = attempt
        image_qc.save_qc_report(chapter_dir, qc_report)
        verdict = image_qc.decide_verdict(attempt - 1, max_retry, qc_report)
        _update_scene_log(chapter_dir, scene_id, "qc", {"verdict": verdict, "attempt": attempt})
        entry["image_qc"] = verdict

        if verdict == "PASS":
            break
        if verdict == "MANUAL_REVIEW":
            _update_scene_log(chapter_dir, scene_id, "qc_note", "max retries exceeded; manual review required")
            break
        # Targeted regeneration: correct only the broken aspect, never restart from zero.
        correction = image_qc.plan_targeted_regeneration(qc_report)
        attempt += 1
        brief = director.build_director_brief(
            root, scene, storyboard_scene, ledger_entry, registry,
            style_notes=style_notes, previous_scene=previous_scene, next_scene=next_scene,
            correction=correction, seed=deterministic_seed(scene_id, attempt=attempt), attempt=attempt,
        )
        director.write_director_brief(chapter_dir, brief)

    # -- 3. upscale (only QC PASS) ---------------------------------------------
    final_path = chapter_dir / "images" / "final" / f"{scene_id}.png"
    upscale_config = preferences.get("upscale", {})
    if entry.get("image_qc") == "PASS" and upscale_config.get("enabled", True):
        if not final_path.exists():
            result = providers["upscaler"].upscale(
                draft_path, final_path,
                scale=int(upscale_config.get("scale", 4)),
                qc_status="PASS",
            )
            _update_scene_log(chapter_dir, scene_id, "upscale", {"size": [result.width, result.height], "provider": result.provider})
        entry["upscale_status"] = "PASS"
        entry["final_image"] = f"images/final/{scene_id}.png"
    else:
        entry["upscale_status"] = "SKIPPED" if entry.get("image_qc") == "PASS" else "BLOCKED"

    entry["draft_image"] = f"images/draft/{scene_id}.png"
    entry.update(
        {
            "scene_id": scene_id,
            "source_span": scene.get("source_span", ""),
            "zh_text": scene.get("zh_narration", ""),
            "zh_subtitle": scene.get("zh_narration", ""),
            "character_states": scene.get("character_states", []),
            "setting_id": scene.get("setting_id", ""),
            "asset_refs": [ref["asset_id"] for ref in brief.get("references", [])],
        }
    )
    scene_manifest.upsert_scene(manifest, entry)
    scene_manifest.save_manifest(chapter_dir, manifest)
    return entry


def process_scene_audio(
    root: str | Path,
    chapter_dir: str | Path,
    scene: dict[str, Any],
    *,
    preferences: dict[str, Any],
    providers: dict[str, Any],
) -> dict[str, Any]:
    """Audio phase: scene-level translation -> TTS (renderer already released)."""
    chapter_dir = Path(chapter_dir)
    scene_id = scene["scene_id"]
    manifest = scene_manifest.load_manifest(chapter_dir)
    entry = scene_manifest.get_scene(manifest, scene_id) or {"scene_id": scene_id}

    # -- translation (scene-level zh -> en) ----------------------------------
    translation_entry = translation.load_scene_translation(chapter_dir, scene_id)
    translation_provider = preferences.get("translation", {}).get("provider", "agent")
    if translation_entry is None and translation_provider == "mock":
        translation_entry = {
            "scene_id": scene_id,
            "zh_text": scene.get("zh_narration", ""),
            "en_text": mock_translate(scene.get("zh_narration", "")),
            "status": "PASS",
            "provider": "mock",
            "created_at": _now(),
        }
        translation.save_scene_translation(chapter_dir, translation_entry)
    if translation_entry and translation_entry.get("status") == "PASS":
        entry["translation_status"] = "PASS"
        entry["en_text"] = translation_entry.get("en_text", "")
        _update_scene_log(chapter_dir, scene_id, "translation", "ok")
    else:
        entry["translation_status"] = "WAITING"
        _update_scene_log(chapter_dir, scene_id, "translation", "waiting for agent translation")

    # -- TTS (scene-level WAV) ------------------------------------------------
    audio_path = chapter_dir / "audio" / f"{scene_id}.wav"
    if entry.get("translation_status") == "PASS":
        if not audio_path.exists():
            tts_config = preferences.get("tts", {})
            tts_result = providers["tts"].synthesize(
                TTSRequest(
                    scene_id=scene_id,
                    text=entry["en_text"],
                    output_path=str(audio_path),
                    voice=tts_config.get("voice", "af_heart"),
                    speed=float(tts_config.get("speed", 1.0)),
                    language=tts_config.get("language", "en-us"),
                    metadata={"emotion": scene.get("emotion", "")},
                )
            )
            _update_scene_log(chapter_dir, scene_id, "tts", {"duration": tts_result.duration, "voice": tts_result.voice})
        sidecar = load_json(audio_path.with_suffix(".json"))
        entry["tts_status"] = "PASS"
        entry["audio"] = f"audio/{scene_id}.wav"
        entry["duration"] = sidecar.get("duration", 0.0)
    else:
        entry["tts_status"] = "WAITING"

    entry["en_subtitle"] = entry.get("en_text", "")
    scene_manifest.upsert_scene(manifest, entry)
    scene_manifest.save_manifest(chapter_dir, manifest)
    _update_scene_log(chapter_dir, scene_id, "finished_at", _now())
    return entry


# ---------------------------------------------------------------------------
# Batch entry points
# ---------------------------------------------------------------------------

def run_scenes(
    root: str | Path,
    chapter: str,
    *,
    scene_ids: list[str] | None = None,
    limit: int | None = None,
    require_pilot: bool = False,
) -> dict[str, Any]:
    root = Path(root)
    require_visual_asset_gate(root)
    if require_pilot:
        require_pilot_gate(root)

    chapter_dir = chapter_path(root, chapter)
    preferences = load_preferences(root)
    narration_doc = load_narration_scenes(chapter_dir)
    storyboard_path = video_state.chapter_artifacts(chapter_dir)["storyboard"]
    storyboard_doc = load_json(storyboard_path) if storyboard_path.exists() else None
    ledger = continuity.load_ledger(chapter_dir)
    registry = asset_registry.load_registry(root)

    manifest = scene_manifest.load_manifest(chapter_dir)
    targets: list[dict[str, Any]] = []
    for scene in narration_doc.get("scenes", []):
        scene_id = scene.get("scene_id")
        if scene_ids and scene_id not in scene_ids:
            continue
        if video_state.scene_complete(manifest.get("scenes", {}).get(scene_id)):
            continue  # resume rule: never redo a fully-PASS scene
        targets.append(scene)
        if limit and len(targets) >= limit:
            break

    providers = build_providers(preferences) if targets else {}
    renderer = providers.get("renderer")
    upscaler = providers.get("upscaler")
    tts = providers.get("tts")

    # Phase A (image): renderer + upscaler stay resident for the whole pass.
    try:
        if renderer is not None:
            renderer.warm()
        if upscaler is not None:
            upscaler.warm()
        for scene in targets:
            process_scene_image(
                root, chapter_dir, scene,
                narration_doc=narration_doc, storyboard_doc=storyboard_doc,
                ledger=ledger, registry=registry, preferences=preferences, providers=providers,
            )
    finally:
        # Free VRAM before the TTS phase: FLUX and IndexTTS must not share the GPU.
        for provider in (renderer, upscaler):
            if provider is not None:
                provider.release()

    # Phase B (audio): translation + TTS, model resident for the whole pass.
    processed: list[str] = []
    try:
        if tts is not None:
            tts.warm()
        for scene in targets:
            process_scene_audio(root, chapter_dir, scene, preferences=preferences, providers=providers)
            processed.append(scene["scene_id"])
    finally:
        if tts is not None:
            tts.release()

    _finalize_chapter(root, chapter_dir, preferences, processed)
    return {"chapter": chapter, "processed": processed, "skipped_pass": len(narration_doc.get("scenes", [])) - len(targets)}


def _finalize_chapter(root: Path, chapter_dir: Path, preferences: dict[str, Any], processed: list[str]) -> None:
    """Regenerate subtitles whenever any scene changed, then refresh the manifest check."""
    if not processed:
        return
    manifest = scene_manifest.load_manifest(chapter_dir)
    ready = [
        scene_manifest.get_scene(manifest, scene_id)
        for scene_id in scene_manifest.ordered_scene_ids(manifest)
    ]
    ready = [entry for entry in ready if entry and entry.get("tts_status") == "PASS"]
    if ready:
        subtitle_manifest = {"scenes": {entry["scene_id"]: entry for entry in ready}}
        subtitle_config = preferences.get("subtitles", {})
        subtitles.generate_subtitles(
            subtitle_manifest,
            chapter_dir / "subtitles",
            default_language=subtitle_config.get("default_language", "en"),
            keep_chinese=subtitle_config.get("keep_chinese", True),
            generate_bilingual=subtitle_config.get("generate_bilingual", True),
            bilingual_order=subtitle_config.get("bilingual_order", ["en", "zh"]),
        )


def run_pilot(root: str | Path, chapter: str, scene_count: int | None = None) -> dict[str, Any]:
    """Gate 2 prep: produce 10-20 consecutive pilot scenes end to end."""
    preferences = load_preferences(root)
    if scene_count is None:
        scene_count = int(preferences.get("pilot", {}).get("scene_count", 15))
    return run_scenes(root, chapter, limit=scene_count, require_pilot=False)


def run_batch(root: str | Path, chapter: str) -> dict[str, Any]:
    """Unattended whole-book production; requires PILOT_APPROVED."""
    return run_scenes(root, chapter, require_pilot=True)


def regenerate_scene(root: str | Path, chapter: str, scene_id: str, scope: str = "all") -> dict[str, Any]:
    """Regenerate one scene only (image / translation / tts / subtitle / all)."""
    root = Path(root)
    chapter_dir = chapter_path(root, chapter)
    steps = video_state.regenerate_plan(scope)
    removed = video_state.clear_scene_artifacts(chapter_dir, scene_id, [step for step in steps if step != "subtitles"])
    if "subtitles" in steps:
        video_state.clear_scene_artifacts(chapter_dir, scene_id, ["subtitles"])

    # Drop stale manifest fields so resume treats the scene as pending again.
    manifest = scene_manifest.load_manifest(chapter_dir)
    entry = manifest.get("scenes", {}).get(scene_id)
    if entry:
        field_map = {
            "draft_image": ["image_qc", "draft_image", "final_image", "upscale_status"],
            "translation": ["translation_status", "en_text"],
            "tts": ["tts_status", "audio", "duration"],
        }
        for step, fields in field_map.items():
            if step in steps or (step == "draft_image" and "image_qc" in steps):
                for field in fields:
                    entry.pop(field, None)
        scene_manifest.save_manifest(chapter_dir, manifest)

    summary = run_scenes(root, chapter, scene_ids=[scene_id])
    summary["regenerated"] = scene_id
    summary["scope"] = scope
    summary["removed"] = removed
    return summary


def export_jianying(root: str | Path, chapter: str, project_name: str | None = None) -> dict[str, Any]:
    from .exporters.jianying import export_jianying_draft

    root = Path(root)
    chapter_dir = chapter_path(root, chapter)
    manifest = scene_manifest.load_manifest(chapter_dir)
    errors = scene_manifest.validate_manifest(manifest, chapter_dir)
    name = project_name or f"{root.name}-{chapter}"
    report = export_jianying_draft(
        manifest, chapter_dir, root / "exports",
        project_name=name,
        include_chinese_track=load_preferences(root).get("subtitles", {}).get("generate_bilingual", True),
    )
    report["manifest_errors"] = errors
    return report
