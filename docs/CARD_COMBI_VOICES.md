# 多段协作语音例外表

卡牌全表的每个语音列只能放一句台词。以下情况不满足这个前提，统一放进单独的 `card_combi_voices` 例外表，**不写入卡牌全表**：

- **三轮生日卡（Present for ○○）的部门协作语音**：`card_vo_skill_combi` 这一条 Cue 依次播放部门内其他成员各一段，三人部门 2 段、四人部门 3 段。
- **其他一条 Cue 含多段音频的情况**：例如 360 号卡的技能语音由两段叠放而成。

卡牌全表的“卡牌协作语音J”仍然只放这条 Cue 的 ACB 元数据文本。该文本是整条 Cue 共用的一句话，不代表每一段的内容，而且三轮生日卡上存在复制粘贴的情况（例如多张卡都是「いろんなことがあったからな」）。

## 用法

```powershell
python -m toolkit sync card_combi_voices --cache "E:\BRMYCache" --output "E:\WikiResults"
python -m toolkit generate card_combi_voices --masterdata "E:\path\master_data.json" --audio "E:\path\Musics" --output "E:\WikiResults"
```

GUI 中位于“语音”分组，名为“多段协作语音（例外表）”。

## 输出

| 文件 | 内容 |
| --- | --- |
| `wiki_output/card_combi_voices.xlsx` | 每段一行：卡牌、Cue、段序、开始秒、时长、候选说话角色、masterdata 协作对象、Cue 元数据文本、音频文件名，以及人工填写的台词J/C列 |
| `audit_output/card_combi_voices.json` | 完整的段结构（Synth/Waveform/AWB 编号）、未识别的轨道命令原值，以及需要人工核对的问题 |
| `audit_output/card_combi_voices_audio/` | 每段的 HCA 原始音频；本机有 ffmpeg 时额外输出 WAV，供试听和听写 |

## 判定规则

1. 解析 ACB 的 Cue → Sequence → Track → TrackEvent，按 note-on 命令收集该 Cue 实际播放的 Synth → Waveform；delay 命令累计为每段的开始时间。
2. 只有一段的 Cue 不进入本表。
3. `card_vo_skill_combi` 段数等于“卡牌角色所在部门人数 − 1”时，类型为“部门协作语音”，候选说话角色是部门内的其他成员。部门按 `mst_character.CharacterGroupCode` 判断，99 组（NPC 等）不算部门。
4. 段数与部门人数对不上时，类型为“协作语音段数与部门人数不符”，记入问题清单。
5. 其他 Cue 含多段时，类型为“其他多段语音”，不给候选角色。

## 限制

- ACB 每条 Cue 只有一份 `title:{}text:{}` 元数据，**无法确定每段由谁说、说了什么**。“候选说话角色”只是部门成员列表，不按顺序对应各段；台词列必须试听后人工填写。每段说话人可以用声纹估计，见 [COMBI_SPEAKER_ID.md](COMBI_SPEAKER_ID.md)。
- 轨道命令 `0x07D5` 的含义尚未确认，原值保留在审计 JSON 中，不据此推断说话角色。
- 只处理 ACB 内嵌的音频；若以后出现流式 AWB（`Streaming` 非 0），音频文件名留空，并需要另行处理。
