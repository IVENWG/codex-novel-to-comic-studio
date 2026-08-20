---
name: scene-planner
description: Decide where single_scene scene boundaries go based on story/visual beats, and produce the continuity ledger before any rendering.
---

# Scene Planner（single_scene 分镜规划）

Input: `chapters/chNN/narration/scenes.json` + story bible + character/setting bibles。

Output:

- `chapters/chNN/single-scene-storyboard.json`
- `chapters/chNN/continuity-ledger.json`

## 分镜决策

禁止机械切割（"3 句话一张图"）。依据以下信号决定新 scene：

- story beat / visual beat 变化
- 场景、时间、动作变化；新人物出现；情绪转折
- 战斗、悬念、重要道具、信息密度、视觉表现价值、前后镜头节奏

软参考：普通叙事 2～4 句 ≈ 1 scene；战斗/重要表情/反转可以 1 句 1 图；环境交代可以整段 1 图。

## Storyboard 字段

每个 scene：`scene_id`、`story_purpose`、`visual_purpose`、`shot_size`、`angle`、`characters`（必须 pin `outfit_id`）、`setting_id`、`props`、`action`、`expression`、`composition`、`transition_from_previous`。

禁止：`panels`、`grid`、一图多格。

## Continuity Ledger

每个 scene 一条记录：`scene_id`、`characters[{character_id, state_id, outfit_id, injury, weapon, expression}]`、`setting_id`、`time`、`weather`、`props`、`relationship_state`、`important_story_state`。

状态规则（`continuity.check_state_persistence` 会校验）：

- 受伤/持武器后，后续 scene 必须保持，直到显式 `cleared: ["injury"]`。
- 换装必须在当条记录标 `outfit_change: true`。
- Director 从 ledger 读取当前状态，不允许模型自己"理解"剧情。

## 校验

```bash
python3 TOOLS/check_scenes.py chapters/chNN/single-scene-storyboard.json
```

镜头重复率由 `director.check_shot_repetition` 检查：连续同景别同角度不能超过 2 次。
