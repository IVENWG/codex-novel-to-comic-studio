---
name: manga-page-director
description: Use when preparing finished comic pages from a chapter script, especially when image2 should generate a complete readable manga page with panels, dialogue, captions, and SFX.
---

# Manga Page Director

Read approved `chapters/chNN/page-script.json`, `chapters/chNN/storyboard.json`, `visual-bible/style.md`, `visual-bible/characters/`, `visual-bible/settings/`, and the relevant `source/chapters/*.txt`.

Produce one file per page:

- `chapters/chNN/director-briefs/page-001-director-brief.md`

Each brief is the exact production instruction for image2 to generate a finished readable page in one pass. Do not write a vague `2x2` or `3x2` grid as the layout. Describe manga panel geometry: splash, inset, tall strip, wide establishing panel, diagonal action panel, reaction close-up, borderless bleed, overlapping SFX, reading path, and page-turn hook.

Every brief must include:

- page purpose and emotional turn
- source spans and beat IDs
- exact reference locks: character ID -> approved reference card path, setting ID -> location card/reference path, prop/card paths when available
- A4 portrait target: 2480x3508 px or higher, minimum short edge 2048
- reading direction
- panel map with numbered panels, relative sizes, shape, shot, camera angle, characters, expressions, poses, action, background, lighting, and continuity notes
- exact Chinese dialogue, captions, and SFX with speaker IDs and placement
- first-appearance intro boxes for new named/recurring characters, placed near the first clear character reveal without covering the face, weapon, or key action
- text safety: bubble tail target, no face/action/prop obstruction, no extra unreadable text
- final copy-ready image2 prompt
- QC checklist for story clarity, manga readability, text correctness, character consistency, and page fill

Do not drop necessary text because image2 might struggle. If a page script needs more dialogue or captions to make the story clear, preserve it and make the image2 prompt stricter about placement, reading order, and exact text.

Character intro boxes are part of finished-page lettering. Use them sparingly and professionally:

- Use once per named character at their formal first appearance in the comic, or when an important hidden identity is first revealed.
- Include name plus a short role hook, for example `Mira Vale / junior sky archivist / hiding a living map`.
- Keep the box outside the face and action path; corner caption plates or slim side labels usually work best.
- Do not intro-box anonymous crowds, one-off background extras, or already-established protagonists unless the chapter is designed as a standalone sample.

`page-art/` is only fallback. The normal output target for these briefs is `chapters/chNN/finished-pages/page-001.png`.
