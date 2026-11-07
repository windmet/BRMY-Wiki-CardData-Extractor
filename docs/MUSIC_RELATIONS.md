# Music 资源关系验收（2026-09-09）

以 mst_music 为目录，按 MusicId 左关联活跃 mst_music_out_game。唯一匹配时使用后者的音频与封面资源名；不匹配保留旧主表字段兼容。重复匹配不任意选取，孤立资源记录保留诊断。完整原始匹配记录写入 audit_output/music_relations.json，普通 XLSX 保留六列。

裸资源名沿用本地导出约定追加 .mp3/.png，已有后缀不重复追加。这是文件名投影，不代表已下载、远端 URL 已验证或文件确实存在。歌词、背景和 ProfileMusicCueId 保留在关系审计，不推断未核实的资源链。

歌曲时长仍仅使用已有主表时长或本地 MP3 测量。mst_music_info 的 PuzzlePlaySeconds 不作为全曲长度。

真实回归使用已固定的 244 表快照（SHA-256 221fd610386eb2041ff1aba1946220a8ba5fab09d48377ed693b28669fde585f）：

- 287 首全部保留，187 首匹配、100 首无 out_game；无重复或孤立异常。
- 对照旧 JSON，仅 AudioFileName 与 JacketFileName 各 187 项变化，其他字段全部等值。
- XLSX 仍为六列、287 条音乐记录。
- 合成回归覆盖未匹配、非活跃资源、重复及孤立记录、已有扩展名、旧字段兼容和不误用游玩时长。

本机证据：`%TEMP%/brmy-music-regression-xsrqzbl2/verification.json`，同目录保留 before/after 实际产物。未重建 EXE，未进行本批音频下载或可见 GUI 验收。
