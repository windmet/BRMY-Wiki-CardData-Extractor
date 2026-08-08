# BRMY Wiki CardData Extractor

面向《Break My Case》Wiki 编辑组的 Masterdata 解密、字段还原和表格导出工具。

这个仓库的首要目标是把 masterdata 中可复用的数据整理成能够直接用于 Wiki 建设的表格，而不是复刻游戏画面或运行时表现。

## 主要用途

- 解密并读取 `master_data.s2b` / `master_data.json`
- 还原卡面、技能、卡池、活动、道具、音乐、生日、配方和任务字段
- 导出 Wiki 可直接继续加工的 XLSX/JSON
- 解析独立的歌词、脚本和谱面 S2B 文件
- 使用 ACB 元数据补充卡面语音字段
- 从 21 人角色 ACB 包提取主页、季节和生日语音，按 Wiki 主体生成长表与审计表
- 根据 masterdata 对 Spin/Snap 资源进行编号、角色、卡面、服装和活动归类

## Spin/Snap 边界

Masterdata 对 Spin/Snap 的职责是**归类、索引和统计**，例如回答某个资源属于哪个角色、卡面、活动或服装。

Wiki 的 Spin 相片终稿以游戏内实际截图为准。本工具不会把本地资源复刻结果当作 Wiki 图片验收基线，也不会依赖 Spine 工具才能完成常规拉表。

详细边界见 [`docs/SPIN_SNAP_BOUNDARY.md`](docs/SPIN_SNAP_BOUNDARY.md)。

## 使用与测试

```powershell
python -m pip install -e .
python -m toolkit list
python -m toolkit run home_voices "E:\path\to\Musics" "E:\path\to\master_data.json"
# 可选第三参数：按 SubjectKey、CueName 或主体名另导出单个主体
python -m toolkit run home_voices "E:\path\to\Musics" "E:\path\to\master_data.json" --subject vo_home_13_126
# 可选：提供旧 ACB 目录，在当前元数据跨 Cue 重复时尝试恢复旧版正确文本
python -m toolkit run home_voices "E:\path\to\Musics" "E:\path\to\master_data.json" --reference-acb "E:\path\to\old\Sound"
./scripts/verify.ps1
```

主页语音默认生成：

- `xlsx_output/home_voice_catalog.xlsx`：仅含 `Wiki长表` 和 `完整度`，台词使用 Excel 单元格内真实换行。
- `json_output/Home_Voice_Catalog.json`：完整机器可读审计记录。
- `json_output/home_voice_audit.md`：完整度、参考修复、待行动异常和非阻断信息。

若目标 XLSX 正被 Excel 占用，工具会改存为 `home_voice_catalog_new.xlsx`，避免覆盖失败。

本地构建后的易用入口为仓库根目录 `bmc_toolkit.exe`。EXE 属于忽略的发布产物，不提交进 Git 历史；正式发布时应在固定 Python/Nuitka 环境重建并附 SHA-256。

`legacy/` 保存迁移前的单用途脚本，只用于核对旧行为。新功能进入 `toolkit/core` 或 `toolkit/domains`。

## 仓库迁移

现有 GitHub 仓库的升级步骤见 [`docs/MIGRATION_GUIDE.md`](docs/MIGRATION_GUIDE.md)。当前本地目录是隔离调试副本，尚未连接或修改远端仓库。

当前优先开发的主页、季节和生日 ACB 语音拉表方案见 [`docs/ACB_HOME_VOICE_EXTRACTION_PLAN.md`](docs/ACB_HOME_VOICE_EXTRACTION_PLAN.md)。

## 数据与许可

仓库只保存源码、文档和人工构造的脱敏测试夹具，不提交游戏数据、音频、图片或批量导出结果。项目自身开源许可证尚待确定。
