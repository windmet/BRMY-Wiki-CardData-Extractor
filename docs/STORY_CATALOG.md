# Story Catalog 首批（2026-09-09）

显式 generate 新增 story_catalog，使用 --masterdata、--output 和可选 --as-of。普通输出 story_catalog.xlsx，审计 story_catalog.json；现有 scripts 正文解析不变。

六类统一索引：主线142（普通82+跨类型60）、角色105、卡牌1087、活动566、登录19、剧情内Puzzle9，共1928。主键为来源表+该表复合编号，章节与节编号不跨父级覆盖。门槛原值、阅读奖励、语音标志、原始记录与父级均保留。仅读取原表声明的脚本名，不按编号拼造。

ReleaseDateTime按发布日期至无期限判断，登录使用实际Start/End；3001占位明确标识，不过滤记录。缺日期保留unknown，不等于已开放或账号解锁。

固定快照1928原始节记录逐条等值、复合键唯一，无父级或奖励缺项。证据：`%TEMP%/brmy-story-catalog-mngdn93i/verification.json`。135项测试与仓库验证通过。

N5尚未完成：跨类型主线的StoryTypeCode/Target目标解析、解锁条件关联、活动免费窗口与Puzzle反向目标尚需完善。当前父级记录保留这些原始字段，不能称为已解析。GUI/EXE未更新。

## 跨类型关系后续批次

60条其他剧情接入主线记录按StoryTypeCode4、StoryTargetChapterId及section号连接原活动节；9条Puzzle按StoryTypeCode1及base/chapter/section连接主线节。当前快照69条全部闭合。只实现这两种已核对关系，不把未知类型当成同编号主线/活动。跨类型主线不改变原活动节的身份或正文文件名。

6条解锁条件按明确condition ID连接；条件码和Value1–3保留原值，不声称已解释游戏解锁语义。63条活动剧情免费窗口按EventId连接并独立判断日期状态，不替代账号判断。对应新增CrossStoryLinks、CrossStoryUnlock与EventFreeWindows页。

1928原节记录除新增解锁条件外逐项等值，69目标存在、6条件与63窗口逐条核对通过。136项测试与仓库验证通过。证据：`%TEMP%/brmy-story-links-vmk1oa9p/verification.json`。GUI可见验收与EXE重建仍未执行。
