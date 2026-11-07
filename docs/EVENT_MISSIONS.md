# 事件任务阶段与奖励（2026-09-09）

活动档案新增 EventMissions 工作表，每行对应一个 MissionId + MissionSequenceNo 阶段，包含活动、阈值、替换 # 后的任务原文、起止时间、隐藏/OnlyAccounting 标志及完整奖励列表。不推断日常/累计标签含义；MissionDisplayTab、MissionType、Value1–3、原始说明和奖励组保留在审计。

仅 SpecialTabTypeCode=1 的活跃任务按 SpecialTabTargetId 关联唯一活跃 Event。type2 Campaign 及其他归属记录在 ExcludedOwners，不因 ID 相同混入事件。活跃阶段按序号排序，支持同组多条奖励；0 阈值保留。缺 Event、缺阶段、重复任务/阶段、缺奖励组与目标名称缺项均有定位信息。重复关系不任意覆盖或重复计奖。

`audit_output/event_mission_relations.json` 保存关系和异常；Event_Archive.json 的每个活动新增 Missions。奖励使用统一 RewardResolver，并保留 RawReward。现有隐藏任务域和活动其他工作表不变。

固定244表快照真实回归：859任务、52活动、1686阶段、1686奖励行逐条对照原表通过；54活动原字段全部等值；已有全部Excel页与53条隐藏任务逐单元格/记录等值。新增页1686行。80条奖励名称缺项，未发现缺组或缺目标；这些缺项保留类型和ID显示，并进入运行告警。

证据：`%TEMP%/brmy-event-missions-ki8pyejs/verification.json` 及同目录 before/after。125项测试与仓库验证通过，覆盖Campaign同ID隔离、排序、多奖励、0阈值、非活跃过滤及缺失/重复关系。

本批尚未增加按 as_of 推导的开放状态，也未重建 EXE；N2 的时间状态契约和后续 GUI 验收仍待完成。
