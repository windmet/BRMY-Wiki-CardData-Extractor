# 下一阶段建设准备（2026-09-09）

实施进度：N1 首批 [统一奖励解析](REWARD_RESOLVER.md) 已实现并接入 events，114 tests 与54活动真实回归通过。N1 其余来源、Music、Item22、OJT 命名及 N2–N7 未完成；下方准备阶段描述保留为实施依据。

后续进度：[Serial/Present 卡牌来源](SERIAL_PRESENT_ACQUISITION.md) 已接入，118 tests 通过，471卡对照仅六张特典卡的来源/方式有意变化。Music 关联后续亦已完成，见 [Music 关系验收](MUSIC_RELATIONS.md)。Item22 与 OJT 文案现已完成，见 [N1 收尾记录](N1_CLOSEOUT.md)。N1 源码和数据回归完成；新 EXE / 可见 GUI 验收待 N7，N2 已完成 [活动分类](EVENT_CLASSIFICATION.md)，[任务关系](EVENT_MISSIONS.md) 已完成，[日期状态](DATE_WINDOW_STATUS.md) 已接入；N2 源码与固定数据回归完成，候选 GUI 验收仍待 N7；N3–N7 尚未实施。

## 本次范围与材料优先级

本次请求是接收网页聊天记录与全量审计，准备下一阶段建设。本批完成当前源码/CI/本地数据复核、修复测试环境前置问题，并确定实施顺序与验收条件；不声称新增业务域已经实现。

材料：Downloads 中 `BRMY-Wiki-Toolkit-审计 (1).md`（聊天记录）及 `BRMY_masterdata_244_table_final_audit (1).md`（244 表清单）。聊天中较晚的玩家纠正优先于较早模型猜测；材料内的“立即实施”“正式发布”等历史措辞不是本次独立授权。以下将其转成下一阶段建设方案。现有 GUI/Excel 验收见 [上一阶段记录](AUDIT_RECONCILIATION_20260908.md)。

继续使用 `E:/Web_build/BRMY-Wiki-CardData-Extractor` 的 `codex/migrate-masterdata-toolkit-v2`，开始核对 HEAD 为 `2df7746`、工作树干净。Wiki/Spine 两套产品边界不变，不覆盖两个旧暂存目录，不自动改名、合并 PR 或发布。

## 已复核的证据

本机既有正式快照：`%TEMP%/brmy-visible-gui-acceptance/online/.bmc_toolkit/master_data.json`。59,021,882 字节，SHA-256 `221fd610386eb2041ff1aba1946220a8ba5fab09d48377ed693b28669fde585f`，244 表、135,621 行。对照附件逐表解析所得 244 条记录，表名无缺失/多余，逐表行数差异为 0。这证明盘点结构一致，不等于验证了网页上传压缩包的字节身份，也不等于每个业务结论都正确。

本机复核摘要：`%TEMP%/brmy-next-stage-preflight-20260909.json`。未重新下载正式资源，未更改真实输入或现有输出。

| 问题 | 当前代码与数据证据 | 施工结论 |
| --- | --- | --- |
| CI 红灯 | HEAD `2df7746` 的 tests run `34227830808` 失败；109 tests 中 3 failures，涉及 `test_generate.py:42`、`test_wiki_output_cleanup.py:120` 两个子用例；日志明确出现 `RUNNER~1` 与 `runneradmin` | 双边 resolve 后比较，保留目录隔离、产物哈希和原文件保留断言；禁止通过跳过测试“修绿” |
| 发布构建与测试不一致 | 同 HEAD build-release run `34227830874` 成功；普通测试原为浮动 Python 3.12 | 保留兼容测试，增加 Python 3.12.9 + release-build.txt 全量测试配置；构建成功不能替代 tests |
| 卡 451–456 来源 | 14 个 serial PresentId；其中卡奖励目标恰为 451–456，来自 present 关系 | 通用 Serial/Present 来源适配，不按卡名、日期或技能名硬编码 |
| 奖励映射 | events `_resolve_reward` 的 type6 实际读取 titles；type10 没进入类型映射。direct reward type3–10 命中分别为 68/68、451/451、387/387、253/253、654/654、185/185、1/1、1218/1218 | 集中 RewardResolver，type6→HonorId，type10→HomeVoiceProductId；背景主键实际为 BackgroundId，不猜 HomeBackgroundId |
| Music | 287 条 mst_music 中 0 条有 AudioFileName；out_game 有 187 条 | 主表保留全部音乐，left join out_game；未匹配保留缺项，不把曲库缩成 187 首 |
| 双人主页 | 当前扫描明确跳过 vo_home_duo；210 个无序角色对，两侧均命中 Category11，共 420 个角色/编号键 | 单独 pair 模型，按明确键对齐，不用单主体 21 人完整度规则 |
| 活动任务 | SpecialTabTypeCode=1：859 条、52 个 target 全命中 Event；type2：540 条、61 个 target 全命中 Campaign | 类型与 ID 联合确定 owner，禁止因 ID 数值重合串联 |
| 活动分类 | Format1/2/3/4/5/6 数量 18/19/11/1/3/2；EventAType1/2/4/5 数量 18/12/5/2 | family + subtype；Making 3/4 合并大类，原始码留 Audit |
| Item22 | 当前 ItemId489，代码枚举尚未覆盖 | 补语音券可读分类，保留未知类型回退 |
| OJT Chart | charts parser 自身说明为 OJT，GUI/说明却称“谱面” | 下一业务批次统一改用户文案；保留 charts 命令及 .s2bchart 兼容 |

## 玩家语义与尚未确定的事项

- 聊天中玩家已解释 BREAK MY PHASE 的技能同名属于彩蛋，不建立 Card→Story 硬关系。获取来源只按 serial/present 奖励链。
- 22、23、25 为剧情 NPC，24 为 Aporia 鸟/吉祥物。1–21 的 staff 完整度集合与 NPC/吉祥物分开；不要从表总人数推导期望人数，也不把模板简介当正式人物信息。
- `.s2bchart` 为 OJT 站位数据。先以 `mst_event_ojt_chart.ChartFileName` 和真实文件核对，再 join 四轴题面/坐标；不推测在线 URL 或坐标单位。
- Puzzle/Purchase 不主动扩张，Quiz 暂缓，Spin 复刻留独立工程。OJT 自身的 Puzzle Phase 与 Story 的 puzzle-story 索引属于对应域的必要关系，不扩大成完整 Puzzle 域。
- Campaign 不能一概翻译成“挑战关”：数据包含多类活动效果。暂不新增独立 Campaign/Bremile/Login/Gacha GUI 域，保留已有关系和未来适配能力。
- MissionDisplayTab 0/1/2/5 的正式玩家名称、ColorLocationType、Tone/TitleBack/Carousel、AR/服装/Puzzle 语音触发仍未确定。不是第一批 blocker：原始值留 Audit，不给普通表编造分类。颜色只保留带原始 type/location 的记录，未确认前不替换全部 UI 主题色。

## 实施批次与验收

| 批次 | 实施范围 / 主要位置 | 必须验收的结果 |
| --- | --- | --- |
| N0 工程前置 | tests 路径比较、test.yml 双环境；本批提交 `d080d2d`、`c95200e` | 本地 verify；远端 release-compatible 与 compatible 两条 tests 均通过。发布 CI 另记，不混为同一证据 |
| N1 正确性 | Wiki 应用内新增奖励关系模块（建议 core/rewards.py）；events、card_relations、music、items；全仓 OJT 文案 | Reward 1–10、100–102 按类型独立解析，99/未知保留可解释回退；同 ID 不跨表兜底；6 张来源告警因真关系消失；所有 14 serial PresentId 可追踪；287 音乐保留，187 out_game 关联；Item22 可读；旧 CLI 兼容 |
| N2 活动分类与 Mission | events + 可复用的任务关系提取；先以现有事件为 owner | 54 事件分类不丢记录；52 Event target 全闭合；逐任务展开 sequence/Border/奖励；type2 Campaign 不混入；孤立奖励组、缺 target、未知枚举有 Audit。累计完成奖励与每日/累计任务不靠文本猜逻辑 |
| N3 OJT 与年度 Birthday | 独立 OJT 领域模型，GUI 可归活动组；生日增加年度档案，保留现有台词表 | 3 OJT、12 Shift、Chart 四轴、Phase/奖励箱/终端文本闭合；真实 .s2bchart 至少一份 join。51 个角色年份记录、153 登录奖励序列及 tap rewards 核对；原生日台词/人工列不被替换 |
| N4 Voice | home_voices + Resolver 资源选择；duo/limited/time labels/system voices | 210 对两侧文本以真实 ACB 验证；pair 缺侧单独告警；旧单人产物等值；全局 limited 名称与角色级时间分别保留；吉祥物不进入 21 staff 分母；原 13 主体缺项逐条复查，不能因调整分类直接消警 |
| N5 Story Catalog | 新索引域与现有 scripts 正文解析分层 | Main/Character/Card/Event/Login/Puzzle Story 六类；采用复合键保留章节、section、owner、门槛、奖励、语音标志与 script target；显式处理跨 story type 引用；无文件名证据时不造文件名；不把技能彩蛋变外键 |
| N6 Collections | CostumeModel/Mini 核心，Honor/Pin/HomeBackground/Item 共用奖励来源查询 | 465 Style、401 Mini 基线；直接卡牌关系、奖励引用与最终获取入口分开；一物多来源不覆盖；缺称号正文不以 title 画面名代替；资产路径与完整关系留 Audit |
| N7 GUI 信息层级与候选验收 | Task 元数据驱动分组、常驻说明、高级帮助和输出核对提示 | 两个生日入口看常驻说明即可区分；OJT 不再写谱面；鼠标与键盘可访问帮助；同步预览注明可能同步 masterdata，缓存数来自校验而非猜测；业务缺项与未使用未知类别分层但原 receipt 不丢；重跑可见布局与新域真实生成，再从干净代码重建 |

N1 是 N2/N3/N5/N6 的奖励基础；N4 可在 N1 后独立推进。每批先确定普通表列与 Audit 字段，再实现与生成样例、语义差异报告，验证后单独提交。不是“一表一个按钮”，不在准备阶段添加空壳域。

### 横向约束：收录与开放状态

在 N2–N6 输出契约阶段共同落实，不等最后 GUI 才补。每次运行明确 as_of 与时区，区分清单收录、日期推导状态、实际用户解锁条件。建议状态为 scheduled、within_window、expired、unreleased_placeholder、unknown；within_window 不能承诺账号已解锁。

3001 等占位日期、9999 等无期限、缺时间与 IsActive 分别保留证据，不统一视作已开放；边界日期有测试。Wiki 需要历史活动，不能用“当前已开放”筛掉全部历史资料。建议默认保留已开始的历史与当前资料，未来/占位单列或显式选入；具体每域筛选默认在输出契约验收时确定。未知状态不得静默丢弃，原始数据全部保留 Audit。

### 输出与回归的共同门槛

- 继续复用 MasterDataSession、TableCatalog、generate/synchronize、OutputContext、receipt 与保存保护；不引入 chdir 或重复 downloader。
- Wiki 保留玩家可读列与翻译位置；技术码、原始键、文件链路、完整奖励引用与缺项原因留 Audit。稳定内部键用于关系和人工更新，不为清理工程字段而删除关联能力。
- 合成测试覆盖未知类型、缺表/外键、非活动记录、时间边界、一对多和 ID 碰撞；固定真实快照比较有意变化及未改列。不用全表计数替代逐关系、逐输出验证。
- 每个新增任务同步扩展 CLI/GUI 注册、资源计划、schema 契约、来源/产物登记和文档；网络资源只按任务需求取得。每轮明确不完整数据，不能将“成功写文件”当内容完整。
- 发布、许可证、版本号和目录迁移另开收口批次；当前准备不触发这些操作。完成本阶段后默认转为 schema diff / 既有域适配，而非继续无边界扩表。

## 第一批可直接开工的工作单

N0 本地 109 tests 与 verify 已通过，日志 `%TEMP%/brmy-next-stage-verify.log`。首次远端复跑进一步揭示占用模拟判断也必须双边 resolve，`c95200e` 已补齐；不能只修最终断言。远端结果在本批交付时另行核对，未通过前不称为 CI 已恢复。

复核结果：提交 `c95200e` 的 [tests run 34307276700](https://github.com/windmet/BRMY-Wiki-CardData-Extractor/actions/runs/34307276700) 中 release-compatible 与 compatible 两个 job 均成功，N0 测试门槛已通过。该结论只覆盖测试修复提交；随后规划文档提交的自动 CI 为独立运行。未将仍在构建中的 release job 称为新冻结程序验收通过，本批未修改业务代码或重建本地 EXE。

1. 在奖励消费层建立表名/主键/可读名称的显式映射和 group/present 展开接口；输入失败与未知映射必须可诊断。type100–102 分别核对真实目标，不沿用当前 items/ingredients 混合兜底。
2. 先接 events 并比较真实奖励投影，再让 card_relations 消费 serial/present provenance；保留先前 source 类型兼容，不为 6 卡单独特判。
3. Music 使用 left join；music_info 的多变体时长不能当整首曲长，cue/cue_sheet 不猜一对一。音频/封面扩展名先对照正式资源键验证。
4. 补 Item22；统一 OJT 用户文案与指南，charts 机器入口兼容不改。
5. 固定上述快照执行改前/改后对照，记录 6 卡、奖励类型和音乐资产字段的具体变化；此后再推进 N2。
