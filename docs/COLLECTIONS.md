# 收藏档案首批（2026-09-09）

显式 generate 新增 collections，使用 --masterdata、--output、可选 --as-of。导出六个种类页：服装465、Mini401、称号257、徽章774、主页背景70、道具569，共2536条。完整原记录及关系保存到audit_output/collections.json。

奖励反向索引按 RewardTypeCode + RewardTargetId，分别保留Direct、Present、OJT固定池与随机池全部引用，不把同ID跨类型匹配、不覆盖一物多组。真实5778条引用逐项对照原表通过。服装/Mini的CharacterCardId关联单独保留；没有把该关系直接标作获取奖励。

空称号、徽章名保留类别和ID，不以文件名代替。日期状态不代表已拥有。主记录与反向引用真实回归证据：`%TEMP%/brmy-collections-c7p_sbf0/verification.json`；137项测试与仓库验证通过。

N6未完成：最终获取入口尚未从奖励组反向连接到事件、任务、序列码等业务对象，AcquisitionEntryStatus明确为not_resolved。当前不是最终获取攻略；GUI/EXE也未更新。

后续入口首批：事件排名/营业/累计/配方/剧情、兑换所、任务（Event/Campaign分型）、序列码与角色年度生日已反向连接。1066对象具有known_entries，1470对象为no_known_entries；后者不等于不可获取。共13050入口引用，保留每个原始消费记录、owner证据及奖励行，不合并一物多来源。新增AcquisitionEntries页；原2536对象字段和5778奖励引用保持一致。

真实每个消费记录均存在原表且其明确奖励组键相等，来源异常0。证据：`%TEMP%/brmy-collection-sources-kp6b9e0z/verification.json`。138项测试和仓库验证通过。OJT、其他登录/剧情/成长等入口尚待补充，不能称完整获取攻略。

OJT入口后续：奖励箱固定池948条、随机池2520条、训练36条收藏引用已沿OjtShiftId→EventId连接。池类型与组编号联合匹配，重复编号不串池；轮次与EventFormat5验证失败会进入来源告警。新3404条入口逐条复查owner链通过，旧入口等值，139项测试和仓库验证通过。证据：`%TEMP%/brmy-ojt-acquisition-txk26cva/verification.json`。其他未适配入口仍保留未知，不宣称已完整覆盖。

## 来源覆盖核对

兑换商品缺失/歧义 owner、任务档位缺失/歧义任务现在进入 SourceIssues；SpecialTabTypeCode 仅接受已验证的0/1/2，未知类型不再自动归为一般任务。

新增 SourceCoverage，仅盘点 active 行中可识别的奖励引用字段，明确 CompleteAcquisitionGuide=false。当前39字段中16已适配、23未适配；这是候选字段盘点，不是完整来源枚举，例如 Honor 的奖励字段可能描述获得称号后的奖励，不能反向当成取得该称号的入口。未来适配前仍需验证字段语义、owner及奖励目标。

每个收藏保留 UnresolvedRewardReferences，普通表增加已确认入口数与未连接入口的奖励引用数；入口类别提供可读名称，原 Kind/Owner/Raw 继续留 Audit。一物存在已知来源不意味着其他引用已全部解释。

真实快照2536对象及既有来源逐字段等值（本次固定 as_of 不同，日期评估另计），来源异常0；2823条奖励引用尚无已适配入口。证据：`%TEMP%/brmy-source-coverage-128oil22/verification.json`。153项测试与仓库验证通过。后续优先核对既有 Story 的阅读奖励和登录奖励链；Purchase/Puzzle 等独立产品范围保持不扩张。

## 剧情与登录来源

接入主线、角色和卡牌剧情阅读奖励，分别使用线程/章/节、角色/章/节、卡牌/节复合键并验证唯一父级。每日/特别登录使用配置ID与序列号，累计登录使用LoginBonusTotalId，玩家生日使用Year；Present与Direct奖励命名空间保持独立。缺失/重复键或父级进入来源诊断，不按编号或标题猜关联。原始门槛和日期保留在 Raw 与 OwnerEvidence，不能把入口存在解释为已解锁或已领取。

真实新增1637条收藏入口引用：主线80、角色105、卡牌1087、每日登录7、特别登录314、累计登录38、玩家生日6（3条配置包含多个收藏奖励）。逐条核对原表、奖励组、复合键及父级通过，旧入口等值，来源异常0。未连接入口的奖励引用从2823降为2462，仍不是完整获取攻略。

证据：`%TEMP%/brmy-story-login-sources-ipw0m45u/verification.json`。155项测试与仓库验证通过。不增加独立登录 GUI 域，本批未重建EXE。

## 角色与颜色 metadata

Spine 交叉核对补充：隔壁独立工程还保留相册便签专用的 `SPIN_STICKY_NOTE_COLORS`，不同于这里的 mst_color_code。例：角色2主数据色 `#7db247`，便签色 `#BED4A9`；Spine 分别导出 CharacterColor 与 StickyNoteColor，绘制便签优先后者。不能将“两套色号”解释为 ColorLocationType 的两个值，也不能据此覆盖 Wiki 主数据色。代码与测试已核对，原始游戏方法来源说明沿用 Spine 既有注释，本次没有重做反编译取证。

收藏Audit新增CharacterMetadata：保留25角色原始记录及27条颜色记录。ColorTargetType1按CharacterId关联，type2按CharacterGroupCode保留成员证据，两个目标命名空间不互相兜底；同目标不同ColorLocationType的记录分别保留。当前数据没有独立部门表，不生成不存在的部门名称。未知类型、缺目标或角色歧义保留状态。

颜色大小写和原值不改，ColorLocationType的用途仍未确认，不应用到GUI。角色Profile原值仅作审计材料，不当作已经核对的人物简介。

真实27条均关联到目标，既有2536收藏记录逐项等值。证据：`%TEMP%/brmy-character-metadata-pzxjgtge/audit_output/collections.json`。159项测试与仓库验证通过。
