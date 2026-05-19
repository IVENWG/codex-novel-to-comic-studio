import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "TOOLS"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def valid_page_story_plan() -> dict:
    return {
        "chapter": "ch01",
        "status": "draft",
        "page_count_policy": "story_first_variable",
        "actual_page_count": 2,
        "reader_promise": "A clear two-page sample.",
        "must_include": ["setup", "hook"],
        "asset_gaps_before_director_briefs": [],
        "pages": [
            {
                "page": 1,
                "source_span": "ch001:p1",
                "story_job": "Set the protagonist's immediate problem.",
                "reader_enters_with": "Who is this?",
                "reader_leaves_with": "The hero has a problem.",
                "beats": ["hero appears", "problem is visible"],
                "tone": "curious",
                "info_density": "medium",
                "handoff": "Let the storyboarder open with a readable character beat.",
            },
            {
                "page": 2,
                "source_span": "ch001:p2",
                "story_job": "Turn the problem into a page-turn hook.",
                "reader_enters_with": "What will the hero do?",
                "reader_leaves_with": "The next scene promises action.",
                "beats": ["choice", "hook"],
                "tone": "urgent",
                "info_density": "medium",
                "handoff": "End with a clear next-scene question.",
            },
        ],
    }


def valid_page_script() -> dict:
    return {
        "chapter": "ch01",
        "status": "draft",
        "source_page_story_plan": "chapters/ch01/page-story-plan.json",
        "page_count_policy": "story_first_variable",
        "actual_page_count": 2,
        "script_strategy": "clarity over word count; no fixed dialogue quota",
        "critical_information": [
            {
                "id": "hero_problem",
                "description": "The protagonist has a concrete problem.",
                "source_span": "ch001:p1",
                "required": True,
            },
            {
                "id": "chapter_hook",
                "description": "The page turn promises action.",
                "source_span": "ch001:p2",
                "required": True,
            },
        ],
        "pages": [
            {
                "page": 1,
                "source_span": "ch001:p1",
                "story_job": "Set the protagonist's immediate problem.",
                "required_information": ["hero_problem"],
                "reader_state": {
                    "known_before": "The reader knows nothing.",
                    "new_information": "The hero has a visible problem.",
                    "open_question": "How will the hero respond?",
                },
                "information_density_goal": "clear enough to understand the problem; no fixed word count",
                "non_omittable_causality": ["Problem causes the next-page choice."],
                "source_lines": {
                    "kept": ["The city was quiet."],
                    "adapted": ["A quiet street becomes the visual opening."],
                },
                "panels": [
                    {
                        "panel": 1,
                        "story_function": "Show the problem.",
                        "visual_brief": "Hero sees the problem in the street.",
                        "dialogue": [{"speaker": "char-001", "text": "We made it.", "purpose": "anchor reader"}],
                        "captions": [],
                        "sfx": [],
                    }
                ],
            },
            {
                "page": 2,
                "source_span": "ch001:p2",
                "story_job": "Turn the problem into a page-turn hook.",
                "required_information": ["chapter_hook"],
                "reader_state": {
                    "known_before": "The hero has a problem.",
                    "new_information": "A choice creates action.",
                    "open_question": "What happens next?",
                },
                "information_density_goal": "deliver hook and motivation; no fixed word count",
                "non_omittable_causality": ["Choice creates the next scene."],
                "source_lines": {
                    "kept": ["Someone knocked twice."],
                    "adapted": ["The knock becomes a final page-turn beat."],
                },
                "panels": [
                    {
                        "panel": 1,
                        "story_function": "Create the hook.",
                        "visual_brief": "A door opens.",
                        "dialogue": [],
                        "captions": [{"text": "Then someone knocked.", "purpose": "page turn"}],
                        "sfx": [{"text": "KNOCK", "purpose": "hook"}],
                    }
                ],
            },
        ],
    }


class ConfigTests(unittest.TestCase):
    def test_default_preferences_are_valid(self):
        from novel_to_comic.config import load_preferences, validate_preferences

        prefs = load_preferences(ROOT / "config" / "user-preferences.json")
        errors = validate_preferences(prefs)
        self.assertEqual(errors, [])
        self.assertEqual(prefs["project"]["mode"], "private_experiment")
        self.assertEqual(prefs["project"]["automation_level"], 3)
        self.assertEqual(prefs["input"]["supported_formats"], ["txt", "epub"])
        self.assertEqual(prefs["comic"]["page_count_policy"], "story_first_variable")
        self.assertEqual(prefs["comic"]["trim_size"], "A4")
        self.assertEqual(prefs["comic"]["page_size_px"], {"width": 2480, "height": 3508})
        self.assertGreaterEqual(prefs["comic"]["minimum_short_edge_px"], 2048)
        self.assertEqual(prefs["image_generation"]["finished_page_text"], "image2_embedded")
        self.assertFalse(prefs["image_generation"]["forbid_text_in_finished_pages"])
        self.assertTrue(prefs["image_generation"]["fallback_page_art_forbids_text"])

    def test_preferences_reject_no_text_finished_page_default(self):
        from novel_to_comic.config import load_preferences, validate_preferences

        prefs = load_preferences(ROOT / "config" / "user-preferences.json")
        prefs["image_generation"]["forbid_text_in_finished_pages"] = True

        errors = validate_preferences(prefs)

        self.assertIn("image_generation.forbid_text_in_finished_pages must be false for finished-page image2 workflow", errors)


class SourceParsingTests(unittest.TestCase):
    def test_parse_txt_extracts_title_and_chapters(self):
        from novel_to_comic.source import parse_txt

        text = """My Test Novel

Chapter 1: Rain
The city was quiet.

Chapter 2: Door
Someone knocked twice.
"""
        parsed = parse_txt(text)

        self.assertEqual(parsed.title, "My Test Novel")
        self.assertEqual(len(parsed.chapters), 2)
        self.assertEqual(parsed.chapters[0].title, "Chapter 1: Rain")
        self.assertIn("Someone knocked", parsed.chapters[1].text)

    def test_write_parsed_source_creates_normalized_outputs(self):
        from novel_to_comic.source import parse_txt, write_parsed_source

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parsed = parse_txt("Title\n\nChapter 1\nAlpha\n\nChapter 2\nBeta")
            write_parsed_source(parsed, root / "source")

            self.assertEqual((root / "source" / "novel.txt").read_text(encoding="utf-8"), parsed.full_text)
            manifest = json.loads((root / "source" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["title"], "Title")
            self.assertEqual(len(manifest["chapters"]), 2)
            self.assertTrue((root / "source" / "chapters" / "ch001.txt").exists())

    def test_parse_epub_uses_metadata_title_and_skips_empty_duplicates(self):
        from novel_to_comic.source import parse_epub

        with tempfile.TemporaryDirectory() as tmp:
            epub = Path(tmp) / "book.epub"
            with zipfile.ZipFile(epub, "w") as archive:
                archive.writestr("mimetype", "application/epub+zip")
                archive.writestr(
                    "META-INF/container.xml",
                    """<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf"/></rootfiles>
</container>""",
                )
                archive.writestr(
                    "OEBPS/content.opf",
                    """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>真实书名</dc:title></metadata>
  <manifest>
    <item id="coverpage" href="cover.xhtml" media-type="application/xhtml+xml"/>
    <item id="ch1" href="ch1.html" media-type="application/xhtml+xml"/>
    <item id="ch2" href="ch2.html" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="coverpage"/>
    <itemref idref="ch1"/>
    <itemref idref="ch2"/>
  </spine>
</package>""",
                )
                archive.writestr(
                    "OEBPS/cover.xhtml",
                    "<html><head><title>cover</title></head><body><p>真实书名</p><p>作者：某人</p><p>www.example-watermark.test</p></body></html>",
                )
                archive.writestr(
                    "OEBPS/ch1.html",
                    "<html><head><title>第一章 开始</title></head><body><p>第一章 开始</p><p>正文一。</p></body></html>",
                )
                archive.writestr(
                    "OEBPS/ch2.html",
                    "<html><head><title>第二章 继续</title></head><body><p>第二章 继续</p><p>正文二。</p></body></html>",
                )

            parsed = parse_epub(epub)

            self.assertEqual(parsed.title, "真实书名")
            self.assertEqual(len(parsed.chapters), 2)
            self.assertEqual(parsed.chapters[0].title, "第一章 开始")
            self.assertEqual(parsed.chapters[0].text, "正文一。")


class StateTests(unittest.TestCase):
    def test_detect_state_reports_next_phase_from_filesystem(self):
        from novel_to_comic.state import detect_state

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = detect_state(root)
            self.assertEqual(state["next_phase"], "phase0_rights_gate")

            (root / "rights").mkdir()
            (root / "rights" / "PROJECT_RIGHTS.md").write_text("private experiment", encoding="utf-8")
            state = detect_state(root)
            self.assertEqual(state["next_phase"], "phase0_ingest")

            (root / "source").mkdir()
            (root / "source" / "novel.txt").write_text("Novel", encoding="utf-8")
            state = detect_state(root)
            self.assertEqual(state["next_phase"], "phase1_story_bible")

            (root / "story-bible").mkdir()
            (root / "story-bible" / "characters.json").write_text("[]", encoding="utf-8")
            state = detect_state(root)
            self.assertEqual(state["next_phase"], "phase1_story_bible")

            (root / "story-bible" / "narrative-map.json").write_text("{}", encoding="utf-8")
            state = detect_state(root)
            self.assertEqual(state["next_phase"], "phase2a_style_preview")

            (root / "visual-bible").mkdir()
            (root / "visual-bible" / "STYLE_APPROVED").touch()
            state = detect_state(root)
            self.assertEqual(state["next_phase"], "phase2b_reference_cards")

            (root / "visual-bible" / "reference-cards").mkdir()
            (root / "visual-bible" / "reference-cards" / "APPROVED").touch()
            state = detect_state(root)
            self.assertEqual(state["next_phase"], "phase3_comic_plan")

            (root / "comic-plan.json").write_text("[]", encoding="utf-8")
            (root / "chapters" / "ch01").mkdir(parents=True)
            state = detect_state(root)
            self.assertEqual(state["next_phase"], "phase4a_manga_story_adaptation")

            (root / "chapters" / "ch01" / "page-story-plan.json").write_text(
                json.dumps({"pages": [{"page": 1}, {"page": 2}]}),
                encoding="utf-8",
            )
            state = detect_state(root)
            self.assertEqual(state["next_phase"], "phase4a_manga_story_adaptation")
            self.assertIn("needs_fix", state["missing"])

            (root / "chapters" / "ch01" / "page-story-plan.json").write_text(
                json.dumps(valid_page_story_plan()),
                encoding="utf-8",
            )
            state = detect_state(root)
            self.assertEqual(state["next_phase"], "phase4a_page_story_plan_review")

            (root / "chapters" / "ch01" / "PAGE_STORY_PLAN_APPROVED").touch()
            state = detect_state(root)
            self.assertEqual(state["next_phase"], "phase4aa_manga_script")

            (root / "chapters" / "ch01" / "page-script.json").write_text(
                json.dumps({"pages": [{"page": 1}, {"page": 2}]}),
                encoding="utf-8",
            )
            state = detect_state(root)
            self.assertEqual(state["next_phase"], "phase4aa_manga_script")
            self.assertIn("needs_fix", state["missing"])

            (root / "chapters" / "ch01" / "page-script.json").write_text(
                json.dumps(valid_page_script()),
                encoding="utf-8",
            )
            state = detect_state(root)
            self.assertEqual(state["next_phase"], "phase4aa_page_script_review")

            (root / "chapters" / "ch01" / "PAGE_SCRIPT_APPROVED").touch()
            state = detect_state(root)
            self.assertEqual(state["next_phase"], "phase4b_storyboard")

            (root / "chapters" / "ch01" / "storyboard.json").write_text(
                json.dumps({"pages": [{"page": 1}, {"page": 2}]}),
                encoding="utf-8",
            )
            (root / "chapters" / "ch01" / "STORYBOARD_APPROVED").touch()
            state = detect_state(root)
            self.assertEqual(state["next_phase"], "phase4b_director_briefs")

            (root / "chapters" / "ch01" / "director-briefs").mkdir()
            (root / "chapters" / "ch01" / "director-briefs" / "page-001-director-brief.md").write_text("brief", encoding="utf-8")
            state = detect_state(root)
            self.assertEqual(state["next_phase"], "phase4b_director_briefs")

            (root / "chapters" / "ch01" / "director-briefs" / "page-002-director-brief.md").write_text("brief", encoding="utf-8")
            state = detect_state(root)
            self.assertEqual(state["next_phase"], "phase4c_generate_finished_pages")

            (root / "chapters" / "ch01" / "finished-pages").mkdir()
            (root / "chapters" / "ch01" / "finished-pages" / "page-001.png").write_text("fake", encoding="utf-8")
            state = detect_state(root)
            self.assertEqual(state["next_phase"], "phase4c_generate_finished_pages")

            (root / "chapters" / "ch01" / "finished-pages" / "page-002.png").write_text("fake", encoding="utf-8")
            state = detect_state(root)
            self.assertEqual(state["next_phase"], "phase4f_qc")

            (root / "chapters" / "ch01" / "director-briefs" / "page-002-director-brief.md").write_text("updated brief", encoding="utf-8")
            state = detect_state(root)
            self.assertEqual(state["next_phase"], "phase4c_generate_finished_pages")

            (root / "chapters" / "ch01" / "finished-pages" / "page-002.png").write_text("new fake", encoding="utf-8")
            state = detect_state(root)
            self.assertEqual(state["next_phase"], "phase4f_qc")

            (root / "chapters" / "ch01" / "qc-report.json").write_text("{}", encoding="utf-8")
            state = detect_state(root)
            self.assertEqual(state["next_phase"], "phase4_review")

            (root / "chapters" / "ch01" / "APPROVED").touch()
            state = detect_state(root)
            self.assertEqual(state["next_phase"], "phase5_bind")

            (root / "output").mkdir()
            (root / "output" / "book.pdf").write_text("fake", encoding="utf-8")
            (root / "output" / "book.cbz").write_text("fake", encoding="utf-8")
            state = detect_state(root)
            self.assertEqual(state["next_phase"], "complete")


if __name__ == "__main__":
    unittest.main()
