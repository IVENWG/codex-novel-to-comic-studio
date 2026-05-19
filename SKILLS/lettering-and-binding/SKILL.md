---
name: lettering-and-binding
description: Use when binding finished comic pages or when fallback lettering is needed after image2 text/layout fails.
---

# Lettering And Binding

Read `storyboard.json`, `director-briefs/`, `finished-pages/`, optional fallback `page-art/`, and `config/user-preferences.json`.

Responsibilities:

- bind finished readable pages under `chapters/chNN/finished-pages/page-001.png`
- add speech bubbles, captions, SFX, and chapter titles outside image generation only in fallback repair mode
- read fallback page art from `chapters/chNN/page-art/page-001.png` only when separate layers are needed
- export project-level PDF and CBZ under `output/`
- preserve A4 portrait output at 2480x3508 px or higher unless the user selects another print size

Default flow asks image2 to render the finished readable page from the director brief. If text is wrong, first try a stricter director brief/regeneration; use deterministic lettering only when regeneration is not enough or the user asks for repair.

Page art is not a complete comic. The final PDF/CBZ must be built from finished pages with character-appropriate dialogue, captions, and SFX.

Lettering QA must check reading order, bubble tail direction, font consistency, text size, text overflow, caption density, SFX placement, and whether text covers faces, hands, action silhouettes, or foreshadowing props.
