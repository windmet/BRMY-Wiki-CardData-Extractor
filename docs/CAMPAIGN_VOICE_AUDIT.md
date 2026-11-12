# 活动页语音覆盖排查（2026-11-12）

## 截图原句已经收录，但活动入口关系缺失

用户提供的 2.5 周年活动页截图中，在間樹帆的台词对应：

- `mst_campaign_character_voice`：CampaignId 185、CharacterId 15、VoiceCueName `vo_home_138`。
- 资源 `Musics/voice_arima_3.acb`：CueIndex 26、CueId 56，标题 `2.5th Anniv.`，ACB UTF 精确匹配，稳定读取。
- `E:/WikiResults/20261108_review/wiki_output/home_voice_catalog.xlsx`：`周年纪念`第 100 行。21 名角色的这一主体全部存在。

原导出仅关联 `mst_home_voice`，因此这组被标为 `acb_only`，备注「masterdata 未登记，可能尚未开放」。实际它已被活动页引用，不能据此推断未开放。本次增加按角色和 Cue 精确关联的 `CampaignReferences`，在原行备注活动名，并新增「活动页引用」表列出活动时段。主页表匹配状态保留，活动页时段不当作这条语音最初发布的时间。

## 确认存在的其他入口缺口

当前缓存的显式引用共 33 条，均能在 ACB 中精确找到：周年活动页 21 条，Shuffle Song 活动页 3 条，Shuffle Talk 对话 9 条。

后 12 条来自 `voice_hinomiya_campaign.acb`、`voice_aizawa_campaign.acb`、`voice_kamiya_campaign.acb`。每个包 4 条，其中序号 1–3 由 `mst_shuffle_talk_sequence` 引用，序号 4 由 `mst_campaign_character_voice` 引用。已有缓存不代表当前任务会下载它们。

`home_voices` 的资源规划只选择角色 general / 1 / 2 / 3 包（以及已支持的系统包），扫描也只接收 `vo_home_*`。所以这 12 条不会进入主页语音表。通用 `audio` 任务能够扫描这些包的文本，但不会输出对应角色、活动、对话顺序的完整业务关系。

CampaignId 188 的起止：2026-11-13 18:00 UTC 至 2026-11-21 04:00 UTC，换算北京时间从 **11 月 14 日 02:00** 开始。截至排查日期尚未开放，资源存在不能标为游戏内已开放。

当前表另有 84 条历史周年活动页配置（CampaignId 53 / 88 / 124 / 157，各 21 人），VoiceCueName 为空、Text 为 `test`。这不是 84 条已经证实丢失的台词，也不能按标题猜测 Cue；需另查客户端取值逻辑才能确认其回退行为。

## 结论与后续范围

截图原句无漏文，问题在入口关联和错误的开放提示，本次已修正。确实另有 12 条活动专用语音缺少结构化导出，后续应增加活动语音与 Shuffle Talk 的资源规划、角色归属、对话顺序和日期状态；这批不能按每个主体应有 21 人的主页规则验收。

其他 general 包中的 puzzle、training、costume、oneshot 等前缀不属于主页域；通用语音任务能取文本，但是否完整覆盖各玩法，需要分别以玩法引用核对。本次不把扫描到的总数当成全游戏覆盖率。

## 可复查证据

- `E:/BRMY-QA/20261112-campaign-voices/audit.py`：在仓库根目录使用 `python -X utf8 -c "import runpy;runpy.run_path('E:/BRMY-QA/20261112-campaign-voices/audit.py')"` 重跑。
- 同目录 `campaign_voice_audit.json`：输入与资源哈希、33 条引用与匹配结果、84 条占位配置。
- 同目录 `shuffle_voice_gap.tsv`：12 条缺口的角色、入口、语音标识、标题、原文。
- `E:/WikiResults/20261112_campaign_voice_audit/wiki_output/home_voice_catalog.xlsx`：修正后的表；原句在「周年纪念」第 100 行及「活动页引用」第 16 行。
