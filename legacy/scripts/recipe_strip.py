import json
import csv

try:
    from openpyxl import Workbook
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

INPUT_JSON = 'bar_extract.json'
OUT_CSV_ING = 'bar_ingredients.csv'
OUT_CSV_REC = 'bar_shift_recipes.csv'

def clean_text(text):
    if not text: return ""
    return text.replace('\\n', '<br>').replace('\n', '<br>')

def get_recipe_tier(recipe_id):
    if recipe_id < 1000: return 1
    elif 1000 <= recipe_id < 10000: return 2
    else: return 3

def get_ingredient_type(ingredient_id):
    return "限定材料" if ingredient_id >= 10000 else "常驻材料"

def main():
    print(f"[*] 正在读取数据 {INPUT_JSON}...")
    try:
        with open(INPUT_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"[!] 错误: {e}")
        return

    event_map = data.get("EventMap", {})
    char_map = data.get("CharacterMap", {})
    ingredients = data.get("Ingredients", {})
    recipes = data.get("Recipes", {})
    shift_menus = data.get("ShiftMenus", {})

    # ==========================================
    # 表1：材料表
    # ==========================================
    headers_ing = ["材料ID", "材料分类", "材料名称", "材料描述", "图标文件名"]
    rows_ing = []
    sorted_iids = sorted([int(k) for k in ingredients.keys()])
    for iid in sorted_iids:
        ing = ingredients[str(iid)]
        rows_ing.append([
            iid, get_ingredient_type(iid), ing.get("Name", ""),
            clean_text(ing.get("Desc", "")), ing.get("Icon", "")
        ])

    # ==========================================
    # 表2：排班配方表
    # ==========================================
    shift_meta = {}
    event_shift_groups = {}
    
    for sid_str, menus in shift_menus.items():
        sid = int(sid_str)
        target_ev_id = 0
        target_ch_id = 0
        
        for menu in menus:
            rid = menu["RecipeId"]
            rec = recipes.get(str(rid), {})
            if rid >= 10000:
                target_ev_id = rec.get("EventId", 0)
                target_ch_id = rec.get("RecommendCharacterId", 0)
                break
                
        if target_ev_id == 0:
            for menu in menus:
                rec = recipes.get(str(menu["RecipeId"]), {})
                target_ev_id = max(target_ev_id, rec.get("EventId", 0))
                if target_ch_id == 0:
                    target_ch_id = rec.get("RecommendCharacterId", 0)
                    
        shift_meta[sid] = {"EventId": target_ev_id, "CharacterId": target_ch_id}
        
        if target_ev_id not in event_shift_groups:
            event_shift_groups[target_ev_id] = []
        event_shift_groups[target_ev_id].append(sid)

    shift_relative_map = {}
    for ev_id, sids in event_shift_groups.items():
        sids.sort()
        for idx, sid in enumerate(sids):
            shift_relative_map[sid] = f"Shift-{idx + 1}"

    headers_rec = [
        "活动ID", "活动名称", "配方名称", "轮班角色", "排班Shift", "配方等级", 
        "售价(EN)", "耗时(秒)", "所需材料", "配方描述", "图标文件名"
    ]
    raw_rows = []
    seen_recipes = set()

    for sid_str, menus in shift_menus.items():
        sid = int(sid_str)
        ev_id = shift_meta[sid]["EventId"]
        ch_id = shift_meta[sid]["CharacterId"]
        
        ev_title = event_map.get(str(ev_id), f"未知活动(ID:{ev_id})") if ev_id else "日常/无活动"
        char_name = char_map.get(str(ch_id), f"未知角色({ch_id})") if ch_id else "无"
        rel_shift = shift_relative_map.get(sid, f"Shift-Raw{sid}")

        for menu in menus:
            seq = menu["MenuSequenceNo"]
            rid = menu["RecipeId"]
            seen_recipes.add(rid)
            rec = recipes.get(str(rid))
            if not rec: continue

            ingredient_names = [ingredients.get(str(i), {}).get("Name", f"未知({i})") for i in rec.get("IngredientIds", [])]
            
            raw_rows.append({
                "sort_key": (ev_id, sid, seq),
                "data": [
                    ev_id, ev_title, rec.get("RecipeName", ""), char_name, rel_shift,
                    get_recipe_tier(rid), rec.get("Price", ""), rec.get("RequiredSecond", ""), 
                    " / ".join(ingredient_names), clean_text(rec.get("RecipeMemo", "")), rec.get("RecipeFileName", "")
                ]
            })

    for rid_str, rec in recipes.items():
        rid = int(rid_str)
        if rid not in seen_recipes:
            ev_id = rec.get("EventId", 0)
            ch_id = rec.get("RecommendCharacterId", 0)
            ev_title = event_map.get(str(ev_id), f"未知活动(ID:{ev_id})") if ev_id else "日常/无活动"
            char_name = char_map.get(str(ch_id), f"未知角色({ch_id})") if ch_id else "无"
            
            ingredient_names = [ingredients.get(str(i), {}).get("Name", f"未知({i})") for i in rec.get("IngredientIds", [])]
            
            raw_rows.append({
                "sort_key": (ev_id, 99999, rid),
                "data": [
                    ev_id, ev_title, rec.get("RecipeName", ""), char_name, "无排班",
                    get_recipe_tier(rid), rec.get("Price", ""), rec.get("RequiredSecond", ""), 
                    " / ".join(ingredient_names), clean_text(rec.get("RecipeMemo", "")), rec.get("RecipeFileName", "")
                ]
            })

    raw_rows.sort(key=lambda x: x["sort_key"])
    rows_rec = [item["data"] for item in raw_rows]

    # ==========================================
    # 输出无格式纯文本表
    # ==========================================
    with open(OUT_CSV_ING, 'w', encoding='utf-8-sig', newline='') as f:
        csv.writer(f).writerow(headers_ing)
        csv.writer(f).writerows(rows_ing)
    with open(OUT_CSV_REC, 'w', encoding='utf-8-sig', newline='') as f:
        csv.writer(f).writerow(headers_rec)
        csv.writer(f).writerows(rows_rec)

    if OPENPYXL_AVAILABLE:
        output_xlsx = 'bar_data_complete.xlsx'
        wb = Workbook()

        # Sheet 1: 材料表
        ws1 = wb.active
        ws1.title = "Ingredients (材料)"
        ws1.append(headers_ing)
        for row in rows_ing: 
            ws1.append(row)

        # Sheet 2: 配方表
        ws2 = wb.create_sheet(title="Recipes (活动排班)")
        ws2.append(headers_rec)
        for row in rows_rec: 
            ws2.append(row)

        wb.save(output_xlsx)
        print(f"[+] 纯净版无格式 Excel 表已生成: {output_xlsx}")
    else:
        print("[!] 提示: 环境中未安装 openpyxl，仅生成了 CSV 文件。")

if __name__ == "__main__":
    main()