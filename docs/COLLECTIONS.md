# 收藏档案首批（2026-09-09）

显式 generate 新增 collections，使用 --masterdata、--output、可选 --as-of。导出六个种类页：服装465、Mini401、称号257、徽章774、主页背景70、道具569，共2536条。完整原记录及关系保存到audit_output/collections.json。

奖励反向索引按 RewardTypeCode + RewardTargetId，分别保留Direct、Present、OJT固定池与随机池全部引用，不把同ID跨类型匹配、不覆盖一物多组。真实5778条引用逐项对照原表通过。服装/Mini的CharacterCardId关联单独保留；没有把该关系直接标作获取奖励。

空称号、徽章名保留类别和ID，不以文件名代替。日期状态不代表已拥有。主记录与反向引用真实回归证据：`%TEMP%/brmy-collections-c7p_sbf0/verification.json`；137项测试与仓库验证通过。

N6未完成：最终获取入口尚未从奖励组反向连接到事件、任务、序列码等业务对象，AcquisitionEntryStatus明确为not_resolved。当前不是最终获取攻略；GUI/EXE也未更新。

后续入口首批：事件排名/营业/累计/配方/剧情、兑换所、任务（Event/Campaign分型）、序列码与角色年度生日已反向连接。1066对象具有known_entries，1470对象为no_known_entries；后者不等于不可获取。共13050入口引用，保留每个原始消费记录、owner证据及奖励行，不合并一物多来源。新增AcquisitionEntries页；原2536对象字段和5778奖励引用保持一致。

真实每个消费记录均存在原表且其明确奖励组键相等，来源异常0。证据：`%TEMP%/brmy-collection-sources-kp6b9e0z/verification.json`。138项测试和仓库验证通过。OJT、其他登录/剧情/成长等入口尚待补充，不能称完整获取攻略。
