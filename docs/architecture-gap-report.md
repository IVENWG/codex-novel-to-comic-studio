# Architecture Gap Report — single_scene 视频生产升级

审计对象：`codex-novel-to-comic-studio` @ `7c64ef9`
升级目标：中文小说 → 英文漫画解说视频 → 剪映草稿（`target_format = "single_scene"`）

## 1. 已有能力（保留并复用）

| 能力 | 位置 | 复用方式 |
| --- | --- | --- |
| TXT / EPUB ingestion | `TOOLS/novel_to_comic/source.py`、`TOOLS/parse_source.py` | 直接复用，scene 通过 `source_span` 追溯到 `source/chapters/chNNN.txt` |
| source_span 追溯 | 各 schema（page-story-plan/page-script/storyboard） | single_scene schema 保留 `source_span` 必填 |
| story bible 约定 | `SKILLS/reader-analyst/SKILL.md` | narration-adapter 读取 story bible，不重读整本小说 |
| visual bible 目录 | `visual-bible/characters|settings|style-samples` | 扩展为 asset registry 管理；旧目录布局兼容 |
| character / setting designer | `SKILLS/character-designer`、`SKILLS/setting-designer` | 扩展 identity/wardrobe/expressions/states 目录约定 |
| storyboard / director 概念 | `SKILLS/storyboard-writer`、`SKILLS/art-director`、`TOOLS/make_image_tasks.py` | 概念保留；single_scene 使用独立的 storyboard/director schema（一张图一个 beat，禁止网格） |
| QC | `TOOLS/novel_to_comic/qc.py` | 保留 manga_page QC；新增 `image_qc.py` 面向 single_scene 图片 |
| state/check_state | `TOOLS/novel_to_comic/state.py`、`TOOLS/check_state.py` | 扩展：`target_format=single_scene` 时输出 video pipeline 状态段 |
| approval gate | `STYLE_APPROVED`、`reference-cards/APPROVED`、章级 APPROVED | 保留；新增 `REFERENCE_ASSETS_APPROVED`、`PILOT_APPROVED` |
| filesystem-first 状态管理 | 全项目 | 继续：所有新状态以 JSON/标记文件落盘 |
| resumable workflow | `state.py` 按文件存在性推进 | 扩展到 scene 级：PASS 的 scene 不重跑 |
| validators | `check_page_story_plan.py`、`check_page_script.py`、`check_director_briefs.py` | 保留；新增 scene/continuity/manifest 校验 |
| 测试 | `tests/test_core_tools.py`、`tests/test_public_contracts.py` | 保留；新增 `tests/test_video_pipeline.py` |

## 2. 缺失能力（本次新增）

| 缺口 | 新增模块 / 文件 | 对应 Phase |
| --- | --- | --- |
| single_scene 格式 + scene schema | `TOOLS/novel_to_comic/scenes.py` | P2 |
| Scene Manifest | `TOOLS/novel_to_comic/scene_manifest.py` | P2 |
| Asset Registry + Asset Lock | `TOOLS/novel_to_comic/asset_registry.py` | P3 |
| Character State / Wardrobe / Setting / Prop 状态 | `asset_registry.py` + 目录约定 | P3 |
| Continuity Ledger + Resolver | `TOOLS/novel_to_comic/continuity.py` | P3 |
| 本地 FLUX.2 Klein 4B renderer（+ mock） | `TOOLS/novel_to_comic/renderers/` | P4 |
| Single Scene Storyboard/Director（镜头语言、reference lock） | `TOOLS/novel_to_comic/director.py` | P5 |
| 资产生成流程（skill 契约） | `SKILLS/narration-adapter`、`SKILLS/scene-planner` 等 | P6/P7 |
| Visual Asset Approval Gate（hard gate） | `asset_registry.check_production_gates` | P7 |
| Image QC + Targeted Regeneration | `TOOLS/novel_to_comic/image_qc.py` | P8 |
| RealESRGAN_x4plus_anime_6B 4× upscale（QC PASS 后） | `TOOLS/novel_to_comic/upscalers/` | P9 |
| scene 级中→英翻译 + terminology | `TOOLS/novel_to_comic/translation.py` | P10 |
| Kokoro-82M TTS（默认 af_heart） | `TOOLS/novel_to_comic/tts/` | P11 |
| 英/中/双语字幕（按实际 WAV 时长） | `TOOLS/novel_to_comic/subtitles.py` | P12 |
| Pilot Approval Gate | `video_state.py` + `pipeline.py` | P13 |
| 剪映草稿 Exporter + export-report | `TOOLS/novel_to_comic/exporters/jianying.py` | P14 |
| state/stale/resume/regenerate + CLI | `TOOLS/novel_to_comic/video_state.py`、`pipeline.py`、`cli.py`、`__main__.py` | P15 |

## 3. 需要修改的现有文件

- `TOOLS/novel_to_comic/config.py`：`TARGET_FORMATS` 增加 `single_scene`；新增 `upscale/tts/subtitles/pilot` 等配置段校验（向后兼容，旧格式不受影响）。
- `config/user-preferences.json`：默认切换到 `single_scene`，新增 `upscale/tts/subtitles/pilot/translation` 配置段。
- `TOOLS/check_state.py` + `TOOLS/novel_to_comic/state.py`：`single_scene` 项目额外输出 `video_pipeline` 状态段。
- `TOOLS/novel_to_comic/__init__.py`：导出新模块。
- `SKILL.md`、`AGENTS.md`、`README*.md`：补充 single_scene 生产流程与命令（旧 manga_page 契约文字保留）。
- `requirements.txt`：登记可选依赖（torch/diffusers/kokoro/realesrgan）。
- `.gitignore`：放行 `visual-bible/props/`、`translation/` 目录的 gitkeep。

## 4. 关键工程决策

1. **不依赖 ComfyUI**：renderer 抽象 `render(prompt, references, width, height, seed, output_path, metadata)`，FLUX.2 Klein 4B 走 diffusers 本地推理；mock renderer 供无 GPU 环境测试。
2. **scene_id 唯一主键**：`scene_NNNN` 贯穿 zh/en narration、storyboard、director brief、图片、QC、upscale、TTS、字幕、剪映时间线；禁止文件名排序推断对应关系。
3. **重依赖惰性导入**：torch/diffusers/kokoro/realesrgan 全部在 provider 首次使用时导入，核心状态/校验/字幕/manifest 逻辑仅用标准库 + Pillow，测试可在无 GPU 机器运行。
4. **硬 Gate**：无 `STYLE_APPROVED` + `REFERENCE_ASSETS_APPROVED` 不允许批量生图；无 `PILOT_APPROVED` 不允许整本生产。LOCKED canonical asset 禁止普通流程覆盖。
5. **断点续跑**：manifest 中每个 scene 各步骤状态落盘；重跑时 PASS 步骤跳过，从第一个未完成 scene 继续。
6. **字幕时间**：以 Kokoro 实际 WAV duration 为准（`wave` 标准库读取），word timestamp 可用时优先。
7. **剪映草稿**：生成 Jianying/CapCut 桌面版 draft（`draft_content.json` + `draft_meta_info.json`），时间单位微秒；第一版仅铺满图片 + 英文字幕轨 + 音频轨，中文 SRT 保留在 `exports/`。
