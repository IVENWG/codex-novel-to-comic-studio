import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "TOOLS"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


class DocumentationContractTests(unittest.TestCase):
    def test_readme_explains_codex_first_story_pipeline(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Codex Novel-to-Comic Studio", text)
        self.assertIn("EPUB/TXT", text)
        self.assertIn("story-first", text)
        self.assertIn("image2 finished pages", text)
        self.assertIn("PDF + CBZ", text)
        self.assertIn("demo-original-one-page.pdf", text)

    def test_private_outputs_are_ignored_by_default(self):
        text = (ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertIn("source/*", text)
        self.assertIn("chapters/*", text)
        self.assertIn("output/*", text)
        self.assertIn("visual-bible/*", text)
        self.assertIn("!source/.gitkeep", text)

    def test_skill_documents_require_story_script_and_finished_pages(self):
        skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        agents_text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("page story plan -> manga page script -> storyboard -> director brief -> image2 finished page", skill_text)
        self.assertIn("Manga Story Adaptation Contract", skill_text)
        self.assertIn("Manga Page Script Contract", skill_text)
        self.assertIn("finished page", agents_text)
        self.assertIn("多个美工 agent 并行", agents_text)


class ValidatorContractTests(unittest.TestCase):
    def test_page_story_plan_validator_rejects_fixed_quota(self):
        from check_page_story_plan import check_page_story_plan

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "page-story-plan.json"
            path.write_text(
                json.dumps(
                    {
                        "chapter": "ch01",
                        "page_count_policy": "fixed_8_pages",
                        "actual_page_count": 1,
                        "pages": [{"page": 1, "story_job": "compress everything"}],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = check_page_story_plan(path)

        self.assertEqual(result["status"], "needs_fix")
        issues = "\n".join(issue["issue"] for issue in result["issues"])
        self.assertIn("page_count_policy must be story_first_variable", issues)

    def test_page_script_validator_requires_critical_information_coverage(self):
        from check_page_script import check_page_script

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "page-script.json"
            path.write_text(
                json.dumps(
                    {
                        "chapter": "ch01",
                        "page_count_policy": "story_first_variable",
                        "actual_page_count": 1,
                        "script_strategy": "clarity over word count",
                        "critical_information": [
                            {
                                "id": "motive",
                                "description": "The protagonist must have a motive.",
                                "source_span": "ch001",
                                "required": True,
                            }
                        ],
                        "pages": [
                            {
                                "page": 1,
                                "source_span": "ch001",
                                "story_job": "A pretty but unclear page.",
                                "required_information": [],
                                "reader_state": {
                                    "known_before": "unknown",
                                    "new_information": "unclear",
                                    "open_question": "unclear",
                                },
                                "information_density_goal": "unclear",
                                "non_omittable_causality": [],
                                "source_lines": {"kept": [], "adapted": []},
                                "panels": [
                                    {
                                        "panel": 1,
                                        "story_function": "placeholder",
                                        "visual_brief": "placeholder",
                                        "dialogue": [],
                                        "captions": [],
                                        "sfx": [],
                                    }
                                ],
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = check_page_script(path)

        self.assertEqual(result["status"], "needs_fix")
        issues = "\n".join(issue["issue"] for issue in result["issues"])
        self.assertIn("critical information not covered: motive", issues)


if __name__ == "__main__":
    unittest.main()
