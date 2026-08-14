# BMC 数据提取工具箱开发现状

> **文档状态说明（2026-08-08）**：本文主体是 2026-07-16 旧工作目录的历史快照，旧 EXE 哈希和菜单 1 至 12 只用于回溯，不能代表当前独立仓库发布状态。当前独立仓库源码已有 13 个 domain、21 项自动化测试，并新增 `home_voices` 的 2099 行/100 主体 ACB 拉表能力。主页语音 XLSX 当前只保留 `Wiki长表` 与 `完整度`，并使用 Excel 真实换行；技术审计输出到 JSON/Markdown。根目录已有通过真实输入验收的本地 QA EXE，但尚未发布 GitHub Release；当前构建哈希、环境警告和语音验收数字见 [`ACB_HOME_VOICE_EXTRACTION_PLAN.md`](ACB_HOME_VOICE_EXTRACTION_PLAN.md)。

> 最后核对：2026-07-16  
> 原工作目录：`<workspace>\tools\masterdata`  
> 用途：记录 Break My Case Wiki 数据提取项目当前已经完成的成果、验证结论、发布状态和后续工作，作为项目回溯入口。

## 1. 当前结论

项目已经从一组零散脚本重构为可独立分发的 Python/Nuitka 工具箱，能够处理三类数据：

1. `master_data.s2b`：解密为约 53 MB 的 `master_data.json`，再提取卡牌、音乐、Snap、生日、配方、任务、道具和活动档案。
2. 独立 S2B 文件：直接解析 `.s2blyrics`、`.s2bscript`、`.s2bchart`，不依赖 masterdata 流程。
3. CRI 音频目录：递归整理 ACB/AWB/ACF/头文件，提取语音文本并可关联卡牌表。

源码目前有 12 个可用 domain。根目录和 `toolkit` 目录各有一个免 Python 依赖运行的 `bmc_toolkit.exe`，已包含 `events`、`audio` 和卡牌语音关联，源码与发布 EXE 一致。

主页/卡面语音的台词来源也已经定位：台词不在 `MstHomeVoice` 明文字段中，而在 CRIWARE `.acb` 的 `CueTable.UserData`。当前通过 `CueNameTable.CueIndex` 精确关联 CueName 和 `title:{...}text:{...}`，已覆盖普通卡与 CR 双角色卡。

## 2. 版本与发布状态

| 组件 | 状态 | 说明 |
|---|---|---|
| `toolkit/` Python 源码 | 当前主版本 | 包含 8 个 masterdata domain、3 个独立 S2B parser 和 1 个 CRI 音频 domain |
| 根目录 `bmc_toolkit.exe` | 当前发布版 | 2026-07-16 卡牌管线修正版，26,253,824 字节；SHA-256 `FC16F86A...4D3CEE68` |
| `toolkit/bmc_toolkit.exe` | 与根目录 EXE 相同 | 同一构建产物的副本 |
| `scripts/` | 历史参考 | 最初的单功能脚本；保留用于核对算法，不再作为主要入口 |
| `artifacts/`、`outputs/` | 历史成果 | 包含早期 JSON/XLSX/CSV，不代表当前输出规范 |
| `json_output/`、`xlsx_output/` | 当前输出目录 | masterdata domain 的标准输出位置 |

当前 Git 历史：

- `57a8870`：初始工具箱仓库。
- `962b0a0`：完善活动档案映射。

## 3. 目录职责

```text
masterdata/
├─ bmc_toolkit.exe             当前对外入口，包含菜单 1 至 12
├─ master_data(1).s2b          masterdata 原始文件样本
├─ master_data.json            已解密主数据，约 53 MB
├─ toolkit/
│  ├─ run.py                   EXE/Python 统一入口
│  ├─ interactive.py           双击运行时的交互菜单与文件选择器
│  ├─ cli.py                   命令行入口
│  ├─ build.bat                Nuitka 构建脚本
│  ├─ core/                    通用扫描、导出、S2B 解析和映射
│  └─ domains/                 各数据域实现
├─ scripts/                    原始单功能脚本
├─ notes/                      项目文档与字段参考
├─ lyrics/                     S2B 歌词/脚本/谱面样本
├─ json_output/                当前 JSON 输出
├─ xlsx_output/                当前 XLSX 输出
├─ artifacts/                 早期集中成果与图标素材
├─ outputs/                    早期输出目录
└─ data/dump.cs                IL2CPP 类型与方法签名导出
```

原上级目录 `<workspace>` 还保存 APK、IL2CPP 文件、游戏缓存、语音 ACB、卡图与脚本等逆向材料。

## 4. 数据源与格式

### 4.1 master_data

当前 `master_data.json` 顶层共有 245 个元素：

- `data[0]` 是 244 张表的索引字典，结构为 `表名 -> [偏移, 长度]`。
- `data[1:]` 是与索引顺序对应的表数据列表。
- `cards.py`、`music.py`、`items.py` 和 `missions.py` 已使用 `TableCatalog` 按表名读取；`events.py` 仍使用自有具名表目录辅助函数，snap/birthday/recipes 仍保留早期特征字段扫描。

解密链：

```text
master_data.s2b
  -> MessagePack 解包
  -> 扩展类型 99
  -> 严格 LZ4 解码（未知扩展或损坏块立即停止）
  -> master_data.json
```

交互入口与 CLI 共用唯一解码器。`master_data.json` 只有在源 S2B SHA-256、解析器版本和输出 JSON SHA-256 都与 `.bmc_toolkit/master_data_cache.json` 匹配时才会复用。

`MasterDataSession` 在全选流程中只加载一次 JSON，并生成 `audit_output/run_manifest.json` 与 `schema_report.md`。schema 合约会在关键表或字段消失时阻断导出；新表、新字段、类型和行数变化会保留为告警，成功运行后更新本地 schema 基线。

### 4.2 独立 S2B 文件

`toolkit/core/s2b_parser.py` 负责公共解析：

- `.s2blyrics`：歌词数据，输出 JSON 和 LRC。
- `.s2bscript`：剧情/演出脚本，输出 JSON。
- `.s2bchart`：OJT/谱面布局，输出 JSON。

这三类文件不走 masterdata 选择流程，可以单独选择一个文件或一个目录处理。

### 4.3 IL2CPP 与 APK

已知材料：

- `data/dump.cs`：约 26 MB，包含 `MstHomeVoice`、`StaffDataVoiceInfo`、资源加载器等类型和方法签名。
- `libil2cpp.so`：上级目录 `files/lib/arm64-v8a/`。
- `global-metadata.dat`：上级目录 `files/il2cpp/Metadata/`。
- 三个 APK：基础包、arm64 配置包、UnityDataAssetPack。

APK 本体主要提供程序和初始资源；大量卡面语音属于运行时资源，不在 APK 内。项目已有可直接访问的 S3 资源来源，因此后续无需继续逆 CDN 地址。

### 4.4 CRIWARE ACB

`.acb` 同时包含 cue 表、音频数据或音频索引，以及可读的 UTF-8 元数据。BMC 的语音文本格式为：

```text
title:{主页语音标题}text:{台词正文}
```

文本中的换行写作字面量 `\n`。用于 Wiki 时统一转换为 `<br>`。

重复标题不能作为关联键。当前纯 Python `core/cri_utf.py` 读取 ACB `@UTF`，使用 `CueNameTable.CueIndex -> CueTable.UserData` 精确关联，不要求用户安装 vgmstream。

## 5. 工具箱架构

```text
run.py
├─ 无参数 -> interactive.py -> tkinter 选择文件/目录
└─ 有参数 -> cli.py
                 |
                 v
          domains/__init__.py
                 |
       +---------+----------+
       |                    |
 masterdata domains     独立 S2B domains
       |                    |
 master_data.json       指定文件或目录
       |                    |
 json_output/           输入旁 json_output/
 xlsx_output/           输入旁 xlsx_output/
```

公共模块：

- `core/scanner.py`：JSON 读写和递归 `walk()`。
- `core/tables.py`：masterdata 具名表目录与结构校验。
- `core/cri_utf.py`：CRI `@UTF` 表读取和 ACB Cue/UserData 关联。
- `core/exporter.py`：创建 `json_output/`、`xlsx_output/` 并统一写 XLSX。
- `core/data.py`：角色、稀有度、属性、部门、拼图块、文本清洗和场景翻译映射。
- `core/s2b_parser.py`：MessagePack/LZ4 S2B 通用解析。

## 6. 已实现功能矩阵

| 菜单 | Domain | 输入 | 主要输出 | 源码 | 当前 EXE |
|---|---|---|---|---|---|
| 1 | `cards` | masterdata + 可选 ACB 目录 | `All_Cards_Database.json`、`cards_data.xlsx` | 已完成，支持语音关联 | 已包含 |
| 2 | `music` | masterdata + 可选本地音频 | `Music_Database.json`、`music_data.xlsx` | 已完成 | 已包含 |
| 3 | `snap` | masterdata | `intermediate_snaps.json`、`Snap_Wiki_Data_Clean.xlsx` | 已完成 | 已包含 |
| 4 | `birthday` | masterdata | `birthday_extract.json`、`birthday_lines.xlsx` | 已完成 | 已包含 |
| 5 | `recipes` | masterdata | `bar_extract.json`、`bar_data_complete.xlsx` | 已完成 | 已包含 |
| 6 | `missions` | masterdata | `hidden_missions.xlsx` | 已完成 | 已包含 |
| 7 | `items` | masterdata | `items_catalog.xlsx` | 已完成 | 已包含 |
| 8 | `lyrics` | 文件或目录 | JSON + LRC | 已完成 | 已包含 |
| 9 | `scripts` | 文件或目录 | JSON | 已完成 | 已包含 |
| 10 | `charts` | 文件或目录 | JSON | 已完成 | 已包含 |
| 11 | `events` | masterdata | `Event_Archive.json`、`event_archive.xlsx` | 已完成 | 已包含 |
| 12 | `audio` | ACB/AWB 目录 | 音频清单、语音索引、卡面语音 XLSX | 已完成首版 | 已包含 |

### 6.1 卡牌数据

已提取：

- 卡牌 ID、角色、卡名、稀有度、属性、实装时间和资源文件名。
- Aura、Visual、Charisma 初始/最大值。
- 队长技能、SP 技能、自动技能、协作技能、突破加成。
- 各类技能升级和突破材料。
- 卡牌剧情章节信息。
- 活动、卡池、奖励组和交换所关系证据，以及带置信度的获取方式判定。
- `CardRarityCode=102` 的 CR 卡和多角色关系。
- 可选读取 `Musics` 目录，将卡面主页、技能和协作语音日文填入原表预留列；中文列保持为空。
- `Voice` 同时保留 masterdata 的 cue/解锁字段和 ACB 的标题、原文、`<br>` 文本及来源文件。

卡牌管线的完整表依赖、证据优先级、CR 与 ACB 细节见 [CARD_PIPELINE.md](CARD_PIPELINE.md)。

### 6.2 音乐数据

已提取曲目 ID、显示名、作者/歌手、音频文件名、封面文件名和时长。存在本地音频时可用 `mutagen` 补充实际时长。

已修复 MusicId 字符串排序导致的 `1, 10, 100, 2` 问题，统一按整数排序。

### 6.3 Snap/拍立得

已关联：

- Snapshot 主文案。
- 角色列表与稀有度。
- 最多四条便利贴评论。
- `SpinSet -> SpinMotion -> SpinCharacterMotion` 场景资源链。
- 基于资源文件名的场景中文映射。

原计划的“Snap Wiki 特殊排版”存在大量格式问题，已经明确放弃并从工具箱注册中移除。当前只保留结构稳定的清洗表 `Snap_Wiki_Data_Clean.xlsx`。

### 6.4 生日台词

按角色和年份提取生日台词，并生成适合横向核对的 XLSX。角色 ID 映射覆盖 1 至 21。

### 6.5 酒保配方

已关联活动、配方、材料、推荐角色、制作时间、价格、难度与排班菜单。输出包括完整 JSON 和多工作表 XLSX。

### 6.6 隐藏任务

从任务主表和阶段表关联隐藏任务，过滤未启用记录，并使用 `Border` 替换描述模板中的 `#`。

### 6.7 道具图鉴

最终输出固定为 8 列：

```text
道具ID | 道具名 | 类型 | 稀有度 | 属性 | 所属标签 | 图标文件名 | 说明
```

已确认并执行的清洗规则：

- 删除 `ItemNameMultiLine`，不再导出多行表示名。
- 删除说明 2 和说明 3，只保留信息最完整的 `ItemDescription1`。
- 图标文件名追加 `.png`。
- `\n` 和真实换行统一转换为 `<br>`。
- 过滤 `IsActive=false`。

### 6.8 活动总档案

`events.py` 已按真实表名读取并关联：

- 活动基本信息、类型、开放/后半/排名/结束时间。
- 活动扩展分支：A、B、C、累积道具、OJT。
- 关联角色、卡牌、PickUp 卡、活动道具和兑换所。
- 剧情梗概、章节、开放条件、有无语音和阅读奖励。
- 规则页、轮班、OJT 脚本、活动配方。
- 排名、营业额、累积奖励。
- Logo、弹窗、终端背景、剧情 Banner 等资源名。

XLSX 工作表：`Overview`、`Story`、`Rules`、`Shifts`、`RewardSummary`、`Mappings`。

奖励解析器目前覆盖道具、水晶/道具、卡牌、称号、Pin、主页语音商品和活动材料；未知类型仍保留原始类型码和目标 ID，避免静默丢数据。

### 6.9 歌词、剧情脚本和 OJT 表

交互模式不再要求先选择 masterdata：

- 可以选择包含同类文件的目录。
- 取消目录选择后可以改选单个文件。
- CLI 可以直接传入文件或目录。
- 未传路径时，模块仍可扫描当前目录，主要用于命令行兼容。

输出生成在输入文件所在目录或所选目录旁，不再固定写到 EXE 旁边。

## 7. 主页与卡面语音研究结论

### 7.1 masterdata 中的职责

相关表：

- `mst_home_voice`：`HomeVoiceTypeCode`、`HomeVoiceTargetId`、`HomeVoiceNo`、分类、解锁条件、时间段和 `VoiceCueName`。
- `mst_home_motion`：播放期间的 Live2D 动作、表情、害羞和眼睛状态；其中 `Body` 是动作资源名，不是台词正文。
- `mst_character_home_voice_limited`：角色限时语音开放时间。
- `mst_character_home_voice_season`：季节和服务年份。
- `mst_character_home_voice_duo`：双人语音和搭档播放延迟。
- `mst_home_voice_product`：语音商品显示名、说明、图标和实装时间。

`KeyTargetValue` 是解锁条件，不是文本 ID。

类型关系目前已验证：

- `HomeVoiceTypeCode=1`：角色通用/季节/生日等语音，`HomeVoiceTargetId` 通常为角色 ID。
- `HomeVoiceTypeCode=2`：卡面附带语音，`HomeVoiceTargetId` 为 `CharacterCardId`。
- `HomeVoiceTypeCode=3`：其他特殊目标，现有数据量很少，待继续分类。

### 7.2 dump.cs 证据

`StaffDataVoiceInfo` 的字段包括：

- `VoiceCueName`
- `VoiceSheetName`
- `IsUnlock`
- `IsPlaying`
- `IsVoice`
- `CardId`
- `KeyTargetValue`
- `Live2DMotionInfo`

它还有只读属性 `Serif` 和 `VoiceTitle`，但没有正文存储字段。这与正文来自已加载 ACB cue 元数据的结果一致。

### 7.3 ACB 实证：恩田灯世［what-if］

`voice_403.acb` 对应：

- `CharacterCardId=403`
- 角色：恩田灯世
- 卡名：`what-if`
- 包大小：267,712 字节

包内共有 6 条 `title/text` 元数据，其中 5 条正文非空：

| Cue | 标题 | 正文 |
|---|---|---|
| `card_vo_home_1` | ホームボイス① | これからも何かと関わる<br>ことにはなるだろう。<br>引き続きよろしく頼む |
| `card_vo_home_2` | ホームボイス② | この２年、与えられた仕事を<br>遂行するお前に俺も世話になった。<br>改めて、感謝する |
| `card_vo_home_3` | ホームボイス③ | お前と同じ仕事にあたる機会は多くは<br>ないが、活躍は十分把握している。<br>それだけ優秀ということだろう。<br>胸を張っていい |
| `card_vo_skill` | スキルボイス | これからも、よろしく頼む |
| `card_vo_skill_combi` | コンビボイス | 当然、そのつもりだ |
| `card_vo_gacha` | ガチャボイス | 空文本 |

因此卡面语音可覆盖主页、技能和协作语音。抽卡 cue 是否有文本必须逐包判断，不能因为 cue 存在就认为正文存在。

### 7.4 旧卡样本定位

截图中的槻本大河卡面已定位为 SSR「夜風にゆらめく」：

- `CharacterCardId=235`
- `HomeVoiceTypeCode=2`
- `HomeVoiceTargetId=235`
- `card_vo_home_1/2/3`
- 对应资源为 `voice_235.acb`

裸 S3 `Musics` 目录已经取得该文件，不需要通过 APK 还原 CDN。

### 7.5 已实现的 ACB domain

`toolkit/domains/audio.py` 已实现：

- 递归建立 ACB/AWB/ACF/头文件清单。
- 从所有 ACB 提取 `title/text` 元数据，保留原文并生成 `<br>` Wiki 文本。
- 单独生成 `Card_Voice_Index.json` 和 `card_voice_texts.xlsx`。
- 以固定标题类别映射卡面 cue，不按不同 UTF 表的裸出现顺序强行 `zip`。
- 读取前后校验文件大小和修改时间，标记下载过程中发生变化的文件。
- 排除自身生成的 `json_output/`、`xlsx_output/`，保证重复扫描结果不自我污染。
- `cards` 可直接接收同一音频目录并关联 `mst_home_voice`。

当前输出：

```text
Musics/
├─ json_output/
│  ├─ Audio_Inventory.json
│  ├─ Card_Voice_Index.json
│  └─ Voice_Text_Index.json
└─ xlsx_output/
   ├─ card_voice_texts.xlsx
   └─ voice_texts.xlsx
```

2026-07-16 实测：扫描期间目录仍在增长；一次完整运行记录 455 个卡面语音包、2,074 条卡面元数据、1,994 条非空卡面文本，以及所有类别合计 6,369 条非空文本。当前 masterdata 的 433 张卡成功关联 1,907 条非空语音文本。

尚未完成的是通用 ACB `@UTF` 关系解析和 `vgmstream` cue/时长批量索引。卡面语音可依靠稳定标题安全映射；剧情语音仍应读取真实 cue 表后再和脚本关联。

## 8. 输出位置规则

### masterdata domain

用户选择 `master_data.s2b` 后，工具会切换到该文件所在目录：

```text
所选目录/
├─ master_data.json
├─ json_output/
└─ xlsx_output/
```

如果同目录已有 `master_data.json`，交互解密会跳过重新生成。更新 masterdata 时应先确认旧 JSON 是否需要替换。

### audio domain

菜单 12 选择 `Musics` 目录后，输出生成在该目录的 `json_output/` 和 `xlsx_output/`。菜单 1 会额外提供一次可取消的音频目录选择；选中后填充卡表语音，取消则维持旧行为。

CLI：

```text
python -X utf8 toolkit\cli.py run audio <Musics目录>
python -X utf8 toolkit\cli.py run cards <Musics目录>
```

### 独立 S2B domain

- 选择单文件：在该文件父目录创建 `json_output/` 和需要的 `xlsx_output/`。
- 选择目录：在该目录内创建输出目录。
- 不再以 EXE 所在目录作为固定输出根目录。

## 9. 使用方式

### 9.1 面向 Wiki 组

双击 `bmc_toolkit.exe`，按菜单选择功能。masterdata 功能选择 `.s2b`；歌词、脚本和 OJT 表选择文件或目录。

注意：当前公开 EXE 尚无活动总档案，活动功能需要先重新构建发布包。

### 9.2 Python CLI

```powershell
python -X utf8 toolkit\run.py list
python -X utf8 toolkit\run.py run cards
python -X utf8 toolkit\run.py run events
python -X utf8 toolkit\run.py run lyrics "E:\path\to\lyrics"
python -X utf8 toolkit\run.py run scripts "E:\path\to\script.s2bscript"
python -X utf8 toolkit\run.py run charts "E:\path\to\charts"
python -X utf8 toolkit\run.py all
```

`decrypt` CLI 当前固定寻找当前目录下名为 `master_data.s2b` 的文件；交互模式可以选择任意 `.s2b` 路径。

## 10. EXE 构建

依赖见 `toolkit/requirements.txt`：

- `openpyxl`
- `msgpack`
- `lz4`
- `mutagen`
- `nuitka`（构建时）

标准命令：

```powershell
python -m nuitka --standalone --onefile --enable-plugin=tk-inter `
  --output-dir=dist --output-filename=bmc_toolkit.exe `
  --assume-yes-for-downloads run.py
```

必须启用 `tk-inter` 插件，否则文件选择窗口不可用。

### 10.1 中文路径问题

Nuitka/SCons 在当前中文路径下曾因 GBK/路径编码失败。已验证的构建方式是：

1. 将 `toolkit` 源码复制到纯 ASCII 临时目录，例如 `%TEMP%\bmc_toolkit_build`。
2. 在临时目录执行 Nuitka 命令。
3. 将生成的 EXE 复制回根目录和 `toolkit` 目录。

`build.bat` 目前仍直接在源码目录构建，因此中文路径问题仍可能复现。

### 10.2 图标

当前构建脚本没有传入自定义图标。已有 `.ico` 素材位于 `artifacts/`。Nuitka 可加入：

```text
--windows-icon-from-ico=路径\logo.ico
```

加入正式图标前应选择唯一图标源，避免 `logo.ico` 与其他实验图标混用。

## 11. 已完成验证

- `python -X utf8 toolkit\run.py list` 可加载全部 11 个源码 domain。
- 根目录 EXE 的 `list` 可正常运行和显示中文，但只列出 10 个旧 domain，不含 `events`。
- `.s2blyrics`、`.s2bscript`、`.s2bchart` 已分别用样本验证文件/目录输入。
- 独立 S2B 输出已验证生成在所选输入旁，而不是 EXE 旁。
- 道具图鉴已确认只导出 8 列，图标带 `.png`，说明换行使用 `<br>`。
- 活动档案已实际生成约 4.23 MB 的 `Event_Archive.json` 和约 210 KB 的 `event_archive.xlsx`。
- 433 张当前卡牌已关联 1977 条 ACB Cue 元数据（1907 条非空台词），全部为 `matched_by_acb_utf`；426/427 的四条主页语音和双角色技能语音均未覆盖。

## 12. 已知问题与技术债

按当前影响排序：

1. **发布版缺少显式版本号**：源码与 EXE 当前一致，但菜单尚未显示构建日期或版本号，后续仍可能发生发布物混淆。
2. **其他 ACB 域尚未做业务关联**：卡牌 Cue 已精确关联，剧情、季节、生日等仍需各自的 masterdata/脚本关系适配。
3. **构建脚本不完全适配中文路径**：建议让 `build.bat` 自动复制到 ASCII 临时目录构建。
4. **源码与旧 notes 有差异**：旧文档仍写“主页语音文本未找到”和旧菜单编号，应以本文为准，后续逐步修订旧文档。
5. **masterdata 解密存在两套实现**：`interactive.py` 与 `cli.py` 重复，应收敛到一个 core 模块，避免修复只落一处。
6. **domain 识表方式不统一**：`cards`、`events` 使用表名，其他早期模块使用字段特征扫描。
7. **输出目录依赖 `os.chdir()`**：交互流程可用，但共享模块的路径语义不够明确，未来适合改为显式传递工作目录。
8. **部分奖励对象尚未映射名称**：奖励枚举已按 `dump.cs` 修正，但主页背景、服装、音乐等类型仍需各自目标表补全名称。
9. **技能文本包含经验规则**：部分百分比替换和获取方式属于推断，Wiki 使用时应保留原始字段以便复核。
10. **自动化测试仍集中于卡牌链路**：当前 14 项覆盖具名表、获取方式、奖励枚举、CR 导出和 ACB 回退；其他 domain 仍以样本烟雾测试为主。

## 13. 推荐后续顺序

### P0：发布一致性

- 每次发布后验证根目录 EXE 的 1 至 12 菜单，以及卡牌可选语音目录流程。
- 将版本号或构建日期显示在菜单中，减少“哪个 EXE 更新”的混淆。

### P1：ACB 深层索引

- 使用 `vgmstream` 批量取得真实 cue 名、stream 数、时长、循环点和音乐变体。
- 解析剧情语音 cue 的角色/序号并与 `.s2bscript` 关联。
- 合并 Jukebox 标准曲长、S3 短版/预览/FV/INF 和 masterdata 曲名。

### P2：高价值 masterdata

- 通用奖励解析器继续补齐类型 4 至 7。
- 兑换所/商店商品。
- Puzzle 关卡、体力、掉落和成就。
- Gacha 卡池、成本、概率和保底组。
- 服装/模型图鉴。
- 剧情索引与外部 `.s2bscript` 文件关联。

### P3：工程化

- 合并重复解密代码。
- 显式工作目录参数，减少全局 `chdir()`。
- 建立小型固定样本和回归测试。
- 自动 ASCII 临时目录构建、复制和版本标记。

## 14. 交接检查清单

更新功能时至少完成以下事项：

- 更新 `domains/__init__.py` 注册。
- 更新 `interactive.py` 菜单、全选范围和输入类型。
- 更新 `cli.py list/all`。
- 用 Python 入口跑一次 `list` 和目标 domain。
- 用目标样本验证输出字段、编码和 `<br>`。
- 若面向 Wiki 组发布，重新构建 EXE 并用 EXE 再验证一次。
- 同步更新本文的版本矩阵、已知问题和验证记录。

## 15. 相关文档

- `reference_masterdata_fields.md`：现有脚本使用的 masterdata 字段手册。
- `reference_data_sources.md`：APK、IL2CPP、S3、故事脚本等数据源说明；其中主页语音结论已过时，以本文第 7 节为准。
- `reference_scripts_tools.md`：ASS 字幕转换、角色颜色和外部工具。
- `project_bmc_toolkit.md`：早期工具箱重构记录，目录和菜单信息已过时。
- `spin初步格式.md`：Spin/Snap 结构研究记录。
