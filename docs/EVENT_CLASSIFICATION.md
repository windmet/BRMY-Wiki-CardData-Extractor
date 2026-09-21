# 活动 family / subtype（2026-09-09）

玩家侧 ActivityType 使用 Classification 的 DisplayLabel。原 EventFormatName、EventFormatLabel 与 SourceSubtype 保留旧审计兼容；这些旧字段不再决定普通表的活动类型。

| Format | Family | Subtype 依据 |
| --- | --- | --- |
| 1 | 常规积分 | standard |
| 2 | 剧情 / Travel | mst_event_a.EventAType：2=Travel/Prequel，4=特殊，5=周年 |
| 3、4 | Making / 摇酒 | 3=常规，4=特殊版本 |
| 5 | OJT | ojt |
| 6 | Vignette / 累积道具 | vignette |

EventAType 2 本身不能区分 Prequel 与 Travelogue，仅当正式 EventTitle 有明确系列前缀时细分，并在 Basis 中记录标题依据。其他名称保留 Travel/Prequel 组合分类，不从道具 ID、日期或猜测的剧情关系细分。未知 Format / EventAType 保留原码与 unknown 状态，不丢活动记录。

固定 244 表快照真实回归：54 活动全部保留，family 数量 18/19/12/3/2；Prequel 和 Travelogue 各6，周年2，Format2特殊5，Making特殊1。JSON 仅新增 Classification 和更新 ActivityType；其他字段逐项等值。XLSX 全部工作表形状不变，仅 Overview 活动类型列54格变化。证据：`%TEMP%/brmy-event-family-5qtascle/verification.json`。

123 项测试与仓库验证通过。未重建 EXE。N2 活动任务序列/奖励、归属审计和开放状态仍待下一批实现；本记录不代表 N2 已全部完成。
