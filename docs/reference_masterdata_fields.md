# master_data.json 字段参考手册

> 本文档整理了所有脚本中使用的 `master_data.json` 字段关键词，供 Wiki 组数据提取参考。
> `master_data.json` 的解密源文件为 `master_data.s2b`（MsgPack + LZ4 压缩），
> 由 `decrypt_s2b.py` / `bmc_toolkit decrypt` 解密产出。

---

## 总览：master_data.json 结构

解密后的 JSON 是一个**外层数组**，内部包含多个**子数组（表）**，每个子数组由相同结构的对象（行）组成：

```json
[
  [ { ... }, { ... } ],   // 表0（如：道具表 Item）
  [ { ... }, { ... } ],   // 表1（如：角色表 Character）
  [ { ... }, { ... } ],   // 表2（如：卡牌表 CharacterCard）
  ...
]
```

以下按**数据域（domain）** 列出各脚本用到的字段。

---

## 一、卡牌数据 (Cards Domain)

### 1.1 全局映射表（预扫描）

这些字段散落在多个表中，脚本通过全量扫描来建立映射字典。

| 字段名 | 类型 | 说明 | 映射用途 |
|--------|------|------|----------|
| `ItemId` | int | 道具 ID | → 道具名映射 |
| `ItemName` | str | 道具名 | 道具名映射的值 |
| `CharacterId` | int | 角色 ID (1~21) | → 角色名映射 |
| `CharacterNameJpn` | str | 角色日文名 | 角色名映射的值 |
| `SpSkillEffectId` | int | SP 技能效果 ID | → SP 技能效果定义 |
| `SkillEffect` | str | 技能效果名 | SP 技能分类（如 "回复", "得分UP"） |
| `SpSkillCategoryCodeList` | list[int] | SP 技能分类编码列表 | 技能细分类型 |
| `AutoSkillEffectId` | int | 自动技能效果 ID | → 自动技能描述模板 |
| `SkillName` | str | 技能名 | 自动/SP/队长技能名称 |
| `SkillDescription` | str | 技能描述模板 | 含 `skill_value1` 等占位符的模板文本 |
| `SkillEffectId` | int | 普通技能效果 ID | → SP 技能描述模板 |
| `CombinationEffectId` | int | 协作技能效果 ID | → 协作技能描述模板 |
| `LeaderSkillEffectId` | int | 队长技能效果 ID | → 队长技能描述模板 |

### 1.2 卡牌主表（CharacterCard 相关）

通过特征字段 `CharacterCardId` 识别。

| 字段名 | 类型 | 说明 | 取值示例 |
|--------|------|------|----------|
| `CharacterCardId` | int | **卡牌唯一编号** | 1, 2, 3 ... |
| `CharacterCardName` | str | 卡牌名（日文） | "皇坂逢【…】" |
| `CharacterId` | int | 角色 ID (1~21) | 1=皇坂逢 |
| `CardRarityCode` | int | 稀有度编码 | 1=R, 2=SR, 3=SSR, 101=XR |
| `CardAttributeCode` | int | 属性编码 | 1=日, 2=月, 3=星 |
| `CombiCharacterId` | int | 协作组合角色 ID | 另一个角色 ID |
| `ReleaseDateTime` | str | 卡牌实装时间 | ISO 时间戳 |
| `CharacterCardIconFileName` | str | 卡牌图标文件名 | "card_icon_1" |
| `CharacterCardFileName` | str | 卡牌立绘文件名 | "card_ill_1" |
| `LiveClipFileName` | str | Live2D 文件名 | "live_clip_1" |
| `SpSkillName` | str | SP 技能名称 | "全力の一撃" |

### 1.3 卡牌基础数值（Stats）

通过字段 `AuraInitialValue` 识别。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `AuraInitialValue` | int | 气质初始值 |
| `AuraMaxValue` | int | 气质最大值（未突破） |
| `VisualInitialValue` | int | 外观初始值 |
| `VisualMaxValue` | int | 外观最大值（未突破） |
| `CharismaInitialValue` | int | 魅力初始值 |
| `CharismaMaxValue` | int | 魅力最大值（未突破） |

### 1.4 队长技能（LeaderSkill）

通过字段 `LeaderSkillEffectId` + `SkillValue1` 识别。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `LeaderSkillEffectId` | int | 技能效果 ID（→ 映射表） |
| `SkillValue1` ~ `SkillValue6` | int | 技能数值参数（多个占位值） |

### 1.5 SP 技能等级数据（SpSkill）

通过字段 `SpSkillLevel` + `SkillDescription` 识别。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `SpSkillLevel` | int | SP 技能等级 (1~MAX) |
| `SkillDescription` | str | 技能描述模板（含 `skill_valueN` 占位符） |
| `SkillValue1` ~ `SkillValue6` | int | 替换占位符的技能数值 |
| `SkillCost` | int | SP 技能消耗（COST） |
| `SpSkillEffectId` | int | SP 技能效果 ID（→ 效果分类） |
| `SpSkillWithCombiType` | str | SP 技能带协作类型标志 |

### 1.6 自动技能（AutoSkill）

通过字段 `AutoSkillLevel` 识别。分为**数值块**和**消耗块**。

**数值块**（`AutoSkillEffectId` 存在）：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| `AutoSkillLevel` | int | 自动技能等级 |
| `AutoSkillEffectId` | int | 效果 ID（→ 映射表） |
| `SkillValue1` ~ `SkillValue3` | int | 技能数值 |
| `PieceCount` | int | 需要碎片数 |

**消耗块**（`ItemId1` 存在）：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| `ItemId1` ~ `ItemId6` | int | 升级所需道具 ID |
| `CostItemCount1` ~ `CostItemCount6` | int | 对应道具数量 |

### 1.7 协作技能（Combination）

通过字段 `CombinationLevel` 识别。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `CombinationLevel` | int | 协作技能等级 |
| `CombinationEffectId` | int | 效果 ID（→ 映射表） |
| `SkillValue1` ~ `SkillValue6` | int | 技能数值 |

### 1.8 界限突破（Revision）

通过字段 `RevisionRank` 识别。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `RevisionRank` | int | 突破段位 (1~MAX) |
| `AuraAdditionalValue` | int | 气质加成 |
| `VisualAdditionalValue` | int | 外观加成 |
| `CharismaAdditionalValue` | int | 魅力加成 |

### 1.9 卡牌剧情

通过字段 `CharacterCardStorySectionNo` 识别。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `CharacterCardStorySectionNo` | int | 剧情章节号 |
| `PopupText` | str | 剧情弹窗文本（小贴士） |

### 1.10 卡池关联（Gacha）

通过字段 `GachaName` + `CostumeIntroductionCharacterCardIds` 识别。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `GachaName` | str | 卡池名称 |
| `CostumeIntroductionCharacterCardIds` | list[int] | 该卡池包含的卡牌 ID 列表 |

### 1.11 卡牌升级通用消耗

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `ItemId1` ~ `ItemId6` | int | 升级/突破材料道具 ID |
| `CostItemCount1` ~ `CostItemCount6` | int | 材料数量 |

---

## 二、音乐数据 (Music Domain)

通过特征字段 `MusicId` + `DisplayName` 识别。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `MusicId` | int | 乐曲编号 |
| `DisplayName` | str | 曲目名称（显示名） |
| `AudioFileName` | str | 音频文件名（无后缀） |
| `JacketFileName` | str | 专辑封面文件名（无后缀） |
| `ArtistNameInformal` | str | **优先** — 完整作者/歌手信息 |
| `ArtistName` | str | 后备 — 作者/歌手名 |
| `Duration` | int | 歌曲时长（秒）— 后备字段 |
| `PlayTime` | int | 歌曲时长（秒）— 后备字段 |

---

## 三、Snap / 拍立得数据 (Snap Domain)

### 3.1 便利贴（StickyNote）

通过 `StickyNoteId` 存在且 `SnapshotId` 不存在识别。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `StickyNoteId` | int | 便利贴编号 |
| `CharacterId` | int | 发言角色 ID |
| `Comment` | str | 便利贴文本内容 |

### 3.2 相片主表（Snapshot）

通过 `SnapshotId` + `Comment` 识别。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `SnapshotId` | int | 相片编号 |
| `Comment` | str | 相片主文案 |
| `SnapshotCharacterIds` | list[int] | 相片中出现角色 ID 列表 |
| `SnapshotRarityCode` | int | 稀有度编码 (1=N, 2=R, 3=SR) |
| `SnapshotSpecialFrameId` | int | 特殊相框 ID（>0 则为生日限定） |
| `StickyNoteId1` ~ `StickyNoteId4` | int | 关联的便利贴 ID |
| `SpinSetId` | int | 动作集 ID（→场景溯源链） |

### 3.3 场景溯源链

**动作集（SpinSet）**：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| `SpinSetId` | int | 动作集 ID |
| `SpinMotionIds` | list[int] | 包含的动作 ID 列表 |

**动作（SpinMotion）**：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| `SpinMotionId` | int | 动作 ID |
| `SpinCharacterMotionIds` | list[int] | 角色动作 ID 列表 |

**角色动作（SpinCharacterMotion）**：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| `SpinCharacterMotionId` | int | 角色动作 ID |
| `SpinCharacterMotionFileName` | str | 场景文件名（含路径，取最后一段解析场景） |

### 3.4 场景汉化对照

从 `SpinCharacterMotionFileName` 中提取文件名部分，对照以下规则翻译：

| 文件名关键词 | 区域 | 细化位置 |
|-------------|------|----------|
| `Bg001` | 太空赌场 | — |
| `Bg002` | 电玩城 | — |
| `Bg003` | 游乐园 | — |
| `Bg004` | 美式餐厅 | — |
| `2ndBD` | 二周年庆典 | — |
| `3rdBD` | 三周年庆典 | — |
| `Slot` | — | 老虎机 |
| `CardsTower` | — | 扑克塔 |
| `Roulette` | — | 轮盘赌 |
| `Sit` | — | 吧台休息 |
| `Crane` / `Magichand` | — | 抓娃娃机 |
| `Toy` / `Spring` | — | 摇摇车 |
| `Talk` | — | 双人聊天 |
| `BeltConveyor` / `CeilingRail` | — | 传送带 |
| `IceCream` | — | 冰淇淋车 |
| `AnimalCar` | — | 动物游览车 |
| `Panel` | — | 拍照打卡板 |
| `Viking` | — | 海盗船 |
| `FerrisWheel` | — | 摩天轮 |
| `RollerCoaster` | — | 过山车 |
| `CandyMachine` | — | 糖果机 |
| `Popcorn` | — | 爆米花机 |
| `Jukebox` | — | 点唱机 |

---

## 四、生日数据 (Birthday Domain)

### 4.1 角色基础信息

通过 `CharacterId` + `CharacterNameJpn` + `BirthMonth` 识别（限 ID 1~21）。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `CharacterId` | int | 角色 ID (1~21) |
| `CharacterNameJpn` | str | 角色日文全名 |
| `BirthMonth` | int | 生日月份 |
| `BirthDay` | int | 生日日期 |

### 4.2 生日台词

从具名表 `mst_character_birthday_mini_game_text` 读取。轮次由 `Year` 与角色生日相对周年边界共同决定；编号形态不能单独决定轮次。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `CharacterBirthdayTextNo` | int | 原始台词序号；第一轮多为偏移分段号，第二轮多为 1-5，第三轮为 1-3 |
| `KeyTargetValue` | int | 第一、二轮为 0；当前第三轮与 1-3 的台词顺序对应，作为格式审计证据保留 |
| `Text` | str | 台词原文 |
| `Year` | int | 台词对应年份 |
| `CharacterId` | int | 角色 ID |

详见 [`BIRTHDAY_CYCLES.md`](BIRTHDAY_CYCLES.md)。

---

## 五、酒保配方数据 (Bar/Recipes Domain)

### 5.1 角色映射（同卡牌域）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `CharacterId` | int | 角色 ID |
| `CharacterNameJpn` | str | 角色名 |

### 5.2 活动映射（Event）

通过 `EventId` + `EventTitle` 识别。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `EventId` | int | 活动 ID |
| `EventTitle` | str | 活动标题名 |

### 5.3 材料表（Ingredient）

通过 `IngredientId` + `IngredientName` 识别。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `IngredientId` | int | 材料 ID |
| `IngredientName` | str | 材料名称 |
| `IngredientDescription` | str | 材料描述 |
| `IngredientFileName` | str | 材料图标文件名 |

### 5.4 排班菜单（Shift Menu）

通过 `ShiftId` + `MenuSequenceNo` + `RecipeId` 识别。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `ShiftId` | int | 排班 ID |
| `MenuSequenceNo` | int | 菜单序号 |
| `RecipeId` | int | 配方 ID |

### 5.5 配方表（Recipe）

通过 `RecipeId` + `RecipeName` + `IngredientIds` 识别。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `RecipeId` | int | 配方 ID |
| `RecipeName` | str | 配方名称 |
| `RecipeMemo` | str | 配方描述/备注 |
| `EventId` | int | 关联活动 ID（0=无活动） |
| `RecommendCharacterId` | int | 推荐角色 ID（0=无） |
| `Price` | int | 售价（EN） |
| `RequiredSecond` | int | 制作耗时（秒） |
| `RecipeDifficulty` | int | 配方难度等级 |
| `IngredientIds` | list[int] | 所需材料 ID 列表 |
| `RecipeFileName` | str | 配方图标文件名 |

### 5.6 配方分级规则

| 条件 | 等级 |
|------|------|
| `RecipeId < 1000` | Tier 1（基础） |
| `1000 <= RecipeId < 10000` | Tier 2（中级） |
| `RecipeId >= 10000` | Tier 3（高级/活动限定） |

### 5.7 材料类型规则

| 条件 | 分类 |
|------|------|
| `IngredientId < 10000` | 常驻材料 |
| `IngredientId >= 10000` | 限定材料 |

---

## 六、隐藏任务 (Missions Domain)

### 6.1 任务主表（MissionMaster）

通过 `MissionId` + `Description` 识别。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `MissionId` | int | 任务 ID |
| `Description` | str | 任务描述模板（含 `#` 占位符） |
| `MissionType` | str | 任务行为类型 |

### 6.2 任务奖励/阶段表（SequenceReward）

通过 `MissionId` + `IsHidden` 识别。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `MissionId` | int | 任务 ID |
| `IsHidden` | bool/int | 是否为隐藏任务（`true` / `1`） |
| `IsActive` | bool/int | 是否已启用（过滤掉 `false` / `0`） |
| `MissionSequenceNo` | int | 任务阶段序号 |
| `Border` | int | 阶段目标阈值数值 |

> 描述中的 `#` 会被替换为 `Border` 的数值：
> `"ホームで皇坂逢を#回タップした！"` → `"ホームで皇坂逢を777回タップした！"`

---

## 七、道具图鉴 (Items Domain)

通过 `ItemId` + `ItemTypeCode` 识别。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `ItemId` | int | 道具 ID |
| `ItemName` | str | 道具名 |
| `ItemNameMultiLine` | str | 多行显示名（含换行符 `\n`） |
| `ItemTypeCode` | int | 道具类型编码（见下方映射表） |
| `ItemRarityCode` | int | 稀有度编码 (1=N, 2=R, 3=SR, 99=特殊) |
| `ItemAttributeCode` | int | 属性编码 (0=なし, 1=日, 2=月, 3=星) |
| `ItemDisplayTab` | int | 显示标签 (0=その他, 1=育成・強化, 2=交換・イベント) |
| `ItemFileName` | str | 图标文件名（无后缀） |
| `ItemDescription1` | str | 说明1（最详细版本） |
| `ItemDescription2` | str | 说明2（精简版本） |
| `ItemDescription3` | str | 说明3（更精简版本，或去掉了口号部分） |
| `IsActive` | bool | 是否有效（过滤掉已废弃的道具） |

### 7.1 道具类型编码映射

| 编码 | 说明 |
|------|------|
| 1 | クリスタル (有償) |
| 2 | クリスタル (無償) |
| 3 | ピース / 欠片 |
| 4 | メダル / 通貨 |
| 5 | アイテム変換券 |
| 6 | スタミナ回復 |
| 7 | アイテムセット |
| 8 | ガチャチケット |
| 9 | プレゼント |
| 10 | カード育成素材 |
| 11 | カードEXP素材 |
| 12 | スキル強化素材 |
| 13 | オートスキル素材 |
| 14 | SPスキル素材 |
| 15 | コンビ強化素材 |
| 16 | リビジョン素材 |
| 17 | トライベル素材 |
| 18 | ストーリーキー |
| 19 | ストーリーEXP |
| 20 | 限定交換素材 |
| 21 | イベント限定 |
| 99 | その他 |

---

## 八、通用工具数据

### 8.1 角色 ID → 角色名映射

| ID | 角色名 |
|----|--------|
| 1 | 皇坂逢 |
| 2 | 城瀬由鶴 |
| 3 | 須王芦佳 |
| 4 | 綾戸恋 |
| 5 | 宇京真央 |
| 6 | 樋宮明星 |
| 7 | 環野揺 |
| 8 | 槻本大河 |
| 9 | 壱川春日 |
| 10 | 隠岐谷誓 |
| 11 | 節見静 |
| 12 | 御門尊 |
| 13 | 新開戦 |
| 14 | 相沢篠信 |
| 15 | 在間樹帆 |
| 16 | 祠堂恭耶 |
| 17 | 立科吏来 |
| 18 | 恩田灯世 |
| 19 | 新名有 |
| 20 | 神家 |
| 21 | 麻波麗 |

### 8.2 稀有度编码映射

| 编码 | 稀有度 |
|------|--------|
| 1 | R |
| 2 | SR |
| 3 | SSR |
| 101 | XR |

### 8.3 属性编码映射

| 编码 | 属性 |
|------|------|
| 1 | 日 (Sun) |
| 2 | 月 (Moon) |
| 3 | 星 (Star) |

### 8.4 部门编码映射

| 编码 | 部门 |
|------|------|
| 1 | 本部 |
| 2 | 交際部 |
| 3 | 管理部 |
| 4 | 強行部 |
| 5 | 交渉部 |
| 6 | 特務部 |

### 8.5 碎片类型映射

| 编码 | 碎片名 |
|------|--------|
| 1 | サンピース（赤色） |
| 2 | サンピース（桃色） |
| 3 | ムーンピース（空色） |
| 4 | ムーンピース（青色） |
| 5 | スターピース（黄色） |
| 6 | スターピース（緑色） |

### 8.6 效果量级映射

| 编码 | 量级 |
|------|------|
| 1 | 小 |
| 2 | 中 |
| 3 | 大 |
| 4 | 特大 |
| 5 | 超特大 |

### 8.7 技能描述占位符

技能描述模板中的可替换标记：

| 占位符 | 说明 |
|--------|------|
| `skill_value1` ~ `skill_value6` | 通用数值 |
| `piece_value1` ~ `piece_value6` | 碎片类型 ID（→ 碎片名） |
| `strength_value1` ~ `strength_value6` | 效果量级 ID（→ 小/中/大） |
| `group_value1` ~ `group_value6` | 部门 ID（→ 部门名） |
| `character_value1` ~ `character_value6` | 角色 ID（→ 角色名） |
| `<sprite name=piece_N>` | Unity 精灵图标记 |
| `combopiece_1` / `combopiece_2` / `combopiece_3` | コンボピース / ダブル / トリプル |
| `hiramekipiece_*` | ひらめきピース |
| `text:{...}` | 包裹的模板前缀/后缀标记 |

### 8.8 文本清洗规则

| 原始内容 | 替换后 | 用途 |
|---------|--------|------|
| `\n` / `\\n` | `<br>` | 换行符统一为 HTML 换行 |
| `heroine_name` / `heroinename` | `衣都` | 女主名替换（大小写不敏感） |

### 8.9 获取方式推断规则

用于卡牌数据后处理：

| 条件 | 获取方式 |
|------|----------|
| `CardId <= 63` | 常驻 |
| 卡池名含 `バースデー` | 生日限定 |
| 卡池名含 `Anniversary` | 周年卡池 |
| 有卡池且非上两项 | 活动卡池 |
| 无卡池 + 稀有度 XR | 活动报酬 |
| 无卡池 + 非 XR (ID > 63) | 活动报酬 |

---

## 九、s2b 文件解析（独立输入）

以下功能**不依赖** `master_data.json`，而是直接解析独立的 `.s2b*` 文件。

### 9.1 .s2blyrics（歌词）

二进制格式：MsgPack + LZ4 (ext type 99)
提取结果：JSON + LRC 字幕

歌词数据结构（位于 `data[0][0]`）：
```
[
  [序号, 时间戳(秒), 歌词文本],
  [序号, 时间戳(秒), 歌词文本],
  ...
]
```

### 9.2 .s2bscript（游戏脚本）

二进制格式：MsgPack + LZ4 (ext type 99)
提取结果：JSON

脚本数据结构（4 层嵌套）：
```
[scene_array [command_array [id, next_ids, type, action, params]]]
```

关键指令类型：
- `Chat` — 对话，含 `chatTitle`（说话人）、`chat`（台词）、`voiceName`（音频 cue）、`emotion`（表情）
- `Image` — 背景切换，含 `time`（淡入时间）
- `Chara` — 角色显示/隐藏/移动，含 `time`
- `Other/Wait` — 等待，含 `time`
- `Other/All` — 场景切换，含 `time`

### 9.3 .s2bchart（OJT 谱面表）

二进制格式：MsgPack + LZ4 (ext type 99)
提取结果：JSON

---

## 附录：字段索引速查

按字母排序：

```
ArtistName
ArtistNameInformal
AudioFileName
AuraAdditionalValue
AuraInitialValue
AuraMaxValue
AutoSkillEffectId
AutoSkillLevel
BirthDay
BirthMonth
CardAttributeCode
CardRarityCode
CharacterBirthdayTextNo
CharacterCardFileName
CharacterCardIconFileName
CharacterCardId
CharacterCardName
CharacterCardStorySectionNo
CharacterId
CharacterNameJpn
CharismaAdditionalValue
CharismaInitialValue
CharismaMaxValue
CombiCharacterId
CombinationEffectId
CombinationLevel
Comment
CostItemCount1~6
CostumeIntroductionCharacterCardIds
Description
DisplayName
Duration
EventId
EventTitle
GachaName
IngredientDescription
IngredientFileName
IngredientId
IngredientIds
IngredientName
IsActive
IsHidden
IsActive (missions)
ItemAttributeCode
ItemDescription1~3
ItemDisplayTab
ItemFileName
ItemId
ItemId1~6
ItemName
ItemNameMultiLine
ItemRarityCode
ItemTypeCode
JacketFileName
LeaderSkillEffectId
LiveClipFileName
MenuSequenceNo
MissionId
MissionSequenceNo
MissionType
MusicId
PieceCount
PlayTime
PopupText
Price
RecipeDifficulty
RecipeFileName
RecipeId
RecipeMemo
RecipeName
RecommendCharacterId
ReleaseDateTime
RequiredSecond
RevisionRank
ShiftId
SkillCost
SkillDescription
SkillEffect
SkillEffectId
SkillName
SkillValue1~6
SnapshotCharacterIds
SnapshotId
SnapshotRarityCode
SnapshotSpecialFrameId
SpSkillCategoryCodeList
SpSkillEffectId
SpSkillLevel
SpSkillName
SpSkillWithCombiType
SpinCharacterMotionFileName
SpinCharacterMotionId
SpinMotionId
SpinMotionIds
SpinSetId
StickyNoteId
StickyNoteId1~4
Text
VisualAdditionalValue
VisualInitialValue
VisualMaxValue
Year
```
