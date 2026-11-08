# 卡牌数据管线

> 最后核对：2026-11-08（客户端 2.1.0 dump + Ghidra）  
> 适用入口：`toolkit/domains/cards.py`  
> 输出：`json_output/All_Cards_Database.json`、`xlsx_output/cards_data.xlsx`

## 1. 本次重构目标

旧实现把表定位、技能渲染、活动推断、语音关联和 47 列 Excel 拼装集中在一个函数中，并三次递归扫描完整 masterdata。获取方式还依赖卡号顺序、`last_valid` 和全局 `stop`，一张新 SSR 无法识别时会清空其后的所有卡。

当前实现分为六层：

1. `core/tables.py`：按 masterdata 表目录读取具名表。
2. `domains/cards.py`：`_build_lookups` 建映射表，`CARD_TABLES` 逐表调用 `_apply_*` 填充卡牌（不再按字段名猜表），随后做 Wiki 用语后处理。
3. `core/skill_text.py`：按客户端 `SkillDescriptionParser` 渲染技能文本，见第 11 节。
4. `domains/card_relations.py`：建立活动、卡池、直发奖励、交换所、多角色和双人主页语音关系。
5. `domains/audio.py` + `core/cri_utf.py`：从 ACB `@UTF` 表精确关联 CueName 与台词。
6. `domains/card_export.py`：使用命名列定义生成 Wiki 表，不再维护易错的超长位置数组。

2026-11-08 改为逐表处理时发现两处字段猜错，一直静默失效：

- 升级材料表的列名是 `CostItemId1..6`，旧代码判断 `ItemId1`，所以 `UpgradeCosts` 全空，Wiki 的“卡牌升级道具1–3”从未填过。现在 466 张卡有值；25 张卡材料超过 3 种，Wiki 列只放前 3 种，完整清单在 JSON。
- `mst_leader_skill_effect` 没有 `SkillName`，队长技能名回退为 `SkillEffect`（`VisualUp` 等），不再是 `Leader_<id>`。

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

例外：三轮生日卡的 `card_vo_skill_combi` 依次播放部门内多名成员的语音，协作语音列只保留整条 Cue 的元数据文本，逐段内容见 [多段协作语音例外表](CARD_COMBI_VOICES.md)。

卡牌 XLSX 的日文语音会移除 `<br>` 和实际换行，避免 Wiki 拉表后出现强制断行。JSON 仍保留 `Text` 与 `TextHtml` 两种形式，关系证据中的 `Confidence`、`Warnings` 也只用于内部排查，不再导出为 Wiki 列。

## 9. 当前验证基线

2026-11-08 masterdata + 652 个 ACB：

- 卡牌总数：495；R 74、SR 115、SSR 277、XR 23、CR 6。
- 获取方式：活动卡池 257、活动报酬 70、常驻 63、生日限定 54、周年卡池 45、序列码兑换 6。
- 技能占位符无法解析：0（有则作为运行警告记录）。
- 自动化测试：207 项。

## 10. 后续扩展原则

1. 新 masterdata 字段先进入 `Raw` 或 `Relations`，确认语义后再进入 Wiki 展示列。
2. 新活动机制优先增加证据适配器，不在导出循环里添加卡号特判。
3. 新稀有度同时保留原始代码和人工确认显示名。
4. 新语音形态以 CueName 和 `CueIndex` 关联，不以标题或物理流顺序关联。
5. 原 47 列除非 Wiki 导入流程同步升级，否则只允许在末尾追加列。
6. 新 APK 到手后先跑 `scripts/dump_schema.py`，它会列出 masterdata 中客户端未定义的枚举值和字段。

## 11. 技能文本：照客户端规则渲染

依据：`Manager.Utility.SkillDescriptionParser.Parse`（2.1.0，RVA `0x7F35F24`）及其辅助函数的 Ghidra 反编译。客户端在不显示图标时的顺序：

1. `skill_value`、`piece_value`、`attribute_value`、`group_value`、`character_value` 依次处理，`<名>N` 一律替换为 `SkillValueN` 的标签。每个占位符只看自己序号的值。
2. `Util.SpecialPieceNameToTextId` 中的特殊棋子名替换为 `mst_text`：`combopiece_1..3` → 100118–100120，`bombpiece_1..6` → 100121–100126，`hiramekipiece_1..6` → 100127–100132，`rainbowpiece` → 100133。
3. `combo:{x}`、`text:{x}` 解包。客户端先取第一个匹配的 `x`，再用它替换所有匹配。
4. `strength_value1..6` → `mst_text` 100134–100138（小、中、大、特大、超特大）。

标签来源：部门 `mst_text` 100014–100019，属性 100114–100117，角色 `mst_character.CharacterNameJpn`，棋子 `mst_piece_info.Name`。找不到时客户端给空串，工具同样给空串并记入运行警告。

Wiki 自己的用语在客户端规则之后应用，并单独保留：棋子写作“サンピース（赤色）”（`PIECE_MAP`）、属性图标转文字、去掉协作文本开头的“さらに”、强度词换算百分比。

改用客户端规则后，2026-11-08 数据的 Wiki 输出变化：

- 卡 221、240、270 的协作 SP 效果原来错了。旧代码只传 `SkillValue1`，`piece_value2/3` 用卡面 SP 颜色顶替；现在按各自的 `SkillValueN` 渲染，例如 240 从“桃桃桃”改为“桃・空・黄”。
- `combopiece_1` 写作“シングルコンボピース”，`hiramekipiece_N` 带颜色（如“緑ひらめきピース”），与客户端 `mst_text` 一致，共 127 格。

### 强度百分比没有客户端依据

`PassiveSkillController.CalcDropRate`（RVA `0x7B2FEDC`）对同属性的 SHOWER 累加 `SkillValue2`，再减去 BLOCK 的 `SkillValue2`，得到 net：

- net ≥ 0：该属性棋子权重 ×`(1 + min(net, 6))`，重力等特殊模式下 net 减半（`CalcDropRateOnIncrease`，RVA `0x7B301D4`）；
- net < 0：权重 ×`0.6^|net|`（`CalcDropRateOnDecrease`）。

`strength_value3` 只决定显示的“小/中/大”。对应的 `SkillValue2` 为：小 1、中 2、大 4、特大 5、超特大 6，即权重 ×2、×3、×5、×6、×7；BLOCK 小、中、大分别为 ×0.6、×0.36、×0.13。现行 Wiki 写法“8/10/12/14/20%UP、1/2/4%DOWN”在客户端中没有对应，暂未改动，等 Wiki 组决定表述方式。

## 12. 客户端证据的复现方法

材料：`E:\BRMY_Data\apk_2.1.0\il2cpp\`（`libil2cpp.so`、`global-metadata.dat`、Il2CppDumper 生成的 `dump/dump.cs`、`script.json`）。

1. **结构与枚举**：`python scripts/dump_schema.py <dump.cs> --masterdata master_data.json [--json out.json]`。`[MemoryTable]` 类给出每张表的字段和类型，`Coly.S2BShared.Enums` 给出代码枚举。2026-11-08 数据对 2.1.0 客户端只报出 `PinCategoryType = 8`（masterdata 比客户端新）。
2. **方法体**：Ghidra 12.1.4（`E:\Tools\ghidra_12.1.4_PUBLIC`，需 JDK 21：`E:\Tools\jdk-21.0.12.1+1`）。项目 `E:\Tools\ghidra_projects\BRMY_2_1_0` 已导入 `libil2cpp.so`，未做全量自动分析（154 MB，耗时数小时），按需反编译：

```powershell
python scripts/ghidra/il2cpp_names.py index <script.json> <idx>
python scripts/ghidra/il2cpp_names.py find <idx>\methods.tsv 'SkillDescriptionParser$$Parse'
$env:JAVA_HOME = 'E:\Tools\jdk-21.0.12.1+1'
& 'E:\Tools\ghidra_12.1.4_PUBLIC\support\analyzeHeadless.bat' 'E:\Tools\ghidra_projects' 'BRMY_2_1_0' `
  -process 'libil2cpp.so' -noanalysis -scriptPath scripts\ghidra `
  -postScript DecompileRvas.java <idx>\methods.tsv out.c 0x7F35F24
python scripts/ghidra/il2cpp_names.py annotate <idx>\names.tsv out.c out_named.c
```

`DecompileRvas.java` 会先给被调用地址建函数并按 `script.json` 命名，否则未分析的二进制会把调用当成跳转，函数体只剩几行。`PTR_*` 操作数会附上指针目标，`annotate` 再把目标换成字符串字面量或类型名。Ghidra 的镜像基址是 `0x100000`，dump.cs 的 RVA 以 0 为基址。

新 APK 上市后，用 Il2CppDumper 重新生成 dump，然后 `-import` 新的 `libil2cpp.so` 到一个新项目即可。
