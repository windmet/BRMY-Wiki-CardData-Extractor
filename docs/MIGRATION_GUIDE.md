# Masterdata 工具迁移指南

## 目标

把现有 GitHub 项目 `windmet/BRMY-Wiki-CardData-Extractor` 升级为独立的 Masterdata/Wiki 拉表工具。Spine 资源复刻和桌宠开发不迁入这个仓库。

## 当前本地基线

- 本地调试目录：`E:\Web_build\BRMY-Wiki-CardData-Extractor`
- 自动化测试：20 项通过
- Python wheel：可构建
- CLI：`python -m toolkit list` 可运行
- 远端 GitHub：未修改

## 迁移顺序

### 1. 固定字段与输出契约

当前最高优先级是主页、季节、生日和期间限定 ACB 语音拉表。具体结构、连接键和输出方案见 [`ACB_HOME_VOICE_EXTRACTION_PLAN.md`](ACB_HOME_VOICE_EXTRACTION_PLAN.md)。Spin/Snap 分类表暂时后移。

优先为下列行为补脱敏夹具：

- 常驻、活动、兑换和卡池获取方式。
- CR 双角色和主/副技能语音。
- `voice_431/432` 等源元数据异常。
- 新活动机制出现新表或缺失旧表。
- Wiki 列顺序、空值、换行和文件名后缀。
- 主页语音 Cue、主体归类、21 人完整度和异常元数据。

这一阶段不改技能匹配算法，只把现有正确行为锁定。

### 2. 简化 Masterdata 流程

- `core`: 解密、装载、表索引、导出。
- `cards.py`: 卡面流程编排。
- `card_relations.py`: 卡池、活动、兑换和角色关系。
- `card_export.py`: Wiki 列和文本格式。
- `audio.py`: ACB/Cue 元数据。
- `home_voices.py`: 主页、季节、生日和限定语音的主体建模与 Wiki 导出。
- 新增独立的 Spin/Snap 分类域，不引入 Unity 或渲染依赖。

每次只移动一个职责，并保持所有回归测试通过。

### 3. 完成发布构建

- 固定 Python 3.12 和 Nuitka 版本。
- 增加 `--version`。
- 在 ASCII 临时目录构建 EXE。
- 对 EXE 执行 `list` 和脱敏输入烟雾测试。
- EXE 和 SHA-256 上传 GitHub Release，不提交到 Git 历史。

### 4. 升级现有 GitHub 仓库

推荐在新的发布工作区操作：

```powershell
cd E:\Web_build
git clone https://github.com/windmet/BRMY-Wiki-CardData-Extractor.git BRMY-Wiki-CardData-Extractor-publish
cd BRMY-Wiki-CardData-Extractor-publish
git switch -c migration/masterdata-toolkit
```

随后：

1. 为旧版本创建 `legacy/card-extractor-v1` 分支或标签。
2. 将旧根脚本移动到 `legacy/original-card-extractor/`。
3. 把本地调试副本覆盖到发布工作区，但不复制 `.git`、输入数据和输出产物。
4. 运行 `./scripts/verify.ps1`。
5. 通过普通分支和 PR 合并，不 force push。

## 日常验收

```powershell
./scripts/verify.ps1
git diff --check
```

正式发布前还必须确认源码许可证、README 免责声明和 Release 内不包含游戏数据。
