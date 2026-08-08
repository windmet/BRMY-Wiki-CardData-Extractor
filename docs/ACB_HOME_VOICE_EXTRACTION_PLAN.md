# ACB 主页、季节与生日语音拉表方案

## 1. 目标

为 Wiki 组生成以“语音主体”为单位、按角色序号排列的日文语音表。例如：

- 秋季主页语音：角色 1 至 21 各一行。
- 新开战生日全员祝福（3年目）：祝福者角色 1 至 21 各一行。
- 用户生日、周年、节日和期间限定语音：按同一主体整理全员文本。

该功能独立于卡面语音表，也暂不处理 Spin/Snap 分类。

## 当前实现状态（2026-08-08）

该方案已在独立调试仓库中实现：

- `audio.py` 已在通用索引中保留 CueName、CueIndex、CueId 和匹配状态。
- `home_voices.py` 已完成 21 人包识别、masterdata 连接、主体建模、完整度与异常检测。
- 已生成 `主体索引`、`Wiki长表`、`原始审计`、`异常` 四层工作簿。
- 可按 SubjectKey、CueName 或完整主体显示名单独导出一个主体。
- 真实本地资源回归为 2099 行、100 个主体、99 个完整主体、7 个 ACB-only 主体。
- 唯一缺失仍是 `vo_home_10_83` 的 CharacterId 19，未用空行掩盖。

源码与 CLI 已完成；独立仓库的发布 EXE 尚未构建和验收。

## 2. 本地资源盘点

扫描目录：`1/Musics`。

- 文件总数：1286
- ACB：959
- AWB：264
- `voice_<数字>.acb`：卡面语音包
- `voice_<角色>_general.acb`：角色通用主页、季节、双人、Puzzle 等语音
- `voice_<角色>_1.acb`：1 年目生日和期间限定语音
- `voice_<角色>_2.acb`：2 年目生日和期间限定语音
- `voice_<角色>_3.acb`：3 年目当前已实装或预装语音

21 名主角色都具备 `general/1/2/3` 四个包。`voice_rare_general.acb` 是额外角色包，不计入 21 人主体表。

排除 `vo_home_duo_*` 双人主页语音后，四组角色包共识别到：

- 100 个不同主页语音 Cue 主体
- 理论完整行数：100 × 21 = 2100
- 本地实际文本：2099 行
- 99 个主体覆盖完整 21 人
- 1 个主体只覆盖 20 人

唯一明确缺口：

```text
ACB: voice_nina_2.acb
CueName: vo_home_10_83
主体: 隠岐谷誓的生日祝福 [2年目]
缺少的发言角色: 新名有 / CharacterId 19
```

## 3. ACB 内部关系

当前 CRI 解析器已经能够读取：

```text
CueNameTable.CueIndex
    -> CueTable[CueIndex].UserData
    -> title:{...}text:{...}
```

每条记录可获得：

- ACB 文件名
- CueName
- CueIndex
- CueId
- UserData 标题
- UserData 日文文本

旧版 `_scan_all_text_metadata()` 在生成通用语音表时会丢弃 CueName、CueIndex 和 CueId。当前实现已经保留这些字段，`home_voices.py` 直接使用 Cue 关系建立主体表。

## 4. Masterdata 关系

### 核心表

`mst_home_voice` 提供主体关系，关键字段为：

```text
HomeVoiceTypeCode
HomeVoiceTargetId
HomeVoiceNo
HomeVoiceCategory
MotionCharacterId
VoiceCueName
```

针对角色主页语音：

```text
HomeVoiceTypeCode = 1
HomeVoiceTargetId = 发言角色 CharacterId
VoiceCueName = ACB CueName
```

推荐主连接键：

```text
(HomeVoiceTypeCode=1, HomeVoiceTargetId=发言角色ID, VoiceCueName)
```

不能只用 `HomeVoiceNo`，因为不同角色和语音类型可能复用编号。

### 补充表

- `mst_character`: 角色序号与角色名
- `mst_character_home_voice_limited`: 期间限定语音起止时间
- `mst_character_home_voice_season`: 季节、HomeVoiceNo、ServiceYears
- `mst_season`: SeasonId 对应月份范围
- `mst_home_voice_product`: 商品显示名、说明、图标和发布时间

当前数据中每名主角色有：

- `mst_home_voice`: 116 行，去重后 113 个 Cue
- `mst_character_home_voice_limited`: 29 行
- `mst_character_home_voice_season`: 8 行
- `mst_home_voice_product`: 57 行

### 已确认的 HomeVoiceCategory

| Category | 含义 |
| --- | --- |
| 2 | 用户生日 |
| 3 | 发言角色自己的生日 |
| 4 | 其他角色生日祝福 |
| 6 | 节日、周年、期间限定 |
| 7 | 季节主页语音 |
| 9 | 朝、昼、夕、夜、深夜问候 |
| 10 | 普通主页语音 |
| 11 | 双人主页语音 |

保留原始 Category 数值，中文名称属于导出层映射。

## 5. 为什么不能按 Title 直接分组

ACB 的文本元数据存在官方源错误和格式不一致：

- 同一 Cue 的标题有空格差异，例如 `4月1日 [1年目]`。
- `voice_ichikawa_general.acb` 多个季节标题发生错位。
- `voice_ayato_2.acb` 的 `vo_home_6_79` 被标成環野生日，并与下一条文本重复。
- `voice_arima_3.acb` 的 `vo_home_13_126` 被标成宇京生日，文本与 `vo_home_5_118` 完全重复。
- `vo_home_13_126` 在其他文件中还同时出现“新開”和“新開戦”两种标题。

因此：

1. CueName 是主体识别主键。
2. Masterdata 决定分类和 HomeVoiceNo。
3. 文件名决定发言角色。
4. TitleRaw 只作为原始证据保留。
5. SubjectDisplayName 由规则生成，不能直接照抄单个 ACB 标题。

## 6. 主体规范化

每条语音先转换为长表记录：

```text
SubjectKey
SubjectType
SubjectDisplayName
SubjectCharacterId
SpeakerCharacterId
SpeakerCharacterName
HomeVoiceNo
HomeVoiceCategory
SeasonId
ServiceYears
AcbFile
AcbBucket
CueName
CueIndex
CueId
TitleRaw
TextRaw
TextWiki
MasterdataMatchStatus
AuditFlags
```

### 生日主体

CueName 示例：

```text
vo_home_13_126
```

规则：

- 第一个数字 `13` 是生日对象 CharacterId。
- ACB 文件名对应发言角色。
- `_1/_2/_3` 包对应 1/2/3 年目批次。

稳定主体键：

```text
birthday:character=13:year=3
```

显示名由 `mst_character.CharacterNameJpn` 生成，不使用错误的单文件 Title：

```text
新開戦生日全员祝福 [3年目]
```

### 用户生日

CueName：`vo_home_user_29/73/113`。

主体键示例：

```text
user_birthday:year=3
```

### 季节语音

优先通过 `mst_character_home_voice_season` 和 `mst_season` 建立月份范围。

主体键必须包含 HomeVoiceNo，避免同一月份存在多代文本：

```text
season:5:home_voice_no=71
season:5:home_voice_no=111
```

Wiki 显示名可以使用“秋季主页语音”，但原始月份范围和 HomeVoiceNo 必须保留在审计数据中。

`ServiceYears` 暂不直接翻译成“第 N 年”，因为当前表中存在 `0/1/2/3` 混合值。需要结合发布日期进一步确认其业务含义。

### 期间限定语音

由 Category 6、HomeVoiceNo、限定起止时间和商品 DisplayName 共同确定主体。

稳定主体键示例：

```text
limited:home_voice_no=100
```

## 7. Masterdata 与 ACB 的覆盖关系

当前 Masterdata 能映射 93 个非双人主页语音主体。

ACB 中另外存在 7 个当前 Masterdata 未映射 Cue：

```text
vo_home_67
vo_home_68
vo_home_111
vo_home_112
vo_home_136
vo_home_5_118
vo_home_17_130
```

这些记录可能是历史遗留或预装的未来语音。应保留为 `acb_only`，不能静默丢弃，也不能在没有时间表证据时直接标记为已实装。

建议状态：

- `matched`: ACB 与 Masterdata 均存在
- `acb_only`: ACB 有文本，当前 Masterdata 无关系
- `master_only`: Masterdata 期望 Cue，但本地 ACB 缺失
- `metadata_conflict`: 标题或文本发生明显冲突
- `complete`: 同一主体覆盖 21 名角色
- `incomplete`: 主体缺少角色

这些状态放在审计表，不进入 Wiki 最终四列表。

## 8. 推荐输出

### 完整工作簿

`home_voice_catalog.xlsx`：

1. `主体索引`: 主体键、类型、显示名、人数、缺失角色
2. `Wiki长表`: 按主体、角色序号排序的可用文本
3. `原始审计`: ACB、Cue、Masterdata 连接和原始标题
4. `异常`: 缺失、重复文本、标题冲突和 ACB-only 记录

### Wiki 长表字段

```text
主体
角色序号
角色名
日文台词
中文翻译
```

技术字段不放入 Wiki 表。中文翻译列留空供 Wiki 组填写。

### 单主体导出

工具提供可选主体筛选：

```text
秋季主页语音（HomeVoiceNo 71）
新開戦生日全员祝福 [3年目]
勤劳感谢日 [2年目]
```

选择后生成只包含该主体、按 CharacterId 1~21 排序的小表。全量导出仍使用长表，避免默认生成上百个工作表或文件。

## 9. 实现模块

保留 `audio.py` 作为 CRI/ACB 底层扫描器，新增独立领域模块：

```text
toolkit/domains/home_voices.py
```

职责：

1. 识别 21 名角色的 ACB 文件名。
2. 保留完整 Cue 字段。
3. 读取 Masterdata 表并建立连接。
4. 生成 SubjectKey 和规范显示名。
5. 计算完整度和异常。
6. 输出完整工作簿和可选单主体表。

不把该逻辑放进 `cards.py`，卡面语音与主页语音是不同数据产品。

## 10. 实施记录

1. [已完成] 为 21 个 ACB 文件名建立显式 CharacterId 映射。
2. [已完成] 修改通用文本索引，保留 CueName/CueIndex/CueId。
3. [已完成] 新增脱敏 ACB/masterdata 连接与导出测试。
4. [已完成] 实现长表记录和完整度报告。
5. [已完成] 用当前本地目录跑全量审计，确认 2099 行和已知异常。
6. [已完成] 实现 Wiki 长表与单主体导出。
7. [已完成] 接入 CLI 和交互菜单；[待完成] 构建并验收独立仓库 EXE。

CLI 示例：

```powershell
python -m toolkit run home_voices "E:\path\to\Musics" "E:\path\to\master_data.json"
python -m toolkit run home_voices "E:\path\to\Musics" "E:\path\to\master_data.json" vo_home_13_126
```
