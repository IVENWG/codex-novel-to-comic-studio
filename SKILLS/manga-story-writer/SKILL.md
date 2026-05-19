---
name: manga-story-writer
description: Use when adapting source novel chapters into reader-first manga page plans before storyboard, director briefs, or image generation.
---

# Manga Story Writer

Read `source/chapters/*.txt`, `story-bible/narrative-map.json`, `story-bible/characters.json`, `story-bible/settings.json`, `comic-plan.json`, and `config/user-preferences.json`.

Produce:

- `chapters/chNN/page-story-plan.json`
- `chapters/chNN/page-story-plan.md`

This role decides how to tell the chapter as manga. It does not draw panels and does not write image2 prompts. It protects story clarity before visual production starts.

Core rules:

- Do not start from a fixed page count. Decide page count after identifying every necessary story beat, emotional turn, joke, reveal, motivation, and transition.
- Preserve the source plot, cast, and motivations. Compression is allowed; missing important information is not.
- Think from the reader's side: after every page, ask whether a new reader understands what happened, why it matters, and why they want the next page.
- Avoid lore dumps. Convert exposition into visual demonstrations, character conflict, jokes, reaction beats, or page-turn reveals.
- Avoid content cliffs. Each page must bridge from the previous page and set up the next page.
- Identify asset gaps before the page director works: missing character cards, setting cards, props, symbols, outfits, injuries, or minor characters that must be controlled.
- Validate the plan with `python3 TOOLS/check_page_story_plan.py chapters/chNN/page-story-plan.json` before asking for approval.

Each page plan must include:

- page number and source span
- story job: what this page must accomplish
- reader question entering the page and answer/hook leaving the page
- required beats, dialogue intent, emotional tone, and information density
- characters, settings, props, and reference needs
- handoff notes for the storyboard/director, but not final panel geometry

Stop before production. The editor-in-chief or user must approve by creating `chapters/chNN/PAGE_STORY_PLAN_APPROVED` only after the page story plan passes validation and reads coherently as a chapter.
