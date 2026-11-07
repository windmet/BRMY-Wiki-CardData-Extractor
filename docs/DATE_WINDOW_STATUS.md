# 日期状态契约（2026-09-09）

事件生成使用同一个带时区 as_of，统一记录为 UTC。GUI/默认生成使用运行开始时刻；显式生成支持 `--as-of 2026-09-09T00:00:00+00:00`。不接受无时区核对参数。

事件使用 OpenStartTime（缺失时 StartTime）至 EndTime，不能把它解释成排名区间；任务各用自身 StartTime/EndTime。开始包含、结束不包含。日期状态不证明账号解锁或可领取；IsActive 单独保留，不参与日期判断。现有活跃记录筛选未改变，不再额外按日期删除历史、未来或占位记录。

- scheduled：尚未开始。
- within_window：日期区间内。
- expired：已到结束时刻。
- unreleased_placeholder：开始年 >=3000，或结束年3000–9998的占位值。
- unknown：缺边界、无时区、无效值或倒置/空区间。

结束年9999独立视为无期限，不能将缺失结束日期同样视为无限期。所有原始时间与判断依据保留，未来若确认不同占位约定须修订规则。

Overview 与 EventMissions 各追加日期状态列，TimeAssessment 页说明核对时刻、边界与含义。JSON 同时保存状态码与 TimeAssessment。旧字段、任务、奖励不变。

固定快照以2026-09-09 00:00 UTC回归：54活动保留（53 expired、1 within_window），859任务保留（855 expired、4 within_window）。除新增时间状态外原数据逐项等值。证据：`%TEMP%/brmy-time-regression-rzutocyx/verification.json`。边界测试覆盖时区换算、开始/结束相等、占位、无限期、缺失、无效、倒置区间及非活跃标志独立性。

本批不增加账号判断或日期过滤，不重建 EXE。后续 OJT/生日/Story/Collections 可复用此模块，但必须明确各自选用的时间字段。
