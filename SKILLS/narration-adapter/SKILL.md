---
name: narration-adapter
description: Adapt a Chinese novel chapter into a Chinese video narration script managed per scene (single_scene). Use after the story bible exists and before scene planning.
---

# Narration Adapter（中文小说 → 中文漫画解说稿）

Input: `source/chapters/chNNN.txt` + `story-bible/*`（narrative-map、characters、settings、plot-beats、chapter-summaries）。不要重新通读整本小说；以 story bible 为准，只在需要细节时回查 `source_span` 对应原文。

Output: `chapters/chNN/narration/scenes.json`，`target_format: "single_scene"`。

## 改编要求

- 保留核心剧情、因果关系、人物动机、伏笔、重要人物关系。
- 删除重复环境描写与不适合视频节奏的冗长叙述；增强推进与悬念。
- 不是摘要：听起来像一个人在讲故事，适合 TTS 与 YouTube 漫画解说。
- 每个 scene 的 `zh_narration` 是可直接朗读的解说词，2～4 句只是软参考，绝不按固定句数切。
- 每个 scene 必须带 `source_span`（可追溯到原文章节/段落）。

## Scene 字段契约

```json
{
  "scene_id": "scene_0001",
  "source_span": "ch001:p3-p4",
  "zh_narration": "……",
  "story_beat": "……",
  "visual_beat": "这一张图要画什么",
  "characters": ["char-001"],
  "character_states": ["char-001@state-001"],
  "setting_id": "set-001",
  "props": ["prop-sword-001"],
  "emotion": "紧张",
  "camera_intent": "close-up",
  "transition": "cut"
}
```

## 硬规则

- scene_id 从 `scene_0001` 连续编号，全章唯一主键。
- 完成后运行校验：`python3 TOOLS/check_scenes.py chapters/chNN/narration/scenes.json`（或在 CLI 中 `validate-narration`）。
- 用户修改 `zh_narration` 后，翻译/TTS/字幕自动进入 stale（见 `video_state.detect_stale`）；视觉 beat 未变时不必重生图片。
