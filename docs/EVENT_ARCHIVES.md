# 活动档案（2026-11-12）

活动按客户端 2.1.0 的枚举 `EventFormat` 分成五类，每类玩法数据不同，所以拆成一份总表加四份玩法档案。GUI「活动」分组和「只出活动表」预设包含全部五项。

| EventFormat | 客户端名 | 类型 | 子型（`mst_event_a.EventAType`） | 期数（11-12） | 档案 |
|---|---|---|---|---|---|
| 1 | A | 交换所活动 | 1 Exchange：常规 | 18 | `交换所与剧情活动.xlsx` |
| 2 | ANonMedal | 无奖章活动 | 2 ExchangeAndRanking：Prequel 6 / Travelogue 6（按标题前缀）；4 NoRanking：无排名特别活动（0.5/1.5/2.5 周年、新年、RMX FES）7；5 SpecialStepMission：阶段任务周年活动（1st / 2nd）2 | 21 | `交换所与剧情活动.xlsx` |
| 3 / 4 | B / BSpecial | 营业（摇酒）活动 | 常规 12 / 特别版 1（Welcome! KAWAII Cafe♡） | 13 | `营业活动档案.xlsx` |
| 5 | C | OJT | — | 4 | `ojt_archive.xlsx`，见 [OJT_ARCHIVE.md](OJT_ARCHIVE.md) |
| 6 | AAccumulateItem | Vignette 活动 | — | 3 | `Vignette活动档案.xlsx` |

旧分类把 EventAType 4 叫「特殊活动」、5 叫「周年活动」，结果半周年被归为特殊、整周年才叫周年。现在按客户端枚举改名，见 `toolkit/domains/event_classification.py`。

## 活动总表 `event_archive.xlsx`（任务 `events`）

文件名不变，工作表改为中文：

| 工作表 | 内容 |
|---|---|
| 活动一览 | 每期一行：类型、子型、开放 / 结束（JST）、日期状态、PICKUP 卡、剧情章节数、任务数、详细档案（指向上表的工作簿） |
| 剧情章节 | 章节类型（通常 / アナザー / アナザー（轮班营业额解锁），客户端 `EventStorySectionType`）、解锁需求值、钥匙消耗、阅读奖励 |
| 活动任务 | 各期任务的阶段、目标值、奖励 |
| 规则说明 | 规则页文本，已去掉 `<color>` / `<size>` 标签，`<br>` 换成真换行 |
| 说明 | 口径 |

原来的 Shifts（营业轮班 + OJT 轮次）和 RewardSummary（排名 / 营业额 / 累积奖励混在一起，5709 行）已移到各玩法档案。`Event_Archive.json` 也不再带这几部分。

## 交换所与剧情活动 `交换所与剧情活动.xlsx`（任务 `exchange_events`）

| 工作表 | 内容 |
|---|---|
| 活动总览 | 类型、子型、开放 / 后半开始 / 排名结束 / 结束、PICKUP 卡、活动卡牌、活动 pt 道具、活动加成、兑换所名与商品数、同期キャンペーン |
| 排名奖励 | 高分排名 / 活动 pt 排名（客户端 `RankingType` 1 HighScore、2 Event）；名次区间由相邻两档的 StartRank 推出，最后一条没有奖励的只作区间终点；ワッペン数 |
| 兑换所 | 按 `mst_event_a.ExchangeId` 展开商品：奖励、消耗（`CostItemIdNumber` 选 CostItemId1/2）、可兑换次数（0 写「不限」）、追加上架 / 提前下架时间 |
| 说明 | 口径 |

## 营业活动档案 `营业活动档案.xlsx`（任务 `bar_events`，取代旧任务「配方」）

| 工作表 | 内容 |
|---|---|
| 活动总览 | 类型、开放 / 结束、轮班数、全轮班共通曲目、PICKUP 卡、活动卡牌、关卡掉落加成、营业额加成、其他关卡掉落材料 |
| 轮班 | 按开始时间编号的轮班、轮班角色、本轮班曲目、3 道菜单、特别营业次数 |
| 菜单与配方 | 每轮班 3 道菜单：配方、等级（RecipeDifficulty）、解锁条件、推荐角色、售价、耗时、材料、配方奖励、说明 |
| 材料 | 全部材料；分类按 ID 段（游戏数据没有分类字段）：1–50 基酒、51–99 利口酒、101–199 软饮、201 起辅料、10000 起联动限定 |
| 关卡掉落 | 活动地图关卡归入轮班（见下）、面、曲目、全轮班共通 / 本轮班、重点材料、掉落材料与概率 |
| 特别营业 | 每轮班的特别营业时段与登场角色（含三丽鸥联动角色，名称取自 `mst_character_collaboration`） |
| 营业额奖励 | `ShiftId` 0 = 全期累计，其余为各轮班；奖励相同的连续档位合并，写成「5,000～20,000 EN（2 档，每档各得一次）」 |
| 说明 | 口径 |

关键规则：

- 菜单解锁条件来自 `mst_event_menu_unlock_condition`，客户端枚举 `MenuUnlockConditionCode` 1 MenuCount / 2 IngredientCount / 3 Sales；现有数据只用 1，对应游戏内「1つ上のレシピを{0}回作って解放」，{0} 为 Value2。
- 活动地图关卡没有 ShiftId；与网站模块 `toolkit/website/bartending.py` 相同，按「同一活动内关卡 ReleaseDateTime / EndTime 与轮班起止完全相同」归入轮班，归不进去的记入审计 `bar_events.json` 的 Issues。现有 13 期 210 关全部唯一匹配。第 1 期（幽界からの招待状）的 16 关游戏数据没有配置材料掉落，表中写明。
- 活动期间角色地图等普通关卡也有材料掉落（`mst_event_puzzle_stage_ingredient` 中不属于活动地图的 8203 条），总览只给关卡数和重点材料。
- 配方奖励来自 `mst_event_recipe.DirectRewardGroupId`。用户于 2026-11-12 游戏内确认：解锁配方并制作之后，点开对应菜单领取奖励。
- 旧任务 `recipes`（`bar_data_complete.xlsx`）仍可从命令行运行，但不再出现在 GUI；旧设置里勾选过「配方」的，打开 GUI 时会改勾「营业（摇酒）活动」。

## Vignette 活动档案 `Vignette活动档案.xlsx`（任务 `vignette_events`）

| 工作表 | 内容 |
|---|---|
| 活动总览 | 登场角色、PICKUP 卡（每期两张 CR）、活动卡牌、累积道具、活动加成、奖励档数 |
| 累积奖励 | 累积数量档位（相同奖励的连续档位合并）、奖励、重点奖励 |
| 说明 | 口径 |

## 共用口径

- 时间统一为日本时间（JST）。日期状态按核对时刻判断。
- 活动加成按 `mst_event_bonus` 字段名翻译（活动卡牌 / 稀有度 / 突破阶段 / 角色 / 属性 / 轮班角色），游戏内没找到逐项文字。
- 奖励名称缺失时写作「类型(ID)」，数量计入各任务的运行提示，并出现在 `待核对汇总.xlsx`。
- 审计 JSON：`bar_events.json`、`exchange_events.json`、`vignette_events.json`，保留原始行。

真实数据回归（2026-11-12 masterdata）：五项任务一次生成，活动一览 59 期；营业活动 13 期 / 54 轮班 / 156 道菜单 / 210 关掉落 / 228 段特别营业，关系异常 0；交换所与剧情活动 39 期 / 210 档排名 / 2006 件商品，关系异常 0；Vignette 3 期 / 504 档合并为 493 行。奖励名缺项：营业 72、交换所 315、Vignette 9（多为没有名称的 Pin）。
