# 主页语音限定与时段（2026-09-09）

Home_Voice_Catalog 新增全局限定原记录/名称、TimeDivisionId 与时段原记录。全局限定按 HomeVoiceNo；角色窗口仍按 CharacterId + HomeVoiceNo。二者不互相覆盖或兜底。时段只使用唯一主记录的 TimeDivisionId，不从文本猜测。

home_voice_catalog.xlsx 新增“开放条件”页，分别展示角色窗口、全局窗口和时段名/起止原值。原Wiki长表及单主体导出列不变。纯数字限定名称保留原值，不人为编造节日名称。时段不推断时区或账号解锁；午夜00:00保留。重复限定记录、缺失/重复时段关联有标志。

固定主数据和真实旧1/Musics回归：2099条中945条关联全局限定、105条关联时段。剔除本批四个新增字段后完整Catalog（包括主体和异常）与HEAD基线等值，没有借此消除旧缺项。证据：`%TEMP%/brmy-voice-conditions-n3of57a7/verification.json` 及同目录真实工作簿。

134项测试及仓库验证通过。N4吉祥物/NPC分类及既有缺项逐条复查仍待后续，GUI/EXE未更新。
