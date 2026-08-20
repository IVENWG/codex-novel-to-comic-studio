---
name: single-scene-director
description: Write one cinematic director brief per single_scene (shot, angle, composition, reference locks, final prompt) and control camera variation across consecutive scenes.
---

# Single Scene Director

Input（`director.build_director_brief` 已自动聚合）：

- 当前 scene（narration + storyboard）
- previous / next scene
- character state（continuity ledger）
- asset registry、setting、props
- style bible

Output: `chapters/chNN/director-briefs/{scene_id}-director-brief.json` + `.md`。

## Brief 必含内容

scene purpose、emotional beat、shot size、camera angle、camera distance、composition、foreground / middle ground / background、character placement、body language、facial expression、clothing lock、prop lock、setting lock、lighting、atmosphere、depth、style、negative constraints、exact references、final generation prompt。

## 镜头语言（禁止单调）

不允许连续几十张都是"人物居中 + 中景 + 正面"。主动轮换：

establishing / extreme wide / wide / medium / medium close-up / close-up / extreme close-up / low angle / high angle / top-down / over-the-shoulder / POV / silhouette / insert / action shot / foreground framing。

同时控制镜头重复率（≤2 连）、场景节奏、人物视线方向、左右位置、动作方向、情绪变化。`director.plan_camera_sequence` 提供确定性轮换基线。

## Reference Lock

参考图必须显式标注用途，不让模型猜：

```
image 1 = identity (char-001)
image 2 = outfit (char-001@travel-black-v1)
image 3 = environment (set-004)
image 4 = visual style
```

多人 scene 由 Renderer Router（`renderers/`）按模型能力决定 multi-reference / 组合调整 / 分角色处理。

## Targeted Regeneration

QC 失败时不要从零重写 prompt：由 `image_qc.plan_targeted_regeneration` 生成 correction reason + 定向强调（衣服错 → 重锁 outfit；脸漂移 → 提高 identity 权重；场景错 → 重锁 setting），`max_retry` 默认 2～3 次，超过转 MANUAL_REVIEW。
