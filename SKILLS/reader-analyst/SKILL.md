---
name: reader-analyst
description: Analyze the parsed novel and create the story bible for a novel-to-comic project.
---

# Reader Analyst

Read `source/novel.txt` and `source/manifest.json`. Produce:

- `story-bible/narrative-map.json`
- `story-bible/characters.json`
- `story-bible/settings.json`
- `story-bible/plot-beats.json`
- `story-bible/chapter-summaries.json`
- `story-bible/themes.md`

Keep output faithful to the source. Do not invent characters or change plot events. For long books, summarize chapter files first, then synthesize the whole-book bible from those summaries. Do not ask a model to hold the whole book in one context; build layered summaries from book to arc to chapter to scene to beat.

`narrative-map.json` must include source spans for arcs, chapters, scenes, and beats. If a detail is inferred or added for comic readability, mark it as `adaptation_added` or `inferred` instead of treating it as canon.

Use stable IDs:

- Characters: `char-001`, `char-002`
- Settings: `set-001`, `set-002`
- Plot beats: `beat-001`, `beat-002`

Each character entry should include name, aliases, role, first appearance, relationships, visual clues from source, personality, and scenes where they matter.

Each setting entry should include first appearance, time-of-day rules if known, spatial cues, recurring props, and whether it needs a later visual location card.
