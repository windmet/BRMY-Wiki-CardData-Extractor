# 网页审计核对记录（2026-08-14）

本文逐项核对网页对 Draft PR #1 的审计结论。状态分为“真实复现”“源码确认”“已修复并回归”和“待后续实现”，避免把静态推断当作运行事实。

## 本次已处理

| 项目 | 核对结果 | 处理与证据 |
| --- | --- | --- |
| 旧 `master_data.json` 被复用 | 真实复现 | 新增源 S2B SHA-256、解析器版本、输出 JSON SHA-256 清单。真实场景由旧 414 卡 JSON + 新 433 卡 S2B 自动重建为 433 卡；第二次才复用。 |
| Masterdata 解码逻辑分叉 | 源码确认 | CLI、交互入口和公共解析器收敛到严格 ext99/LZ4 解码；损坏块或未知扩展立即失败，不再尝试 zlib/LZMA 或返回原始字节继续导出。 |
| 稀疏 `SkillValue` 下标错位 | 源码确认，当前数据未触发 | Leader/Auto/Combination 改为保留原始编号。当前四类技能表中非连续参数行数为 0，因此固定快照导出未变化；脱敏测试覆盖 `SkillValue1=None, SkillValue2=5`。 |
| cards 的 audio 导入错误 | 真实复现 | 修复前在 433 卡 + 空 ACB 目录下报 `ModuleNotFoundError: domains`；改为包内相对导入后，源码、wheel 安装版和真实 ACB 路径均通过。 |
| `all` 域失败仍返回成功 | 本地回归时额外发现 | 修复为汇总失败并返回非零退出码；交互模式不再显示“全部处理完成”。 |

## 真实数据验收

固定输入是 2026-06-22 本地快照：244 张表、433 张卡，S2B SHA-256 为 `d4e1b1189fdae8d1400de0d760a66c589823ef88deb063c3c9e450a032fcf6e6`。

- 严格解码结果与既有 55.6 MB JSON 语义完全相等。
- 改前/改后全域导出：6 个 JSON 对象完全相等。
- 改前/改后全域导出：8 个 XLSX 的工作表、尺寸、合并区域、公式和全部单元格值相等。
- cards + 实际 Musics：455 个 ACB 包、1907 条非空文本、433 张卡；JSON/XLSX 与已接受成果完全相等。
- Card 431/432 均为两条主页语音和一条技能语音；技能文本仍是 `結婚、か`，说明它来自现有 ACB 元数据，不是本次代码回归。
- wheel 构建并安装到隔离目录后，cards + 空 ACB 路径完整运行成功。

可复用方法见 [`REAL_DATA_REGRESSION.md`](REAL_DATA_REGRESSION.md) 和 `scripts/compare_exports.py`。

## 其余审计项状态

| 审计项 | 当前结论 | 后续边界 |
| --- | --- | --- |
| 多数域仍靠字段特征识别 | 部分处理 | music/items/missions 已迁入 `TableCatalog` 并用字段撞名 decoy 测试；snap/birthday/recipes 待迁，events 仍需删除自有 `_tables/_group/_by_id`。 |
| `all` 重复加载 JSON | 已处理 | CLI/交互全选共享一个只读 `MasterDataSession`；真实全域运行以守卫确认 masterdata 只加载一次。 |
| 缺少 schema 漂移检测 | 已处理 | 已增加表/字段/类型/行数快照、稳定 schema fingerprint、关键字段阻断和本地前次成功基线比较。 |
| birthday 写死 cycle/年份 | 成立 | 从数据推导最新周期，并提供显式覆盖参数；先保留旧快照契约测试。 |
| Excel 数字字符串自动转 int | 成立 | 改为列 schema 决定类型，避免前导零标识符损坏。 |
| 缺少增量更新和人工列保留 | 成立 | 独立设计 Update/Diff Mode，不与解析核心重构混做。 |
| Nuitka 与依赖未固定 | 成立 | 固定构建依赖、CI 产出 EXE/SHA-256，并执行安装版/EXE 烟雾测试后再发布。 |
| 文档存在历史与当前混杂 | 成立 | 用户指南、当前架构、字段参考、历史调查分层整理。 |

## 下一批建议

本批后续已完成 schema fingerprint、运行清单与只读 `MasterDataSession`：真实 433 卡全选只加载一次 JSON，连续两次运行分别为基线初始化告警和 PASS，原有 Wiki 输出语义不变。music/items/missions 也已完成具名表迁移且真实输出等值。下一批应继续按单域处理 snap/birthday/recipes，再统一 events 公共 API；Update/Diff Mode 和 GUI 属于后续独立产品批次。
