"""道具图鉴提取 + 导出 XLSX。"""
from collections import Counter

from ..core.scanner import load_json
from ..core.exporter import write_xlsx, xlsx_path

INPUT_JSON = 'master_data.json'

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


def _clean(text):
    if not text:
        return ""
    return str(text).replace("\\n", "<br>").replace("\n", "<br>")


def run(session=None):
    data = session.data if session else load_json(INPUT_JSON)

    items = []
    for sub in data:
        if isinstance(sub, list) and sub and isinstance(sub[0], dict):
            if "ItemId" in sub[0] and "ItemTypeCode" in sub[0]:
                items = sub
                break

    if not items:
        print("[!] 未找到道具数据")
        return

    headers = [
        "道具ID", "道具名", "类型", "稀有度",
        "属性", "所属标签", "图标文件名", "说明",
    ]

    rows = []
    for item in items:
        if not item.get("IsActive", True):
            continue
        rows.append([
            item["ItemId"],
            item.get("ItemName", ""),
            ITEM_TYPE.get(item.get("ItemTypeCode", 0), f"未知({item['ItemTypeCode']})"),
            RARITY.get(item.get("ItemRarityCode", 0), f"Lv{item['ItemRarityCode']}"),
            ATTRIBUTE.get(item.get("ItemAttributeCode", 0), ""),
            DISPLAY_TAB.get(item.get("ItemDisplayTab", 0), f"Tab{item['ItemDisplayTab']}"),
            (item.get("ItemFileName", "") or "") + ".png",
            _clean(item.get("ItemDescription1", "")),
        ])

    rows.sort(key=lambda r: r[0])

    out = xlsx_path('items_catalog.xlsx')
    write_xlsx(rows, out, headers, sheet_title="道具图鉴")
    print(f"[+] 提取 {len(rows)} 条道具 → {out}")

    # 统计摘要
    types = Counter(r[2] for r in rows)
    rarities = Counter(r[3] for r in rows)
    print(f"\n  类型分布:")
    for t, c in sorted(types.items(), key=lambda x: -x[1]):
        print(f"    {t}: {c}")
    print(f"  稀有度分布:")
    for r_, c in sorted(rarities.items()):
        print(f"    {r_}: {c}")
