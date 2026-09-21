# 双人主页语音首批（2026-09-09）

显式 generate 的 home_voice_duo 域使用 --masterdata、--audio、--output，输出 home_voice_duo.xlsx 和 audit_output/home_voice_duo.json。GUI/正式资源选择尚待后续接通。

mst_character_home_voice_duo 两侧分别按 CharacterId/HomeVoiceNo 关联 HomeVoiceTypeCode1、Category11 的主记录，再用角色ID与实际 VoiceCueName 匹配 ACB。无序角色对仅用于盘点，不反转对话顺序；PartnerVoiceStart 保留原值。

双人扫描保留所有包来源，仅接受稳定 ACB UTF 元数据。多个来源文字一致可以合并展示，冲突、缺侧、空文本、重复/缺主记录均明确诊断，不选择其中一份冒充完整结果。与单人21角色完整度模型独立。

真实输入 `E:/做了一半的字幕/bmc_unpack/1/Musics` 与固定244表快照：210无序角色对、420侧稳定非空文本全部关联。旧单人扫描2099条结果及告警与HEAD基线逐项等值。证据：`%TEMP%/brmy-duo-real-fnnyeuqq/verification.json`。此处验收是元数据文本，不声称试听或播放时序已验证。

133项测试与仓库验证通过。N4其他限定语音、时段标签与吉祥物区分仍待实施；EXE未重建。
