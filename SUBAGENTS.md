# Novel-To-Comic Subagent Pipeline

This project currently uses `SKILLS/*/SKILL.md` as role contracts. The next production mode can map those role contracts to a real subagent pipeline.

## Serial Gates

These stages should stay mostly serial because each one changes the contract for the next stage:

1. Rights and source ingest.
2. Narrative map and story bible.
3. Visual bible style approval and core reference cards.
4. Page story plan.
5. Manga page script.
6. Storyboard.
7. Director briefs.

Each serial gate writes one canonical artifact and waits for validation or approval before downstream work starts.

## Parallel Art Agents

Finished-page image generation can use multiple parallel art agents after all director briefs pass validation.

Use disjoint page ranges and disjoint write scope:

- Artist agent A: `chapters/chNN/director-briefs/page-001-director-brief.md` -> `chapters/chNN/finished-pages/page-001.png`
- Artist agent B: `chapters/chNN/director-briefs/page-002-director-brief.md` -> `chapters/chNN/finished-pages/page-002.png`
- Artist agent C: `chapters/chNN/director-briefs/page-003-director-brief.md` -> `chapters/chNN/finished-pages/page-003.png`

For larger batches, assign ranges such as pages 001-006, 007-012, and 013-018. No two art agents may write the same image, source text, QC note, or regenerated page.

## Agent Responsibilities

- `reader-analyst`: source understanding, narrative map, source trace.
- `manga-story-writer`: page story plan and variable page count.
- `manga-script-writer`: critical information, causality, dialogue, captions, SFX.
- `storyboard-writer`: panel grammar and readable page flow.
- `manga-page-director`: exact whole-page image2 brief with references and text placement.
- `parallel art agents`: generate assigned finished pages only.
- `continuity-editor`: inspect outputs across pages and request targeted regenerations.
- `lettering-and-binding`: fallback text repair, PDF, and CBZ.

## Merge Rules

Parallel art agents are not allowed to edit shared contracts such as `page-script.json`, `storyboard.json`, visual bible files, or other agents' pages. If an agent finds a script, character, or continuity problem, it writes a note under `chapters/chNN/logs/` and stops that page for editor review.
