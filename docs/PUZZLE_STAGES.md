# 消消乐关卡与 GROOVE 谱面

两个任务各读一类独立小文件，都以 masterdata 行为主键：

| 任务 | 玩法 | 文件 | 主键 | 产物 |
| --- | --- | --- | --- | --- |
| `puzzle_stages` | 消消乐（Puzzle） | `Stages/*.s2bStage` | `mst_puzzle_stage` (PuzzleMapId, PuzzleStageNo, PuzzleType) | `puzzle_stages.xlsx` |
| `groove_charts` | GROOVE（音游） | `Score/*.s2bscore` | `mst_groove_music_stage` (MusicId, GrooveMusicStageType) | `groove_charts.xlsx` |

```powershell
python -m toolkit sync puzzle_stages groove_charts --cache "E:\BRMYCache" --output "E:\WikiResults"
python -m toolkit generate puzzle_stages groove_charts --masterdata "E:\data\master_data.s2b" --source "E:\data\files" --output "E:\WikiResults"
```

本地 `--source` 可以是单个文件或目录，目录会递归查找，所以选 `Stages/` 与 `Score/` 的上级目录即可。

## 面（A/B/C…）

- 消消乐：`PuzzleType` 1–6 = A–F（客户端枚举 `PuzzleType`）。普通关卡是 A/B/C，C 面多为隐藏的金币关；D/E/F 只出现在少数特殊关卡（如 2nd Anniversary 全员曲 107 关）。
- GROOVE：`GrooveMusicStageType` 1–3 = A/B/C，每首曲统一三面。

关卡种类是 `PuzzleStageType`：通常 / 挑战 / 每日 / 指定编成（Preset，固定编成的 Another Story）/ 个人曲 / 个人曲Remix / OJT / 全员曲 / Shuffle曲。工作簿按种类分表，“通常”再按地图归属分为角色 / 活动 / CP。每张表按开放日期排列。

## 文件来源

2.1.0 客户端格式串：`Stage{0}_{1}_{2}`、`StoryStage{0}_{1}_{2}_{3}`、`.s2bStage`、`Stages`。

- **Stages 不在正式清单里。** 正式 CDN 的 `https://s2b-assets-prod.s2b-coly.com/Stages/<名>` 按此名称直接提供，内容与 staging 桶相同，没有 LZMA 外层。`resources.DERIVED_PREFIXES` 只放行 `Stages/`；`download_derived` 不要求清单确认，缓存按 ETag 条件请求复验，离线时只用已校验缓存。2026-11-11 的 masterdata 推导出 1951 个关卡与 10 个主线剧情关卡，在正式 CDN 上全部存在。
- **Score 是清单类别 8**，路径 `Score/`，按 `StageFileName + .s2bscore` 选择。未上线曲目（如 ReleaseDateTime 为 2027 的占位曲）在 CDN 返回 403，规划时直接跳过，表中写“谱面未发布”。
- staging 桶 `Stages/` 下另有约 670 个没有 masterdata 行的文件（旧两段式 `Stage{map}_{no}`、`Stage0_*` 调试关、模板、`Stage6_500_1` 等 2023 年测试文件），任务不读取。`Stage6_500_1` 是地图 6 的第 500 关，与卡牌 500 无关。

## .s2bStage 格式

MessagePack-CSharp `Lz4BlockArray`：`[ext98(各块原始长度), bin, bin, …]`，各块 LZ4 解压后拼接，得到一个按位置序列化的 `Puzzle.StageInfoDefinition.StageInfo` 数组。`core/s2b_parser.py` 统一处理 ext98 与 ext99。字段位置（2.1.0 `dump.cs` 的 `[Key(n)]`）：

| Key | 字段 | 表中用途 |
| --- | --- | --- |
| 1 | map（30 列 × 24 行；-2 无格，0 空格，>0 PieceInfoId） | 盘面初始机关 |
| 3 | spawnerType（DropCell：pieceDrop / gimmickDrop 的 [id, 权重]） | 掉落机关 |
| 4, 14, 15, 19 | fixGimmickMap 1–3、fixGimmickMapOnMainPiece | 盘面初始机关 |
| 16, 17 | wallGimmick_Line / _Column | 盘面初始机关 |
| 5 | phaseList（BGM MusicInfoId 与小节、chapter 序列） | 曲目兜底 |
| 7 | attributeInfo（stageAttibute、SpCost） | 属性兜底 |
| 8 | targetInfoList（[targetId, value, clear]；targetId 是 PieceInfoId，0 为分数） | 通关目标 |
| 9 | scoreInfo（scoreRank 字典、averageCombo） | 仅 JSON |
| 10 | life（defaultValue、damage、recoveryRate、continuePermission） | 生命 |
| 11 | tutorial（[TutorialId, showOnStart]） | 新机关提示（mst_gimmick_tutorial.GimmickName） |
| 18 | rule（specialPieceType、isGravity、isNoSeekBar、moveLimitCount） | 步数上限（-1 为不限） |

SS 分数线与平均连击取 masterdata 的 `SSRankScore` / `AverageCombo`；关卡文件自带的分数线与平均连击和 masterdata 并不总一致，只保留在 `puzzle_stages.json`。

## .s2bscore 格式

明文 MessagePack 字典：`CueSheetName`、`CueName`、`Bpm`、`StartDelayMs`、`FirstStartBarTime`、`ComboPieceSelectorLabelName`、`EndTimeMs`、`Notes`、`Gimmicks`。

- Note：`TimeMs`、`Type`（Left / Right），可选 `DurationMs`（长按）、`NoteType`（Rare / Hirameki；Hirameki 都是长按）、`DivisionCount` + `ComboPieces`（分段音符）。
- Gimmick：`Bush`（连打，`RequiredTapCount`）和 `SeekBar`（预告，`PreviewNoteDataList`）。

难度列是 `GrooveMusicStageDifficulty` 原值，没有换算。
