# Windows EXE 受控构建与发布

## 边界

`bmc_toolkit.exe` 是本地构建产物，通过正式发布门槛后才作为 GitHub Release 资产；构建成功不代表已发布。它不进入 Git 源码历史，`dist/` 和根目录 EXE 都受 `.gitignore` 排除。

受控构建固定了 Python、Nuitka 和 Python 包版本，并记录源提交与产物 SHA-256。它不声称不同 Windows/MSVC 机器生成的 EXE 二进制字节必然完全相同；每个产物必须以自身 manifest 和 SHA 为准。

## 固定环境

- Windows x64
- CPython `3.12.9`
- Nuitka `4.1.2`
- 精确 Python 包版本：[`requirements/release-build.txt`](../requirements/release-build.txt)

`pyproject.toml` 保留源码安装的兼容范围；`requirements/release-build.txt` 是 EXE 构建锁定文件，两者职责不同。旧 `toolkit/requirements.txt` 已删除，避免两份浮动运行依赖并行维护。

## 本地构建

双击或从 CMD 运行：

```bat
toolkit\build.bat
```

或显式运行：

```powershell
./scripts/build_release.ps1 `
  -PythonExe "C:\path\to\Python312\python.exe" `
  -InstallDependencies
```

构建器会：

1. 拒绝非 Python `3.12.9` 和非 Nuitka `4.1.2`。
2. 验证所有已安装包与锁定文件精确一致。
3. 使用 MSVC、Tkinter 插件和 onefile 模式构建。
4. 在空临时目录运行 EXE 烟雾测试。
5. 生成 SHA-256、构建 manifest 和烟雾报告。

## 产物

```text
dist/
  bmc_toolkit.exe
  bmc_toolkit.exe.sha256
  build_manifest.json
  smoke_report.json
```

`build_manifest.json` 至少包含：

- EXE 大小与 SHA-256
- Git commit 与 `git_dirty`
- Python/Nuitka 版本
- 全部锁定包的实际版本
- 烟雾状态

正式发布候选必须满足 `git_dirty=false` 和 `smoke_status=PASS`。

## EXE 烟雾范围

[`scripts/smoke_release.ps1`](../scripts/smoke_release.ps1) 不依赖游戏数据，检查：

- `doctor --json`：必须为 `PASS` 且 `frozen=true`。
- `gui --self-test`：构造隐藏 Tk 窗口，必须为 `PASS` 且范围为 `hidden-widget-construction`。
- `list`：必须包含 cards、home_voices 和 update cards。
- 严格 masterdata 解密：用脱敏的单表 ext99/LZ4 输入生成 JSON 与哈希缓存 manifest。

这些证明冻结程序可启动、核心包已包含、Tcl/Tk 和 GUI 组件可加载且 S2B 解密链可运行。它不代替可见 GUI 布局、真实交互或固定真实 masterdata/ACB 的业务回归。双击默认打开 GUI，CLI 命令继续从终端使用；构建采用 `--windows-console-mode=hide` 隐藏新建控制台。

## GitHub Actions

[`build-release.yml`](../.github/workflows/build-release.yml) 在以下情况构建 Windows x64 产物：

- Pull Request
- `main` 分支 push
- 手动 `workflow_dispatch`

Actions artifact 名为 `brmy-wiki-toolkit-windows-x64`。Artifact 只是审查/验收产物，不会自动创建 Release。

## 正式发布门槛

1. 源码测试与 build-release Actions 全绿。
2. 下载 CI artifact，检查 `git_commit`、`git_dirty=false`、SHA 和 smoke report。
3. 用固定真实 masterdata 及 ACB 执行 [`REAL_DATA_REGRESSION.md`](REAL_DATA_REGRESSION.md)。
4. 完成可见 GUI 的五项正式任务、本地文件选择与生成、打开本次文件、离线缺资源、取消重试和占用替代路径验收；逐项核对 [`AUDIT_RECONCILIATION_20260908.md`](AUDIT_RECONCILIATION_20260908.md) 的当前证据与未完成项。
5. 决定 LICENSE 和版本号，更新 Nuitka 文件/产品版本。
6. 为对应 tag 创建 GitHub Release，上传 EXE、SHA 和 manifest。

添加图标时，在选定唯一 `.ico` 源后给 Nuitka 增加 `--windows-icon-from-ico=<path>`，并重跑完整冻结烟雾。
