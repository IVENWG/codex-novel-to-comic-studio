---
name: novel-to-comic
description: Convert long-form fiction from TXT or EPUB into a recoverable comic production project. Use when the user wants to adapt a novel into manga/comic pages, create story bibles, visual bibles, storyboard JSON, image-generation task sheets, PDF/CBZ outputs, or continue an existing novel-to-comic project from filesystem state.
---

# Novel To Comic

Use this skill to run a conservative v0 pipeline for adapting a novel into a comic. Treat `novel-to-comic-skill-design.md` as product background, not as an exact command list.

## Operating Model

Work as the editor-in-chief. Keep all state on disk. Before acting, inspect the project with:

```bash
python3 TOOLS/check_state.py .
```

Respect `config/user-preferences.json` and `rights/PROJECT_RIGHTS.md`. v0 supports `txt` and `epub` input only. Default comic pages are A4 portrait at 2480x3508 px or higher, with a minimum short edge of 2048 px. Page count is story-first by default: do not force a source chapter into a fixed page budget if the story becomes choppy. The default production path is **page story plan -> manga page script -> storyboard -> director brief -> image2 finished page**: image2 should receive a rigorous whole-page manga director brief and generate one complete readable page with panel layout, balloons, captions, SFX, and page art together. `page-art/` plus deterministic lettering is only a fallback when text rendering fails or the user asks for separate layers.

## Rights And Source Traceability

Start every new project with a rights gate. Record the user's selected project mode in `config/user-preferences.json` and summarize the boundary in `rights/PROJECT_RIGHTS.md`.

- `private_experiment`: local workflow testing only.
- `licensed_commercial`: user has provided a rights basis for publication.
- `public_domain`: the source is public-domain or otherwise cleared.

Do not bypass DRM or platform restrictions. Every adapted beat, panel, prop, relationship, injury, costume change, or story reveal must carry a `source_span`. If something is added for comic readability, mark it as `adaptation_added` instead of silently treating it as canon.

## Visual Asset Cadence

Use a **Core-first, arc-expanded, chapter-checked** strategy.

- **Core-first**: before production pages, lock the global style preview, the core cast reference cards, recurring world symbols, and the most important baseline settings.
- **Arc-expanded**: before each story arc, add reference cards for new important characters, costumes, locations, props, injuries, weapons, or status changes.
- **Chapter-checked**: before generating a chapter, verify that every speaking or visually important character, outfit, setting, and story-critical prop in that chapter has an approved reference.
- **Bible feedback**: after a chapter, promote especially strong poses, outfits, props, or settings back into `visual-bible/` so later chapters become more consistent instead of drifting.

## Workflow

0. **Rights gate**: create `rights/PROJECT_RIGHTS.md` and confirm the project mode in `config/user-preferences.json`.
1. **Ingest source**: parse a `.txt` or `.epub` into `source/novel.txt`, `source/manifest.json`, and `source/chapters/chNNN.txt`.
2. **Build narrative map and bibles**: create `story-bible/narrative-map.json`, `characters.json`, `settings.json`, `plot-beats.json`, `chapter-summaries.json`, and `themes.md`. Treat `settings.json` as the v0 World Bible seed until richer location cards exist.
3. **Build visual bible**: create `visual-bible/style.md`, page-level preview prompts/images under `visual-bible/style-samples/`, character reference cards, and setting reference cards. Use the visual asset cadence above. After style approval, create `visual-bible/STYLE_APPROVED`. After reference-card approval, create `visual-bible/reference-cards/APPROVED`.
4. **Plan adaptation**: create both `comic-plan.json` for tools and `comic-plan.md` for human review.
5. **Manga story adaptation**: create `chapters/chNN/page-story-plan.json` and `.md`. This decides how to tell the chapter as manga, page by page, with no fixed page count unless the user explicitly requires one.
6. **Manga page script**: create `chapters/chNN/page-script.json` and `.md`. This defines critical information, reader known/new/open questions, non-omittable causality, and panel-level dialogue/captions/SFX. Story clarity matters more than word count.
7. **Chapter script/storyboard**: create `chapters/chNN/storyboard.json` from the approved page script. This defines panel grammar and visual continuity while preserving the script's information payload.
8. **Whole-page director briefs**: create `chapters/chNN/director-briefs/page-001-director-brief.md` etc. Each brief is the contract for image2 to draw one finished manga page.
9. **Generate finished pages**: use image2 once per page from the director brief. Save readable complete pages directly to `chapters/chNN/finished-pages/page-001.png`.
10. **Fallback separate layers only if needed**: if image2 text is wrong, create `page-art/` and repair with deterministic lettering or regenerate the page with a stricter director brief.
11. **QA and regeneration loop**: create `chapters/chNN/qc-report.json`. High-severity story, continuity, image, layout, or text issues must be fixed before approval.
12. **Bind**: export PDF + CBZ from finished pages.

## Manga Story Adaptation Contract

Before any page director briefs, a manga story writer must turn the source chapter into a reader-first page plan:

- **Coverage first**: list all important events, motivations, relationship beats, setup/payoff, jokes, reveals, and emotional turns from the source.
- **Reader experience**: for each page, state what the reader learns, feels, and wants to know next.
- **Variable page count**: choose as many pages as needed to tell the chapter clearly and attractively. `target_pages` is a soft planning reference, not a quota.
- **Page-level story units**: each page needs a concrete story job, not just “introduce X” or “lore montage.”
- **Continuity bridges**: every page must connect from the previous page and set up the next page.
- **Information density**: avoid lore dumps and avoid missing source information; split dense exposition into action, comedy, reaction, and visual demonstration.
- **Asset implications**: identify every character, setting, prop, outfit, or symbolic element that needs a reference before director briefs.
- **Approval gate**: do not produce or regenerate finished pages until `PAGE_STORY_PLAN_APPROVED` exists for the chapter.
- **Validation gate**: run `python3 TOOLS/check_page_story_plan.py chapters/chNN/page-story-plan.json`; fix every issue before asking for approval.

## Manga Page Script Contract

After the page story plan is approved and before storyboard/director briefs, a manga script writer must produce `chapters/chNN/page-script.json` and `.md`:

- **Critical information**: list every source fact, motive, relationship, setup/payoff, and causal link that the reader must receive.
- **Reader state**: for every page, state what the reader already knows, what they learn now, and what question pulls them forward.
- **Panel text**: write panel-level dialogue, captions, and SFX with a purpose, not placeholder notes.
- **Source trace**: mark source lines or ideas as `kept`, `adapted`, or `adaptation_added`.
- **Causality**: name what cannot be omitted without making the plot jumpy.
- **Clarity over word count**: do not use fixed text quotas such as 70-120 words. Add or remove text based on whether the reader understands the story.
- **Image2 trust**: do not remove necessary text because image2 might struggle. Make the prompt clearer; use fallback lettering only when the generated page actually fails.
- **Approval gate**: do not produce storyboard or director briefs until `PAGE_SCRIPT_APPROVED` exists for the chapter.
- **Validation gate**: run `python3 TOOLS/check_page_script.py chapters/chNN/page-script.json`; fix uncovered critical information before storyboard.

## Whole-Page Director Brief Contract

Every `page-NNN-director-brief.md` must be precise enough for a manga artist/image2 to draw the page without guessing:

- **Page purpose**: what the reader must understand or feel after this page.
- **Source trace**: source chapter, scene, and beat IDs; mark any `adaptation_added`.
- **Reference lock**: exact character cards, outfit/stage versions, setting cards, prop cards, and style bible paths. Use paths such as `visual-bible/characters/char-001/reference-card.png`.
- **Page layout**: A4 portrait, reading direction, non-mechanical manga panel arrangement, relative panel sizes, border style, gutters, overlaps, bleed/splash areas, and reading path.
- **Panel directives**: for each panel, specify shape, size, shot, angle, camera distance, characters, expressions, poses, action, background, lighting, and continuity constraints.
- **Text directives**: exact Chinese dialogue/captions/SFX, speaker IDs, balloon/caption/SFX placement, reading order, font mood, tail target, and “do not cover” areas.
- **Image2 prompt block**: a final copy-ready prompt that includes the reference locks, page layout, all panel directives, exact text, and negative constraints.
- **QC checklist**: story clarity, panel readability, character consistency, correct text, no wrong extra text, and no face/action obstruction.

## Hard Rules

- Do not alter the source story's plot, cast, or ending.
- Do not fix page count before the chapter is understood. Tell the chapter well first; page count follows story clarity.
- Do not skip manga story adaptation. A visually strong page can still fail if the chapter logic, motivation, or reader flow is broken.
- Do not skip the manga page script. A page can have beautiful panels and still fail if critical information, motivation, dialogue, or causality is under-written.
- Do not set fixed word-count quotas for pages. Use as much or as little text as needed for story clarity.
- The default image2 target is `finished page`: a readable comic page with art, manga panels, dialogue, captions, and SFX in one generated image.
- Distinguish fallback `page art` from `finished page`. `page art` is only the image layer; `finished page` is the readable comic page.
- Do not generate from a vague grid like `2x2` or `3x2` alone. The director brief must describe real manga panel geometry and reading path.
- Do not ask image2 to guess character identity. Every speaking or visually important character must name the exact approved reference card path and stage/outfit.
- Do not mark a chapter approved while `qc-report.json` has open `high` or `blocking` issues.
- Do not let image generation invent canon facts; use `source_span` or `adaptation_added`.
- Do not approve a visual bible from text alone; show at least one page-level style preview.
- Do not generate production comic pages before core character reference cards exist and are approved.
- Keep the two required approvals: visual bible and first chapter.
- Prefer small resumable files over hidden state.
- If a phase output already exists, read it and continue instead of regenerating it.

## Role Guides

Use the role instructions in `SKILLS/*/SKILL.md` as contracts for each production step. The default mode is still editor-in-chief orchestration through multiple skills, but the contracts are designed to become a real subagent pipeline.

When real subagents are available, keep story and script gates serial, then use parallel art agents only after director briefs pass validation. Parallel art agents must own disjoint page ranges and disjoint write scope, for example one agent writes only `chapters/chNN/finished-pages/page-001.png` and its `.source.txt`, while another writes only page 002. See `SUBAGENTS.md`.

## Useful Commands

```bash
python3 TOOLS/parse_source.py path/to/book.txt --out source
python3 TOOLS/parse_source.py path/to/book.epub --out source
python3 TOOLS/check_page_story_plan.py chapters/ch01/page-story-plan.json
python3 TOOLS/check_page_script.py chapters/ch01/page-script.json
python3 TOOLS/check_director_briefs.py chapters/ch01/director-briefs
python3 TOOLS/bind.py chapters/ch01/finished-pages --book-slug my-comic
python3 TOOLS/check_state.py .
python3 -m unittest discover -s tests -v
```
