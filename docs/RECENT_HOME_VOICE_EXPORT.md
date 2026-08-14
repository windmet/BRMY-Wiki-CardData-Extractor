# 近一年主页与生日祝福语音导出

## 使用方式

```powershell
python -m toolkit run home_voices "E:\path\to\Musics" "E:\path\to\master_data.json" --recent-year 2026-08-15
```

`--recent-year` 的参数是窗口结束日，工具向前取 365 天。上例窗口为 2025-08-15 至 2026-08-15，包含两个边界日。

输出：

- `xlsx_output/home_voice_recent_year_20250815_20260815.xlsx`
- `json_output/home_voice_recent_year_20250815_20260815_audit.json`

XLSX 只保留 Wiki 编辑需要的五列：主体、角色序号、角色名、日文台词、中文翻译。中文翻译列留空，台词换行使用 Excel 真换行。筛选依据仅保留在 JSON 审计文件。

## 两个分表

### 主页与季节语音

收录与窗口重叠或在窗口内发布的：

1. 节日、周年、期间限定主页语音。
2. 季节主页语音。
3. ACB 已有、masterdata 尚无行的新服务年度话题。
4. 新服务年度的“你的生日”语音。

当前固定数据得到 20 个主体、420 行。

### 生日祝福语音

只收录“某角色生日，其他全员祝福”，不与“你的生日”混在一起。

工具用 `mst_character.BirthMonth/BirthDay` 和服务年次计算每个主体的实际生日日期。因此 2025-08-15 至 2026-08-15 会同时包含：

- 第二轮中实际生日在 2025-08-15 以后的 15 名角色。
- 第三轮当前已出现的 5 名角色。

当前结果为 20 个主体、419 行。少 1 行是因为 `vo_home_10_83` 缺少角色 19 新名有的 ACB 文本，不是筛选删除。

## 数据怎么查

### 1. ACB 文本

扫描 `voice_<character>_general.acb` 和 `voice_<character>_[1-3].acb`：

1. 从 `CueNameTable` 取 `CueName` 和 `CueIndex`。
2. 按 `CueIndex` 连接 `CueTable.UserData`。
3. 从 `title:{...}text:{...}` 取语音主体和日文台词。

### 2. Masterdata 连接

基础连接键：

```text
(HomeVoiceTypeCode=1, HomeVoiceTargetId=发言角色ID, VoiceCueName=CueName)
```

主要表：

| 用途 | 表和字段 |
| --- | --- |
| 语音分类与年次 | `mst_home_voice.HomeVoiceCategory`, `HomeVoiceNo`, `KeyTargetValue` |
| 限定生效时间 | `mst_character_home_voice_limited.StartTime`, `EndTime` |
| 季节名与月份 | `mst_character_home_voice_season.SeasonId`, `ServiceYears` + `mst_season.SeasonName` |
| 角色生日 | `mst_character.BirthMonth`, `BirthDay` |
| 商品显示名 | `mst_home_voice_product.DisplayName`，只用作年次交叉验证 |

### 3. 近一年判定

- 限定语音：`StartTime/EndTime` 与日期窗口有重叠即收录。
- 季节语音：用 `SeasonName` 的月份范围与 `ServiceYears` 定位年份，再判断重叠。
- `HomeVoiceNo=109` 的 `ServiceYears=0`：不作为旧语音删除；它位于 2026 年 3~4 月与 7~8 月两组已知记录之间，按顺序定位为 2026 年 5~6 月。
- ACB-only 与“你的生日”：由 ACB 标题和服务年度开始日定位。
- 角色生日祝福：由服务年次和角色生日月日计算唯一日期。

不使用 `mst_home_voice_product.ReleaseDateTime` 作为原始发布日。该字段可因商店重上架统一刷新，会把旧的 `1st Anniv.` 误判为新语音。

## 当前边界

- 窗口内的常驻、时间问候若没有发布日、服务年次或限定时间证据，不会仅凭 `HomeVoiceNo` 较大就收录。
- 当前结果依赖本地 ACB 和 `master_data.json` 快照。资源更新后需重跑同一命令，不应手工继续追加旧表。
