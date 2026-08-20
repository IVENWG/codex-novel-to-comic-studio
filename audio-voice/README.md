# 旁白音色（IndexTTS-2.5 参考音频）

IndexTTS-2.5 是零样本音色克隆：全书所有 scene 的英文旁白共用**同一个参考音频**决定音色。
把最终选定的参考音频保存为：

```
audio-voice/narrator-reference.wav    # 5~10 秒，干净人声，无 BGM/噪声，≥16kHz WAV
```

对应配置：`config/user-preferences.json` → `tts.reference_audio`。
该文件是和视觉资产同级的锁定资产：一经 Pilot 审核通过，不要中途更换（否则全书音色不一致）。

## 获取音色的三条路（按推荐顺序）

### 方案 A：用 Kokoro 预设"合成"一个专属音色（最省事，版权干净）

```bash
cd TOOLS
python3 -m novel_to_comic make-voice-samples
```

会在 `audio-voice/candidates/` 生成 6 个候选（af_heart / af_nicole / af_bella / af_sarah / am_michael / am_echo）。
试听后挑一个最有"讲故事"感觉的，用剪映/ffmpeg 截取 5~10 秒最干净的片段，另存为 `narrator-reference.wav`。

漫画解说选声建议：

- 温暖叙述感（女声）：`af_heart`（默认首选）、`af_nicole`（更柔、偏深夜故事）
- 明亮活泼（女声）：`af_bella`，适合轻松爽文
- 沉稳旁白（男声）：`am_michael`（男声首选）、`am_echo`（更低沉，适合悬疑/暗黑题材）

### 方案 B：自己录 5~10 秒

手机安静环境录一段讲故事的语音（你或已授权的朋友），保存为 WAV。音色完全属于你，商用无争议。

### 方案 C：LibriVox 公有领域录音

[LibriVox](https://librivox.org) 的全部录音均为公有领域（官方声明可用于任何用途）。
在 Advanced Search 里选 Fiction / Short Stories，找一位 storytelling 感强的朗读者，
下载后截取 5~10 秒干净片段作为参考音频。注意只截取人声段，避开片头声明和音乐。

## 硬性边界

- **不要克隆真人博主、声优、主播的声音**，尤其 `licensed_commercial` 项目。
- 参考音频确定后，在 Pilot 审核时一并确认音色；Pilot 通过后保持 `narrator-reference.wav` 不变。
- 想换音色 = 重新走一遍 Pilot（音频全部 stale，需重跑 TTS 阶段）。

## 跨语种玩法

IndexTTS-2.5 支持中文参考音 → 英文输出（音色保留）。如果你找到一个很喜欢的中文讲述音色，
也可以直接用它做参考音频生成英文旁白。
