---
name: setting-designer
description: Create recurring setting reference folders for a novel-to-comic project.
---

# Setting Designer

Input is one setting from `story-bible/settings.json` plus `visual-bible/style.md`.

Create `visual-bible/settings/{id}/` with:

- `location-card.md`
- `wide-day.png` slot
- `wide-night.png` slot
- `medium-day.png` slot
- `medium-night.png` slot
- detail image slots for recurring props or layout cues

`location-card.md` should include fixed spatial rules: entrances, windows, stairs, furniture, major props, lighting, time-of-day rules, forbidden changes, and the chapters where the setting applies.

For each missing reference image, create a neighboring `prompt.md` or section in `location-card.md` with image2 instructions and a target path. Every important location needs an establishing-shot reference before repeated use.
