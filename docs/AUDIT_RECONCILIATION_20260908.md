# 本地审计核对与后续修复规划（2026-09-08）

最初请求是阅读本地仓库、核对既有审计并制定后续规划。附件中的历史问答是审计材料。用户随后要求继续实施，R1 已完成，验收见下方；未迁移目录、合并产品或发布版本。

## 当前核对结论（优先于下方历史批次记录）

**GUI 补验已完成（用户协助选择文件后）：** 本地 masterdata 文件成功预填，来源自动切换为本地；可见 GUI 生成生日表，与正式源输出的 198 个单元格在值、类型、数字格式上等值，4 个登记产物 SHA-256 与大小校验通过。`打开选中文件` 实际启动 Microsoft Excel 并显示 `birthday_lines.xlsx`。保持 Excel 打开再次生成，GUI 显示 `birthday_lines_new.xlsx`，原文件哈希不变，替代工作簿内容等值且 4 个新登记产物校验通过。首次仅有 schema 基线告警，第二次为 PASS。

证据：`%TEMP%/brmy-visible-gui-acceptance/local-verification.json` 与 `excel-lock-verification.json`，receipt 分别为 `fb914eb9a5d547d897d9fde7ad4bfd0b`、`dc182f06e1784670a71ef3dc6628b6e9`。原生文件对话框由用户完成输入并确认，不能称为全自动文件选择验收；此前控制工具阻塞已由用户协助解除。下方“本地选择/打开结果/实际 Excel 尚未验收”为历史状态。

R4 当前候选的上述交互门槛已通过，EXE 仍对应干净代码提交 `bffff8a`，随后仅改文档，无需因文档更新重建。正式发布、许可证/版本决定、仓库迁移、staging 与 Spine 源优化仍属各自后续批次，不在本轮自动执行。

当前开发分支为 `codex/migrate-masterdata-toolkit-v2`，正式源提交截至 `56abc7a`；GUI 工程实现提交为 `bc863fc`。下方第 1/2 节保留首次审计快照，表中“未实现”不代表最新状态。

最新修复代码为 `bffff8a`，109 项测试通过。干净提交重建的 EXE 已完成 smoke 和默认布局复看；五项正式源可见任务、取消与离线恢复已有验收。本地文件选择完整流程、打开结果按钮仍未完成，不将这些项目计为通过。

| 范围 | 当前状态 | 下一步 |
| --- | --- | --- |
| 原审计 P0、Session、TableCatalog、schema、卡牌人工列更新 | 已有提交与回归测试 | 保持回归，不重复重构 |
| R1/R2：Wiki/Audit 投影、保存保护、显式输出及 receipt | 已完成提交 | 在 GUI 中核对实际文件与告警显示 |
| R3：正式清单、缓存、格式适配、任务 Resolver | 已完成提交 | 核对新增真实数据中的业务告警；staging 尚未实现 |
| R4：GUI | 工程实现已提交，冻结共享服务验收通过 | 完成可见窗口与冻结 EXE 验收后才能称为可分发 |
| R5：Spine 在线源 | 尚未实施 | Wiki GUI 正式源验收之后，单独确定资源范围与接入方案 |

本轮重新执行 `scripts/verify.ps1`，107 项测试通过，日志为 `%TEMP%/brmy-audit-current-verify.log`。这包含隐藏 Tk 窗口的组件测试，不能替代可见窗口布局、真实交互或冻结程序验收。GUI、入口和构建脚本已完成工程批次提交；可见窗口与正式发布验收仍未完成。

补查既有真实运行日志 `%TEMP%/brmy-full-card-sync.log`：默认卡牌任务已关联 471 个 ACB、2060 条非空语音文本，导出 471 卡，结果为 `PASS_WITH_WARNINGS`，有 6 条获取关系告警。因此下方 R3 批次当时的“尚未全量下载”已有后续证据补充；这些业务告警仍需逐条判定，不能宣称新快照完全正确。本轮未重新下载全量资源。

### 接下来按以下小批次推进

1. **GUI 收尾与错误恢复。** 现有工程实现已提交；继续验收正式服在线、显式离线和本地三种模式，检查资源计划、取消、失败后重试、本次产物清单和 Excel 占用替代路径。检查常用 Windows 缩放下底部操作区是否可见，不能只凭隐藏组件测试关闭布局问题。
2. **五项真实用户任务。** 分别执行卡牌、活动、主页语音、生日和旧卡表更新。每项记录输入/清单版本、实际输出、告警和人工列变化。针对 6 条卡牌获取关系告警及主页语音不完整主体，先区分来源内容缺失与解析缺陷，再作有证据的修复。
3. **冻结 EXE 验收与使用文档。** 构建后验证双击打开 GUI、CLI 兼容、Tcl/Tk 加载和至少一条完整正式源流程；补查离线、取消及保存失败。隐藏构造 smoke 只证明 Tk 能加载，不表示 GUI 工作流已验收。整理普通用户用法与维护者诊断入口，再提交可复核批次；不把构建成功等同正式发布。
4. **后续扩展。** staging discovery 与未知资源类别作为维护者功能单列，不混入普通正式结果；在线谱面路径没有证据前继续只支持本地。Wiki GUI 正式源验收之后再研究 Spine 的 bundle/场景资源需求，复用协议经验，保持独立依赖与发布。仓库改名/迁移另作批次，不覆盖两个未提交的暂存目录。

### R4 可见 GUI 验收进展

在用户明确恢复桌面验收后，用干净提交 `07efaef` 构建的 EXE（SHA-256 `68d0dd2e40e48da43ee0a1b822084269a09304f1ddf09372be0094ea9affe911`，`git_dirty=false`）执行可见操作：

- 默认打开 GUI；主页面、高级设置、最大化与恢复均可操作。四类正式任务的资源计划显示 556 个资源，实际生成卡牌、活动、主页语音和生日四个文件，13 个登记产物哈希通过复核。告警显示 53 条未知类别、6 条卡牌来源缺项、13 个主页语音不完整主体。
- 在界面填入中文路径的人工维护旧卡表，取消一次更新后重试成功。25,016 个单元格与已验收共享服务结果在值、类型、格式、样式、批注和链接上等值，原旧表不变。证据 `%TEMP%/brmy-visible-gui-acceptance/update-verification.json`。
- 改为离线模式并指定空缓存，任务明确失败，界面显示本次 0 文件且旧结果已清空；恢复有效缓存后离线重试成功。取消和缺缓存均有独立失败 receipt。
- 可见验收发现默认列表只露出约一行，以及离线错误直接展示系统异常。后续修订压缩上方留白，增加离线缺失的中文恢复说明，首次 schema 基线使用可读提示；109 项测试通过，修订后的布局仍需重建并复看。本地文件选择/导出、打开结果按钮和实际 Excel 占用仍需补充可见验收。

验收产物位于 `%TEMP%/brmy-visible-gui-acceptance`。这是内部工程与交互验收，尚未正式发布，Spine 与 staging 扩展仍分开处理。

### R4 最新冻结候选与占用验收

- 从干净提交 `bffff8a4f057e18ff3a9431f8e69d6b3cda3f6e8` 重建，`git_dirty=false`，Python 3.12.9 / Nuitka 4.1.2，smoke 为 PASS。`dist/bmc_toolkit.exe` 为 12,439,040 字节，SHA-256 `9f08fb473def82c34d2d4c238c0b7e51e5d1840f9af08dfba3778d4223da1028`。
- 最新 EXE 默认窗口在本机 150% 缩放下已复看，多行结果及底部操作按钮可见，修复前约一行结果的问题已解决；这不代表所有显示器和缩放组合均已验证。
- 使用真实 Windows 文件共享锁禁止写入已有 `cards_data_updated.xlsx`，通过可见 GUI 再次执行离线卡表更新。GUI 显示实际替代路径 `cards_data_updated_new.xlsx`，原文件哈希不变，7 个登记产物校验通过。证据 `%TEMP%/brmy-visible-gui-acceptance/lock-verification.json`，receipt `36a8125269b44e96a1cc7b5c5725ecf9`。锁已释放；这是操作系统文件占用验收，不是实际 Excel 进程验收。
- 本地“添加并识别文件”已弹出原生选择对话框，但桌面工具对子窗口的输入焦点、截图及元素缓存返回不一致，重置控制会话后仍无可用状态，因此停止该项自动操作。没有完成本地文件选择/生成，也没有验证打开结果按钮；不能据此判定产品文件选择器存在缺陷。
- 下一批先补齐上述两项交互与本地生成，再整理正式分发文档。Spine 正式源、staging、未知类别与目录迁移保持独立后续范围，不因 Wiki 主流程通过而自动启动。

### 人工维护卡表验收补充

真实人工格式验收发现并修复旧表样式迁移缺陷：原实现直接复制跨工作簿 `_style` 索引，生成流程成功但访问自定义字体/填充时出现 `IndexError`。现改为逐项注册样式组件，并通过公开 hyperlink setter 更新重排后的链接归属。新增保存后重读的样式与行移动回归，全部 108 项测试通过。

使用正式 471 卡表独立副本，在首部、中部、末部添加中文、换行、自定义列、公式、字体、填充、批注、超链接，再由 GUI 的共享服务以正式离线缓存更新。27 个人工/自定义非空单元格的内容、类型、样式、批注和链接全部保留；特意改旧的一项自动字段被更新，差异计数为新增 0、修改 1、移除 0，原工作簿 SHA-256 不变。本机证据 `%TEMP%/brmy-manual-acceptance-81dhmr6x/verification.json`。这是共享服务验收，可见 GUI 操作仍待验收。

### GUI 工程与首轮冻结验收

GUI 用法已写入 `GUI_GUIDE.md`，包括三种来源、旧卡表更新、取消、实际产物和告警处理。冻结 smoke 新增隐藏 GUI 构造检查；可见布局与真实点击验收仍未完成。

本轮使用 Python 3.12.9 / Nuitka 4.1.2 构建 EXE，冻结 smoke 通过（doctor、隐藏 GUI 构造、list、合成 S2B 解密）。EXE SHA-256 为 `c925229430fd543ae79ea427c9a126ab43e93bc38ac25a62b10b8ba4272be219`，12,436,992 字节。构建时工作树有修改，manifest 的 `git_dirty=true`，因此仅作为工程验收产物，正式候选需从干净提交重建。

该 EXE 随后通过 CLI 使用既有正式缓存，完成 cards/events/birthday/home_voices/card_update 五项真实任务，均为 `PASS_WITH_WARNINGS`；29 个登记产物逐个复核 SHA-256，所有 XLSX 可以重新读取。结果包含 471 卡、54 个活动、2387 行主页语音；用本轮卡表再次更新的 Added/Modified/Removed 工作表均只有表头。它验证冻结程序的共享服务与真实输出，不替代 GUI 点击或人工列修改场景。证据在本机 `%TEMP%/brmy-frozen-gui-workflows-6f259dc0107142148115b365ad007f8c/verification.json`，构建报告在 `dist/`；不提交游戏数据与二进制。

6 条卡牌告警已定位到卡牌 451–456（`BREAK MY PHASE`）。当前快照的六张卡均为 `CardRouteCode=2`、`CardRarityCode=101`，各有 direct reward 记录，但当前关联结果没有活动、卡池或交换所来源。进一步扫描当前具名表中直接的 CardId/Reward 标量引用，排除卡牌属性表后没有找到额外来源引用。这只限定了当前快照和直接引用范围，不能证明不存在间接关联或游戏内领取途径；保留告警，暂不凭日期或名称硬编码活动来源。

## 1. 施工基线与两套系统边界（首次核对快照）

| 本地目录 | 本次实查 | 后续用途 |
| --- | --- | --- |
| `E:/Web_build/BRMY-Wiki-CardData-Extractor` | 分支 `codex/migrate-masterdata-toolkit-v2`，HEAD `5594e5c`；开始核对时工作树干净；有完整提交历史与 origin | 当前 Wiki 数据工具的开发基线；沿用此处修复，名称调整另做迁移批次 |
| `E:/Web_build/BRMY-Wiki-Toolkit` | `main` 尚无提交，文件全部未跟踪；README 明确称复制出的重构暂存区 | 不是最新 Wiki 实现，不在这里重复修复；保留原目录 |
| `E:/Web_build/BRMY-Spine-Toolkit` | `main` 尚无提交，文件全部未跟踪；独立 Python/浏览器工具 | 独立维护；Wiki GUI 和正式源接通并验收后再优化其源 |

比较源码发现，暂存区 masterdata 副本缺少 `core/masterdata.py`、`core/session.py`、`domains/card_update.py`、`domains/home_voices.py` 等后续实现，不能拿它继续施工。Spine 独立目录与暂存区中检查的 41 个代码/配置文件哈希一致；这不是全部目录或游戏资源完全一致的声明。

Wiki 负责数据解析、Wiki 表格和人工列维护；Spine 负责 Unity/Spine 提取、场景重建和预览。共享资源目录协议可以后续讨论，不能让 Wiki 安装依赖 UnityPy、Node 或 Spine Runtime，也不让 Spine 依赖 Wiki GUI。

本次只核对本地 Git 状态，未刷新远端，不能据附件宣称当前 PR 仍是 Draft 或 GitHub 尚未发布。

## 2. 审计状态核对（首次核对快照）

| 项目 | 当前状态 | 本地证据 / 限定 |
| --- | --- | --- |
| 旧 JSON 缓存复用 | 已修复 | `core/masterdata.py` 校验源 SHA-256、parser version、输出 SHA-256；提交 `63b77cd` |
| Masterdata decoder 分叉 | 已修复 | CLI/交互接公共严格解码器；独立 S2B 文件格式仍有自己的入口，不应把所有格式强行当 masterdata |
| 稀疏 SkillValue 错位、audio 导入 | 已修复 | `domains/cards.py` 保存参数原编号，使用 `.audio` 相对导入；有回归测试 |
| 全选重复读取 | 已修复 | `MasterDataSession`，提交 `d4fe18f`；CLI/交互复用 |
| 具名表迁移 | 已完成当前域迁移 | `TableCatalog`，提交 `b472fcb`、`5d4465d`、`ab8c0cb` |
| Schema 漂移与运行清单 | 已有 | `core/session.py`；不等于未来所有官方变更都已覆盖 |
| 生日轮次、Excel 类型 | 已修复原审计问题 | `6490aba`、`7303a83`；生日空白祝福占位是另一个未处理问题 |
| 人工列保留与差异表 | 卡牌已实现 | `domains/card_update.py`、`9e98e2e`；不能宣称其他域均支持 |
| 构建固定与冻结程序 smoke | 构建配置已实现 | `requirements/release-build.txt`、`b117ce8`、`74bf653`；本次未重新构建 EXE |
| 主页语音产品化 | 部分完成 | 日文/中文 Wiki 投影、年次审计、近 365 天双分表已有；默认 `export_home_voice_catalog()` 仍带完整度页，单主体表只有 Wiki 页 |
| Wiki/Audit 全域切分 | 未完成 | `events` 仍带来源码、Mappings；`missions` 带原始描述；`audio` 带 Cue/稳定性等技术列；`snap` 带折叠重复数 |
| 生日空白祝福 | 未清理 | `birthday.py` 仍为 21 人追加空白祝福 J/C 行；不是已有 ACB 文本 |
| 统一输出与保存 | 未完成 | 公共路径仍是 `json_output/xlsx_output`；`events.py`、`recipes.py` 直接 `wb.save()`，绕过占用保护 |
| 正式服 Provider / Resolver | 未实现 | 当前 Wiki `toolkit/` 未找到对应实现 |
| 完整 GUI | 未实现 | 现有交互为控制台菜单配合 tkinter 文件选择框 |
| Spine 在线源 | 未实现本轮设想 | `s3_import.py` 是本地已下载文件的 LZMA 导入，不能等同于在线 List/下载 Provider |

验证：本次执行 `python -m unittest discover -s tests -p 'test_*.py'`，75 项通过。日志在本机 `%TEMP%/brmy-audit-tests-20260908.log`。历史 433 卡、455 ACB 等实数见 `REAL_DATA_REGRESSION.md`，本次没有重跑真实输入，不作为今天的实测结果。

## 3. 修正附件中不宜直接照搬的建议

- 清理工程字段不等于删除所有 ID、资源名、规则页或轮班信息。保留卡牌契约；其他域按 Wiki 实际用途划定列，稳定维护键和有用的图片文件名可以保留。
- `missions` 目前只有 XLSX 输出。先把原始描述、行为码和关联键保存到 Audit，再从 Wiki 表移除，否则会丢掉诊断证据。
- 正式资源清单里出现某资源，只能证明被正式清单收录，不能单独证明活动已开放或内容已实装。Catalog 收录状态与 masterdata 开放时间应分开记录。
- 用户随后提供了组内 `Break_My_Case.py`，已核对入口与类别映射，详见下方补充。其依赖的 Codec/Network 实现未随附，具体解压参数仍需实证，不能从函数名猜测。
- 普通 GUI 可以隐藏源配置细节；客户端直接访问上游时，不能承诺地址保密。Provider 配置与 parser 分离即可，不因此引入代理服务。

## 4. 后续批次与验收

### R1：清理 Wiki 输出契约，先形成一批可验收成果

首个代码批次建议限定 `missions`、`birthday`、`snap` 和公共保存入口：

1. missions 新增完整审计 JSON；Wiki 表保留任务 ID、阶段、目标值、可读任务内容，原始模板与行为码进审计。
2. birthday 删除无数据的角色祝福空行，保留庆典台词、翻译位置、轮次和日期；祝福文本继续由 ACB/home_voices 管线负责。
3. snap 折叠计数留在审计，Wiki 表移除该列，稳定标识及场景信息保留。
4. events/recipes 接公共安全保存，完成页使用实际生成路径。

验收：新增输出契约测试；检查生成的 XLSX 表头、值和中文输入位置；Audit 保留被移出的信息；Excel 被占用能返回实际替代路径；cards 与人工列更新行为不变。真实输入前后比较只允许已列明的投影差异，不应要求改后整本工作簿与旧版完全相同。

### R2：完成其余域投影和输出路径收口

整理 events、audio、home_voices 的普通输出；Mappings、技术码、Cue 和完整度移入维护者审计。保留活动规则、奖励和轮班中确有 Wiki 用途的信息。卡牌原有列顺序及 update 契约保持兼容。

引入明确的输出上下文与实际产物列表，逐步替换隐式当前目录和全局路径；普通输出统一到 `wiki_output`，诊断到 `audit_output`。为现有 CLI 路径保留兼容方式，避免一次目录重命名破坏旧脚本。独立 scripts/charts/lyrics 属于技术 JSON/LRC 产物，不能假装全部都能投影为 Excel。

验收：输出到显式目录，不污染输入和缓存目录；不同任务产物可追踪；失败不会展示旧文件为本次成功结果；非修改域的语义回归通过。

### R3：正式服资源接入与任务解析，先 CLI 验证

组内 downloader 脚本已取得，清单入口、索引和类别路径已有源码依据。接下来以官方清单样本验证实际封装及记录结构，确认 Codec 参数和资源外层压缩。此项不阻塞 R1/R2。

建立小型 `ResourceDescriptor / Provider / Catalog / Resolver`：LocalProvider 与 ProdManifestProvider 产出相同资源描述；Provider 找资源、下载原字节，格式解码交给对应 parser。先打通 cards 所需 masterdata 与可选卡牌 ACB，再扩展主页语音和独立 S2B。

Catalog 保存来源、逻辑路径、原始元数据、清单版本和清单收录状态；缓存保存本地 SHA-256，临时下载验证后原子替换。ETag 是更新线索，不当成内容 SHA-256。显式处理超时、错误响应、路径越界、取消、残缺下载与离线旧缓存提示。

验收：合成清单/下载测试通过后，再小规模验证真实正式清单、一个 masterdata 和必要 ACB；二次运行缓存命中，失败不污染成功缓存。禁止用“接口类已有”代替真实源接通。

staging discovery 放在正式源之后作为维护者扩展，不阻塞普通 GUI。与正式资源分开记录，不自动混入普通 Wiki 结果；缺失可选 ACB 要提示文本不完整，不能表示完整成功。

### R4：Wiki GUI

正式源 CLI 链路验收后，GUI 复用同一 Resolver：检查资源更新 → 选择 Wiki 输出 → 同步并生成 → 打开本次文件；高级入口保留本地文件、离线和旧卡表更新。区分清单资源增量与实际卡牌/活动数据增量。

先评估轻量桌面 GUI 与现有 Nuitka 构建的兼容性，不将附件建议的 tkinter、EXE 大小作为已确定约束。后台任务、取消、错误原因、部分结果、Excel 占用和输出路径必须有明确反馈；不得在线程里用全局 `os.chdir()` 切换并发任务目录。

验收五个真实任务：拉新卡、拉活动、拉主页语音、拉生日、更新旧卡表。还需离线/缺资源/取消/失败后的恢复验证；最后重新构建冻结程序验收。

### R5：Spine 源优化与各自发布

Wiki GUI 和正式源验收后，Spine 再接自己的资源需求（Unity bundle、场景等），复用已验证的协议或描述格式，不导入 Wiki 应用包。保持现有本地 S3/LZMA 导入和预览兼容，独立测试、依赖、版本及发布。

Wiki 发布前另做 README/当前文档整理、仓库命名迁移、许可证与冻结 EXE 的真实工作流终验。尚无首个提交的两个暂存目录不自动初始化提交，更不能以清理名义删除。

## 5. 本批结果

已完成本地核对、自动化基线复验和规划落盘。用户要求继续实施后，R1/R2 已完成（旧命令保留路径兼容）；R3 正式清单、原始缓存、格式适配及任务 Resolver 已实现，staging 维护者扩展仍待后续批次；R4/R5 尚待实施。每批分别交付代码、预期变化样例及验收证据。

### R3 任务 Resolver 验收（2026-09-08）

- 新增 `sync` CLI 与 `synchronize()` 应用服务，按任务建立计划，最多四个并发下载，严格校验后送入 generate；本地来源仍通过 generate 支持。
- 卡牌根据 masterdata 的 ID 选择可选 ACB，主页语音选择 parser 支持的角色包；可选下载失败保留告警，必需资源失败和取消阻止成功状态。
- 独立脚本实测 LZMA 外层，歌词实测直接 ext99 MessagePack；分开适配，不在 Provider 里统一解压。
- 全新任务准备目录与实际产物 receipt 避免旧资源混入；resource_manifest 保留计划和下载/解码证据，进度/取消回调可供 GUI 使用。
- 100 项测试与仓库验证通过，含选择范围、未知类别、必需/可选失败、独立文件真实生成、取消最后一个域及重复任务隔离。
- 真实主页语音 84 包在线同步成功，2387 行/116 主体，其中 13 主体不完整、15 主体无 masterdata 映射；保留告警。完整离线复用不发网络请求且 Wiki 表等值。
- cards/events/birthday 离线同步（不含可选卡牌语音）与剧情/歌词资源任务成功；默认 cards 的 472 资源计划通过核对。本批没有全量下载 471 个卡牌 ACB，仍需后续默认卡牌工作流验收。
- 用法及详细证据见 `SYNC_TASKS.md`。本批没有 GUI、冻结 EXE、staging 或 Spine 源验收。

### R3 正式清单与缓存验收（2026-09-08）

- 读取组内脚本后用正式响应验证 raw DEFLATE/MessagePack 清单协议；实现 `ProdManifestProvider`、Resource 描述、完整原始记录和指纹、未知类别诊断、按需下载及离线缓存。
- 真实清单 21,133 条，已识别 21,080 条，未知类别 7/8 共 53 条。额外发现 3 组大小写不同的远程路径，以路径哈希隔离本地缓存，避免 Windows 覆盖。
- 正式 masterdata 使用 raw DEFLATE 外层而非 LZMA；专用适配器验证 MessagePack/表结构后才发布解码文件，保留原始资源及来源哈希。ACB 样本直接交给原有 CRI parser。
- 92 项测试通过，覆盖畸形清单、路径、完全重复记录、大小写隔离、压缩流边界、缓存指纹变化、缓存损坏、截断下载、取消、离线及验证失败时保留旧文件。
- 正式 Provider 下载 masterdata/一个 ACB 样本后，二次命中缓存，离线不发网络请求；471 卡与全部 8 个 masterdata 域成功运行。新快照业务语义并未全部人工验收。
- 命令、详细来源哈希及本机证据见 `PRODUCTION_RESOURCES.md`。本批尚未实现一键按任务下载、staging、GUI 或 Spine 源改造。

### R2 输出上下文验收（2026-09-08）

- 新增 `python -m toolkit generate <域...> --output <目录> --masterdata <文件>`，同一 `generate()` 服务供后续 GUI 使用。详见 `GENERATE_OUTPUTS.md`。
- 新流程不调用 `os.chdir()`；上下文按调用隔离，所有域的 XLSX/LRC 路由至 `wiki_output`，JSON/Markdown 路由至 `audit_output`，缓存与 schema 基线位于指定输出下。旧 run/all/update/交互入口暂保持路径兼容。
- 成功写出文件后登记实际路径、任务、大小、SHA-256；每次生成独立 receipt，并原子更新 latest receipt。失败重试不扫描旧目录、不将旧输出作为本次产物，部分产物标注失败任务。
- 输出状态区分 PASS、PASS_WITH_WARNINGS、FAIL，schema 与语音完整度/扫描告警可传递至应用。缺少 openpyxl 时明确失败，不再跳过后宣称成功。
- 85 项自动化测试与仓库验证通过，包含并发隔离、输入目录不变、schema 阻断、失败重试、Excel 替代文件路径以及告警传递。
- 真实 S2B 通过新 CLI 生成全部 8 域，6 个中间 JSON 与此前成果等值，8 个 XLSX 与已接受投影等值；登记 19 个产物。输入 S2B 哈希及输入目录文件名清单不变。
- 真实主页语音登记 5 个产物，Wiki 表等值；433 卡旧表更新登记 6 个产物，新增/修改/移除均为 0，更新工作簿等值。所有登记产物 SHA-256 复核通过。
- 本机报告 `%TEMP%/brmy-output-regression-26u8og9u/report.json`。本批未做冻结 EXE 或 GUI 验收，也没有访问远端资源源。

### R2 投影清理验收（2026-09-08）

- events 移除 Overview 的类型码/来源分支、Story/Rules 的技术类型码和 Mappings 页，保留可读业务内容。完整活动对象与枚举映射写入 `audit_output/event_archive_audit.json`；旧中间 JSON 暂保留，随输出上下文批次统一。
- 默认 home_voice_catalog 只包含 Wiki长表；完整度仍在 Catalog Subjects 和 Markdown 审计中。主页语音的 JSON/MD（含近年筛选审计）改存 `audit_output`。
- audio 普通工作簿只保留卡牌 ID 或资源文件、标题、日文台词、中文翻译；仅输出有正文的记录。空文本、Cue、匹配方式、稳定性等完整索引写入 `audit_output`。通用资源无法可靠识别角色时保留文件名，不猜角色。
- 79 项自动化测试通过，包括生成工作簿的列/正文核对、空语音元数据保留以及活动枚举审计。
- 与 `aa2443e` 隔离源码比较真实活动导出，所有保留的工作表和列在单元格值、类型、格式上等值。
- 真实 `1/Musics` 主页语音：2099 行、100 主体，前后完整 Catalog 及 Wiki长表等值（本批未启用参考旧 ACB 修复）。
- 真实 `voice_403/412/414.acb` 三包通用音频：所有有正文行按新列投影后与旧结果一致。本次不是全量音频域回归。
- 本机证据：`%TEMP%/brmy-r2-projection-x61wwkwz/report.json`，同目录保留 before/after 输出和日志。本批未构建 EXE，未接通线上源。

### R1 实施验收（2026-09-08）

- missions Wiki 表改为任务 ID、阶段、目标值、任务内容；完整原始记录进入 `audit_output/hidden_missions.json`。
- birthday 去掉空白祝福行，将空白语音文件名行改为轮次；实际日文和人工翻译位置保留。
- snap 去重计数及每组原始 ID 保存到 `audit_output/snap_deduplication.json`，Wiki 表移除折叠计数列。
- events/recipes 使用公共占用保护并返回、打印实际输出路径。
- 77 项自动化测试通过，含实际 XLSX 契约读取、模拟 Excel 占用的替代保存及原文件保留。
- 真实输入沿用固定快照，源 S2B SHA-256 `d4e1b1189fdae8d1400de0d760a66c589823ef88deb063c3c9e450a032fcf6e6`，本次读取的 JSON SHA-256 `2e063d26a1d8f033d34b7e627f4514b1666c64d7b1a6db4c454dd62fb247a1a1`。
- 从 HEAD `5594e5c` 导出干净源码到隔离目录，和候选代码使用同一 JSON 分别运行全部 8 个 masterdata 域。6 个原有 JSON 语义等值；cards/events/recipes/items/music 的 5 个 XLSX 值、类型、格式等值。
- missions 52 条记录仅移列；原描述完整进入 Audit。snap 642 条输出仅移除最后一列，计数逐行与审计一致。birthday 51 → 9 行，全部实际台词和日期一致，删除的 42 行均无文本数据。
- 本机报告：`%TEMP%/brmy-r1-regression-xi2hltt9/report.json`；同目录保存 before/after 输出和运行日志。不提交真实游戏数据。本次未重跑 ACB 关联，也未重新构建 EXE。

## 6. 组内下载脚本补充核对

来源：用户提供的本地 `Break_My_Case.py`（2026-09-08 读取）。仅阅读源码，未执行脚本、访问远端或下载游戏资源。

脚本依赖宿主的 `GUI`、`Config.Game`、`Network.Download.dlbin`、`FileHandler` 和 `Codec`，不是可独立运行的下载器。其确定行为为：

1. 请求 `https://s2b-assets-prod.s2b-coly.com/Tables/FileAssetList.s2bcoly`。
2. 执行 `msgunpackb(ddeflate(bytes))[0]` 并遍历记录。
3. 读取每条记录的 `[0]` 作为文件名、`[2]` 作为类别、`[4]` 作为原始大小相关值。
4. 拼接类别目录与文件名作为资源键，并在正式服根地址后拼接该键形成 URL。

| 类别 | 目录 |
| --- | --- |
| 0 | `Files/Android/` |
| 1 | `Scripts/` |
| 2 | `Tables/` |
| 3 | `LightingSets/` |
| 4 | `Movies/` |
| 5 | `Musics/` |
| 6 | `Jukebox/` |

需要保留为未确认或改变实现的细节：

- `ddeflate`、`msgunpackb`、`dlzma` 的具体实现未提供，raw deflate/zlib wrapper、MessagePack 参数及 LZMA 格式不能仅凭命名确定。
- 大小输出实际键仍为 `szie`，与“已修正为 size”的注释相反；乘数 `1000475.4942283422` 没有单位证据。Catalog 保留原始值，暂不用于精确字节数或下载完整性判断。
- 未知类别只打印警告并跳过。新 Provider 应保留未知记录与诊断，且不将不完整分类宣称为完整清单。
- `GetDec()` 尝试 LZMA 解压并原地覆盖下载文件，失败则静默返回；这不能证明所有资源都是 LZMA，也不能将任意解压失败视为正常原始文件。新链路保留原始缓存，另由格式适配层识别、解码和记录结果。
- 脚本以资源路径为字典键，重复路径会覆盖。清单解析测试需覆盖短记录、未知类别、重复路径、非法路径及结构变更。
- 脚本没有建立“任务需要哪些资源”的关系；Resolver 仍需根据实际 masterdata/ACB 关联实现，不能由这七个目录直接推断所有任务依赖。

结论：正式服应实现 ManifestProvider，staging 才是潜在的 S3 ListProvider。现在已不缺参考脚本，R3 剩余的是协议样本验证和工程实现；不需要把组内下载器的 GUI 与文件状态机嵌入 Wiki Toolkit。
