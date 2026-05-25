import json
import re

# 配置文件名
#INPUT_JSON = 'master_data.json'
TARGET_CARD_ID = None  # 设置为 None 则会遍历所有卡牌并生成一个超大表

def main(input_json="master_data.json", output_json="All_Cards_Database.json"):
    print(f"[*] 正在加载数据库...")
    try:
        with open(input_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"[+] 数据库加载成功！")
    except Exception as e:
        print(f"[!] 错误: {e}")
        return

    print("[*] 正在构建全局关联字段映射表...")
    item_map = {}
    skill_effect_map = {}
    character_map = {}
    sp_effect_def_map = {}
    notice_list = []
    card_to_char_map = {}

    rarity_map = {1: "R", 2: "SR", 3: "SSR", 101: "XR"}
    attribute_map = {1: "日", 2: "月", 3: "星"}

    # 部门名称映射
    dept_map = {
        1: "本部", 2: "交際部", 3: "管理部", 
        4: "強行部", 5: "交渉部", 6: "特務部"
    }

    # 碎片颜色ID绝对映射表
    piece_map = {
        1: "サンピース（赤色）", 2: "サンピース（桃色）",
        3: "ムーンピース（空色）", 4: "ムーンピース（青色）",
        5: "スターピース（黄色）", 6: "スターピース（緑色）"
    }

    # 角色专属棋子颜色映射兜底表
    char_piece_map = {
        1: "サンピース（赤色）", 6: "サンピース（赤色）", 13: "サンピース（赤色）", 16: "サンピース（赤色）",
        4: "サンピース（桃色）", 10: "サンピース（桃色）", 19: "サンピース（桃色）",
        2: "ムーンピース（空色）", 7: "ムーンピース（空色）", 8: "ムーンピース（空色）",
        11: "ムーンピース（青色）", 17: "ムーンピース（青色）", 20: "ムーンピース（青色）", 21: "ムーンピース（青色）",
        3: "スターピース（黄色）", 5: "スターピース（黄色）", 9: "スターピース（黄色）",
        12: "スターピース（緑色）", 14: "スターピース（緑色）", 15: "スターピース（緑色）", 18: "スターピース（緑色）"
    }

    # 技能强度文本映射表
    magnitude_map = {
        1: "小", 2: "中", 3: "大", 4: "特大", 5: "超特大"
    }

    def pre_scan(obj):
        if isinstance(obj, dict):
            if 'CharacterCardId' in obj and 'CharacterId' in obj:
                card_to_char_map[obj['CharacterCardId']] = obj['CharacterId']

            if 'ItemId' in obj and 'ItemName' in obj:
                item_map[obj['ItemId']] = obj['ItemName']
            if 'CharacterId' in obj and 'CharacterNameJpn' in obj:
                character_map[obj['CharacterId']] = obj['CharacterNameJpn']
            if 'SpSkillEffectId' in obj and 'SkillEffect' in obj:
                sp_effect_def_map[obj['SpSkillEffectId']] = {
                    "SkillEffect": obj['SkillEffect'],
                    "SpSkillCategoryCodeList": obj.get('SpSkillCategoryCodeList', [])
                }
            if 'NoticeId' in obj and 'TitleName' in obj and 'FileDesc' in obj:
                notice_list.append((obj['TitleName'], obj['FileDesc']))

            if 'AutoSkillEffectId' in obj and 'SkillName' in obj:
                skill_effect_map[f"Auto_{obj['AutoSkillEffectId']}"] = {
                    "Name": obj['SkillName'], "Desc": obj.get('SkillDescription', '')
                }
            elif 'SkillEffectId' in obj and 'SkillName' in obj:
                skill_effect_map[f"Sp_{obj['SkillEffectId']}"] = {
                    "Name": obj['SkillName'], "Desc": obj.get('SkillDescription', '')
                }
            elif 'CombinationEffectId' in obj and 'SkillDescription' in obj:
                skill_effect_map[f"Combo_{obj['CombinationEffectId']}"] = {
                    "Name": obj.get('SkillEffect', f"Combo_{obj['CombinationEffectId']}"),
                    "Desc": obj.get('SkillDescription', '')
                }
            elif 'LeaderSkillEffectId' in obj and 'SkillDescription' in obj:
                skill_effect_map[f"Leader_{obj['LeaderSkillEffectId']}"] = {
                    "Name": obj.get('SkillName', f"Leader_{obj['LeaderSkillEffectId']}"),
                    "Desc": obj.get('SkillDescription', '')
                }

            for v in obj.values(): pre_scan(v)
        elif isinstance(obj, list):
            for item in obj: pre_scan(item)

    pre_scan(data)

    def format_skill_desc(template, values, char_id=None):
        if not template: return ""
        if template.startswith("text:{") and template.endswith("}"): 
            template = template[6:-1]
        
        # 1. 优先替换 Sprite 图标
        template = template.replace("<sprite name=piece_1><sprite name=piece_2>", "サンピース")
        template = template.replace("<sprite name=piece_3><sprite name=piece_4>", "ムーンピース")
        template = template.replace("<sprite name=piece_5><sprite name=piece_6>", "スターピース")
        
        # 2. 铲除官方叠词
        template = template.replace("サン属性ピースサンピース", "サンピース")
        template = template.replace("ムーン属性ピースムーンピース", "ムーンピース")
        template = template.replace("スター属性ピーススターピース", "スターピース")
        template = template.replace("サン属性ピース", "サンピース")
        template = template.replace("ムーン属性ピース", "ムーンピース")
        template = template.replace("スター属性ピース", "スターピース")
        template = template.replace("属性ピース", "ピース")
        
        # 3. 动态常量映射
        template = template.replace("combopiece_1", "コンボピース")
        template = template.replace("combopiece_2", "ダブルコンボピース")
        template = template.replace("combopiece_3", "トリプルコンボピース")
        template = re.sub(r'hiramekipiece_\d+', 'ひらめきピース', template)
        template = re.sub(r'combopiece_\d+', 'コンボピース', template)

        # 4. 根据传参映射变量占位符
        for i, val in enumerate(values):
            if val is not None:
                val_str = str(val)
                if f"skill_value{i+1}" in template:
                    template = template.replace(f"skill_value{i+1}", val_str)
                else:
                    if f"piece_value{i+1}" in template and isinstance(val, int) and val in piece_map:
                        template = template.replace(f"piece_value{i+1}", piece_map[val])
                    elif f"strength_value{i+1}" in template:
                        template = template.replace(f"strength_value{i+1}", magnitude_map.get(val, val_str))
                    elif f"group_value{i+1}" in template:
                        template = template.replace(f"group_value{i+1}", dept_map.get(val, val_str))
                    elif f"character_value{i+1}" in template:
                        template = template.replace(f"character_value{i+1}", character_map.get(val, val_str))
                        
        return template

    def extract_costs(obj):
        costs = []
        for i in range(1, 7):
            iid = obj.get(f'ItemId{i}', 0)
            count = obj.get(f'CostItemCount{i}', 0)
            if iid > 0 and count > 0:
                costs.append({"Item": item_map.get(iid, f"Item_{iid}"), "Count": count})
        return costs

    cards_db = {}
    def get_card(cid):
        if cid not in cards_db:
            cards_db[cid] = {"Meta": {}, "Stats": {}, "LeaderSkill": {}, "SpSkill": {}, "AutoSkill": {}, "Combination": {}, "Revision": {}, "UpgradeCosts": {"AutoSkill": {}, "SpSkill": {}, "Combination": {}, "Revision": {}}, "Story": [], "Assets": {}, "Voice": [], "Gacha": []}
        return cards_db[cid]

    def scan_obj(obj):
        if isinstance(obj, dict):
            cid = obj.get('CharacterCardId')
            if cid:
                card = get_card(cid)
                current_char_id = card_to_char_map.get(cid)

                if 'CharacterCardName' in obj:
                    card["Meta"].update({
                        "Name": obj.get('CharacterCardName'),
                        "CharId": obj.get('CharacterId'),
                        "CharName": character_map.get(obj.get('CharacterId'), f"Char_{obj.get('CharacterId')}"),
                        "Rarity": rarity_map.get(obj.get('CardRarityCode'), obj.get('CardRarityCode')),
                        "Attribute": attribute_map.get(obj.get('CardAttributeCode'), obj.get('CardAttributeCode')),
                        "CombiCharName": character_map.get(obj.get('CombiCharacterId'), f"Char_{obj.get('CombiCharacterId')}"),
                        "Release": obj.get('ReleaseDateTime')
                    })
                    card["SpSkill"]["Name"] = obj.get('SpSkillName')
                if 'AuraInitialValue' in obj:
                    card["Stats"] = {"Aura": {"Min": obj.get('AuraInitialValue'), "Max": obj.get('AuraMaxValue')}, "Visual": {"Min": obj.get('VisualInitialValue'), "Max": obj.get('VisualMaxValue')}, "Charisma": {"Min": obj.get('CharismaInitialValue'), "Max": obj.get('CharismaMaxValue')}             }
                
                if 'RevisionRank' in obj:
                    rank = obj['RevisionRank']
                    if 'AuraAdditionalValue' in obj:
                        card["Revision"][f"Rank{rank}"] = {
                            "Aura+": obj.get('AuraAdditionalValue', 0),
                            "Visual+": obj.get('VisualAdditionalValue', 0),
                            "Charisma+": obj.get('CharismaAdditionalValue', 0)
                        }
                    if 'ItemId1' in obj: card["UpgradeCosts"]["Revision"][f"Rank{rank}"] = extract_costs(obj)

                if 'LeaderSkillEffectId' in obj and 'SkillValue1' in obj:
                    effect_id = obj.get('LeaderSkillEffectId')
                    values = [obj.get(f'SkillValue{i}') for i in range(1, 7) if obj.get(f'SkillValue{i}') is not None]
                    effect_info = skill_effect_map.get(f"Leader_{effect_id}", {"Name": f"Leader_{effect_id}", "Desc": ""})
                    card["LeaderSkill"] = {"Name": effect_info["Name"], "Desc": format_skill_desc(effect_info["Desc"], values, current_char_id)}
                
                if 'SpSkillLevel' in obj and 'SkillDescription' in obj:
                    lv = obj['SpSkillLevel']
                    values = [obj.get(f'SkillValue{i}') for i in range(1, 7) if obj.get(f'SkillValue{i}', 0) > 0]
                    card["SpSkill"][f"Lv{lv}"] = {"Desc": format_skill_desc(obj.get('SkillDescription', ''), values, current_char_id), "Cost": obj.get('SkillCost')}
                    sp_effect_id = obj.get('SpSkillEffectId')
                    if sp_effect_id and sp_effect_id in sp_effect_def_map:
                        card["SpSkill"]["SkillEffect"] = sp_effect_def_map[sp_effect_id]["SkillEffect"]
                        card["SpSkill"]["SpSkillCategoryCodeList"] = sp_effect_def_map[sp_effect_id]["SpSkillCategoryCodeList"]
                
                if 'SpSkillWithCombiType' in obj:
                    card["SpSkill"]["CombiBonus"] = {"Desc": format_skill_desc(obj.get('SkillDescription', ''), [obj.get('SkillValue1')], current_char_id), "Value": obj.get('SkillValue1')}
                
                if 'AutoSkillLevel' in obj:
                    lv = obj['AutoSkillLevel']
                    if 'AutoSkillEffectId' in obj:
                        values = [obj.get(f'SkillValue{i}') for i in range(1, 4) if obj.get(f'SkillValue{i}') is not None]
                        effect_info = skill_effect_map.get(f"Auto_{obj.get('AutoSkillEffectId')}", {"Name": "Auto", "Desc": ""})
                        card["AutoSkill"][f"Lv{lv}"] = {"Name": effect_info["Name"], "Desc": format_skill_desc(effect_info["Desc"], values, current_char_id), "PieceCount": obj.get('PieceCount')}
                    if 'ItemId1' in obj: card["UpgradeCosts"]["AutoSkill"][f"Lv{lv}"] = extract_costs(obj)
                
                if 'CombinationLevel' in obj:
                    lv = obj['CombinationLevel']
                    if 'CombinationEffectId' in obj:
                        values = [obj.get(f'SkillValue{i}') for i in range(1, 7) if obj.get(f'SkillValue{i}') is not None]
                        effect_info = skill_effect_map.get(f"Combo_{obj.get('CombinationEffectId')}", {"Desc": ""})
                        card["Combination"][f"Lv{lv}"] = {"Desc": format_skill_desc(effect_info["Desc"], values, current_char_id)}
            
            if 'GachaName' in obj and 'CostumeIntroductionCharacterCardIds' in obj:
                for target_cid in obj['CostumeIntroductionCharacterCardIds']:
                    get_card(target_cid)["Gacha"].append(obj['GachaName'])

            for v in obj.values(): scan_obj(v)
        elif isinstance(obj, list):
            for item in obj: scan_obj(item)

    #print("[*] 正在执行深度扫描与数据缝合...")
    scan_obj(data)

    # ★ 新增：概率精确转译拦截器
    def apply_percentage_fix(desc, rarity):
        if not desc: return desc
        
        # 获取持续时间用于特殊平衡规则判定
        duration = 0
        m = re.search(r'(\d+)秒間', desc)
        if m: duration = int(m.group(1))
            
        # UP 转换
        desc = desc.replace("超特大アップ", "20%UP")
        desc = desc.replace("特大アップ", "14%UP")
        desc = desc.replace("大アップ", "12%UP")
        desc = desc.replace("中アップ", "10%UP")  
        desc = desc.replace("小アップ", "8%UP")
        
        # DOWN 转换
        desc = desc.replace("大ダウン", "4%DOWN")
        desc = desc.replace("中ダウン", "2%DOWN")
        desc = desc.replace("小ダウン", "1%DOWN")
        
        return desc

    #print("[*] 正在执行后处理: 填补协作占位符、精修概率并重定向XR卡活动...")
    color_regex = re.compile(r'(サンピース（赤色）|サンピース（桃色）|ムーンピース（空色）|ムーンピース（青色）|スターピース（黄色）|スターピース（緑色）)')

    for cid, card in cards_db.items():
        card["Gacha"] = list(dict.fromkeys(card["Gacha"]))
        rarity = card["Meta"].get("Rarity", "")
        
        # 1. 处理活动名溯源
        if str(cid) in ["160", "161"]:
            card["Meta"]["NoticeEvent"] = "2025 HAPPY NEW YEAR!"
        elif rarity in ["XR", "101", 101]:
            c_name = card["Meta"].get("Name", "")
            found_title = ""
            for title, desc in notice_list:
                if c_name and c_name in desc:
                    found_title = re.sub(r'^【.*?】', '', title).strip()
                    break
            card["Meta"]["NoticeEvent"] = found_title

        # 2. 精准上下文颜色提取
        card_sp_color = None
        sp_skill = card.get("SpSkill", {})
        for lv, sp_data in sp_skill.items():
            if lv.startswith("Lv") and "Desc" in sp_data:
                match = color_regex.search(sp_data["Desc"])
                if match:
                    card_sp_color = match.group(1)
                    break
                    
        # 3. 颜色安全兜底
        if not card_sp_color:
            attr = card.get("Meta", {}).get("Attribute", "")
            if attr == "日": card_sp_color = "サンピース（赤色）"
            elif attr == "月": card_sp_color = "ムーンピース（空色）"
            elif attr == "星": card_sp_color = "スターピース（黄色）"
            else: card_sp_color = "ピース"

        # 4. 主 SP 技能精修
        for lv, sp_data in sp_skill.items():
            if lv.startswith("Lv") and "Desc" in sp_data:
                sp_data["Desc"] = apply_percentage_fix(sp_data["Desc"], rarity)

        # 5. CombiBonus (协作SP) 精修
        combi_bonus = sp_skill.get("CombiBonus", {})
        if "Desc" in combi_bonus:
            desc = combi_bonus["Desc"]
            desc = re.sub(r'^さらに\s*', '', desc) # 切除协作头部的 さらに
            desc = re.sub(r'piece_value\d+', card_sp_color, desc) # 填补主属性颜色
            desc = apply_percentage_fix(desc, rarity)
            combi_bonus["Desc"] = desc

        # 6. AutoSkill 与 Combination 精修
        for lv, auto_data in card.get("AutoSkill", {}).items():
            if lv.startswith("Lv") and "Desc" in auto_data:
                desc = auto_data["Desc"]
                desc = re.sub(r'piece_value\d+', card_sp_color, desc)
                desc = apply_percentage_fix(desc, rarity)
                auto_data["Desc"] = desc
                
        for lv, combo_data in card.get("Combination", {}).items():
            if lv.startswith("Lv") and "Desc" in combo_data:
                desc = combo_data["Desc"]
                desc = re.sub(r'^さらに\s*', '', desc) # 切除协作头部的 さらに
                desc = re.sub(r'piece_value\d+', card_sp_color, desc)
                desc = apply_percentage_fix(desc, rarity)
                combo_data["Desc"] = desc
                
        # 7. 队长技能精修
        leader_skill = card.get("LeaderSkill", {})
        if "Desc" in leader_skill:
            leader_skill["Desc"] = apply_percentage_fix(leader_skill["Desc"], rarity)

    filename = f"Comprehensive_Card_{TARGET_CARD_ID}_Data.json" if TARGET_CARD_ID else "All_Cards_Database.json"
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(cards_db.get(TARGET_CARD_ID) if TARGET_CARD_ID else cards_db, f, ensure_ascii=False, indent=4)
    print(f"[+] 卡牌信息已保存至: {output_json}")

if __name__ == "__main__":
    main()