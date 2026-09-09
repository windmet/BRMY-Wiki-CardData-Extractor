# OJT 主数据档案（2026-09-09）

当前补充：已接入分组 GUI 和可选本地坐标输入，见下方“坐标连接验收”。下文首批描述为历史记录。

显式 generate 入口新增 `ojt` 域，传入 `--masterdata`、`--output`，可选 `--as-of`。目前未接入 GUI 正式资源选择或旧交互菜单。

输出 `wiki_output/ojt_archive.xlsx`，包括 Charts、Shifts、Stages、TerminalTexts、TrainingRewards、PrizeBoxes、BoxRewards、Notes。坐标资源名仅来自 ChartFileName，当前不加载或猜测 .s2bchart 文件路径；坐标连接仍待真实样本验收。独立 charts 解析命令继续保留。

EventId → OjtShiftId 分层连接。固定池与随机池分别按自己的奖励组键展开，不因组号相同混用；股票数量、权重、Phase 和文本类型保留原值，不推断最终概率或尚未确认的枚举名称。RawTables 保留全部 OJT 表，包括未进入普通表的 BREAK bonus、常量、motion 和 dummy user 数据。

真实快照回归：3活动、12轮次、3题面、84关卡、48终端文本、36训练奖励、45奖箱；按箱展开3480条奖励引用。阶段、文本、训练及箱记录逐条与原表等值，固定/随机组逐箱核对通过。无关系异常，12条奖励名称缺项保留ID并告警。证据：`%TEMP%/brmy-ojt-regression-0d5k3ye8/verification.json`。

129项测试与仓库验证通过。本批是 N3 主数据首批实现，不代表完整 OJT 验收：坐标文件连接、BREAK/常量玩家侧投影、训练关卡更深关系和 GUI 集成仍待后续；年度生日档案尚未实施，EXE 未重建。

## 后续：规则与训练阶段关系

新增 BreakBonus 的10档原值、GlobalRules 全局字段及 ChartStamp 转换奖励。后者通过 DirectRewardGroupId 解析为 ItemId3、数量5，不把组号当道具号。未确认的数值单位和计算公式仍不推断，全局字段名称按原名保留供整理核对。

84条 StageMaps 均按 PuzzleMapId 唯一闭合；36条训练奖励按 OjtShiftId + OjtPhase 找到对应关卡。不同轮次的同 Phase 不能互相补缺。地图及阶段原始关系进入审计，不扩展完整 Puzzle 系统。

真实回归前批全部事件数据与原有Excel页等值，新关系84/36项通过，10档BREAK与转换奖励验证通过。130项测试和仓库验证通过。证据：`%TEMP%/brmy-ojt-rules-_yc7w7j4/verification.json`。坐标文件连接、可见GUI验收和年度生日档案仍待完成。

## 坐标连接验收

`generate ojt --masterdata <文件> --source <s2bchart文件或目录> --output <目录>` 可补充坐标；目录递归寻找 `.s2bchart`，只按主表 `ChartFileName` 与文件 stem 精确匹配。GUI 使用本地资源模式，在“输入与高级设置”的“歌词 / 脚本 / OJT Chart”填入文件或目录。正式在线/离线模式本批不读取这一可选本地输入，也不猜坐标下载路径。

不提供 source 时主数据档案仍可生成。提供后，缺文件、同名文件、无主表匹配、非法角色/坐标及不支持的布局结构保留诊断。新增 Coordinates 页，保存角色、X/Y和排序原值；四轴继续在 Charts 页。Audit 保存原始布局、文件 SHA-256、匹配状态。坐标单位未确认。独立 charts 解析入口保留，GUI 将其归入活动组。

Event43 真实样本 `event43_chart_layout.s2bchart`（SHA-256 `4e5599e52b75309a758de17a7a1bf0fcaefb371f452710bc5e5b29b8e3c908b3`）的21角色坐标与排序逐条等值，Excel 数值核对通过。其他两期缺坐标文件，状态为 partial，receipt 为 PASS_WITH_WARNINGS；不宣称三期坐标齐全。原 Events、规则、奖励、RawTables 与既有工作表等值。

证据：`%TEMP%/brmy-ojt-coordinates-zsmgohxi/verification.json`。145项测试和仓库验证通过。本批未重建 EXE，也未进行可见 GUI 验收。
