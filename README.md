# BRMY Wiki CardData Extractor

面向《Break My Case》Wiki 编辑组的正式资源同步、Masterdata 解密、字段还原和表格导出工具。桌面产品名为 BRMY Wiki Toolkit，当前仓库目录与名称仍保留迁移前命名。

桌面入口：`python -m toolkit gui`；新构建的 EXE 双击默认打开 GUI。使用步骤及当前验收边界见 [GUI 说明](docs/GUI_GUIDE.md)。

新一轮数据审计的已核对问题、建设范围与验收顺序见 [下一阶段建设准备](docs/NEXT_STAGE_PLAN_20260909.md)。其中规划中的新域尚未实现。

需要指定输入与输出目录时，使用新的 [`generate` 入口](docs/GENERATE_OUTPUTS.md)：统一生成 `wiki_output`、`audit_output` 和本次产物清单，保留旧命令兼容。

维护者可使用 [`resources` 入口](docs/PRODUCTION_RESOURCES.md)读取正式服清单、按需下载原始资源并准备 masterdata；当前已支持缓存校验和显式离线模式。

需要自动取得任务资源并生成表格时，使用 [`sync` 入口](docs/SYNC_TASKS.md)，例如 `python -m toolkit sync cards events --cache E:\BRMYCache --output E:\WikiResults`。

这个仓库的首要目标是把 masterdata 中可复用的数据整理成能够直接用于 Wiki 建设的表格，而不是复刻游戏画面或运行时表现。

## 主要用途

- 解密并读取 `master_data.s2b` / `master_data.json`
- 还原卡面、技能、卡池、活动（按交换所·剧情、营业（摇酒）、Vignette、OJT 分档）、道具、音乐、生日和任务字段
- 导出 Wiki 可直接继续加工的 XLSX/JSON
- 解析独立的歌词、脚本和OJT Chart S2B 文件
- GROOVE 曲目、Bonus Runner、Runner 位次、Relation、SIDE 原始数据（`generate groove` / `sync groove`）；角色对照用 `HasStaffCard` 区分有 Staff Card 的角色
- 消消乐关卡目录（目标、生命、步数、盘面机关）与 GROOVE 谱面统计（`puzzle_stages` / `groove_charts`），见 [`docs/PUZZLE_STAGES.md`](docs/PUZZLE_STAGES.md)
- Spin 相片备忘录检索表（R/SR/SSR 三联去重、话题对照、评论检索；`spin_memos`），见 [`docs/SPIN_MEMOS.md`](docs/SPIN_MEMOS.md)
- 使用 ACB 元数据补充卡面语音字段；一条 Cue 含多段音频的卡（如三轮生日部门协作）另出[例外表](docs/CARD_COMBI_VOICES.md)，不写入卡牌全表
- 卡牌语音元数据存在跨卡复制、空文本等问题，同时输出[待核对清单](docs/CARD_VOICE_REVIEW.md)，卡牌表不自动改写
- 从 21 人角色 ACB 包提取主页、季节和生日语音，按 Wiki 主体生成长表与审计表
- 根据 masterdata 对 Spin/Snap 资源进行编号、角色、卡面、服装和活动归类

## Spin/Snap 边界

Masterdata 对 Spin/Snap 的职责是**归类、索引和统计**，例如回答某个资源属于哪个角色、卡面、活动或服装。

Wiki 的 Spin 相片终稿以游戏内实际截图为准。本工具不会把本地资源复刻结果当作 Wiki 图片验收基线，也不会依赖 Spine 工具才能完成常规拉表。

详细边界见 [`docs/SPIN_SNAP_BOUNDARY.md`](docs/SPIN_SNAP_BOUNDARY.md)。

## 使用与测试

普通使用推荐 GUI；正式服在线会按所选任务取得资源，正式服离线缓存只复用已校验缓存，本地模式使用指定文件且不联网。输出目录中的 `wiki_output` 保存普通表格，`audit_output` 保存诊断和本次产物清单。卡表更新需指定旧工作簿，以保留人工翻译与自定义列。

源码安装及新入口示例：

```powershell
python -m pip install -e .
python -m toolkit gui
python -m toolkit list
python -m toolkit doctor --json
python -m toolkit sync cards events --cache "E:\BRMYCache" --output "E:\WikiResults"
python -m toolkit sync birthday --offline --cache "E:\BRMYCache" --output "E:\WikiResults"
python -m toolkit generate birthday --masterdata "E:\path\to\master_data.json" --output "E:\WikiResults"
./scripts/verify.ps1
```

旧的 `run` / `all` / `update` / `decrypt` 命令和 `--interactive` 菜单已停用，对应写法如下（`--masterdata` 可直接给 `.s2b`）：

```powershell
python -m toolkit generate birthday --masterdata "E:\path\to\master_data.s2b" --output "E:\WikiResults"            # 自动选择最新生日轮次
python -m toolkit generate birthday --masterdata "E:\path\to\master_data.s2b" --output "E:\WikiResults" --cycle 1  # 也支持 --year 2026
python -m toolkit generate card_update --masterdata "E:\path\to\master_data.s2b" --audio "E:\path\to\Musics" --old-workbook "E:\path\to\old_cards_data.xlsx" --output "E:\WikiResults"
python -m toolkit generate home_voices --masterdata "E:\path\to\master_data.s2b" --audio "E:\path\to\Musics" --output "E:\WikiResults"
# 可选：--subject vo_home_13_126（单独导出一个主体）、--reference-acb "E:\path\to\old\Sound"（旧 ACB 恢复重复文本）、
#       --recent-year 2026-08-15（指定日期向前 365 天的双分表）
```

`.s2b` 解码结果缓存在输出目录的 `.bmc_toolkit/`，并按源文件哈希校验；替换新版 S2B 后会自动重新解码，损坏或未知格式会停止导出。

Masterdata 域在一次运行中共享同一个 `MasterDataSession`，不会为每个域重复解析大型 JSON。每次运行还会生成：

- `audit_output/run_manifest.json`：输入哈希、schema 状态、各域结果和耗时。
- `audit_output/schema_report.md`：新增/删除表、字段、类型和行数变化。
- `.bmc_toolkit/masterdata_schema.json`：上一次成功运行的本地 schema 基线。

首次运行因建立基线显示 `PASS_WITH_WARNINGS` 属正常情况；同一输入再次运行时该基线提示消失，但资源或业务缺项告警可能继续存在，不能据重复运行预期一定为 `PASS`。必需表或字段消失时会在导出前阻断。

涉及字段、关系或导出行为的改动还应按 [`docs/REAL_DATA_REGRESSION.md`](docs/REAL_DATA_REGRESSION.md) 使用固定真实输入执行改前/改后语义比较。

通用 XLSX 导出默认保留原始值类型，不会再把所有纯数字字符串猜成整数。需要数值转换的列必须显式声明列类型；真实回归同时比较单元格值、Excel 数据类型与数字格式。

对已有 Wiki 人工列的卡牌表，使用增量更新模式保留译名、中文语音列和自定义列，并单独生成变更表；详见 [`docs/CARD_UPDATE_MODE.md`](docs/CARD_UPDATE_MODE.md)。

生日庆典 masterdata 的三轮编号方式不同；轮次推导、原始编号保留和真实数据分布见 [`docs/BIRTHDAY_CYCLES.md`](docs/BIRTHDAY_CYCLES.md)。

主页语音通过 GUI / `sync` / `generate` 生成：

- `wiki_output/home_voice_catalog.xlsx`：仅含 `Wiki长表`，台词使用 Excel 单元格内真实换行。旧 `run home_voices` 仍使用 `xlsx_output`。
- `audit_output/Home_Voice_Catalog.json`：完整机器可读审计记录。
- `audit_output/home_voice_audit.md`：完整度、参考修复、待行动异常和非阻断信息。
- `home_voices --recent-year YYYY-MM-DD`：生成近 365 天主页/季节与生日祝福双分表，筛选规则见 [`docs/RECENT_HOME_VOICE_EXPORT.md`](docs/RECENT_HOME_VOICE_EXPORT.md)。

若目标 XLSX 正被 Excel 占用，工具会改存为 `home_voice_catalog_new.xlsx`，避免覆盖失败。

本地构建后的易用入口为 `dist/bmc_toolkit.exe`。EXE 属于忽略的发布产物，不提交进 Git 历史。受控构建固定 Python 3.12.9、Nuitka 4.1.2 及全部构建包，并生成 EXE、SHA-256、manifest 和 smoke report；详见 [`docs/RELEASE_BUILD.md`](docs/RELEASE_BUILD.md)。

`legacy/` 保存迁移前的单用途脚本，只用于核对旧行为。新功能进入 `toolkit/core` 或 `toolkit/domains`。

## 仓库迁移

本仓库由 v1 单脚本卡牌工具迁移为 v2 Masterdata 工具箱。迁移边界、历史保留和审计步骤见 [`docs/V2_MIGRATION.md`](docs/V2_MIGRATION.md)，实现阶段记录见 [`docs/MIGRATION_GUIDE.md`](docs/MIGRATION_GUIDE.md)。旧版源码和 Release 通过 `v1.0.0` 标签及 `legacy/v1-main` 分支保留。

当前优先开发的主页、季节和生日 ACB 语音拉表方案见 [`docs/ACB_HOME_VOICE_EXTRACTION_PLAN.md`](docs/ACB_HOME_VOICE_EXTRACTION_PLAN.md)。

## 数据与许可

仓库只保存源码、文档和人工构造的脱敏测试夹具，不提交游戏数据、音频、图片或批量导出结果。项目自身许可证尚待确定；加入 `LICENSE` 文件前不声明特定开源许可证。
