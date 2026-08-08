"""道具图鉴提取脚本

用法: python items.py [master_data.json路径]

输出: items_catalog.xlsx (同目录)
"""

import json
import os
import sys
from collections import Counter

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False
    print("[!] openpyxl 未安装，请执行: pip install openpyxl")
    sys.exit(1)

# ====== 映射表 ======
ITEM_TYPE = {
    1: "クリスタル (有償)", 2: "クリスタル (無償)",
    3: "ピース / 欠片", 4: "メダル / 通貨",
    5: "アイテム変換券", 6: "スタミナ回復",
    7: "アイテムセット", 8: "ガチャチケット",
    9: "プレゼント", 10: "カード育成素材",
    11: "カードEXP素材", 12: "スキル強化素材",
    13: "オートスキル素材", 14: "SPスキル素材",
    15: "コンビ強化素材", 16: "リビジョン素材",
    17: "トライベル素材", 18: "ストーリーキー",
    19: "ストーリーEXP", 20: "限定交換素材",
    21: "イベント限定", 99: "その他",
}

RARITY = {1: "N", 2: "R", 3: "SR", 99: "特殊"}

ATTRIBUTE = {0: "なし", 1: "日", 2: "月", 3: "星"}

DISPLAY_TAB = {0: "その他", 1: "育成・強化", 2: "交換・イベント"}

# Rarity colors (header fill)
RARITY_COLORS = {
    "N": PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid"),
    "R": PatternFill(start_color="E3F2FD", end_color="E3F2FD", fill_type="solid"),
    "SR": PatternFill(start_color="F3E5F5", end_color="F3E5F5", fill_type="solid"),
    "特殊": PatternFill(start_color="FFF3E0", end_color="FFF3E0", fill_type="solid"),
}

HEADER_FILL = PatternFill(start_color="37474F", end_color="37474F", fill_type="solid")
HEADER_FONT = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
DATA_FONT = Font(name="微软雅黑", size=10, color="333333")
THIN_BORDER = Border(
    left=Side(style="thin", color="DDDDDD"), right=Side(style="thin", color="DDDDDD"),
    top=Side(style="thin", color="DDDDDD"), bottom=Side(style="thin", color="DDDDDD"),
)


def load_items(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for sub in data:
        if isinstance(sub, list) and sub and isinstance(sub[0], dict):
            if "ItemId" in sub[0] and "ItemTypeCode" in sub[0]:
                return sub
    return []


def build_catalog(items):
    headers = [
        "道具ID", "道具名", "类型", "稀有度",
        "属性", "所属标签", "图标文件名", "说明",
    ]

    rows = []
    for item in items:
        if not item.get("IsActive", True):
            continue

        itype = ITEM_TYPE.get(item.get("ItemTypeCode", 0), f"未知({item['ItemTypeCode']})")
        rarity = RARITY.get(item.get("ItemRarityCode", 0), f"Lv{item['ItemRarityCode']}")
        attr = ATTRIBUTE.get(item.get("ItemAttributeCode", 0), "")
        tab = DISPLAY_TAB.get(item.get("ItemDisplayTab", 0), f"Tab{item['ItemDisplayTab']}")

        row = [
            item["ItemId"],
            item.get("ItemName", ""),
            itype,
            rarity,
            attr,
            tab,
            (item.get("ItemFileName", "") or "") + ".png",
            (item.get("ItemDescription1", "") or "").replace("\\n", "<br>").replace("\n", "<br>"),
        ]
        rows.append(row)

    # Sort by ID
    rows.sort(key=lambda r: r[0])
    return headers, rows


def write_xlsx(headers, rows, out_path):
    wb = Workbook()
    ws = wb.active
    ws.title = "道具图鉴"

    # Write headers
    for ci, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=ci, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = THIN_BORDER

    # Write data
    for ri, row in enumerate(rows, 2):
        rarity = row[3]  # Column D = Rarity
        row_fill = RARITY_COLORS.get(rarity)
        for ci, val in enumerate(row, 1):
            cell = ws.cell(row=ri, column=ci, value=val)
            cell.font = DATA_FONT
            cell.border = THIN_BORDER
            cell.alignment = Alignment(vertical="center", wrap_text=(ci >= 8))
            if row_fill:
                cell.fill = row_fill

    # Column widths
    widths = {"A": 8, "B": 30, "C": 22, "D": 8, "E": 6, "F": 18, "G": 28, "H": 50}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w

    # Freeze header row
    ws.freeze_panes = "A2"

    # Auto-filter
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(rows)+1}"

    wb.save(out_path)
    return len(rows)


def print_stats(rows):
    """打印统计摘要。"""
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    types = Counter(r[2] for r in rows)
    rarities = Counter(r[3] for r in rows)
    tabs = Counter(r[5] for r in rows)

    print(f"\n{'='*50}")
    print(f"  Item Catalog Stats ({len(rows)} items)")
    print(f"{'='*50}")

    print(f"\nBy type:")
    for t, c in sorted(types.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")

    print(f"\nBy rarity:")
    for r, c in sorted(rarities.items()):
        print(f"  {r}: {c}")

    print(f"\nBy tab:")
    for t, c in sorted(tabs.items()):
        print(f"  {t}: {c}")


def main():
    # Default: find master_data.json in current dir
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "新建文件夹", "master_data.json")
        if not os.path.exists(path):
            path = os.path.join(os.getcwd(), "master_data.json")

    if not os.path.exists(path):
        print(f"[!] 找不到 master_data.json: {path}")
        print("用法: python items.py <master_data.json路径>")
        return

    print(f"[*] 读取 {path} ...")
    items = load_items(path)
    if not items:
        print("[!] 未找到道具数据")
        return

    print(f"[*] 找到 {len(items)} 条道具记录")

    headers, rows = build_catalog(items)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "items_catalog.xlsx")
    n = write_xlsx(headers, rows, out)
    print(f"[+] 输出 {n} 条有效道具 → {out}")

    print_stats(rows)


if __name__ == "__main__":
    main()
