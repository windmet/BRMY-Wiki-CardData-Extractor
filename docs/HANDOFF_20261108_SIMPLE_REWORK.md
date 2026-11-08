# 交接：简易改造（feat/simple-rework，2026-11-08）

分支 `feat/simple-rework`，从 main `85ce545` 拉出，**未推送**。上一份交接在分支 `docs/handoff-20261108` 的 `docs/HANDOFF_20261108.md`。

## 已完成（提交）

| 提交 | 内容 |
| --- | --- |
| `aa5aa7d` | GUI 按用途分组（卡牌/语音/活动与剧情/音乐/网站数据），预设（版本更新全套/只更新语音/只出活动表），模式改为“联网更新/用本地缓存”，失败时自动跳到详情页，高 DPI 适配；CLI 精简，旧命令（decrypt/all/run/update/extract/export）退休并提示等价 `generate` 命令；删除 interactive 入口；`NEEDS_MASTERDATA` 统一定义在 generate.py |
| `cd3a9f8` | 适配当前服务器数据：birthday_archive 不再强依赖 mini_game 表；双层 LZMA 脚本可解；空歌词占位跳过并告警 |
| `6c7628f` | birthday 默认导出全部轮次（每轮一个工作表，可用 `--cycle/--year` 选单轮）；home_voice_catalog 按用途分子表（节日与话题/周年纪念/季节/角色生日祝福/玩家生日/常驻与问候），A–E 列不变，新增“开始时间”“备注”；OJT `.s2bchart` 在线下载（CDN 路径 `Chart/`） |
| `f44b43d` | 下载器对断连/SSL EOF 重试 3 次，HTTP 4xx 不重试 |
| （本次） | `scripts/combi_speaker_id.py` + `docs/COMBI_SPEAKER_ID.md`：协作语音声纹识别 |

测试：197 个全部通过（约 13 秒）。

## 关键结论

- **0x07D5**：协作 Cue 中 delay 与下一个 note-on 之间的 2 字节标记，载荷几乎都是 0000（421、492 例外），不含说话人信息。
- **三轮生日协作语音顺序**：整条 Cue 固定播放完（`CutInEnd ≈ CombiVoiceStart + Cue 时长`），顺序由每张卡的 ACB 写死，不随编成变化，也不符合“协作对象优先”或“纯编号”任一规律。声纹结果见 `docs/COMBI_SPEAKER_ID.md`：群友记忆 437/471/434 一致；**492 冲突**（模型 灯世→有→麗，群友 有→灯→麗），421 margin 低，均待试听。
- **S3 staging 桶**：公开可列举，从正式服同步，额外有上传时间、`Stages/`（2645）、`Score/`（117）。“提前一期”实际上是：新卡资源（card_illust_N、card_N_*.s2bscript）在正式服也比 masterdata 先上线。
- **正式服 Files/Android 每个 bundle 都包了一层 LZMA-alone**（不是只有 S3），UnityPy 前先解包。

## 产出位置

| 路径 | 内容 |
| --- | --- |
| `E:\WikiResults\20261108_review\` | 全部表的评审版。`birthday_lines_new.xlsx`、`home_voice_catalog_new.xlsx` 是因原文件被 Excel 占用而另存的，关掉 Excel 重跑即可覆盖 |
| `E:\BRMY_Data\s3_stg_20261108\` | S3 清单（listing.json）、正式服 key 对比、下载的文件 |
| `E:\WikiResults\20261108_s3\` | `upcoming_cards.xlsx`（496–503、507）和 `new_card_art\`（新卡美术 PNG） |
| `E:\WikiResults\20261108_speaker_id\` | 声纹结果 `combi_speakers.json` 和解码缓存 |

新卡：496 静、500 大河、503 揺（Present for Yuragi）、502 疑似有的三轮生日卡、507 戦（只有称号图标和 1 个脚本）、501 活动 R 卡。

## 待办

1. **Score/ 与 Stages/ 研究**：Score 是音游谱面（Bpm、Notes 的 TimeMs/Type、A/B/C 难度）；Stages 是 `.s2bStage`，内部嵌套压缩，疑似 GROOVE 新模式，`Stage6_500_1` 引用了卡 500。
2. 可选：把声纹结果作为一列并入 `card_combi_voices`。
3. 等站长新方案：CR 卡、多人协作。
4. 上一份交接遗留：表格人性化（仅内部表）、masterdata 驱动的下拉框、文档压缩、exe 重新打包。
5. 关掉 Excel 后重跑 birthday / home_voices，覆盖 `_new` 文件。
6. 合并：分支未推送，确认后推送并开 PR 到 main。
