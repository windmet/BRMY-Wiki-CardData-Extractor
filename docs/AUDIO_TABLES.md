# 卡牌与通用语音文本表

任务 `audio`（GUI「通用语音文本」）读取 ACB 和 masterdata，输出两份可筛选的工作簿。联网或离线同步会一并取得 masterdata；本地生成需要选择 masterdata 和 ACB 目录。

```powershell
python -m toolkit generate audio --masterdata master_data.json --audio Musics --output results
python -m toolkit sync audio --offline --cache E:\BRMYCache --output E:\WikiResults\audio
```

## 表头与筛选

`card_voice_texts.xlsx`：卡牌编号、卡牌名、卡牌角色名、说话人、语音分类、标题、日文台词、中文翻译、语音标识、资源文件、核对状态、说明。

`voice_texts.xlsx`：说话人、语音分类、标题、日文台词、中文翻译、卡牌编号、卡牌名、卡牌角色名、语音标识、资源文件、核对状态、说明。

卡牌角色名参照 card data，使用 `mst_character_card.CharacterId` 加 `mst_character_card_multi_character` 的附加角色。CombiCharacterId 是协作对象，不混入卡牌角色名。卡牌表按编号排列，通用表按说话人编号、卡牌编号、类别和语音标识排列。两表复用项目的表头样式、冻结首行、全列自动筛选、文本换行；编号为数值，中文翻译列留空。

## 逐句说话人的依据

- 角色 general / 1 / 2 / 3 / campaign 包：沿用主页语音已确认的角色文件名映射；生日祝福里的对象编号不是说话人。
- 卡牌主页：优先使用 `mst_home_voice` 卡牌类型的精确 Cue 配置和 MotionCharacterId；因此双角色卡可逐句区分人物。
- 带角色编号的技能 Cue：后缀编号对应卡牌角色或配置中的协作角色；不把任意数字当说话人。
- 单角色卡的主页、技能、抽卡语音：关联卡牌主角色。
- 单段协作语音：只有 ACB 序列证据确认是单段时，才关联卡牌 CombiCharacterId。多段、未解析的序列或缺少协作对象时，保留待核对，不按卡牌角色代填。
- `local_voice.acb` 的 `vo_coly_N`、`vo_dl_N`、`vo_title_N`、`vo_profile_1/2/3_N`：当前2.1.0客户端 `Util.GetLocalVoiceFileName(localVoiceType, CharacterId)`（RVA 0x77CB8E8）按1–21的角色编号生成这些名称。只对该包及这些完整格式应用规则。
- boss角色包和机关语音中含明确角色名的 Cue：按已有角色名映射。
- 没有映射的资源、冲突配置、缺少名称、读取不稳定及标题回退匹配：表中保留文本、资源文件、核对状态和原因，不静默删行。

原始 Cue 字段、原始文本仍保存在 `Card_Voice_Index.json` 和 `Voice_Text_Index.json`；新增 Identity、SpeakerBasis、ClipCount 与 ClipEvidence 等关联证据。底层 `scan_card_voices` 接口不变，卡牌主表及协作例外表不受影响。

2026-11-13真实缓存验收：495个卡牌包、7074条有文本记录；7063条关联到说话人，11条协作语音仍待核对。所有495个卡号均有对应卡牌名与卡牌角色。448号 Vignette -Line- 的卡牌角色为節見静 / 相沢篠信，逐句主页和技能语音可分别定位；421、492号例外协作条目继续保留待核对。

本地原文证据与验收日志：`E:/BRMY-QA/20261113-audio-labels`；工作簿：`E:/WikiResults/20261113_audio_labels/wiki_output`。客户端规则证据来自现有Ghidra工程的只读反编译，不是运行游戏观察。
