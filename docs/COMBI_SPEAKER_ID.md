# 协作语音声纹识别（谁在第几段说话）

`card_combi_voices` 能拆出每段音频，但 ACB 里没有“这段是谁”的字段。本方法用声纹给每段估出说话角色，主要用于三轮生日卡（Present for ○○）的部门协作语音。脚本是 `scripts/combi_speaker_id.py`。

## 为什么顺序是固定的

- 协作语音 `card_vo_skill_combi` 在 ACB 里是**一条 Cue 内的固定序列**：note-on（0x07D0）播放一段，delay（0x07D1）等待，再 note-on 下一段。段与段之间的 0x07D5 只是 2 字节分隔标记，不含说话人信息。
- `mst_character_card_sp_skill_with_combi` 的 `CutInEnd ≈ CombiVoiceStart + 整条 Cue 时长`，所以无论编成里带了谁，整个部门序列都会完整播完。
- 结论：**播放顺序由每张卡自己的 ACB 写死**，不随编成变化。群里“先协作对象再按编号”和“只按编号”两种说法都解释不了所有卡，实际上是逐卡不同。

## 原理

1. **参考声音**：每个角色在自己所有非 CR 卡（`CardRarityCode != 102`）上的单段、非 combi 语音。这些 Cue 只有该角色本人在说，相当于免费的带标签训练数据。每个角色约 85–108 段。
2. **特征（MFCC）**：解码为 16 kHz 单声道 → 预加重 0.97 → 25 ms Hamming 窗、10 ms 步长 → 512 点 FFT → 40 个 mel 滤波器（60–7600 Hz）→ 取对数 → DCT，保留第 1–19 维（去掉第 0 维音量）。只保留能量高于该段 35 分位的帧（去掉静音和气口），再按段减去均值（抵消录音/混音差异）。
3. **模型**：每个角色一个全协方差高斯分布（协方差加 1e-3·I 防止奇异）。音色差异主要体现在 MFCC 的均值和相关结构上，单高斯在这个数据量下已经够用。
4. **判定**：对待测段的每帧算对数似然，取平均；只在**该部门的候选人**（masterdata `CharacterGroupCode`，排除 99）中选得分最高的。候选人数少，正是准确率高的原因。
5. **置信度**：输出每段的 `Margin` = 第一名减第二名的得分。经验上 margin ≥ 0.5 比较可靠，< 0.3 应人工试听。

## 验证

**留一卡交叉验证**：依次拿掉一张卡的全部语音，用剩下的卡训练，再在部门内判定被拿掉的那张。这样模拟“新卡、模型没听过这张卡”的真实情况。

- 总体：**1889 / 1946 = 97.1%**
- 各角色基本 100%，弱项：
  - **5 宇京真央 67%**（误判为 7 揺 20 次、6 明星 8 次、4 恋 3 次）。真央部门的结果要多留心。
  - 12 御門尊 91%，4 綾戸恋 97%，20 神家 97%。
- 18 恩田灯世 与 19 新名有 在验证中 100% 可分。

## 当前结果（按播放顺序）

| 卡 | 卡名 | 协作对象 | 模型顺序 | 各段 margin | 群友记忆 |
| --- | --- | --- | --- | --- | --- |
| 407 | Present for Kyoya | 15 樹帆 | 17 吏来 → 15 樹帆 | 0.99, 1.02 | |
| 414 | Present for Kou | 6 明星 | 5 真央 → 6 明星 → 7 揺 | 4.2, 0.97, 0.97 | |
| 421 | Present for Soyogu | 14 篠信 | 11 静 → 12 尊 → 14 篠信 | 0.15, 0.4, 0.48 | margin 低，需试听 |
| 434 | Present for Mao | 7 揺 | 4 恋 → 6 明星 → 7 揺 | 0.33, 1.64, 0.43 | 一致 |
| 437 | Present for Riku | 16 恭耶 | 16 恭耶 → 15 樹帆 | 0.91, 0.7 | 一致 |
| 450 | Present for Roka | 2 由鶴 | 1 逢 → 2 由鶴 | 0.77, 2.02 | |
| 463 | Present for Haruhi | 8 大河 | 8 大河 → 10 誓 | 0.29, 0.58 | |
| 470 | Present for Kiho | 17 吏来 | 16 恭耶 → 17 吏来 | 1.15, 0.77 | |
| 471 | Present for Sei | 9 春日 | 9 春日 → 8 大河 | 0.7, 0.6 | 一致 |
| 478 | Present for Takeru | 11 静 | 11 静 → 13 戦 → 14 篠信 | 1.05, 0.64, 1.39 | |
| 491 | Present for Shinobu | 13 戦 | 11 静 → 12 尊 → 13 戦 | 0.65, 0.45, 0.44 | |
| 492 | Present for Kamiya | 19 有 | 18 灯世 → 19 有 → 21 麗 | 1.1, 0.92, 1.03 | **冲突**：群友记为 有 → 灯 → 麗 |

492 的第 1 段：灯世 −18.1、麗 −19.2、有 −19.6，有反而是最低分；第 2 段有 −17.3 领先。加上灯世/有在验证中完全可分，模型判断较可信，但仍建议游戏内或用 `card_combi_voices_audio/` 里的 WAV 试听确认。

（2026-11-08，production masterdata 495 张卡。）

## 复用方法

前置：本机有 ffmpeg（需支持 `-f hca`），已安装 numpy、scipy；先跑一次 `card_combi_voices` 得到审计 JSON，并且 ACB 已同步到缓存。

```powershell
python scripts/combi_speaker_id.py `
  --masterdata "E:\WikiResults\<run>\.bmc_toolkit\master_data.json" `
  --acb-root "E:\BRMYCache\production-<hash>\raw" `
  --combi "E:\WikiResults\<run>\audit_output\card_combi_voices.json" `
  --output "E:\WikiResults\<run>_speaker_id"
```

- `--acb-root` 下递归查找 `voice_<卡号>.acb`。
- 解码结果按卡缓存在 `<output>/decoded/<卡号>.npz`，第二次运行几分钟内完成；首次需要解码全部卡（较慢）。
- 结果写入 `<output>/combi_speakers.json`：`Validation`（总体与逐角色准确率、误判对象）、`Results`（每段的 Speaker、Margin、各候选得分、`IsPermutation` 是否每人恰好一次）。
- `--skip-validation` 跳过交叉验证，只出结果。
- `--kind` 可换成 `card_combi_voices` 里的其他 Kind（例如多段叠放的技能语音）。

新卡上线后：同步 masterdata 和 ACB → 重跑 `card_combi_voices` → 重跑本脚本。新卡自己的单段语音会自动加入参考集。

## 限制

- 只在部门候选人内判定。如果某段是部门外角色（或 NPC），会被强行分给部门内最像的人。
- 需要每个候选人都有足够的单段参考语音；新角色或语音极少的角色不可靠。
- 同一角色用明显不同的演技（耳语、喊叫、唱歌）时得分会下降。
- CR 卡语音含两人，被排除在参考集之外；本方法也没有针对 CR 卡的双人 Cue 做过验证。
- 结果是统计估计，不是游戏数据。写进 wiki 前，低 margin 或与群友记忆冲突的条目应人工试听。
