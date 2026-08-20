---
name: video-producer
description: Produce the video half of single_scene - per-scene English translation, Kokoro-82M TTS (af_heart), en/zh/bilingual subtitles, scene manifest and the Jianying draft.
---

# Video Producer（翻译 / TTS / 字幕 / Manifest / 剪映）

## 翻译（scene 级，禁止整本一次翻译再切分）

对每个 scene：`scene_NNNN.zh → scene_NNNN.en`，写入 `chapters/chNN/translation/scene_NNNN.json`：

```json
{"scene_id": "scene_0001", "zh_text": "……", "en_text": "……", "status": "PASS", "provider": "agent"}
```

要求：自然、简洁、有故事感的 Native English YouTube narration；适合 TTS；保持剧情、情绪、伏笔、人物说话风格；不像机翻。

术语统一：维护 `translation/terminology.json`（characters / locations / skills / organizations / props / titles）。整本小说同一个名字禁止出现多个英文译法。

## TTS（Kokoro-82M，本地，scene 级）

- 默认 `hexgrad/Kokoro-82M`、American English、voice `af_heart`（可配置，默认不变）。
- 每个 scene 单独生成 `audio/scene_NNNN.wav` + sidecar json（scene_id、en_text、voice、speed、duration、audio_path、sample_rate、word timestamps 若有）。
- 禁止整章一次生成超长 WAV。批量期间模型保持驻留。

## 字幕

时间必须来自 Kokoro 实际 WAV duration（word timestamp 优先；否则实际时长 + 英文语义分句），禁止按字符数估算。中文映射到同一 scene 时间段。输出：

- `subtitles/subtitles.en.srt`（默认轨）
- `subtitles/subtitles.zh.srt`（必须保留）
- `subtitles/subtitles.bilingual.srt`（en 在上）

## Scene Manifest

`chapters/chNN/video/scene-manifest.json` 以 scene_id 为主键汇总：zh_text、en_text、draft_image、final_image、audio、duration、字幕、character_states、setting_id、asset_refs、image_qc / translation_status / tts_status / upscale_status。禁止用文件名排序推断对应关系。

## Pilot Gate（Gate 2）

Pilot（默认 15 个连续 scene）完整跑通：中文解说 → 英文解说 → 图片 → QC → upscale → TTS → 双语字幕 → manifest → 小型剪映草稿。用户审核后：

```bash
python3 -m novel_to_comic approve-pilot
```

没有 `visual-bible/PILOT_APPROVED` 禁止整本无人值守生产。

## 剪映导出

```bash
python3 -m novel_to_comic export-jianying --chapter chNN
```

第一版保持简单：图片铺满（保持比例）、英文字幕轨、Kokoro 音频、scene 顺序排列；图片时长 = 对应 TTS 实际时长。不加随机特效——镜头变化来自 Director + 生图。中文 SRT 完整保留在 `exports/`。输出 `exports/jianying/<project>/draft_content.json` + `draft_meta_info.json` + `export-report.json`。
