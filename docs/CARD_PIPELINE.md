# 卡牌数据管线

> 最后核对：2026-07-16  
> 适用入口：`toolkit/domains/cards.py`  
> 输出：`json_output/All_Cards_Database.json`、`xlsx_output/cards_data.xlsx`

## 1. 本次重构目标

旧实现把表定位、技能渲染、活动推断、语音关联和 47 列 Excel 拼装集中在一个函数中，并三次递归扫描完整 masterdata。获取方式还依赖卡号顺序、`last_valid` 和全局 `stop`，一张新 SSR 无法识别时会清空其后的所有卡。

当前实现分为五层：

1. `core/tables.py`：按 masterdata 表目录读取具名表。
2. `domains/cards.py`：提取卡牌原始字段、数值、技能、消耗、剧情和资源。
3. `domains/card_relations.py`：建立活动、卡池、直发奖励、交换所、多角色和双人主页语音关系。
4. `domains/audio.py` + `core/cri_utf.py`：从 ACB `@UTF` 表精确关联 CueName 与台词。
5. `domains/card_export.py`：使用命名列定义生成 Wiki 表，不再维护易错的超长位置数组。

## 2. 回滚点

重构前源码、历史脚本、EXE 和 SHA256 清单位于：

```text
backups/cards_before_layered_refactor_20260716_114729/
```

其中 `All_Cards_Database.no_audio.baseline.json` 是第一层改造前的 433 卡无音频基线。具名表改造完成后曾与该文件逐字段比较，结果完全一致。

## 3. 具名表依赖

核心卡牌：

- `mst_character_card`
- `mst_character_card_parameter`
- `mst_character_card_revision`
- `mst_character_card_leader_skill`
- `mst_character_card_sp_skill_level`
- `mst_character_card_sp_skill_with_combi`
- `mst_character_card_auto_skill_level`
- `mst_character_card_combination_level`
- `mst_character_card_story_section`
- `mst_character_card_multi_character`

技能定义和升级材料：

- `mst_auto_skill_effect`
- `mst_sp_skill_effect`
- `mst_combination_effect`
- `mst_leader_skill_effect`
- `mst_item_card_revision`
- `mst_item_card_sp_skill_level_up`
- `mst_item_card_auto_skill_level_up`
- `mst_item_card_combination_level_up`

获取关系：

- `mst_event` 与四类活动扩展表
- `mst_gacha`、`mst_gacha_arrival`
- `mst_direct_reward`
- `mst_exchange`、`mst_exchange_product`

语音关系：

- `mst_home_voice`
- `mst_home_voice_character_card_duo`
- `voice_<CharacterCardId>.acb`

## 4. JSON 分层

每张卡保留以下主要区块：

- `Raw`：`mst_character_card` 原始行，新增字段不会因当前展示层未识别而丢失。
- `Meta`：角色、卡名、稀有度、属性、实装时间等常用字段。
- `Stats`、`Revision`：基础值和突破加成。
- `LeaderSkill`、`SpSkill`、`AutoSkill`、`Combination`：已渲染技能文本。
- `UpgradeCosts`：四类升级消耗。
- `Story`：卡牌剧情小节原始记录。
- `Assets`：图标、立绘、LiveClip、技能特效和 CueSheet 文件名。
- `Relations`：所有关系证据，不只保存最终显示名。
- `Acquisition`：由关系证据派生出的 Wiki 获取方式。
- `Voice`：masterdata 解锁条件与 ACB 台词的合并结果。

## 5. 获取方式判定

### 5.1 基线

`CardRouteCode` 来自 `dump.cs`：

- `1 = Gacha`
- `2 = EventReward`

活动、卡池和交换所只用于确定名称与细分类，不再反过来猜大类。

### 5.2 证据优先级

活动报酬卡：

1. 活动扩展表 `PickUpCharacterCardId(s)`，且实装时间位于活动期间。
2. `mst_direct_reward` 类型 1 的卡牌奖励，经 `mst_exchange_product` 反查交换所。
3. 同期活动扩展表 `CharacterCardIds`。

卡池卡：

1. `mst_gacha_arrival.CharacterCardIds` 到 `GachaGroupId`。
2. `mst_gacha.CostumeIntroductionCharacterCardIds` 作为旧数据回退。
3. 同期活动扩展表，解决活动已写入但卡池表尚未出现的更新窗口。
4. 初始卡号 1 至 63 优先标为常驻；后续 Megamix、复刻等卡池引用只保存在关系证据中，不改变首次获取来源。

最终对象同时保存 `Confidence`、`Evidence` 和 `Warnings`。未知新机制只影响自己的判定，不会再触发后续卡牌连锁清空。

### 5.3 奖励类型修正

`dump.cs` 的 `RewardTypeCode` 已确认：

- `1 = CharacterCard`
- `2 = Item`
- `3 = HomeBackground`
- `4 = CostumeModel`
- `5 = CostumeMini`
- `6 = Honor`
- `7 = Pin`
- `8 = Music`
- `9 = SpinAlbumReleaseItem`
- `99/100/101/102` 分别为信息、活动道具、食材、旅行币。

旧 `events.py` 把 1 当道具、3 当卡牌，现已修正。

## 6. CR 与多角色卡

`CardRarityCode=102` 是 `CR`。当前样本：

- 426：皇坂逢、立科吏来 `Vignette -Emperor-`
- 427：樋宮明星、神家 `Vignette -Skip-`

第二角色来自 `mst_character_card_multi_character`，主页双人衔接来自 `mst_home_voice_character_card_duo`。Wiki 活动页人工核对地址：

<https://wiki.biligame.com/breakmycase/Vignette_-Emperor/Skip->

程序仍保留 `RarityCode=102` 原值，避免以后仅凭显示名处理枚举。

## 7. ACB 语音关联

不能用 `title:{...}` 作为唯一键。CR 包中同一标题会出现两次，例如两个“主页语音①”和两个“技能语音”。

精确关系位于 ACB 内部：

```text
CueNameTable.CueIndex
  -> CueTable[ CueIndex ].UserData
  -> title:{...}text:{...}
```

`core/cri_utf.py` 是纯 Python `@UTF` 读取器，因此发布 EXE 不依赖 vgmstream。旧测试样本或非标准二进制无法解析 `@UTF` 时，才回退到 NUL 字符串池和标题映射，并在 `MatchStatus` 中标记回退来源。

426 已验证得到六条互不覆盖的 Cue：

```text
card_vo_home_1
card_vo_home_2
card_vo_home_3
card_vo_home_4
card_vo_skill_1
card_vo_skill_17
```

所有正文换行统一输出为 `<br>`。

## 8. Excel 兼容策略

原 47 列的顺序保持不变。以下字段追加在末尾：

- 卡牌附加角色名
- 卡牌语音④J/C
- 卡牌副角色技能语音J/C

CR 卡的“卡牌角色名”直接输出两名角色，主角色技能仍写入原“卡牌技能语音J”，副角色技能写入新增列。普通卡的 `card_vo_skill_combi` 只进入协作语音列，不会误判成副角色技能。

卡牌 XLSX 的日文语音会移除 `<br>` 和实际换行，避免 Wiki 拉表后出现强制断行。JSON 仍保留 `Text` 与 `TextHtml` 两种形式，关系证据中的 `Confidence`、`Warnings` 也只用于内部排查，不再导出为 Wiki 列。

## 9. 当前验证基线

- 卡牌总数：433。
- 稀有度：R 65、SR 105、SSR 246、XR 15、CR 2。
- 获取方式：常驻 63、活动卡池 222、周年卡池 44、生日限定 45、活动报酬 59。
- 获取方式空白：0。
- 获取关系警告：0。
- 含剧情索引的卡：416。
- 已关联 ACB 正文的卡：433。
- 精确 `matched_by_acb_utf` Cue 元数据：1977，其中非空台词 1907。
- 未替换技能占位符：0。
- 自动化测试：14 项。

## 10. 后续扩展原则

1. 新 masterdata 字段先进入 `Raw` 或 `Relations`，确认语义后再进入 Wiki 展示列。
2. 新活动机制优先增加证据适配器，不在导出循环里添加卡号特判。
3. 新稀有度同时保留原始代码和人工确认显示名。
4. 新语音形态以 CueName 和 `CueIndex` 关联，不以标题或物理流顺序关联。
5. 原 47 列除非 Wiki 导入流程同步升级，否则只允许在末尾追加列。
