"""酒保配方数据提取 + 导出。"""
from ..core.scanner import walk, load_json, save_json
from ..core.exporter import write_xlsx, json_path, xlsx_path
from ..core.data import clean_text

INPUT_JSON = 'master_data.json'


def extract():
    data = load_json(INPUT_JSON)
    character_map = {}
    event_map = {}
    ingredients = {}
    recipes = {}
    shift_menus = {}

    for obj in walk(data):
        if 'CharacterId' in obj and 'CharacterNameJpn' in obj:
            character_map[obj['CharacterId']] = obj['CharacterNameJpn']
        if 'EventId' in obj and 'EventTitle' in obj:
            event_map[obj['EventId']] = obj['EventTitle']
        if 'IngredientId' in obj and 'IngredientName' in obj:
            iid = obj['IngredientId']
            ingredients[iid] = {
                "Id": iid, "Name": obj.get('IngredientName', ''),
                "Desc": obj.get('IngredientDescription', ''),
                "Icon": obj.get('IngredientFileName', ''),
            }
        if 'ShiftId' in obj and 'MenuSequenceNo' in obj and 'RecipeId' in obj:
            sid = obj['ShiftId']
            shift_menus.setdefault(sid, []).append({
                "MenuSequenceNo": obj['MenuSequenceNo'],
                "RecipeId": obj['RecipeId'],
            })

    for obj in walk(data):
        if 'RecipeId' in obj and 'RecipeName' in obj and 'IngredientIds' in obj:
            rid = obj['RecipeId']
            recipes[rid] = {
                "RecipeId": rid, "RecipeName": obj.get('RecipeName', ''),
                "RecipeMemo": obj.get('RecipeMemo', ''),
                "EventId": obj.get('EventId', 0),
                "RecommendCharacterId": obj.get('RecommendCharacterId', 0),
                "Price": obj.get('Price', 0),
                "RequiredSecond": obj.get('RequiredSecond', 0),
                "RecipeDifficulty": obj.get('RecipeDifficulty', 1),
                "IngredientIds": obj.get('IngredientIds', []),
                "RecipeFileName": obj.get('RecipeFileName', ''),
            }

    out = json_path('bar_extract.json')
    save_json({
        "EventMap": event_map, "CharacterMap": character_map,
        "Ingredients": ingredients, "Recipes": recipes, "ShiftMenus": shift_menus,
    }, out)
    print(f"[+] 提取 {len(recipes)} 配方, {len(ingredients)} 材料 → {out}")
    return event_map, character_map, ingredients, recipes, shift_menus


def get_tier(rid):
    if rid < 1000: return 1
    if rid < 10000: return 2
    return 3


def get_ing_type(iid):
    return "限定材料" if iid >= 10000 else "常驻材料"


def export():
    data = load_json(json_path('bar_extract.json'))
    event_map = data.get("EventMap", {})
    char_map = data.get("CharacterMap", {})
    ingredients = data.get("Ingredients", {})
    recipes = data.get("Recipes", {})
    shift_menus = data.get("ShiftMenus", {})

    headers_ing = ["材料ID", "材料分类", "材料名称", "材料描述", "图标文件名"]
    rows_ing = []
    for iid in sorted(ingredients.keys(), key=int):
        ing = ingredients[iid]
        rows_ing.append([int(iid), get_ing_type(int(iid)), ing.get("Name", ""),
                         clean_text(ing.get("Desc", "")), ing.get("Icon", "")])

    shift_meta, ev_groups = {}, {}
    for sid_str, menus in shift_menus.items():
        sid = int(sid_str)
        target_ev, target_ch = 0, 0
        for menu in menus:
            rec = recipes.get(str(menu["RecipeId"]), {})
            if menu["RecipeId"] >= 10000:
                target_ev = rec.get("EventId", 0)
                target_ch = rec.get("RecommendCharacterId", 0)
                break
        if target_ev == 0:
            for menu in menus:
                rec = recipes.get(str(menu["RecipeId"]), {})
                target_ev = max(target_ev, rec.get("EventId", 0))
                if target_ch == 0:
                    target_ch = rec.get("RecommendCharacterId", 0)
        shift_meta[sid] = {"EventId": target_ev, "CharacterId": target_ch}
        ev_groups.setdefault(target_ev, []).append(sid)

    shift_rel = {}
    for ev_id, sids in ev_groups.items():
        for idx, s in enumerate(sorted(sids)):
            shift_rel[s] = f"Shift-{idx + 1}"

    headers_rec = [
        "活动ID", "活动名称", "配方名称", "轮班角色", "排班Shift", "配方等级",
        "售价(EN)", "耗时(秒)", "所需材料", "配方描述", "图标文件名",
    ]
    raw_rows, seen = [], set()
    for sid_str, menus in shift_menus.items():
        sid = int(sid_str)
        ev_id = shift_meta[sid]["EventId"]
        ch_id = shift_meta[sid]["CharacterId"]
        ev_title = event_map.get(str(ev_id), f"未知活动(ID:{ev_id})") if ev_id else "日常/无活动"
        char_name = char_map.get(str(ch_id), f"未知角色({ch_id})") if ch_id else "无"
        for menu in menus:
            seq, rid = menu["MenuSequenceNo"], menu["RecipeId"]
            seen.add(rid)
            rec = recipes.get(str(rid))
            if not rec: continue
            ing_names = [ingredients.get(str(i), {}).get("Name", f"未知({i})") for i in rec.get("IngredientIds", [])]
            raw_rows.append({
                "sort_key": (ev_id, sid, seq),
                "data": [ev_id, ev_title, rec.get("RecipeName", ""), char_name, shift_rel.get(sid, f"Shift-Raw{sid}"),
                         get_tier(rid), rec.get("Price", ""), rec.get("RequiredSecond", ""),
                         " / ".join(ing_names), clean_text(rec.get("RecipeMemo", "")), rec.get("RecipeFileName", "")],
            })

    for rid_str, rec in recipes.items():
        rid = int(rid_str)
        if rid not in seen:
            ev_id = rec.get("EventId", 0)
            ch_id = rec.get("RecommendCharacterId", 0)
            ev_title = event_map.get(str(ev_id), f"未知活动(ID:{ev_id})") if ev_id else "日常/无活动"
            char_name = char_map.get(str(ch_id), f"未知角色({ch_id})") if ch_id else "无"
            ing_names = [ingredients.get(str(i), {}).get("Name", f"未知({i})") for i in rec.get("IngredientIds", [])]
            raw_rows.append({
                "sort_key": (ev_id, 99999, rid),
                "data": [ev_id, ev_title, rec.get("RecipeName", ""), char_name, "无排班",
                         get_tier(rid), rec.get("Price", ""), rec.get("RequiredSecond", ""),
                         " / ".join(ing_names), clean_text(rec.get("RecipeMemo", "")), rec.get("RecipeFileName", "")],
            })

    raw_rows.sort(key=lambda x: x["sort_key"])
    rows_rec = [r["data"] for r in raw_rows]

    from openpyxl import Workbook
    out = xlsx_path('bar_data_complete.xlsx')
    wb = Workbook()
    ws1 = wb.active
    ws1.title = "Ingredients"
    ws1.append(headers_ing)
    for row in rows_ing: ws1.append(row)
    ws2 = wb.create_sheet(title="Recipes")
    ws2.append(headers_rec)
    for row in rows_rec: ws2.append(row)
    wb.save(out)
    print(f"  [xlsx] {out}")


def run():
    extract()
    export()
