# 奖励引用解析

`toolkit/core/rewards.py` 是 Wiki 领域的奖励查询层，接收现有 TableCatalog，不访问网络、写输出或依赖 GUI。当前 events 的阅读奖励、排名 Present、Sales 与 Accumulate 奖励已接入；Card Serial/Present 来源及其他新域尚待后续接入。

## 契约

- `resolve(row)` 返回原有 RewardTypeCode / RewardType / RewardTypeLabel / RewardTargetId / RewardName / RewardCount，并增加 Resolution、RawReward 及目标表/键/记录证据。
- `direct(group_id)` 与 `present(present_id)` 按各自序号展开活动记录；相同数字的两个 group 不混用。0/None 表示无奖励；非零缺组记录 missing_reward_group。
- type1–10 的目标依次为 Card、Item、HomeBackground、CostumeModel、CostumeMini、Honor、Pin、Music、SpinAlbumReleaseItem、HomeVoiceProduct。type101 只查 Ingredient，绝不回退到同 ID 的 Item。
- type99/100/102 暂为 context_required：当前快照 type100 无样本，type102 两条基础掉落 TargetId=0，不能假定其为全局道具外键。类别标签沿用既有枚举，不把标签当作目标已解析的证据。
- 未知类型、缺表、缺目标、重复目标分别保留诊断；目标不活动仍可识别，但 TargetActive=false 不等于当前可获取。
- 已知对象没有可读名称时为 name_unavailable，显示类别和 ID。图标/标题画面文件名不会冒充称号或 Pin 名称；TargetRecord 保留资产字段供维护者核对。
- Card 可由消费域传入 card_names，保持其现有角色/稀有度等展示格式。奖励层不引入 Card→Story 彩蛋关联。

events 在 `audit_output/event_reward_resolution.json` 保存缺项，完整奖励记录也进入 Event Archive Audit。存在缺项时 generate receipt 为 PASS_WITH_WARNINGS；Wiki 表结构不新增工程列。

## 2026-09-09 验收

114 tests 与仓库 verify 通过，含类型 ID 碰撞、Honor/Title 混淆、type10 实际活动 XLSX、缺组、空名称、不活动对象、重复目标、多奖励顺序及未知/上下文类型。

固定 244 表快照 SHA-256 `221fd610386eb2041ff1aba1946220a8ba5fab09d48377ed693b28669fde585f` 改前/改后对照：

- 保留 54 个活动；递归比较所有非奖励字段相等，所有奖励 type/target/count 不变。
- 5988 次活动奖励引用中，5705 次有名称，283 次指向存在但缺名称的 Honor/Pin。不是 283 个对象缺失，也不声称 283 个独立对象。
- 301 个 RewardSummary 单元格有意更新：奖励名称引用变化包括 Pin 142 次、Honor 141 次、背景14次、Mini4次；卡牌和道具名称保持一致。所有非奖励列、工作表形状和值/类型/格式保持一致。
- 全量 direct + present 的7281条记录试解析：6127条有名称，1154条对象存在但无名称，未出现缺目标。该计数不证明所有其他奖励表或上下文类型均已解析。
- 本次6个登记产物逐一校验 SHA-256。本机证据 `%TEMP%/brmy-reward-regression-wwc5ol3_/verification.json`，同目录保留 before/after。真实数据不提交。

本批没有重建 EXE 或重复可见 GUI 验收。N1 的 Serial/Card acquisition、Music、Item22 与 OJT 命名仍待实施。
