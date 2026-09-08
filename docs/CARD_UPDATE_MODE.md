# 卡牌表增量更新模式

`update cards` 用新 masterdata 重新提取自动字段，同时从 Wiki 组已经加工的旧工作簿保留人工列。旧工作簿只读，工具不会原地覆盖它。

## 使用

```powershell
python -m toolkit update cards "E:\path\to\old_cards_data.xlsx"
python -m toolkit update cards "E:\path\to\old_cards_data.xlsx" "E:\path\to\Musics"
```

交互模式中选择“卡牌增量更新（保留人工列）”，再选旧 XLSX 和可选的 Musics 目录。

## 合并契约

- 主键固定为 `卡牌编号`；缺失、空值或重复主键会立即停止。
- 卡名、属性、技能、获取方式等自动列以本次新提取为准。
- `卡牌译名`、各中文语音列以旧工作簿为准。
- 旧表中不属于标准导出的自定义列会追加保留。
- 保留单元格的公式、样式、数字格式、批注和超链接。
- 新增卡按新表顺序输出；已移除卡不进入更新表，但会写入差异表。

## 输出

- `xlsx_output/cards_data_updated.xlsx`：新数据与人工列合并后的工作簿。
- `xlsx_output/cards_data_changes.xlsx`：`Summary`、`Added`、`Modified`、`Removed` 四张差异表。
- `json_output/cards_update_audit.json`：主键、人工列、自定义列、保留公式和变更计数。

若输出文件正被 Excel 占用，工具会改存 `_new.xlsx`，不会删除或覆盖已打开的文件。

## 验收要求

无数据变化时，更新表应在单元格值、Excel 数据类型和数字格式上与旧表一致。有数据变化时，必须先审查 `cards_data_changes.xlsx` 再将更新表作为新基线。

人工样式必须在保存后重新打开工作簿核对。跨工作簿直接复制内部样式索引会产生无效字体/填充引用；当前实现逐项注册字体、填充、边框、对齐、保护和数字格式。卡牌行重排时，超链接归属也随目标单元格更新。回归覆盖自定义样式、批注及行移动后的链接位置。
