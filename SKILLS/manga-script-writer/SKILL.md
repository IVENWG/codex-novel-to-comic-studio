---
name: manga-script-writer
description: Use when a manga adaptation feels jumpy, thin, under-explained, or needs page-level dialogue, captions, SFX, and source-information coverage before storyboard or image generation.
---

# Manga Script Writer

Read the approved `chapters/chNN/page-story-plan.json`, relevant `source/chapters/*.txt`, `story-bible/`, and `visual-bible/`.

Produce:

- `chapters/chNN/page-script.json`
- `chapters/chNN/page-script.md`

This role turns the page story plan into a readable manga script. It decides what information reaches the reader, how each page carries plot and emotion, and which dialogue/captions/SFX should appear before the storyboarder designs panel grammar.

Core rules:

- Prioritize clarity over word count. Do not use a fixed word-count quota.
- Trust image2 to render finished-page text when the prompt is clear. Do not remove necessary dialogue just because text generation may be hard.
- Every page must state its critical information, reader known/new/open question, dialogue intent, and non-omittable causality.
- Preserve source motivations and causal links. Compression is allowed; unclear motivation is not.
- Convert exposition into readable manga: narration plates, character banter, map labels, visual demonstrations, reaction beats, and page-turn hooks.
- For named characters or recurring important side characters, include a first-appearance intro box when they formally enter the story. Use it once at the first clear reveal, not on every appearance. If the first panel is a silhouette or suspense tease, place the intro box on the first readable face/body panel.
- Do not make every page dense. Quiet/emotional pages can be sparse if the necessary information lands.
- Mark exact source lines or ideas as `kept` or `adapted`; mark purely connective comic additions as `adaptation_added`.
- Validate with `python3 TOOLS/check_page_script.py chapters/chNN/page-script.json` before asking for approval.

Each page script must include:

- required critical information IDs
- reader state: known before, new information, open question
- information density goal in plain language, not a number target
- non-omittable causality
- source lines kept/adapted
- panel-level story function, visual brief, dialogue, captions, and SFX with purpose
- first-appearance intro boxes for new named characters, including name plus a compact role hook

Stop before storyboard. The editor-in-chief or user must approve by creating `chapters/chNN/PAGE_SCRIPT_APPROVED`.
