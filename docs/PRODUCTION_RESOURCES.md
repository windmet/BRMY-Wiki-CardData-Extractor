# 正式服资源清单与缓存

`toolkit.resources.ProdManifestProvider` 使用正式服 `Tables/FileAssetList.s2bcoly`，不使用 S3 List。以下协议已在 2026-09-08 用实际响应验证。

- 清单：raw DEFLATE → MessagePack 单对象 → 外层列表的第 0 项为记录列表。
- 记录 `[0]` 是资源名、`[2]` 是类别。完整记录保留，作为更新指纹；`[4]` 保留原值，不按组内脚本乘数猜测字节数。
- 类别 0–6 路径依次是 `Files/Android`、`Scripts`、`Tables`、`LightingSets`、`Movies`、`Musics`、`Jukebox`。
- 类别 7、8 当前未确认路径，原始记录进入 catalog 的 `unknown_records`，不猜路径、不下载这些记录。
- 本次 masterdata 使用 raw DEFLATE 外层，解压后为现有 parser 可读取的 MessagePack 流；ACB 样本直接为 `@UTF`。Provider 不统一尝试 LZMA。

## 命令

```powershell
python -m toolkit resources catalog --cache "E:\BRMYCache"
python -m toolkit resources masterdata --cache "E:\BRMYCache"
python -m toolkit resources download Musics/voice_403.acb --cache "E:\BRMYCache"
python -m toolkit resources masterdata --cache "E:\BRMYCache" --offline
```

`masterdata` 命令打印解码并校验后的 `.s2b` 路径，可传给 `generate --masterdata`。原始下载与解码文件分开保存，旁边有来源/hash 记录。当前命令是维护者入口；自动任务选源与 GUI 仍待后续接入。

## 缓存规则与失败边界

- 每次在线 refresh 拉取清单；只有清单解析通过后才替换缓存。失败不自动回退成“最新”，离线必须显式选择。
- 每个对象比较完整清单记录指纹，并重新校验本地文件大小、SHA-256。相同指纹且缓存完整才复用；文件改变、丢失或指纹变化则重新下载。此策略依赖上游清单记录随对象变化更新，不声称能发现清单元数据完全不变的上游替换。
- ETag/Last-Modified 仅保存为 HTTP 证据，ETag 不作为 SHA-256。下载校验真实 Content-Length（若提供），并设置大小限制、超时和取消检查。
- 下载/解压失败不会覆盖之前的成功文件；临时文件在失败后清理。缓存文件按资源路径哈希隔离，因为正式清单存在仅大小写不同的 HTTP 路径，在 Windows 上不能直接按原路径存储。
- 已知类别内完全相同的资源路径重复、非法路径、清单结构变化、损坏压缩流明确失败。目录遍历、Windows 特殊文件名和缓存目录外的路径不接受。
- `offline` 不发送网络请求；缺少或损坏的缓存明确报错。离线清单不代表已检查最新状态。
- 清单收录不等于活动开放或内容已实装；Wiki 业务状态仍由 masterdata 内容和时间字段判断。

## 本次线上证据

清单原始 SHA-256：`2b1e0fa54bbfaffdd13931155a91512091d72e159a0e9fcc6965469ac37a9d94`。

总记录 21,133 条；已识别资源 21,080 条；未知类别 53 条；存在 3 组仅大小写不同的路径，完整保留。

masterdata 原始 SHA-256：`05f77780ddde106245d9d9216c6ab31670400e425d57a4a2d24399f330fcaa67`；去除 DEFLATE 外层后的 SHA-256：`2043da6836c2d9d46db87399199cd1a052a27e2f83dbd9b13cb42899e0cd12b0`。

现有严格 parser 识别 244 张表、471 卡，全部 8 个 masterdata 域运行成功并生成 19 个产物；新输出目录首次 schema 基线状态为告警。该检查证明正式源至导出的链路可运行，不替代新快照全部业务字段的人工核对。

`Musics/voice_403.acb` 下载后由现有 ACB parser 读出 6 条元数据。masterdata/ACB 二次命中缓存；离线测试将网络函数替换为立即失败，仍成功复用已验证 masterdata。

本机记录：`%TEMP%/brmy-production-acceptance-pwr35qj9/acceptance.json`。不提交游戏资源或导出文件。
