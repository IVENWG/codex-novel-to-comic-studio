---
name: asset-producer
description: Generate and register canonical visual assets (character identity, wardrobe, expressions, settings, props, style) with FLUX.2 Klein 4B, then hand them to Visual Asset Approval. Use before any batch scene rendering.
---

# Asset Producer（视觉资产生成 + Asset Registry）

Input: story bible + `visual-bible/style.md` + `chapters/chNN/narration/scenes.json`（用于确定首批需要的角色/服装/场景/道具）。

## 生成清单（Core-first）

主角与重要配角：

- `visual-bible/characters/{char-id}/identity/face.png`、`full-body.png`、`reference-sheet.png`
  - reference sheet 尽量包含：正脸、侧面、3/4 face、全身、基础表情、默认服装、色彩说明
- `expressions/{neutral,happy,angry,sad,shocked}.png`
- `wardrobe/default/reference.png` + 剧情需要的其他 outfit
- `states/state-NNN.json`（identity_version、outfit_id、injury、weapon）
- `signature/description.md`（不变量：脸型、眼型、发色、疤、轮廓、常驻饰品）

重要场景：

- `visual-bible/settings/{set-id}/location-card.md` + `wide-day.png`、`wide-night.png`、`medium-day.png`、`details/`
- location card 必须记录：建筑结构、门窗楼梯位置、房间连接、家具、道路山水、地标、光源、recurring props、日夜差异、空间关系、forbidden changes

重要道具：

- `visual-bible/props/{prop-id}/reference.png`

风格：

- `visual-bible/style-samples/` 整页/竖版预览图

## Registry 与 Lock

每个资产用 `asset_registry.register_asset(...)` 写入 `visual-bible/asset-registry.json`：

```json
{"id": "char-001", "type": "character_identity", "version": "v1",
 "path": "visual-bible/characters/char-001/identity/reference-sheet.png",
 "status": "DRAFT", "hash": "...", "created_at": "...", "approved_at": null}
```

- 审核通过 → `APPROVED`；批量生产确认后 → `LOCKED`。
- LOCKED canonical asset 禁止普通流程覆盖（`asset_registry.assert_writable`）。
- 资产缺失或 style 未 APPROVED 时，批量生图必须被 hard gate 阻断（`check_production_gates`），不是 warning。

## Gate 1

资产生成完成后暂停，请用户审核人物/画风/服装/场景。用户确认后：

```bash
python3 -m novel_to_comic approve-assets
```

创建 `visual-bible/REFERENCE_ASSETS_APPROVED`（STYLE_APPROVED 在风格预览确认时创建）。
