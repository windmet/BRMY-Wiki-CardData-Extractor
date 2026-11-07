# 网站数据源更新

正式服抓取、S2B 解码、PINS / Puzzle / Bartending / Marvelous / Items /
Collections 原生表关联均由 `toolkit.website` 维护。代码从网站当前已审阅
适配器迁入，保留原有身份、未解析语义和来源边界。网站仅归一化公开 JSON。

```powershell
python -m toolkit website check --cache E:/BRMYCache --output E:/WebsiteSource
python -m toolkit website prepare --cache E:/BRMYCache --output E:/WebsiteSource --expected-manifest <check.json 的 manifestSha256>
# EXE 支持完全相同的 website check / prepare 参数。
```

`check` 只取得并校验正式清单，不下载 masterdata。`prepare` 使用刚检查的
同一份清单，若缓存清单已改变则要求重试；资源指纹相同且缓存 SHA/大小完整
才复用。不会下载无关图片、音乐或卡牌 ACB。`--offline` 必须明确指定，不能
把离线检查称为已确认服务器最新。网络/解析/未知格式失败不会回退假成功。

`prepare` 先运行 GROOVE / Music / Jukebox，再从同一份已绑定 raw → decoded →
JSON 的 masterdata 导出另外六个原生源。源 Issues、缺表和损坏输入明确失败。
`website_receipt.json` 只在整条链路成功后写入，绑定本次 runId、所有原生源
SHA、masterdata JSON SHA 和 GROOVE receipt。`website_failure.json` 是失败记录。
每次使用全新的输出目录，禁止把旧 receipt 当成本次成功。

网站候选校验、测试、构建、每日调度、图像/音频补充和正式站发布由网站维护。
此入口不修改网站，不发布数据。清单指纹规则无法发现上游元数据完全不变的
对象替换；未知类别仍保留计数，不猜资源路径。

源码全测试和受控 EXE smoke 均必须通过。真实快照的 EXE 网站源导出属于额外
验收，不把隐藏 Tk 构造测试当作可见 GUI 人工验收。
