# 按任务同步正式资源

`sync` 将正式清单、资源选择、校验下载、输入准备和 `generate` 串成一次任务。普通任务不需要手工寻找下载后的 masterdata/ACB 路径。

```powershell
# 卡牌及默认可选卡牌语音；同时可选择其他 masterdata 域
python -m toolkit sync cards events --cache "E:\BRMYCache" --output "E:\WikiResults"

# 只生成卡牌数据，不请求可选 ACB
python -m toolkit sync cards --no-card-audio --cache "E:\BRMYCache" --output "E:\WikiResults"

# 主页语音，或离线复用已验证的正式资源缓存
python -m toolkit sync home_voices --cache "E:\BRMYCache" --output "E:\WikiResults"
python -m toolkit sync home_voices --offline --cache "E:\BRMYCache" --output "E:\OfflineResults"

# 保留旧卡表人工列
python -m toolkit sync card_update --old-workbook "E:\manual\cards_data.xlsx" --cache "E:\BRMYCache" --output "E:\WikiResults"

# 查看任务计划（需要 masterdata 的任务会先取得并解码该文件）
python -m toolkit sync cards --plan-only --cache "E:\BRMYCache" --output "E:\WikiResults"

# 显式选择独立资源；不指定 --resource 时，选择该域的所有已识别文件
python -m toolkit sync lyrics --resource Jukebox/personal_song_lyrics_14.s2blyrics --cache "E:\BRMYCache" --output "E:\WikiResults"
```

生日、主体和近年筛选继续支持 `--cycle`、`--year`、`--subject`、`--recent-year`；需要人工指定参考旧 ACB 时可传 `--reference-acb`。本地输入仍使用 `generate`，不会擅自联网。

## 选择规则

- masterdata 域只需要一份 masterdata。卡牌可选语音按实际卡牌 ID 查找 `Musics/voice_<ID>.acb`，不下载无关卡包。
- home_voices 选择当前 parser 支持的 21 个角色名与 general/1/2/3 包；缺少某角色全部包或任意选中包下载失败，明确停止，避免输出假完整表。
- audio 是通用音频文本任务，选择 Musics 下 ACB；文本解析不需要 AWB 音频负载。
- scripts/lyrics/charts 按清单中已识别的后缀选择，`--resource` 可以重复传入以限制范围。目前实际 chart 位于尚未确认路径的类别，因此在线 charts 明确报错；本地 charts 仍可用。
- 不根据 staging 或猜测 URL 补资源。清单中仅大小写不同的对象隔离存储；独立文件导出遇到同名冲突则要求缩小选择，不静默覆盖。

## 下载和生成边界

最多四个并发下载。每次任务建立新的准备目录，只放入本次计划选中的文件，旧资源不会混入本次扫描。原始缓存保持不变；ACB 验证 `@UTF`，独立 S2B 支持已验证的 LZMA-alone 外层或直接 MessagePack，再通过严格 parser 校验。

必需资源失败阻止生成；可选卡牌语音失败允许生成卡表，但进入 warnings。获取关系/语音扫描告警也传入最终结果。取消在网络分块、资源/域边界检查，正在解析的单个域可能需要先结束；取消后不会返回完整成功。

`audit_output/resource_manifest.json` 保存正式清单 SHA-256、任务计划、来源路径、原始/准备后 SHA-256、命中缓存情况及警告。文件仍通过 `output_receipt.json` 向调用方报告，前置资源失败也生成失败 receipt；不拿旧文件表示本次成功。

Python 调用 `toolkit.resolve.synchronize()`，可传入 `progress(event)` 和 `cancelled()`，供 GUI 后台任务使用。事件阶段为 catalog/masterdata/plan/download/generate。

## 2026-09-08 真实验收

- 默认 cards 计划是 1 份 masterdata + 471 个 ACB，没有无关图像/场景资源。该默认卡牌全量 ACB 本批仅验证计划；实际卡表生成验收使用 `--no-card-audio`。
- 正式缓存离线同步 cards/events/birthday 成功生成 10 个产物；独立剧情与歌词成功生成 4 个产物。CLI 离线歌词命令也实际运行通过。
- 84 个主页语音包全部在线下载并验证，连同 masterdata 共 85 个资源；生成 2387 行、116 主体、103 完整主体，结果为 PASS_WITH_WARNINGS。13 个主体缺失部分角色文本、15 个主体无 masterdata 映射，保留审计，不假装补齐。
- 随后将网络入口替换为立即失败函数，完整离线同步仍成功；线上与离线 Wiki 工作簿的值、类型、格式完全一致。
- 本机目录 `%TEMP%/brmy-sync-acceptance-ify51tay/` 保存各任务产物和 `acceptance.json`。固定快照测试不代表未来未知包格式、未知类别或全部新业务字段已被验证。
