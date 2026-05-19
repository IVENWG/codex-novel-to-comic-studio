# Codex Novel-to-Comic Studio

**Codex 向けの小説コミカライズ Skill。TXT/EPUB 小説を、物語優先の漫画制作パッケージへ変換します。**

これは単なる「本を画像モデルに投げる」ツールではありません。小説を漫画にするには、動機、因果関係、ページターン、セリフ、ナレーション、SFX、キャラクターの一貫性、読者の理解を守る必要があります。この Skill は Codex を編集長として動かし、各工程をファイル化し、検証し、途中から再開できる制作ラインを作ります。

![Original demo finished comic page](docs/assets/demo-page-001.png)

Demo PDF: [demo-original-one-page.pdf](docs/assets/demo-original-one-page.pdf)

この demo は本リポジトリ用のオリジナル素材です。ユーザーの小説、生成済みページ、PDF/CBZ、キャラクター参照画像などは、権利保護のためデフォルトで Git 管理から除外されます。

## Workflow

1. Rights gate
2. TXT/EPUB source parsing
3. Narrative map and story bible
4. Visual bible with style preview and reference cards
5. Comic adaptation plan
6. Page-level manga story plan
7. Page script with dialogue, captions, SFX, and required information
8. Storyboard and whole-page director briefs
9. Codex image2 finished pages
10. QC and targeted regeneration
11. PDF + CBZ binding

## Quick Start

```bash
git clone https://github.com/lhfer/codex-novel-to-comic-studio.git
cd codex-novel-to-comic-studio
python3 TOOLS/check_state.py .
python3 TOOLS/parse_source.py source/my-book.epub --out source
python3 TOOLS/check_state.py .
```

Codex should continue from `next_phase` and preserve existing artifacts.
