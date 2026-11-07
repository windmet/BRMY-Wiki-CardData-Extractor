# N1 源码与数据回归收尾（2026-09-09）

已完成统一奖励解析、Serial/Present 来源、Music 左关联、Item22 与 OJT 命名修正。前面三个批次的独立证据见 REWARD_RESOLVER.md、SERIAL_PRESENT_ACQUISITION.md、MUSIC_RELATIONS.md。

本批 ItemTypeCode 22 显示为「ボイスチケット / 语音券」。固定 244 表快照中 ItemId 489 的名称为ボイスチケット，说明指向 staff data 中解锁期间限定主页语音。真实导出前后逐单元格对照，569 条道具中仅 C490（ItemId 489）的类型由未知(22) 改为新分类，其余单元格等值。证据位于 `%TEMP%/brmy-item22-7z3rc56y/verification.json`。

当前 GUI 标签、校验提示、文件选择器、交互菜单、CLI 帮助与使用文档统一称 OJT Chart。保留 charts 域名和 .s2bchart 扩展名，未改解析器或线上资源推断。历史审计文档仍保留当时用词。

120 项测试与 scripts/verify.ps1 通过，包括 GUI 预下载校验。这里只证明源码和后台行为，未将隐藏窗口构造测试称为可见 GUI 验收；本批未重建 EXE。N7 仍需新版本可见布局、点击与实际生成验收。

下一批 N2：活动 family/subtype 与事件任务归属、任务序列阈值和奖励。先核对输出契约及真实关系，再实现；Campaign 任务按类型隔离，不因数值 ID 相同关联到 Event。
