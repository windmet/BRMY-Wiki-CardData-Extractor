# 年度生日档案首批（2026-09-09）

`python -m toolkit generate birthday_archive --masterdata <路径> --output <目录>`，可选带时区的 `--as-of`。独立输出 birthday_archive.xlsx / audit_output/birthday_archive.json，原 birthday 周期台词域未改动，GUI入口仍待整合。

以 CharacterId + Year 为复合键，关联登录页、Campaign页、小游戏及台词。登录奖励经 PresentId 展开；TapRewardNo1/2/3/SecretPin 经 DirectRewardGroupId 展开，不把数字当奖励对象ID。零组号不输出虚构奖励。页面资产与完整原表保留在审计，普通表包含年度概览、登录奖励、点击奖励、全年台词和日期说明。

真实快照回归：51年度记录、153登录阶段、168非零点击奖励组、237台词、51登录页、51Campaign页、9小游戏配置逐条匹配。登录和点击奖励的原始行逐组验证通过，无关系异常，42条奖励名称缺项以目标ID保留并告警。证据：`%TEMP%/brmy-annual-birthday-819b3_sg/verification.json`。

131项测试与仓库验证通过，合成测试覆盖跨年隔离、Present/Direct相同编号分离及孤立关系。此批未处理服装名称关联、播放器动作复原或账号解锁判断；未重建EXE。年度表不替换已有生日周期台词表或人工列。

后续服装关联：DisplayCostumes 页展示首日与生日后服装。51年度共102项，mst_character_birthday 与 campaign_page 的服装ID全部一致并匹配唯一 CostumeModel 记录；未标记成“可获得奖励”。缺目标、冲突、重复目标或缺名均保留诊断，不静默选择。重复页面和重复登录阶段也有诊断，重复阶段不重复计奖。

132项测试及仓库验证通过，原有年度记录逐项等值。真实证据：`%TEMP%/brmy-birthday-costume-s6o9ezcs/verification.json`。GUI入口及EXE仍未更新。
