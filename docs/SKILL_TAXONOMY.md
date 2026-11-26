# 技能分类与索引域（`skills`）

`skills` 是纯 `masterdata` 驱动的独立导出任务，用于维护 Break My Case 的 SP 技能、自动技能与队长技能权威分类字典，**不修改既有 `cards_data.xlsx` 的任何列序或百分比文案**。

## 使用方式

- **GUI**：`生成资料` → `卡牌` 分组 → **「技能分类与索引」**（已纳入「版本更新全套」预设）。
- **CLI**：
  ```powershell
  python -m toolkit.cli sync skills --cache E:/BRMYCache --output <输出目录> --offline
  python -m toolkit.cli generate skills --masterdata <master_data.json或s2b> --output <输出目录>
  ```

## 输出产物（`wiki_output/skills_catalog.xlsx`）

1. **`SP技能分类`**：按官方 6 大类（`1 消除 / 2 转换 / 3 生成 / 4 恢复 / 5 机关 / 99 其他`）对照全部已使用的 `SpSkillEffectId`（含双重归属、客户端英文枚举 `SpSkillType`、主数据键 `SkillEffect`、基础与协作卡数）。
2. **`自动技能分类`**：完整收录全部已用 `AutoSkillEffectId`（含 `ASSIST` 等 15 类），附图标文件名与 Android 资源包路径（`Files/Android/<IconFileName>`）及持有卡编号。
3. **`卡牌技能标签索引`**：1 行 = 1 卡，将基础 SP 与协作追加 SP 分列，同时给出参数展开后的玩家侧标签（如全月/全星/定向转色/范围随机/候选值随机），并保留原表日文与公告 #223 旧版表记对照。
4. **`公告与漂移核对`**：当未来版本出现字典尚未收录的新 `SpSkillEffectId` / `AutoSkillEffectId` / `LeaderSkillEffectId` 时自动告警并写入 `待核对汇总.xlsx`，同时汇总 `mst_notice` 中涉及技能调整的公告。
5. **`客户端机制附注`**：与 `masterdata` 严格分层，单独记录客户端 `2.1.0` 反编译确认的硬编码机制（卡 214 `PandoraBox` 28 项加权池、`ShuffleW` 与 `ShuffleS` 的 `avoidMatch` 差异、公告 #223 SHOWER 五档新旧表记对照）。大版本更新时需人工复核。
