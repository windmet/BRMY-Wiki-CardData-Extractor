# OJT 主数据档案（2026-09-09）

显式 generate 入口新增 `ojt` 域，传入 `--masterdata`、`--output`，可选 `--as-of`。目前未接入 GUI 正式资源选择或旧交互菜单。

输出 `wiki_output/ojt_archive.xlsx`，包括 Charts、Shifts、Stages、TerminalTexts、TrainingRewards、PrizeBoxes、BoxRewards、Notes。坐标资源名仅来自 ChartFileName，当前不加载或猜测 .s2bchart 文件路径；坐标连接仍待真实样本验收。独立 charts 解析命令继续保留。

EventId → OjtShiftId 分层连接。固定池与随机池分别按自己的奖励组键展开，不因组号相同混用；股票数量、权重、Phase 和文本类型保留原值，不推断最终概率或尚未确认的枚举名称。RawTables 保留全部 OJT 表，包括未进入普通表的 BREAK bonus、常量、motion 和 dummy user 数据。

真实快照回归：3活动、12轮次、3题面、84关卡、48终端文本、36训练奖励、45奖箱；按箱展开3480条奖励引用。阶段、文本、训练及箱记录逐条与原表等值，固定/随机组逐箱核对通过。无关系异常，12条奖励名称缺项保留ID并告警。证据：`%TEMP%/brmy-ojt-regression-0d5k3ye8/verification.json`。

129项测试与仓库验证通过。本批是 N3 主数据首批实现，不代表完整 OJT 验收：坐标文件连接、BREAK/常量玩家侧投影、训练关卡更深关系和 GUI 集成仍待后续；年度生日档案尚未实施，EXE 未重建。
