# 剧情分话出场与熟肉索引

本仓库提供两套互补的剧情表入口：

## 1. Toolkit EXE / CLI 内置任务：`story_cast`（剧情分话出场）

适用于直接从游戏正式服缓存或本地 `.s2bscript` 生成**精确到每一话**的出场人物工作簿，无需依赖 BWIKI 快照或字幕出轴站。

- **GUI 位置**：`生成资料` → `要生成什么` → **「剧情与台词」**分组 → **「剧情分话出场」**（位于「剧情目录」与「剧情脚本」之间）。
- **CLI 用法**：
  ```powershell
  # 联网或离线缓存模式（推荐，自动同步/复用约两千个 .s2bscript 小文件）
  python -m toolkit.cli sync story_cast --cache E:/BRMYCache --output <输出目录> --offline

  # 本地文件模式
  python -m toolkit.cli generate story_cast --masterdata <master_data.s2b或json> --source <含.s2bscript目录> --output <输出目录>
  ```
- **输出产物**：
  - `wiki_output/story_cast.xlsx`（4 张工作表）：
    1. `剧情总表`：1 行 = 1 篇，大分类统一为「主线 / 活动 / 个人 / 卡牌 / 其他」，系列/关联活动细分 `周年活动`、`部门箱活（banner）`、`初始常驻`、`一至三轮生日` 等，含归属角色、实装日期（开服内容补齐 `2024-05-09`）、话数、已解析话数、出场人物（含全部 NPC·原样署名）、剧情 ID。
    2. `分话出场表`：1 行 = 1 话，列出本话出场人物、出场人数与本话状态（`已解析` / `未公开` / `待复核`）。
    3. `分话角色明细`：1 行 = 1 话 × 1 人物，按台词数降序，区分 `主要角色`（21 位 Aporia 成员）与 `NPC`。
    4. `说明`：核对时刻、解析覆盖统计与口径摘要。
  - `audit_output/story_cast.json`：结构化分话出场 JSON 与异常审计。

## 2. 社区熟肉合集 + V3 五表成品工作簿

先用字幕站 `tools/build_site_data.py` 刷新正式服主表、脚本与语音，生成至暂存目录；有跳过项先对账，不要直接覆盖站点。保存 BWIKI「熟肉合集」原页 HTML 和读取日期。安装项目的 `story-index` 可选依赖后运行：

```powershell
python -m toolkit.story_index --master <master_data.json> --station <含index.json及ep的目录> --wiki <熟肉合集.html> --wiki-date YYYY-MM-DD --out <新批次目录>
```

CSV 使用 UTF-8 BOM，JSON 每张表首行是列名。新批次另存，不覆盖人工补录。熟肉索引状态统计的是有没有找到资源线索，不是翻译完整率。

### 成品工作簿导出

- **V3 分话版五表（推荐）**：直接从 `story-index.json` 生成完整 5 页工作簿（`剧情总表`、`分话出场表`、`分话角色明细`、`熟肉链接库`、`进度看板与待处理`），可选通过 `--preserve` 继承已有维护表的 `中文标题`、`备注` 与 `熟肉链接库`：
  ```powershell
  python scripts/export_story_v3.py <story-index.json> <输出V3成品.xlsx> --preserve <已有维护表.xlsx> --export-json <clean-v3.json>
  ```
- **V2 模板增量刷新（兼容旧模板）**：以人工维护中的 V2 模板为底，保留原有 `中文标题`、`归属角色`、`备注`、`熟肉链接库` 与跨表公式，删去 `角色别名映射` 页，仅输出 4 页：
  ```powershell
  python scripts/export_story_v2.py <V2维护模板.xlsx> <story-index.json> <输出成品.xlsx>
  ```
  当新快照包含新增 `story_id` 时自动末尾追加并同步扩展筛选区域、条件格式及跨表引用；若快照缺少模板已有 ID 会报错拦截。
- **工程底账工作簿（可选）**：如需核对全量 8 张底账表，可用 `node scripts/story_workbook.mjs <story-index.json> <输出.xlsx>` 打包（需可解析 `@oai/artifact-tool`）。

## 分类与核对口径

1. **底账与未公开占位**：按主表原生复合键定篇、定话；不从卡池稀有度推测剧情。主线 Interlude 章节若原表章节名为空，回退使用系列名（如 `Interlude I`）。登录与独立 campaign 短篇进「其他」。`3001-01-01` 等未来占位（如个人故事第 2~5 话共 84 话）在源头标记为 `未公开`，不计入异常缺漏。
2. **主线拼图关与分支台词**：含剧情内拼图关的主线话（`mst_puzzle_story_stage`）优先读取完整重读脚本（`RereadStoryFileName`，即 `*_skip-pazzle`），避免仅读取拼图前导段导致后半段角色漏计（如 `main-2-3-2`）。`story_cast` 沿剧本命令图广度遍历全部可达分支，不漏记选项分支内的发言角色。
3. **活动分组**：Prequel、Travelogue 均为「活动 → 部门箱活（banner）」。Prequel 全语音重读用原入口 ID 回连活动原话，不另造主线篇章，在分话与总表出场统计中均不重复计数。
4. **出场口径**：不做别名归并，严格保留剧本原样署名（仅清理已知角色名内部空白）；保留全部 NPC，仅剔除玩家占位符 `<Self...>` 与极少数纯标点/数字脏署名（如 `・`、`2`）。
5. **大分类、实装日期与排序口径**：
   - 大分类保持 5 类（`主线 / 活动 / 个人 / 卡牌 / 其他`）；周年活动故事归入「活动」、周年登录短篇归入「其他」，均在 `系列 / 关联活动` 标「周年活动」；周年卡、一至三轮生日卡与初始常驻卡留在「卡牌」并在系列列细分。
   - 复刻/精选（如 0.5th/1.5th/2.5th Anniversary）不抢占卡牌的原属首发活动；无原表日期时依次回退：开服初始内容（`card-1..63`、主线 Thread 0/1、初始 3 人个人故事的 `2001-01-01` 占位）补齐开服日 `2024-05-09`，早期活动卡继承唯一首发活动开放日，其余非活动卡回退 `mst_gacha` 最早开池日。
   - 排序按大类自然顺序：主线按 `(ThreadNo, ChapterNo)`，个人按 `(CharacterId, ChapterNo)`（官方 1–21 角色顺序），活动与卡牌按 `(实装日期, 数值ID)` 正序，彻底避免字符串字典序错位与初始卡沉底。
