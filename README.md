# Codex Novel-to-Comic Studio

**A Codex-first production skill for turning EPUB/TXT novels into story-first manga and comic packages.**

Codex Novel-to-Comic Studio is not a blind “make pictures from a book” prompt. It is a recoverable editorial pipeline for adapting long-form fiction into readable comic chapters: rights gate, source parsing, narrative bible, visual bible, manga story plan, page script, storyboard, whole-page director briefs, image2 finished pages, QC, then PDF + CBZ export.

[简体中文](README.zh-CN.md) | [日本語](README.ja.md)

![Original demo finished comic page](docs/assets/demo-page-001.png)

Example PDF: [demo-original-one-page.pdf](docs/assets/demo-original-one-page.pdf)

> The demo page is an original sample created for this repository. Real user novels, parsed chapters, reference cards, finished pages, PDFs, and CBZ files are ignored by default because they may be rights-sensitive derivative works.

## Why This Exists

AI image models can now draw richly detailed comic pages, but good comics are not just attractive images. A novel adaptation has to preserve motive, causality, character continuity, page turns, dialogue, captions, SFX, and reader comprehension. This skill gives Codex a production desk: each stage writes files, validates the next gate, and can be resumed without losing the plot.

## What It Produces

- Parsed TXT/EPUB source under `source/`
- Story bible and narrative map
- Visual bible with style previews, character cards, setting cards, and approval markers
- Story-first `comic-plan.json` / `comic-plan.md`
- Chapter-level `page-story-plan.json` for manga adaptation
- `page-script.json` with critical information, reader state, dialogue, captions, and SFX
- Storyboard JSON and precise whole-page director briefs
- Codex image2 finished pages in `chapters/chNN/finished-pages/`
- QC reports
- Final PDF and CBZ exports

## Core Workflow

1. **Rights gate**: choose `private_experiment`, `licensed_commercial`, or `public_domain` in `config/user-preferences.json`, then document the boundary in `rights/PROJECT_RIGHTS.md`.
2. **Source ingest**: parse a `.txt` or `.epub` into normalized chapters.
3. **Reader analysis**: build narrative map, story bible, character bible, and world bible seeds.
4. **Visual bible**: approve a page-level style preview first, then approve core character and setting reference cards.
5. **Adaptation plan**: decide the conversion strategy and chapter order.
6. **Manga story writer**: decide what every page must do for the reader. Page count is story-first and variable.
7. **Manga script writer**: write required information, reader known/new/open questions, dialogue, captions, SFX, and non-omittable causality.
8. **Storyboard writer**: turn script into panel grammar and visual continuity.
9. **Manga page director**: write `page-001-director-brief.md` style briefs with exact references, panel shapes, text placement, safe zones, and image2 prompts.
10. **Image2 finished pages**: generate one complete readable comic page per brief. The default output is a finished page with art, panels, dialogue, captions, and SFX together.
11. **QC loop**: fix story, continuity, text, layout, and image issues page by page.
12. **Bind**: export PDF + CBZ.

## Single Scene Video Pipeline（中文小说 → 英文漫画解说视频 → 剪映草稿）

`target_format = "single_scene"` is the video production mode: one visual story beat = one standalone comic image, narrated in English and assembled as an editable Jianying (剪映) draft.

- Chinese narration script per scene, planned by story/visual beats (never fixed sentence quotas)
- Asset registry + asset lock: canonical identity / wardrobe / setting / prop assets generated with local **FLUX.2 Klein 4B** and locked after approval
- Continuity ledger resolved before rendering (outfits, injuries, weapons persist until explicitly cleared)
- Single-scene director briefs with labeled references (image 1 = identity, image 2 = outfit, image 3 = environment, image 4 = style) and camera variation
- Draft renders at 1024×1536, QC (PASS / RETRY / MANUAL_REVIEW) with bounded targeted regeneration, then 4× **RealESRGAN_x4plus_anime_6B** upscale for PASS images only
- Scene-level zh→en translation with terminology control; English narration via local **IndexTTS-2.5** (zero-shot clone of one locked narrator reference clip, per-scene emotion injection; see `audio-voice/README.md`), with **Kokoro-82M** (`af_heart`) as the fallback provider; one WAV per scene
- English (default) + Chinese + bilingual SRT subtitles timed to real audio durations; scene manifest keyed by `scene_id`
- Two hard approval gates (visual assets, pilot) then unattended batch production; fully resumable, per-scene regeneration

```bash
cd TOOLS
python3 -m novel_to_comic ingest ../source/my-book.txt
python3 -m novel_to_comic make-voice-samples    # pick the narrator voice for IndexTTS
python3 -m novel_to_comic approve-assets        # Gate 1 (after human review)
python3 -m novel_to_comic pilot --chapter ch001
python3 -m novel_to_comic approve-pilot         # Gate 2 (after human review)
python3 -m novel_to_comic run --chapter ch001
python3 -m novel_to_comic export-jianying --chapter ch001
```

Optional GPU dependencies (install on the rendering machine): `torch`, `diffusers` (FLUX.2 Klein 4B), `index-tts` (IndexTTS-2.5 narrator cloning), `kokoro` + `soundfile` (fallback TTS / voice candidates), `realesrgan` (upscale). Mock providers keep the whole pipeline testable without a GPU.

## Install For Codex

Clone the repository:

```bash
git clone https://github.com/lhfer/codex-novel-to-comic-studio.git
cd codex-novel-to-comic-studio
```

Option A: work directly inside the cloned project folder with Codex.

Option B: install it as a Codex skill folder:

```bash
mkdir -p ~/.codex/skills
cp -R . ~/.codex/skills/codex-novel-to-comic-studio
```

Then open the folder in Codex and say something like:

```text
Use the novel-to-comic skill. Parse source/my-book.epub and run the Level 3 single-chapter pilot.
```

## Quick Start

Put a rights-cleared `.txt` or `.epub` in `source/`, then run:

```bash
python3 TOOLS/check_state.py .
python3 TOOLS/parse_source.py source/my-book.epub --out source
python3 TOOLS/check_state.py .
```

After each phase, Codex should inspect `next_phase` and continue without overwriting existing artifacts.

Useful validation and export commands:

```bash
python3 TOOLS/check_page_story_plan.py chapters/ch01/page-story-plan.json
python3 TOOLS/check_page_script.py chapters/ch01/page-script.json
python3 TOOLS/check_director_briefs.py chapters/ch01/director-briefs
python3 TOOLS/bind.py chapters/ch01/finished-pages --book-slug my-comic
python3 -m unittest discover -s tests -v
```

## Production Philosophy

- **Story first, page count second.** A chapter should use as many pages as it needs to read clearly and feel exciting.
- **Finished pages by default.** The image2 target is a whole readable comic page, not isolated panels and not an unlettered art layer.
- **Half-manual confirmation.** Style previews and reference cards are approved before production pages.
- **Traceability.** Every adapted beat should point to a source span or be marked `adaptation_added`.
- **Reference discipline.** Important characters, outfits, settings, props, and stage changes must be locked before image generation.
- **Parallel when safe.** Story/script/director gates stay serial; after director briefs pass validation, art agents can generate disjoint page ranges in parallel.

## Repository Layout

```text
SKILL.md                         Main Codex skill contract
AGENTS.md                        Editor-in-chief operating rules
SUBAGENTS.md                     Future parallel subagent pipeline
SKILLS/*/SKILL.md                Role contracts for each production desk
TOOLS/                           Parsers, validators, image task builders, QC, binding
config/user-preferences.json     User-selectable production preferences
rights/PROJECT_RIGHTS.md         Rights gate template
source/                          Local user inputs, ignored by git
chapters/                        Local chapter artifacts, ignored by git
visual-bible/                    Local reference assets, ignored by git
output/                          Local PDF/CBZ outputs, ignored by git
docs/assets/                     Original public demo assets
```

## Supported Inputs

- TXT
- EPUB

The skill does not provide DRM bypass instructions and should only be used with books you have the right to process.

## Roadmap

- Real subagent orchestration for story, script, storyboard, director, QC, and parallel art generation
- Better public-domain demo projects
- More export formats, including web reader builds
- Richer visual bible feedback from accepted pages back into future chapter packs

## License

MIT. See [LICENSE](LICENSE).
