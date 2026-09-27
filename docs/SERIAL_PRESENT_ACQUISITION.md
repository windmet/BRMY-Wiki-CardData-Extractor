# 卡牌 Serial / Present 来源

`card_relations._serial_present_relations()` 使用 RewardResolver 的 Present 展开能力：

`mst_present_serial_code.PresentId → mst_present.PresentId → RewardTypeCode=1 → mst_character_card.CharacterCardId`

不把 PresentId 当 DirectRewardGroupId，不根据卡名、日期、技能名或故事同名推断。只消费活动标记与活动礼物行；奖励指向非卡牌时不会建立卡牌关系。缺礼物组、缺卡目标与无 PresentId 标记均保留诊断。

卡牌的 `Relations.SerialPresentAssociations` 与 `Acquisition.Evidence` 保留全部匹配来源。已有卡池/活动/常驻的主要来源保持原结果；当主要来源缺失时，用序列码兑换及 PresentDescription 填补。无描述仍保留来源缺项告警，不拿 PresentId 冒充可读名称。原始 CardRouteCode 不改写，即使它的旧枚举仍显示 EventReward，也以派生 Method 与明确证据区分兑换。

`audit_output/card_serial_present.json` 保存本次所有活动 serial 标记及展开后的礼物（不限卡牌），供复核来源链。卡牌 Wiki 表沿用已有列契约；旧“卡牌对应活动名”列当前实际承担获取来源显示，包含本次特典说明。后续改列名时需要同时提供旧工作簿兼容，不能直接破坏人工卡表更新。

## 2026-09-09 验收

- 118 项测试与 verify 通过。新增合成测试覆盖任意卡 ID、两个来源保留、Item/Card ID 碰撞、Present/DirectReward 同 ID、不活动行、缺组/目标、缺描述，以及已有来源不被后续特典替换。
- 固定快照 SHA-256 `221fd610386eb2041ff1aba1946220a8ba5fab09d48377ed693b28669fde585f`，471 卡改前/改后对照：仅451–456的 Acquisition 有意变化，新增 SerialPresentAssociations 外的所有其他结构等值。
- 六卡均指向 Present144，Method 为“序列码兑换”，SourceName 为原始 CD 特典说明；六条来源告警消失。没有改卡号、技能或原始 route。
- 实际 XLSX 仅这六行的来源和获取方式共12个单元格改变，工作表形状、其余值/类型/数字格式保持一致。此次未加载可选 ACB，不能据此宣称重新验收完整卡牌语音链。
- 14个活动 serial Present 均有审计记录，无来源关系缺项；5个登记产物 SHA-256 校验通过。首次 schema 基线提示保留，不把 receipt 称作无告警 PASS。
- 本机证据 `%TEMP%/brmy-serial-regression-k_z9phdt/verification.json`，同目录保留 before/after；真实数据不提交。

本批没有重建 EXE。Music join、Item22、OJT 命名仍是 N1 后续工作。
