# Masterdata 工具迁移指南

## 文档定位

本文记录从散落脚本到独立 Masterdata/Wiki 工具箱的实现过程。GitHub 仓库升级、旧历史保留和回滚方案以 [`V2_MIGRATION.md`](V2_MIGRATION.md) 为准。

Spine 资源复刻、游戏画面还原和桌宠开发不迁入本仓库。Masterdata 对 Spin/Snap 只负责字段归类、索引和统计；Wiki 最终图片仍以游戏内截图为准。

## 当前基线

- 自动化测试：以 `scripts/verify.ps1` 当前计数为准
- CLI：`python -m toolkit list` 可运行
- Python 包：可安装并构建 wheel
- 易用入口：本地可构建 `bmc_toolkit.exe`，但 EXE 不进入 Git 历史
- 数据边界：不提交游戏原始数据、音频、图片和批量导出结果

## 已完成的职责拆分

- `toolkit/core`：解密、装载、表索引、导出和公共格式化
- `toolkit/domains/cards.py`：卡面流程编排
- `toolkit/domains/card_relations.py`：卡池、活动、兑换和角色关系
- `toolkit/domains/card_export.py`：Wiki 列和文本格式
- `toolkit/domains/audio.py`：ACB/Cue 元数据
- `toolkit/domains/home_voices.py`：主页、季节、生日和限定语音主体建模与 Wiki 导出
- 独立 S2B 解析：歌词、脚本和OJT Chart不依赖 Masterdata 解密流程

新增或调整职责时，每次只移动一个边界，并保持回归测试通过。技能匹配等已有多层规则应先补夹具，再修改实现。

## 当前优先级

1. 稳定主页、季节、生日和期间限定 ACB 语音拉表。
2. 为常驻/活动/兑换/卡池、CR 双角色与多技能语音补脱敏夹具。
3. 处理 Cue 重复、源元数据异常和新活动机制中的缺表情况。
4. 保持 Wiki XLSX 简洁，把索引、来源和异常详情放入 JSON/Markdown 审计输出。
5. Spin/Snap 映射表延后到语音和卡面管线稳定之后。

## 日常验收

```powershell
./scripts/verify.ps1
git diff --check
```

受控 EXE 构建、脱敏 masterdata 烟雾、SHA/manifest 和 Actions artifact 已实现，见 [`RELEASE_BUILD.md`](RELEASE_BUILD.md)。EXE 和 SHA-256 应作为 GitHub Release 资产发布，不提交到源码历史；正式 Release 仍需要许可证、版本 tag 和真实数据终验。

项目许可证仍需单独决定；迁移 PR 不代替许可证选择。
