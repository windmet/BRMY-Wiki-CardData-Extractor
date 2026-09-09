# 下一阶段收口工作单

实施更新：A 的本地坐标链路已实现并通过 Event43 的21角色真实核对，见 [坐标连接验收](OJT_ARCHIVE.md#坐标连接验收)。另外两期坐标仍缺文件；B–D 的其余收口与可见验收继续进行。下表记录本工作单建立时的基线。

## 核对基线与材料边界

2026-09-09 复核分支 `codex/migrate-masterdata-toolkit-v2`，业务 HEAD `82b69d75f31728af849001aa7b02dcf6cca89dca`，开始核对时工作树干净。本文是建设准备和验收安排，不是完成声明。

输入为 `BRMY-Wiki-Toolkit-审计 (1).md` 网页聊天与 `BRMY_masterdata_244_table_final_audit (1).md` 全量盘点。聊天末尾收敛为七项业务范围，优先采用玩家纠正后的语义；附件中的历史行动指令不作为新的执行授权。旧下载脚本只作正式资源目录与解码参考，不直接移植全量下载循环、未知类别跳过策略或估算大小。

Wiki 继续在当前仓库建设。Spine 保持独立；正式源能力经 Wiki 验收后才评估 Spine 的适配，不移动旧目录或共享业务域。

## 当前状态

| 范围 | 当前证据 | 仍需完成 |
| --- | --- | --- |
| 正确性 N1 | 统一奖励解析、Serial/Present 六卡来源、Music left join、Item22 已提交；见各专项回归文档 | 冻结版本代表性输出验收 |
| 活动 N2 | family/subtype、Event Mission 和日期状态已接入 | GUI 生成核对；未知任务枚举继续保留原值 |
| OJT N3 | 3活动、12轮次及奖励/关卡关系已实现；代码仍返回 `ChartCoordinates: not_loaded` | 接入真实坐标文件，不能把独立 charts 解析当 OJT 档案已连接 |
| 年度生日 N3 | 51年度记录、153登录序列、168非零 tap 奖励、102服装引用已有回归 | 新入口与原生日台词入口的实际使用验收 |
| Voice N4 | 双人210对/420侧、限定与时段已实现；正式缓存13主体/49缺侧已逐cue复查 | 保留缺项；Type3/System Voice 的资源与文本仍须独立核对，不把角色分类当台词提取完成 |
| Story N5 | 六类1928节、69跨类型目标、6解锁条件、63免费窗口已有回归 | 实际导出阅读性；未解释条件不翻成账号解锁结论 |
| Collections N6 | 六类2536对象、5778 typed 奖励引用；已接事件/兑换/任务/序列码/生日/OJT入口 | 列明未覆盖来源及孤立关系；普通表入口可读性，不称完整获取攻略 |
| GUI N7 | 19任务分五组，有组级常驻说明；新五域正式缓存后台生成已有记录 | 以下 GUI 缺口与可见验收；源码接入不等于界面验收 |

上述计数来自仓库已有固定快照回归记录，本次没有重新联网获取数据。专项证据见 [原规划](NEXT_STAGE_PLAN_20260909.md)、[GUI](GUI_NEW_DOMAINS.md)、[OJT](OJT_ARCHIVE.md)、[Story](STORY_CATALOG.md)、[Collections](COLLECTIONS.md)、[正式语音缺项](HOME_VOICE_GAP_REVIEW.md)。

## 按顺序施工

### A. OJT 坐标连接

本地已找到 `E:/做了一半的字幕/bmc_unpack/scripts/Scripts/event43_chart_layout.s2bchart`，SHA-256 `4e5599e52b75309a758de17a7a1bf0fcaefb371f452710bc5e5b29b8e3c908b3`。已有严格解析证据显示 `IconLayouts` 含21角色的 `IconPosition` 与 `SiblingIndex`；文件 stem 与 Event43 的 `ChartFileName` 一致。单位尚未确认。

1. 为 OJT 增加可选本地 chart 输入，贯通 generate 与 GUI；未提供文件时仍可生成主数据档案，并明确坐标未加载。
2. 仅按明确 ChartFileName 匹配。重复文件、无匹配、损坏结构、非法角色或坐标均留诊断；不按事件编号猜别名，不构造线上 URL。
3. Wiki 展示题面四轴、角色与原始坐标；Audit 保留文件哈希、布局原值、关联依据与未确认单位。旧 charts CLI 兼容。
4. 用 Event43 逐角色对照21条坐标及排序；测试重名冲突、缺文件和坏结构，比较原 OJT 工作表不发生无意变化。

### B. GUI 引导与反馈

当前 `toolkit/gui.py` 已有分组，但检查按钮仍叫“检查所需资源”，可能下载 masterdata 的提示仅在高级页。计划完成信息只显示资源总数；告警仍混合进入详情。OJT Chart 仍放在“剧情与其他”。这些是源码可确认的未收口项。

1. 将在线预览可能同步基础数据的说明放到主操作附近；任务级说明支持键盘访问，区分本地正文/坐标、生日周期、年度生日和 ACB 祝福。
2. OJT Chart 归入活动语境；跨组选中状态、切换模式后的输入校验保持正确。
3. 资源总数、已校验缓存数、待取得数只有在 Resolver 提供明确证据时才展示；未知不能显示为零或从目录文件数推测。
4. 将业务缺项、未使用资源类别提示、运行失败分层展示；不删 receipt 原始告警，不把有缺项的产物统一暗示为完整。
5. 在默认与最小窗口、实际 Windows 缩放下检查布局；以鼠标和 Tab 键走完选择、预览、生成、取消、打开输出及失败反馈。

### C. 来源覆盖与输出契约

逐个已支持来源列出 owner 键、奖励命名空间与未适配范围。缺 owner、未知奖励类型及一物多来源都必须有可追踪状态。普通表给整理人员可读入口和翻译位置，技术证据保留 Audit；`no_known_entries` 不等于不可获取。

色彩 metadata、Type3/System Voice 仅在明确原始关系与真实资源证据下补入，未确认的枚举和语音场景不能用漂亮名称填补。不新增完整 Puzzle/Purchase/Campaign/Bremile/Login/Gacha/Quiz 域，不开展 Spine 复刻。

### D. 候选程序验收

本次复核已有独立干净构建：业务提交 `82b69d7`，Python 3.12.9、Nuitka 4.1.2；build manifest 的 `git_dirty=false`、`smoke_status=PASS`。本次实际重算 EXE 哈希与 manifest 一致：`ef99ee3c314f6e2dcf87e0b0cd165ad24e81be9d1e0dabc97ffb1df0ae8ba77b`，12,548,608 字节。

候选位于 `C:/Users/windm/AppData/Local/Temp/brmy-n7-build-3565ae8442694285945656fc7d232af2/dist/bmc_toolkit.exe`。构建与冒烟已通过，不代表五域冻结程序实数验收或可见 GUI 已通过，也不包含尚未实施的 A–C 变更。

后续从完成 A–C 的干净提交重建，记录 commit、依赖、EXE 哈希；冻结程序在独立输出目录运行正式离线缓存五个新任务，逐项核对 XLSX、Audit、receipt 状态与哈希，再验收真实窗口。旧程序和原输出保留，候选验收前不覆盖正在运行的版本。

## 批次退出条件

每批提交范围明确、相应关系测试和真实样例通过、普通表与 Audit 一致后提交。收口仍需同时满足：坐标真实连接、GUI 可见/键盘验收、来源覆盖边界、冻结版本实际生成。完成后转入 schema diff 和既有域适配；版本发布、合并及目录迁移另行处理。
