# 生日庆典台词轮次与编号

`birthday` 域读取 `mst_character_birthday_mini_game_text`，处理的是生日角色本人的庆典台词。它不等同于 ACB 中 21 人对该角色的生日祝福；后者由 `home_voices` 域按主体整理。

## 轮次选择

默认模式从 masterdata 自动推导：

1. 取最早数据年份中已出现角色的最早生日作为周年边界。
2. 当前真实数据推导出的边界为 `05-14`。
3. `05-14` 至年底属于当年起始的轮次，`01-01` 至 `05-13` 属于上一年起始的同一轮次。
4. 对所有记录计算轮次起始年，选择最新轮次。

可显式覆盖：

```powershell
python -m toolkit run birthday --cycle 1
python -m toolkit run birthday --cycle 2
python -m toolkit run birthday --cycle 3
python -m toolkit run birthday --year 2026
```

`--year` 指轮次起始年。若同时传入 `--year` 与 `--cycle`，两者必须对应，否则停止导出。

EXE 交互菜单单独选择 `[4] 生日台词` 时，也可输入轮次号或起始年份；直接回车使用自动最新。选择 `[A] 全部` 时固定使用自动最新，不额外打断全量流程。

## 三种实际编号形态

固定 2026-06-22 快照中存在以下形态，不能把 `CharacterBirthdayTextNo` 一律解释为 1、2、3：

| 轮次 | 人数与文本 | `CharacterBirthdayTextNo` | `KeyTargetValue` |
| --- | --- | --- | --- |
| 第一轮 | 21 人、每人 5 条 | 20 人使用偏移分段号；1 人恰好为 1-5 | 全部为 0 |
| 第二轮 | 21 人、每人 5 条 | 20 人为 1-5；祠堂恭耶仍为 76-80 | 全部为 0 |
| 第三轮 | 当前已实装 3 人、每人 3 条 | 1-3 | 1-3 |

祠堂恭耶 2024 与 2025 的 76-80 中前三条相同、后两条不同，因此编号形态不能单独决定轮次，也不能因为文本重复就删除记录。工具按生日日期归轮，编号和 `KeyTargetValue` 只作为审计证据。

## 导出规则

- 选中角色与自然年后，按原 `CharacterBirthdayTextNo` 排序，再归一化为第 1 至 N 条。
- `BirthdayTexts` 保存归一化结果；第一、二轮 XLSX 输出 5 条，第三轮输出 3 条。
- `BirthdayTextMeta` 保存目标年份、原始编号、`KeyTargetValue`、格式形态、行数和是否与上一自然年完全相同。
- 原始有效文本不会因重复判断被丢弃。
- 尚未发布的角色保留为空，并标记 `not_released`。

默认自动模式按输入选择最新轮次。2026-09-08 输出清理后，XLSX 保留角色、日期、轮次及实际庆典台词 J/C 行；不再生成空白的 21 人祝福 J/C 行，原空白“语音文件名”行改为轮次。ACB 生日祝福继续使用 `home_voices`。本次未改变 `TargetCycle`、`Characters`、`BirthdayTexts` 或技术 JSON。
