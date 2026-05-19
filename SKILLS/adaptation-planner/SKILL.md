---
name: adaptation-planner
description: Plan how source chapters become comic chapters without changing the story.
---

# Adaptation Planner

Read `story-bible/narrative-map.json`, `story-bible/chapter-summaries.json`, `story-bible/plot-beats.json`, and `config/user-preferences.json`.

Produce both:

- `comic-plan.json`
- `comic-plan.md`

The JSON is for tools. The Markdown is for human review. Each comic chapter should include source chapter coverage, estimated pages as a soft range, key scenes, appearing characters, primary settings, emotional purpose, required source spans, must-not-reveal items, and cliffhanger/page-turn intent.

Compression is allowed. Plot changes are not.

Do not lock exact page count here. The `manga-story-writer` decides the actual page count after page-level story decomposition.
