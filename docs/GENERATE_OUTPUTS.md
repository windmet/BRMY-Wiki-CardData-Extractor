# 显式输入输出与本次产物

新的 `generate` 命令供日常生成和后续 GUI 共用，不改变当前工作目录，不把解码缓存、schema 基线或导出文件写入输入目录。

```powershell
python -m toolkit generate cards events --masterdata "E:\data\master_data.s2b" --output "E:\WikiResults"
python -m toolkit generate home_voices --masterdata "E:\data\master_data.json" --audio "E:\data\Musics" --output "E:\WikiResults"
python -m toolkit generate birthday --masterdata "E:\data\master_data.json" --cycle 2 --output "E:\WikiResults"
python -m toolkit generate card_update --masterdata "E:\data\master_data.json" --old-workbook "E:\manual\cards_data.xlsx" --output "E:\WikiResults"
python -m toolkit generate lyrics --source "E:\data\song.s2blyrics" --output "E:\WikiResults"
```

可连续列出多个域，masterdata 只读取一次。`--audio` 是音频目录；`--source` 是独立歌词/脚本/谱面输入。主页语音还支持 `--subject`、`--reference-acb`、`--recent-year`；生日支持 `--cycle` / `--year`。

输出目录中：

- `wiki_output/`：Wiki XLSX 和可使用的 LRC。
- `audit_output/`：中间 JSON、原始证据、schema、运行和产物清单；独立脚本/谱面的 JSON 也在此处。
- `.bmc_toolkit/`：本地解码缓存和 schema 基线。

`audit_output/output_receipt.json` 仅列出本次成功写出的文件，包含所属任务、文件绝对路径、大小及 SHA-256。Excel 被占用时记录实际另存的文件。每次另留 `output_receipt_<run_id>.json`，不会通过扫描目录把旧文件冒充本次结果。

状态为 `PASS`、`PASS_WITH_WARNINGS` 或 `FAIL`。失败任务先前写出的部分产物可以保留，但其 `domain_status` 为 `FAIL`；调用方不能将它们表示为完整成功。没有写出的旧产物不进入清单。缺少参数、schema 阻断和单文件解析失败都会进入错误记录；CLI 失败返回非零。

Python 调用使用 `toolkit.generate.generate()`，返回相同字典。输出上下文按调用线程隔离；并发调用使用不同输出根目录。当前不支持多个任务同时写同一输出目录。

旧 `run/all/update` 及控制台交互入口暂保留原路径，便于已有脚本继续工作。新 GUI 将消费 `generate`；本批不宣称 GUI 已实现。旧目录不会自动搬迁或删除。
