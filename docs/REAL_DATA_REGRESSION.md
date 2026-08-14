# 真实数据回归流程

自动化测试只使用脱敏夹具，不能单独证明真实游戏数据没有变化。修改字段匹配、解码、关系或导出逻辑时，还必须使用同一份输入做改前/改后语义比较。

## 验收层级

1. `./scripts/verify.ps1`：运行脱敏单元和契约测试。
2. 使用修改前代码和固定 `master_data.json` 分别运行 `python -m toolkit all`，保存为两个独立输出目录。
3. 比较两次输出：

```powershell
python scripts/compare_exports.py <accepted-output-root> <candidate-output-root>
```

脚本对 JSON 做对象级比较，对 XLSX 比较工作表、尺寸、合并区域、公式和全部单元格值。它不比较 ZIP 时间戳等无关二进制差异。

`audit_output/` 是每次运行的技术审计层，不参与 Wiki 表格等值比较；必须另外检查 `run_manifest.json` 的总状态、各域状态和 `schema_report.md`。

4. 若修改 ACB 关联，再使用固定 Musics 快照运行 cards/home_voices，并比较 JSON/XLSX，同时核对包数、非空文本数、异常数和已知边界卡。
5. 若预期数据会改变，先人工审查差异并记录原因，再更新接受基线；不能因为测试失败就直接覆盖基线。

## 当前固定快照

2026-08-14 对 2026-06-22 的本地快照完成验证：

- S2B SHA-256：`d4e1b1189fdae8d1400de0d760a66c589823ef88deb063c3c9e450a032fcf6e6`
- 244 张表、433 张卡
- 当前四类技能表中不存在非连续 `SkillValue` 行
- 全域改前/改后：6 个 JSON 对象完全相等，8 个 XLSX 全部单元格相等
- music/items/missions/snap/birthday/recipes 迁移到具名表后再次全域验证，结果仍为 6 个 JSON 对象与 8 个 XLSX 全部等值
- events 统一到 `TableCatalog` 后第三次全域验证，活动 JSON 与多工作表 XLSX 仍完全等值
- cards + ACB：455 个包、1907 条非空语音文本；与已接受的 433 卡 JSON/XLSX 完全相等
- MasterDataSession 全选只加载一次 `master_data.json`；首次 schema 基线为 `PASS_WITH_WARNINGS`，第二次固定输入为 `PASS`

真实输入和接受基线只保存在本地，不提交到 Git。该快照只证明上述固定资源；游戏更新后必须重新建立并记录新快照。
