# 冻结候选验收

业务提交：`04b43970990218e6d8ac8f693948ebe63b59e16d`。独立 detached 工作树构建，manifest 的 git_dirty=false。Python 3.12.9 / Nuitka 4.1.2；固定环境155项测试通过，构建和发布冒烟均通过。

候选文件：`C:/Users/windm/AppData/Local/Temp/brmy-closeout-build-fc3a471b93b14a82a25a84a4ab2073c6/dist/bmc_toolkit.exe`

SHA-256：`210ee0281026ff54c633838a202c75c984217fa4e2a0150f75e618ce7876f405`。运行前重算哈希并与 build_manifest.json 核对。旧工作目录 dist 程序保持原样。

## 已执行

- 冻结 EXE 正式离线预览 OJT、年度生日、剧情目录、收藏、双人主页：85资源全部通过缓存校验。
- 同一 EXE 正式离线生成上述五任务：每域 PASS，整体 PASS_WITH_WARNINGS，13登记产物全部重新计算SHA-256并与receipt一致。
- 同一 EXE 本地 generate ojt 加入 Event43 的 s2bchart：21角色坐标导出，Excel与Audit逐项核对，缺少其他两期坐标仍保留partial。

证据：`%TEMP%/brmy-frozen-closeout-7okgtug7/verification.json`；该目录的 preview/five/coordinates 各保存运行结果与日志。验收脚本位于 `%TEMP%/brmy-frozen-closeout-verify.py`。

## 尚未执行

真实窗口布局、鼠标流程与键盘操作仍未通过验收。当前桌面工具能找到旧Wiki窗口，但截图为黑屏；重新定位后激活仍返回 `failed to activate captured window`，已停止界面输入。不能将隐藏组件测试、EXE冒烟或后台生成当作可见验收。

本候选未发布、未替换正在运行的旧EXE。来源覆盖仍有明确未适配项；整体建设目标保持未完成。
