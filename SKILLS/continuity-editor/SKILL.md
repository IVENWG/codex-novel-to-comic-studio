---
name: continuity-editor
description: Review generated chapter images against visual bible references and produce a QC report.
---

# Continuity Editor

Read a chapter's `director-briefs/`, `finished-pages/`, optional fallback `page-art/`, `storyboard.json`, and `visual-bible/`.

Produce `chapters/chNN/qc-report.json` with:

- overall notes
- page-level and panel-level issues
- source span, character card, setting card, or style rule involved
- suggested action: `accept`, `edit`, or `regenerate`
- edit instruction when a local fix is enough

In v0, do not pretend to have a precise numeric vision model score. Use qualitative severity: `low`, `medium`, `high`, `blocking`.

Review four layers: story faithfulness, continuity, image quality, and comic readability. A chapter cannot be marked approved while `high` or `blocking` issues remain open.

For finished-page image2 output, also check exact rendered Chinese text, balloon order, SFX placement, and whether the generated page obeyed the director brief's panel geometry instead of collapsing into a mechanical grid or poster collage.
