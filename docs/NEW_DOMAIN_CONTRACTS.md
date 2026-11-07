# 新档案输入契约

generate 在各任务执行前检查五个新域的必需主体表与关系键，错误登记到该 domain 的 receipt。必需表缺失不再等同于空表；声明存在但没有记录的表仍可处理。活动记录逐行检查，不能用另一行具有该字段来掩盖某行缺键。非对象行报错，明确 IsActive=false 的历史行不参与必需字段检查。

契约覆盖 OJT 主体与关键子表、年度生日六表、双人主页的双方键、七张剧情节表及六类收藏主体表。具体字段以 `toolkit/core/domain_contracts.py` 为准。名称为空、未知奖励语义及外键不闭合继续由业务审计处理；本契约不是全量244表schema语义证明。

任务开始前失败不会生成该任务工作簿；其他任务仍继续，整次状态为FAIL。已有产物的保存保护保持不变。

真实244表快照对五契约全部通过。使用独立副本删除首条CostumeModelId后，收藏receipt为FAIL，错误指出表名和行号，无collections.xlsx输出。证据：`%TEMP%/brmy-contract-rejection-h5833z21/output/audit_output/output_receipt.json`。原输入未修改。

157项测试与仓库验证通过，包括缺表/空表区分、逐行字段检查、任务隔离。该变更晚于04b4397候选，旧候选未包含此门槛，最终EXE需更新后重新验收。
