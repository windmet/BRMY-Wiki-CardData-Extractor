# V2 GitHub 迁移说明

## 迁移范围

远端 v1 是面向卡牌数据的单脚本工具。v2 将其升级为模块化 Masterdata/Wiki 工具箱，覆盖卡面关系、物品、音乐、任务、配方、独立 S2B 文件和 ACB 语音元数据。

本次迁移只发布源码、文档、CI 和脱敏测试夹具，不发布游戏数据、批量拉表结果、音频、图片、Spine 工程或本地 EXE。

## 历史保留

- 远端原 `main` 的最终状态保存在 `legacy/v1-main` 分支。
- 现有 `v1.0.0` 标签和 Release 保持不变。
- v2 从 `codex/migrate-masterdata-toolkit-v2` 分支提交 Draft PR，不直接推送或强制改写 `main`。
- 迁移分支通过双父提交连接 v1 与 v2 的独立 Git 历史；该提交保留 v2 文件树，同时让 v1 的全部提交继续可达。
- 审计通过后使用普通 merge commit 合并 Draft PR，不 squash，以保留两条历史的边界。

## 审计重点

1. 确认仓库不包含原始游戏数据、音频、图片、批量导出表或本机构建产物。
2. 检查卡面关系、CR 双角色、卡池排除和技能语音的回归夹具是否覆盖现有规则。
3. 检查 ACB 语音的主体归类、角色排序、Cue 重复恢复、真实换行和异常报告边界。
4. 确认独立 `.s2bscript`、`.s2blyrics`、`.s2bchart` 解析不依赖 Masterdata 流程。
5. 确认 Wiki XLSX 只保留编辑所需字段，技术索引和来源证据留在 JSON/Markdown。
6. 检查 CLI、交互入口、输出到输入文件对应目录和 Windows EXE 构建路径。
7. 将许可证选择作为独立决策；当前仓库没有 `LICENSE`，不得假定采用某种开源许可证。

## 合并门槛

```powershell
./scripts/verify.ps1
git diff --check
```

此外需要 GitHub Actions 通过、Draft PR 审计结论已处理，并确认 `main` 和 `legacy/v1-main` 的远端提交指针符合预期。正式 EXE Release 是后续独立工作，不是本次源码迁移的合并条件。

## 回滚

Draft PR 合并前，只需关闭 PR，远端 `main` 不受影响。合并后若需回退，应 revert 迁移 PR 的 merge commit；`legacy/v1-main` 和 `v1.0.0` 可用于核对旧版源码与发布资产，不需要重写 Git 历史。
