"""Tests for the single_scene video pipeline (schema, assets, continuity,
director, renderer mock, QC, upscale gate, translation, TTS, subtitles,
manifest, Jianying export, stale detection, resume, retry, regeneration).

These tests use mock providers only, so they run without GPU, torch, kokoro
or realesrgan.
"""

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "TOOLS"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from PIL import Image  # noqa: E402

from novel_to_comic import (  # noqa: E402
    asset_registry,
    continuity,
    director,
    image_qc,
    pipeline,
    scene_manifest,
    scenes,
    subtitles,
    translation,
    video_state,
)
from novel_to_comic.config import load_preferences, validate_preferences  # noqa: E402
from novel_to_comic.exporters.jianying import export_jianying_draft  # noqa: E402
from novel_to_comic.renderers.base import RenderRequest, deterministic_seed  # noqa: E402
from novel_to_comic.renderers.mock import MockRenderer  # noqa: E402
from novel_to_comic.source import parse_txt  # noqa: E402
from novel_to_comic.tts.base import TTSRequest, validate_tts_mapping, wav_duration  # noqa: E402
from novel_to_comic.tts.mock import MockTTS  # noqa: E402
from novel_to_comic.upscalers.base import UpscaleGateError, create_upscaler  # noqa: E402


SCENE_COUNT = 10


def make_png(path: Path, size=(256, 256), color=(120, 80, 200)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, format="PNG")


def outfit_for(index: int) -> str:
    return "default" if index < 5 else "travel-black"


def build_narration_doc(scene_count: int = SCENE_COUNT) -> dict:
    scene_list = []
    for index in range(1, scene_count + 1):
        setting = "set-001" if index <= 5 else "set-002"
        scene_list.append(
            {
                "scene_id": scenes.make_scene_id(index),
                "source_span": f"ch001:p{index}",
                "zh_narration": f"第{index}段解说：林晚在故事中向前推进了一步。",
                "story_beat": f"推进剧情第 {index} 步",
                "visual_beat": f"画面表现第 {index} 个关键瞬间",
                "characters": ["char-001"] + (["char-002"] if index <= 2 else []),
                "character_states": [f"char-001@state-{index:03d}"],
                "setting_id": setting,
                "props": ["prop-sword-001"] if index >= 3 else [],
                "emotion": "紧张" if index % 2 else "平静",
                "camera_intent": "medium",
                "transition": "cut",
            }
        )
    return {"chapter": "ch001", "target_format": "single_scene", "scenes": scene_list}


def build_storyboard_doc(scene_count: int = SCENE_COUNT) -> dict:
    shots = scenes.SHOT_SIZES
    angles = scenes.CAMERA_ANGLES
    scene_list = []
    for index in range(1, scene_count + 1):
        scene_list.append(
            {
                "scene_id": scenes.make_scene_id(index),
                "story_purpose": f"第 {index} 个 beat 的叙事任务",
                "visual_purpose": f"第 {index} 个 beat 的画面任务",
                "shot_size": shots[(index - 1) % len(shots)],
                "angle": angles[(index * 2) % len(angles)],
                "characters": [{"id": "char-001", "outfit_id": outfit_for(index)}],
                "setting_id": "set-001" if index <= 5 else "set-002",
                "props": ["prop-sword-001"] if index >= 3 else [],
                "action": f"动作 {index}",
                "expression": "focused",
                "composition": "主体偏左，视线朝右" if index % 2 else "主体偏右，视线朝左",
                "transition_from_previous": "cut",
            }
        )
    return {"chapter": "ch001", "target_format": "single_scene", "scenes": scene_list}


def build_ledger(scene_count: int = SCENE_COUNT) -> dict:
    entries = []
    for index in range(1, scene_count + 1):
        char_001 = {
            "character_id": "char-001",
            "state_id": f"state-{index:03d}",
            "outfit_id": outfit_for(index),
            "expression": "focused",
        }
        if index == 5:
            char_001["outfit_change"] = True
        if index >= 4:
            char_001["injury"] = "left-shoulder-cut"
        if index >= 3:
            char_001["weapon"] = "prop-sword-001"
        characters = [char_001]
        if index <= 2:
            characters.append(
                {"character_id": "char-002", "state_id": "state-001", "outfit_id": "default", "expression": "calm"}
            )
        entries.append(
            {
                "scene_id": scenes.make_scene_id(index),
                "setting_id": "set-001" if index <= 5 else "set-002",
                "time": "day" if index <= 7 else "night",
                "weather": "rain" if index >= 6 else "",
                "characters": characters,
                "props": ["prop-sword-001"] if index >= 3 else [],
                "relationship_state": "陌生人 -> 救命恩人" if index >= 4 else "陌生人",
                "important_story_state": f"state at scene {index}",
            }
        )
    return {"chapter": "ch001", "entries": entries}


def scaffold_project(root: Path, scene_count: int = SCENE_COUNT) -> Path:
    """Create a fully-gated single_scene project with approved mock assets."""
    (root / "rights").mkdir(parents=True, exist_ok=True)
    (root / "rights" / "PROJECT_RIGHTS.md").write_text("private experiment\n", encoding="utf-8")

    preferences = {
        "project": {
            "mode": "private_experiment",
            "target_language": "en",
            "target_format": "single_scene",
            "automation_level": 3,
            "human_review": True,
        },
        "input": {"supported_formats": ["txt", "epub"]},
        "visuals": {"style_family": "cinematic manga"},
        "approvals": {"visual_assets_required": True, "pilot_required": True},
        "image_generation": {
            "renderer": "mock",
            "width": 256,
            "height": 384,
            "device": "cpu",
            "seed_policy": "deterministic_by_scene",
            "require_reference_images": True,
        },
        "upscale": {
            "enabled": True,
            "provider": "mock",
            "model": "RealESRGAN_x4plus_anime_6B",
            "scale": 4,
            "only_after_qc_pass": True,
        },
        "translation": {"provider": "mock"},
        "tts": {
            "provider": "mock",
            "model": "hexgrad/Kokoro-82M",
            "language": "en-us",
            "voice": "af_heart",
            "speed": 1.0,
            "output_format": "wav",
        },
        "subtitles": {
            "default_language": "en",
            "keep_chinese": True,
            "generate_bilingual": True,
            "bilingual_order": ["en", "zh"],
        },
        "qc": {"max_retry": 3},
        "pilot": {"scene_count": scene_count},
    }
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "user-preferences.json").write_text(
        json.dumps(preferences, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Visual assets + approval markers (Gate 1 cleared).
    visual = root / "visual-bible"
    make_png(visual / "style-samples" / "style-preview.png")
    for char_id in ("char-001", "char-002"):
        make_png(visual / "characters" / char_id / "identity" / "reference-sheet.png")
        make_png(visual / "characters" / char_id / "wardrobe" / "default" / "reference.png")
    make_png(visual / "characters" / "char-001" / "wardrobe" / "travel-black" / "reference.png")
    for setting_id in ("set-001", "set-002"):
        make_png(visual / "settings" / setting_id / "wide-day.png")
        make_png(visual / "settings" / setting_id / "wide-night.png")
    make_png(visual / "props" / "prop-sword-001" / "reference.png")
    (visual / "STYLE_APPROVED").write_text("approved\n", encoding="utf-8")
    (visual / "REFERENCE_ASSETS_APPROVED").write_text("approved\n", encoding="utf-8")

    registry = {"assets": {}}
    for char_id in ("char-001", "char-002"):
        asset_registry.register_asset(
            root, registry, asset_id=char_id, asset_type="character_identity",
            path=f"visual-bible/characters/{char_id}/identity/reference-sheet.png", status="APPROVED",
        )
        asset_registry.register_asset(
            root, registry, asset_id=f"{char_id}@default", asset_type="outfit",
            path=f"visual-bible/characters/{char_id}/wardrobe/default/reference.png", status="APPROVED",
        )
    asset_registry.register_asset(
        root, registry, asset_id="char-001@travel-black", asset_type="outfit",
        path="visual-bible/characters/char-001/wardrobe/travel-black/reference.png", status="APPROVED",
    )
    for setting_id in ("set-001", "set-002"):
        asset_registry.register_asset(
            root, registry, asset_id=setting_id, asset_type="setting",
            path=f"visual-bible/settings/{setting_id}/wide-day.png", status="APPROVED",
        )
    asset_registry.register_asset(
        root, registry, asset_id="prop-sword-001", asset_type="prop",
        path="visual-bible/props/prop-sword-001/reference.png", status="APPROVED",
    )
    asset_registry.save_registry(root, registry)

    # Chapter documents.
    chapter = root / "chapters" / "ch001"
    scenes.write_json(chapter / "narration" / "scenes.json", build_narration_doc(scene_count))
    scenes.write_json(chapter / "single-scene-storyboard.json", build_storyboard_doc(scene_count))
    scenes.write_json(chapter / "continuity-ledger.json", build_ledger(scene_count))
    return chapter


class SceneSchemaTests(unittest.TestCase):
    def test_scene_id_helpers(self):
        self.assertEqual(scenes.make_scene_id(1), "scene_0001")
        self.assertEqual(scenes.parse_scene_id("scene_0021"), 21)
        self.assertTrue(scenes.is_scene_id("scene_0321"))
        self.assertFalse(scenes.is_scene_id("scene-1"))
        with self.assertRaises(ValueError):
            scenes.parse_scene_id("page_001")

    def test_narration_validation_rejects_duplicates_and_gaps(self):
        doc = build_narration_doc(3)
        self.assertEqual(scenes.validate_narration_scenes(doc), [])

        doc["scenes"][1]["scene_id"] = "scene_0001"
        errors = scenes.validate_narration_scenes(doc)
        self.assertTrue(any("duplicate" in error for error in errors))

        doc = build_narration_doc(3)
        doc["scenes"][2]["scene_id"] = "scene_0005"
        errors = scenes.validate_narration_scenes(doc)
        self.assertTrue(any("contiguous" in error for error in errors))

        doc = build_narration_doc(2)
        del doc["scenes"][0]["zh_narration"]
        errors = scenes.validate_narration_scenes(doc)
        self.assertTrue(any("zh_narration" in error for error in errors))

    def test_storyboard_validation_forbids_grids_and_requires_outfit(self):
        doc = build_storyboard_doc(3)
        self.assertEqual(scenes.validate_storyboard_scenes(doc), [])

        doc["scenes"][0]["panels"] = [{"panel": 1}]
        errors = scenes.validate_storyboard_scenes(doc)
        self.assertTrue(any("grid" in error for error in errors))

        doc = build_storyboard_doc(3)
        del doc["scenes"][0]["characters"][0]["outfit_id"]
        errors = scenes.validate_storyboard_scenes(doc)
        self.assertTrue(any("outfit_id" in error for error in errors))


class AssetRegistryTests(unittest.TestCase):
    def test_lock_blocks_overwrite_and_gates_block_without_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter = scaffold_project(root)

            registry = asset_registry.load_registry(root)
            asset_registry.set_asset_status(registry, "char-001", "LOCKED")
            with self.assertRaises(asset_registry.AssetLockError):
                asset_registry.register_asset(
                    root, registry, asset_id="char-001", asset_type="character_identity",
                    path="visual-bible/characters/char-001/identity/reference-sheet.png", status="DRAFT",
                )
            with self.assertRaises(asset_registry.AssetLockError):
                asset_registry.assert_writable(registry, "char-001")

            # Gates cleared in the scaffold.
            self.assertEqual(asset_registry.check_production_gates(root, registry), [])

            # Removing markers must hard-block production.
            (root / "visual-bible" / "REFERENCE_ASSETS_APPROVED").unlink()
            errors = asset_registry.check_production_gates(root, registry)
            self.assertTrue(any("REFERENCE_ASSETS_APPROVED" in error for error in errors))

    def test_scene_assets_gate_requires_approved_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scaffold_project(root)
            registry = asset_registry.load_registry(root)

            scene = {
                "scene_id": "scene_0001",
                "characters": [{"id": "char-001", "outfit_id": "default"}],
                "setting_id": "set-001",
                "props": ["prop-sword-001"],
            }
            self.assertEqual(asset_registry.check_scene_assets(root, registry, scene), [])

            scene["characters"][0]["outfit_id"] = "battle-damaged"
            scene["props"] = ["prop-amulet-999"]
            errors = asset_registry.check_scene_assets(root, registry, scene)
            self.assertTrue(any("battle-damaged" in error for error in errors))
            self.assertTrue(any("prop-amulet-999" in error for error in errors))

    def test_asset_hash_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scaffold_project(root)
            registry = asset_registry.load_registry(root)
            self.assertTrue(asset_registry.verify_asset_hash(root, registry, "char-001"))
            target = root / "visual-bible/characters/char-001/identity/reference-sheet.png"
            make_png(target, color=(1, 2, 3))
            self.assertFalse(asset_registry.verify_asset_hash(root, registry, "char-001"))


class ContinuityTests(unittest.TestCase):
    def test_ledger_validation_and_resolution(self):
        narration = build_narration_doc(5)
        ledger = build_ledger(5)
        self.assertEqual(continuity.validate_ledger(ledger, narration), [])

        entry = continuity.resolve_state_for_scene(ledger, "scene_0003")
        self.assertEqual(entry["setting_id"], "set-001")
        char = continuity.character_state_at(ledger, "scene_0004", "char-001")
        self.assertEqual(char["injury"], "left-shoulder-cut")

        del ledger["entries"][2]
        errors = continuity.validate_ledger(ledger, narration)
        self.assertTrue(any("scene_0003" in error for error in errors))

    def test_state_persistence_flags_vanishing_injury(self):
        ledger = build_ledger(6)
        self.assertEqual(continuity.check_state_persistence(ledger), [])

        # Injury silently vanishes in scene 6 -> must be flagged.
        broken = build_ledger(6)
        del broken["entries"][5]["characters"][0]["injury"]
        errors = continuity.check_state_persistence(broken)
        self.assertTrue(any("injury" in error for error in errors))

        # Explicit clear is legitimate.
        cleared = build_ledger(6)
        cleared["entries"][5]["characters"][0].pop("injury")
        cleared["entries"][5]["characters"][0]["cleared"] = ["injury"]
        self.assertEqual(continuity.check_state_persistence(cleared), [])

    def test_outfit_change_requires_marker(self):
        broken = build_ledger(6)
        broken["entries"][4]["characters"][0]["outfit_id"] = "formal"
        errors = continuity.check_state_persistence(broken)
        self.assertTrue(any("outfit" in error for error in errors))


class DirectorTests(unittest.TestCase):
    def test_camera_plan_avoids_repetition(self):
        plan = director.plan_camera_sequence(24)
        self.assertEqual(len(plan), 24)
        for index in range(len(plan) - 2):
            window = [json.dumps(plan[slot], sort_keys=True) for slot in range(index, index + 3)]
            self.assertEqual(len(set(window)), 3, "three consecutive identical camera setups")

    def test_shot_repetition_warning(self):
        storyboard = build_storyboard_doc(6)
        self.assertEqual(director.check_shot_repetition(storyboard), [])
        for scene in storyboard["scenes"]:
            scene["shot_size"] = "medium"
            scene["angle"] = "eye_level"
        warnings = director.check_shot_repetition(storyboard)
        self.assertTrue(warnings)

    def test_brief_labels_references_and_locks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scaffold_project(root)
            registry = asset_registry.load_registry(root)
            narration = build_narration_doc(5)
            ledger = build_ledger(5)
            scene = narration["scenes"][3]  # scene_0004: injury + weapon active

            brief = director.build_director_brief(
                root, scene, build_storyboard_doc(5)["scenes"][3],
                continuity.resolve_state_for_scene(ledger, "scene_0004"),
                registry, style_notes="cinematic manga",
                previous_scene=narration["scenes"][2], next_scene=narration["scenes"][4],
            )

            roles = [reference["role"] for reference in brief["references"]]
            self.assertEqual(roles[0], "identity")
            self.assertIn("outfit", roles)
            self.assertIn("setting", roles)
            self.assertEqual(roles[-1], "style")
            self.assertIn("image 1 = identity", brief["prompt"])
            self.assertIn("left-shoulder-cut", brief["prompt"])
            self.assertEqual(brief["setting_lock"], "set-001")
            self.assertIn("panel grid", brief["negative_constraints"][0])

            json_path, md_path = director.write_director_brief(Path(tmp) / "ch", brief)
            self.assertTrue(json_path.exists() and md_path.exists())
            self.assertEqual(director.load_director_brief(Path(tmp) / "ch", "scene_0004")["scene_id"], "scene_0004")


class RendererQcUpscaleTests(unittest.TestCase):
    def test_mock_renderer_is_deterministic_and_records_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            renderer = MockRenderer()
            request = RenderRequest(
                prompt="hero stands in the rain",
                output_path=str(Path(tmp) / "a.png"),
                width=256,
                height=384,
                seed=deterministic_seed("scene_0001"),
                metadata={"scene_id": "scene_0001"},
            )
            first = renderer.render(request)
            request.output_path = str(Path(tmp) / "b.png")
            second = renderer.render(request)
            self.assertEqual(first.seed, second.seed)
            self.assertEqual(
                hashlib.sha256((Path(tmp) / "a.png").read_bytes()).hexdigest(),
                hashlib.sha256((Path(tmp) / "b.png").read_bytes()).hexdigest(),
            )
            with Image.open(Path(tmp) / "a.png") as image:
                self.assertEqual(image.size, (256, 384))
                self.assertIn("hero stands", image.text["ntc:prompt"])

    def test_qc_retry_manual_review_and_targeted_regeneration(self):
        brief = {"scene_id": "scene_0001", "references": [{"role": "identity", "asset_id": "char-001", "path": "x.png"}]}
        report = image_qc.qc_scene_image(Path("/does/not/exist.png"), brief)
        self.assertEqual(report["verdict"], "RETRY")

        plan = image_qc.plan_targeted_regeneration(
            {"checks": [{"check": "outfit", "status": "fail", "detail": "wrong coat"}]}
        )
        self.assertTrue(plan["needed"])
        self.assertTrue(any("outfit" in item for item in plan["emphasis"]))
        self.assertIn("outfit", plan["relock"])

        self.assertEqual(image_qc.decide_verdict(0, 3, report), "RETRY")
        self.assertEqual(image_qc.decide_verdict(3, 3, report), "MANUAL_REVIEW")
        self.assertEqual(image_qc.decide_verdict(9, 3, {"verdict": "PASS"}), "PASS")

    def test_upscale_gate_blocks_non_pass_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "draft.png"
            make_png(src, size=(64, 96))
            upscaler = create_upscaler("mock")

            with self.assertRaises(UpscaleGateError):
                upscaler.upscale(src, Path(tmp) / "final.png", scale=4, qc_status="RETRY")

            result = upscaler.upscale(src, Path(tmp) / "final.png", scale=4, qc_status="PASS")
            self.assertEqual((result.width, result.height), (256, 384))
            self.assertEqual(result.model, "RealESRGAN_x4plus_anime_6B")


class TranslationTtsSubtitleTests(unittest.TestCase):
    def test_terminology_validation_and_application(self):
        terminology = {"characters": {"林晚": "Lin Wan"}, "locations": {}, "skills": {}, "organizations": {}, "props": {"听雨剑": "Rain-Listener Sword"}, "titles": {}}
        self.assertEqual(translation.validate_terminology(terminology), [])

        bad = dict(terminology, characters={"林晚": ""})
        self.assertTrue(translation.validate_terminology(bad))

        flagged = {
            "characters": {"林晚": {"en": "Lin Wan", "avoid": ["Ling Wan"]}},
            "locations": {}, "skills": {}, "organizations": {}, "props": {}, "titles": {},
        }
        self.assertEqual(translation.validate_terminology(flagged), [])
        errors = translation.check_terminology_applied("Ling Wan drew the sword.", flagged)
        self.assertTrue(errors)

    def test_translation_mapping_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp)
            narration = build_narration_doc(2)
            translation.save_scene_translation(
                chapter,
                {"scene_id": "scene_0001", "zh_text": narration["scenes"][0]["zh_narration"], "en_text": "Rain fell.", "status": "PASS"},
            )
            errors = translation.validate_translation_mapping(chapter, narration)
            self.assertTrue(any("scene_0002" in error for error in errors))

            translation.save_scene_translation(
                chapter,
                {"scene_id": "scene_0002", "zh_text": "不同的文本", "en_text": "Wrong source.", "status": "PASS"},
            )
            errors = translation.validate_translation_mapping(chapter, narration)
            self.assertTrue(any("drifted" in error for error in errors))

    def test_mock_tts_writes_wav_sidecar_and_mapping_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp)
            tts = MockTTS()
            narration = build_narration_doc(2)
            for index in (1, 2):
                scene_id = scenes.make_scene_id(index)
                result = tts.synthesize(
                    TTSRequest(scene_id=scene_id, text=f"Scene {index} narration text for testing.", output_path=str(chapter / "audio" / f"{scene_id}.wav"))
                )
                self.assertGreater(result.duration, 0)
                self.assertEqual(result.voice, "af_heart")

            self.assertEqual(validate_tts_mapping(chapter, narration), [])
            duration = wav_duration(chapter / "audio" / "scene_0001.wav")
            self.assertIsNotNone(duration)
            sidecar = json.loads((chapter / "audio" / "scene_0001.json").read_text(encoding="utf-8"))
            self.assertEqual(sidecar["scene_id"], "scene_0001")
            self.assertAlmostEqual(sidecar["duration"], duration, places=2)

    def test_subtitle_timeline_uses_real_durations(self):
        manifest = {
            "scenes": {
                "scene_0002": {"scene_id": "scene_0002", "duration": 4.0, "en_text": "Second scene. More words here.", "zh_text": "第二个场景。"},
                "scene_0001": {"scene_id": "scene_0001", "duration": 6.5, "en_text": "First scene opens. Rain falls hard.", "zh_text": "第一幕开始。雨下得很大。"},
            }
        }
        timeline = subtitles.build_timeline(manifest)
        # Ordering must come from numeric scene id, not dict order.
        self.assertAlmostEqual(timeline["scene_0001"]["start"], 0.0)
        self.assertAlmostEqual(timeline["scene_0002"]["start"], 6.5)
        self.assertAlmostEqual(timeline["scene_0002"]["end"], 10.5)

        with tempfile.TemporaryDirectory() as tmp:
            written = subtitles.generate_subtitles(manifest, Path(tmp))
            self.assertTrue(Path(written["en"]).exists())
            self.assertTrue(Path(written["zh"]).exists())
            self.assertTrue(Path(written["bilingual"]).exists())
            en_srt = Path(written["en"]).read_text(encoding="utf-8")
            self.assertIn("00:00:00,000 --> ", en_srt)
            self.assertIn("00:00:10,500", en_srt)
            bilingual = Path(written["bilingual"]).read_text(encoding="utf-8")
            self.assertIn("Rain falls hard", bilingual)
            self.assertIn("第一幕开始", bilingual)

        self.assertEqual(subtitles.format_srt_timestamp(3661.25), "01:01:01,250")


class PipelineE2ETests(unittest.TestCase):
    def _scaffold(self, tmp: str) -> Path:
        root = Path(tmp)
        scaffold_project(root)
        return root

    def test_full_pilot_resume_regenerate_and_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._scaffold(tmp)

            # Gate 2 must block whole-book production before pilot approval.
            with self.assertRaises(asset_registry.AssetLockError):
                pipeline.run_batch(root, "ch001")

            summary = pipeline.run_pilot(root, "ch001")
            self.assertEqual(summary["processed"], [scenes.make_scene_id(i) for i in range(1, SCENE_COUNT + 1)])

            chapter = root / "chapters" / "ch001"
            manifest = scene_manifest.load_manifest(chapter)
            self.assertEqual(len(manifest["scenes"]), SCENE_COUNT)
            for scene_id in scene_manifest.ordered_scene_ids(manifest):
                entry = manifest["scenes"][scene_id]
                self.assertTrue(scene_manifest.scene_is_pass(entry), f"{scene_id} not PASS: {entry}")
                self.assertTrue((chapter / entry["final_image"]).exists())
                self.assertTrue((chapter / entry["audio"]).exists())
                self.assertEqual(entry["image_qc"], "PASS")
                self.assertEqual(entry["translation_status"], "PASS")
                self.assertEqual(entry["tts_status"], "PASS")
                self.assertEqual(entry["upscale_status"], "PASS")
                self.assertGreater(entry["duration"], 0)

            # Final images are 4x the draft resolution (mock upscale = LANCZOS).
            final_img_0001 = chapter / manifest["scenes"]["scene_0001"]["final_image"]
            with Image.open(final_img_0001) as final_image:
                self.assertEqual(final_image.size, (1024, 1536))

            # Subtitles: en default + zh kept + bilingual, timed to WAV durations.
            for name in ("subtitles.en.srt", "subtitles.zh.srt", "subtitles.bilingual.srt"):
                self.assertTrue((chapter / "subtitles" / name).exists())
            self.assertEqual(scene_manifest.validate_manifest(manifest, chapter), [])
            self.assertEqual(validate_tts_mapping(chapter, scenes.load_narration_scenes(chapter)), [])

            # Per-scene production logs exist.
            self.assertTrue((chapter / "logs" / "scene_0001.json").exists())

            # Jianying export: timeline keyed by scene_id, durations from TTS.
            report = pipeline.export_jianying(root, "ch001")
            draft_path = Path(report["draft_dir"]) / "draft_content.json"
            self.assertTrue(draft_path.exists())
            draft = scenes.load_json(draft_path)
            track_types = [track["type"] for track in draft["tracks"]]
            self.assertIn("video", track_types)
            self.assertIn("audio", track_types)
            self.assertIn("text", track_types)
            video_track = next(track for track in draft["tracks"] if track["type"] == "video")
            self.assertEqual(len(video_track["segments"]), SCENE_COUNT)
            cursor = 0
            for segment in video_track["segments"]:
                self.assertEqual(segment["target_timerange"]["start"], cursor)
                self.assertGreater(segment["target_timerange"]["duration"], 0)
                cursor += segment["target_timerange"]["duration"]
            self.assertEqual(cursor, draft["duration"])

            # --- Resume: rerun must not reprocess any PASS scene ---
            final_img_0006 = chapter / manifest["scenes"]["scene_0006"]["final_image"]
            before = final_img_0006.stat().st_mtime_ns
            rerun = pipeline.run_pilot(root, "ch001")
            self.assertEqual(rerun["processed"], [])
            self.assertEqual(final_img_0006.stat().st_mtime_ns, before)

            # --- Failure at scene 7: rerun continues from scene 7 only ---
            self._break_scene(chapter, "scene_0007")
            kept = {
                scene_id: (chapter / manifest["scenes"][scene_id]["final_image"]).stat().st_mtime_ns
                for scene_id in ("scene_0001", "scene_0006", "scene_0008")
            }
            resumed = pipeline.run_pilot(root, "ch001")
            self.assertEqual(resumed["processed"], ["scene_0007"])
            for scene_id, mtime in kept.items():
                self.assertEqual((chapter / manifest["scenes"][scene_id]["final_image"]).stat().st_mtime_ns, mtime)
            manifest = scene_manifest.load_manifest(chapter)
            self.assertTrue(scene_manifest.scene_is_pass(manifest["scenes"]["scene_0007"]))

            # --- Single-scene regeneration (image only) ---
            final_img_0005 = chapter / manifest["scenes"]["scene_0005"]["final_image"]
            other_before = final_img_0005.stat().st_mtime_ns
            regen = pipeline.regenerate_scene(root, "ch001", "scene_0003", scope="image")
            self.assertEqual(regen["processed"], ["scene_0003"])
            self.assertEqual(final_img_0005.stat().st_mtime_ns, other_before)
            manifest = scene_manifest.load_manifest(chapter)
            self.assertTrue(scene_manifest.scene_is_pass(manifest["scenes"]["scene_0003"]))
            # translation/tts survive an image-only regeneration
            self.assertEqual(manifest["scenes"]["scene_0003"]["tts_status"], "PASS")

            # --- Stale detection after editing zh narration ---
            narration_path = chapter / "narration" / "scenes.json"
            future = (chapter / "translation" / "scene_0001.json").stat().st_mtime + 60
            os.utime(narration_path, (future, future))
            stale = video_state.detect_stale(chapter, root)
            self.assertIn("scene_0001", stale)
            self.assertTrue(any("translation" in reason for reason in stale["scene_0001"]))

            # --- Pilot approval unlocks batch mode (nothing left to do) ---
            pipeline.mark_approved(root, "pilot")
            self.assertTrue((root / "visual-bible" / "PILOT_APPROVED").exists())
            batch = pipeline.run_batch(root, "ch001")
            self.assertEqual(batch["processed"], [])

    def _break_scene(self, chapter: Path, scene_id: str) -> None:
        """Simulate a mid-production crash: artifacts gone, manifest entry gone."""
        for rel in (
            f"images/draft/{scene_id}.png",
            f"images/final/{scene_id}.png",
            f"qc/{scene_id}.qc.json",
            f"audio/{scene_id}.wav",
            f"audio/{scene_id}.json",
            f"translation/{scene_id}.json",
        ):
            path = chapter / rel
            if path.exists():
                path.unlink()
        manifest = scene_manifest.load_manifest(chapter)
        manifest["scenes"].pop(scene_id, None)
        scene_manifest.save_manifest(chapter, manifest)

    def test_visual_asset_gate_blocks_pilot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._scaffold(tmp)
            (root / "visual-bible" / "REFERENCE_ASSETS_APPROVED").unlink()
            with self.assertRaises(asset_registry.AssetLockError):
                pipeline.run_pilot(root, "ch001")


class ConfigAndFixtureTests(unittest.TestCase):
    def test_repository_default_preferences_validate_as_single_scene(self):
        preferences = load_preferences(ROOT / "config" / "user-preferences.json")
        self.assertEqual(validate_preferences(preferences), [])
        self.assertEqual(preferences["project"]["target_format"], "single_scene")
        self.assertEqual(preferences["tts"]["provider"], "indextts")
        self.assertEqual(preferences["tts"]["reference_audio"], "audio-voice/narrator-reference.wav")
        self.assertEqual(preferences["tts"]["voice"], "af_heart")
        self.assertEqual(preferences["upscale"]["model"], "RealESRGAN_x4plus_anime_6B")
        self.assertEqual(preferences["image_generation"]["renderer"], "flux2_klein")

    def test_indextts_provider_requires_reference_audio(self):
        preferences = load_preferences(ROOT / "config" / "user-preferences.json")
        preferences["tts"].pop("reference_audio")
        errors = validate_preferences(preferences)
        self.assertTrue(any("reference_audio" in error for error in errors))

        # Provider factory must construct without heavy deps (lazy import).
        from novel_to_comic.tts.base import create_tts

        provider = create_tts("indextts", {"reference_audio": "audio-voice/narrator-reference.wav"})
        self.assertEqual(provider.name, "indextts")

    def test_sample_chinese_fixture_parses(self):
        text = (ROOT / "tests" / "fixtures" / "sample-novel-zh.txt").read_text(encoding="utf-8")
        parsed = parse_txt(text)
        self.assertEqual(parsed.title, "听雨剑")
        self.assertEqual(len(parsed.chapters), 1)
        self.assertIn("林晚", parsed.chapters[0].text)

    def test_video_state_summary_reports_next_scene(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scaffold_project(root)
            state = video_state.detect_video_state(root)
            chapter_state = state["chapters"]["ch001"]
            self.assertEqual(chapter_state["sections"]["narration"], "READY")
            self.assertEqual(chapter_state["sections"]["manifest"], "MISSING")
            self.assertEqual(chapter_state["next_scene"], "scene_0001")


if __name__ == "__main__":
    unittest.main()
