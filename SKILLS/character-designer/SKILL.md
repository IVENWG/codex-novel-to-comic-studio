---
name: character-designer
description: Create character reference folders and wardrobe matrices for a novel-to-comic project.
---

# Character Designer

Input is one character from `story-bible/characters.json` plus `visual-bible/style.md`.

Create:

- `visual-bible/characters/{id}/bio.md`
- `reference-card.png` with face, full body, 2-3 expressions, default outfit, and color notes in one image
- stage/version notes with chapter range, outfit, injuries, weapons, relationship status, and forbidden future-state leaks
- optional granular slots such as `face-canonical.png`, `expressions/`, and `wardrobe/default/` when higher consistency is needed
- `signature/description.md` when the character has must-keep marks or props

For half-manual image generation, write the exact image2 task text beside each missing image slot as `prompt.md`. The approved `reference-card.png` is the default page-generation reference in v0 and should not be regenerated casually.

Separate visual invariants from variables. Invariants include face shape, hair, eye color, body type, scars, signature props, and silhouette. Variables include emotion, lighting, pose, temporary damage, and chapter-specific wardrobe.
