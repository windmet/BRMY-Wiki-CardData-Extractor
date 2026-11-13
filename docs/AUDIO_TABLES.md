# 通用语音文本表

任务 `audio`（GUI「通用语音文本」）只输出非卡牌语音，工作簿为 `voice_texts.xlsx`。说话人、分类、标题、原文、翻译空列、语音标识、资源文件、核对状态和说明均可筛选；首行冻结，默认按说话人编号排序。

卡牌主页、技能、抽卡和协作语音不在此任务重复导出。卡牌资料和已支持的台词使用 card data，多段协作语音使用已有例外表。`audio` 不再生成 `card_voice_texts.xlsx` 或 `Card_Voice_Index.json`，底层 `scan_card_voices` 接口保留，卡牌主表的提取不受影响。

## 范围与资源规划

- 排除 `voice_<卡号>.acb` 整包，以及 masterdata 中 `VoiceCueSheetName` 指定的其他卡牌包。
- 对共享资源，再排除 `card_vo_*` 条目。其他文本与空元数据的审计记录继续保留。
- 联网 / 离线同步的资源规划同样排除卡牌包。若同次还选择卡牌任务，卡牌任务可按自己的需要下载，不会混入通用语音输出。
- `Audio_Inventory.json` 是输入目录的物理资源清单，可能包含原目录的卡牌文件名；`Voice_Text_Index.json` 明确标记 `non_card_audio_only`，不含卡牌文本。
- 使用新的输出目录查看本批结果；旧目录中的历史文件不会自动删除，也不会算作本次输出。

本地生成需要 masterdata 和 ACB 目录；联网或离线同步会一并取得 masterdata，用于说话人名称及卡牌包排除规则。

```powershell
python -m toolkit generate audio --masterdata master_data.json --audio Musics --output results
python -m toolkit sync audio --offline --cache E:\BRMYCache --output E:\WikiResults\audio
```

## 说话人关联

- 角色 general / 1 / 2 / 3 / campaign 包沿用主页语音已确认的角色文件名映射；生日祝福中的对象编号不是说话人。
- `local_voice.acb` 的 `vo_coly_N`、`vo_dl_N`、`vo_title_N`、`vo_profile_1/2/3_N`，按2.1.0客户端 `Util.GetLocalVoiceFileName(localVoiceType, CharacterId)`（RVA 0x77CB8E8）的1–21角色编号规则关联。
- boss角色包及机关语音中明确包含角色名的 Cue，按已有角色名映射。
- 无法确认说话人、缺少名称、读取不稳定或标题回退匹配时，保留原文并列明待核对原因。

此前7074条文本中有2158条卡牌语音；剔除后，当前缓存应有4916条通用语音。此前11条未确认的协作语音属于卡牌，不再进入此任务的待核对统计。
