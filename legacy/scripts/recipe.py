import json

INPUT_JSON = 'master_data.json'
OUTPUT_JSON = 'bar_extract.json'

def main():
    print(f"[*] 正在加载数据库 {INPUT_JSON}...")
    try:
        with open(INPUT_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"[+] 数据库加载成功！")
    except Exception as e:
        print(f"[!] 错误: {e}")
        return

    character_map = {}
    event_map = {}
    ingredients = {}
    recipes = {}
    shift_menus = {} # 新增：存储排班与配方的映射关系

    # 第一遍扫描：收集基础映射与材料字典
    def pre_scan(obj):
        if isinstance(obj, dict):
            if 'CharacterId' in obj and 'CharacterNameJpn' in obj:
                character_map[obj['CharacterId']] = obj['CharacterNameJpn']
                
            # 【修复1】将 EventName 修正为 EventTitle
            if 'EventId' in obj and 'EventTitle' in obj:
                event_map[obj['EventId']] = obj['EventTitle']
            
            # 抓取 Ingredient (摇酒专属材料)
            if 'IngredientId' in obj and 'IngredientName' in obj:
                iid = obj['IngredientId']
                ingredients[iid] = {
                    "Id": iid,
                    "Name": obj.get('IngredientName', ''),
                    "Desc": obj.get('IngredientDescription', ''),
                    "Icon": obj.get('IngredientFileName', '')
                }
                
            # 【新增】抓取排班与菜单序号的关联关系
            if 'ShiftId' in obj and 'MenuSequenceNo' in obj and 'RecipeId' in obj:
                sid = obj['ShiftId']
                if sid not in shift_menus:
                    shift_menus[sid] = []
                shift_menus[sid].append({
                    "MenuSequenceNo": obj['MenuSequenceNo'],
                    "RecipeId": obj['RecipeId']
                })
            
            for v in obj.values(): pre_scan(v)
        elif isinstance(obj, list):
            for item in obj: pre_scan(item)

    print("[*] 正在构建酒吧材料、排班映射与全局映射表...")
    pre_scan(data)
    print(f"[+] 发现 {len(ingredients)} 种材料, {len(shift_menus)} 个排班记录.")

    # 第二遍扫描：抓取配方(Recipe)数据
    def scan_recipes(obj):
        if isinstance(obj, dict):
            if 'RecipeId' in obj and 'RecipeName' in obj and 'IngredientIds' in obj:
                rid = obj['RecipeId']
                recipes[rid] = {
                    "RecipeId": rid,
                    "RecipeName": obj.get('RecipeName', ''),
                    "RecipeMemo": obj.get('RecipeMemo', ''),
                    "EventId": obj.get('EventId', 0),
                    "RecommendCharacterId": obj.get('RecommendCharacterId', 0),
                    "Price": obj.get('Price', 0),
                    "RequiredSecond": obj.get('RequiredSecond', 0),
                    "RecipeDifficulty": obj.get('RecipeDifficulty', 1),
                    "IngredientIds": obj.get('IngredientIds', []), 
                    "RecipeFileName": obj.get('RecipeFileName', '')
                }
            for v in obj.values(): scan_recipes(v)
        elif isinstance(obj, list):
            for item in obj: scan_recipes(item)

    print("[*] 正在执行配方数据深度提取...")
    scan_recipes(data)

    # 汇总输出
    extracted_data = {
        "EventMap": event_map,
        "CharacterMap": character_map,
        "Ingredients": ingredients,
        "Recipes": recipes,
        "ShiftMenus": shift_menus
    }

    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(extracted_data, f, ensure_ascii=False, indent=4)

    print(f"[+] 提取完成！共找到 {len(recipes)} 个配方数据。")
    print(f"[+] 数据已保存至: {OUTPUT_JSON}")

if __name__ == "__main__":
    main()