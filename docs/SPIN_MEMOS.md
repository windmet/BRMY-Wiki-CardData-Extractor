# Spin 备忘录检索表

`spin_memos` 生成 `spin_memos.xlsx`，目标是“好查”：一行一张备忘录卡，所有分类维度都是可筛选的列，不再靠拆表或多级表头表达分类。旧的 `snap` 任务（`Snap_Wiki_Data_Clean.xlsx`）保持不变。

```powershell
python -m toolkit sync spin_memos --cache "E:\BRMYCache" --output "E:\WikiResults"
python -m toolkit generate spin_memos --masterdata "E:\data\master_data.s2b" --output "E:\WikiResults"
```

## 备忘录卡

`mst_spin_snapshot` 按 SnapshotId 顺序每三张一组：N → R → SR（Wiki 称 R / SR / SSR）。同一组内容会因抽取时间（ExtractTime）、姿势、相框、所在 SpinSet 不同重复出现：2026-11 的数据有 3450 张相片、1150 组，合并后是 237 张卡。合并键是主角 + 三张备忘录文本 + 每张的评论（评论角色, 文本）。同一句评论放在不同角落时 StickyNoteId 不同，所以不按 ID 比较。

少数组跨两个 SpinSet（如 2485–2487：N 在 400038，R/SR 在 400039），内容相同，按一组处理。不是 N→R→SR 或主角不一致的组记入 `spin_memos.json` 的 Issues。

## 列

| 列 | 来源 |
| --- | --- |
| 编号 | 该卡第一张相片的 SnapshotId |
| 日期 | 仅限定卡：解锁它的限定服装 `mst_costume_mini.ReleaseDateTime`（日本时间） |
| 场景 | SpinSet 的 SpinBaseCode：1 太空赌场、2 电玩城、3 游乐园、4 美式餐厅（客户端 Casino / Factory / AmusementPark / AmericanDiner，沿用 Wiki 译名） |
| 位置 | SpinSet 角色动作文件名经 `translate_scene` 推断（老虎机、轮盘赌、抓娃娃机……） |
| 类别 | 通常 / 限定 × 单人 / 双人 / 三人 / 四人。限定 = 只在 `mst_spin_film_limited_costume_mini` 中追加、基础胶卷没有的 SpinSet |
| 主角 | SnapshotCharacterIds |
| 话题 | 备忘录以“〜话题〜”开头时提取，例如“朝型？夜型？” |
| R/SR/SSR 备忘录与评论 | Comment 与 StickyNoteId1–4（左上、右上、左下、右下）；评论列数按数据最大值生成 |
| 限定服装、所属胶卷 | 服装名；胶卷写作“角色(胶卷稀有度 N/R/SR)” |

## 其他工作表

- **话题对照**：行是角色，列是话题（按出现次数排），格子是回答。只收单人卡，便于横向比较。
- **评论检索**：一行一条评论，按评论角色排列，可查“某角色写过的全部评论”及其所评论的备忘录。
- **角色统计**：每个角色的单人卡、多人卡、写下与收到的评论数。

通常卡没有可靠的上线日期，按 SpinSetId 先后排列；限定卡排在后面，按日期排列。中文翻译不在本表内，需要时在 Wiki 侧另加列。
