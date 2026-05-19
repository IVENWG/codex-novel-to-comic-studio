---
name: storyboard-writer
description: Convert a comic chapter plan into page and panel storyboard JSON.
---

# Storyboard Writer

Read one approved `chapters/chNN/page-script.json`, the related `chapters/chNN/page-story-plan.json`, relevant `source/chapters/*.txt`, and `visual-bible/style.md`.

Produce `chapters/chNN/storyboard.json`. This is a page-by-page storyboard derived from the approved manga page script, not a replacement for it and not the final image2 prompt. The manga page director converts it into precise whole-page director briefs before image generation.

Each planned panel/beat must include:

- page and panel numbers
- layout intent, but not as a final mechanical grid
- shot, angle, and transition from previous panel
- visual description with no lettering baked into the image
- source_span, or `adaptation_added` with a short reason
- character IDs, outfit IDs, expressions, and approximate positions
- setting ID and setting time
- dialogue, captions, SFX, speaker IDs, bubble type, and lettering anchor
- page-turn beat flag when relevant
- required critical information IDs carried from `page-script.json`

Write dialogue as final-reader text, not placeholder notes. A user should be able to read the storyboard's dialogue/captions straight through and understand an engaging comic scene.

Prefer readable comic pacing over literal paragraph-by-paragraph conversion, but do not drop page-script critical information, source motivations, or non-omittable causality. Do not shorten dialogue merely to satisfy a fixed word count.

Check comic grammar before handing off: avoid too many consecutive same-shot panels, add establishing shots for new locations, use close-ups for emotional turns, use insert shots for foreshadowing props, and keep dialogue short enough for bubbles.

Hand off to `manga-page-director`; do not generate finished pages directly from this JSON unless director briefs already exist.
