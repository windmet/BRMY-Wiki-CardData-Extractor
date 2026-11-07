import json

# 配置文件名
INPUT_JSON = 'master_data.json'
TARGET_CARD_ID = None  # 设置为 None 则会遍历所有卡牌并生成一个超大表

def main():
    print(f"[*] 正在加载数据库...")
    try:
        with open(INPUT_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"[+] 数据库加载成功！")
    except Exception as e:
        print(f"[!] 错误: {e}")
        return

    # 1. 建立临时关联映射表 (在内存中预扫描，不用输出到 JSON 中)
    print("[*] 正在构建全局关联字段映射表...")
    item_map = {}
    skill_effect_map = {}
    character_map = {}
    sp_effect_def_map = {} # 新增：SP技能全局效果及分类定义映射表

    rarity_map = {1: "R", 2: "SR", 3: "SSR", 101: "XR"} # 新增：支持 XR (101) 稀有度
    attribute_map = {1: "日", 2: "月", 3: "星"}

    def pre_scan(obj):
        if isinstance(obj, dict):
            # 道具映射
            if 'ItemId' in obj and 'ItemName' in obj:
                item_map[obj['ItemId']] = obj['ItemName']
            # 角色映射
            if 'CharacterId' in obj and 'CharacterNameJpn' in obj:
                character_map[obj['CharacterId']] = obj['CharacterNameJpn']
            
            # --- 新增：SP技能效果全局定义映射 (用于匹配 SpSkillCategoryCodeList) ---
            if 'SpSkillEffectId' in obj and 'SkillEffect' in obj:
                sp_effect_def_map[obj['SpSkillEffectId']] = {
                    "SkillEffect": obj['SkillEffect'],
                    "SpSkillCategoryCodeList": obj.get('SpSkillCategoryCodeList', [])
                }
            
            # --- 技能描述模板映射 (加入安全前缀防止ID互撞) ---
            # 自动技能
            if 'AutoSkillEffectId' in obj and 'SkillName' in obj:
                skill_effect_map[f"Auto_{obj['AutoSkillEffectId']}"] = {
                    "Name": obj['SkillName'],
                    "Desc": obj.get('SkillDescription', '')
                }
            # SP/普通技能
            elif 'SkillEffectId' in obj and 'SkillName' in obj:
                skill_effect_map[f"Sp_{obj['SkillEffectId']}"] = {
                    "Name": obj['SkillName'],
                    "Desc": obj.get('SkillDescription', '')
                }
            # 协作技能 (Combination)
            elif 'CombinationEffectId' in obj and 'SkillDescription' in obj:
                skill_effect_map[f"Combo_{obj['CombinationEffectId']}"] = {
                    "Name": obj.get('SkillEffect', f"Combo_{obj['CombinationEffectId']}"),
                    "Desc": obj.get('SkillDescription', '')
                }
            # 队长技能 (LeaderSkill)
            elif 'LeaderSkillEffectId' in obj and 'SkillDescription' in obj:
                skill_effect_map[f"Leader_{obj['LeaderSkillEffectId']}"] = {
                    "Name": obj.get('SkillName', f"Leader_{obj['LeaderSkillEffectId']}"),
                    "Desc": obj.get('SkillDescription', '')
                }

            for v in obj.values():
                pre_scan(v)
        elif isinstance(obj, list):
            for item in obj:
                pre_scan(item)

    pre_scan(data)

    # 2. 格式化描述文本的辅助函数 (自动去除 text:{} 并替换占位符)
    def format_skill_desc(template, values):
        if not template:
            return ""
        if template.startswith("text:{") and template.endswith("}"):
            template = template[6:-1]
        for i, val in enumerate(values):
            if val is not None:
                template = template.replace(f"skill_value{i+1}", str(val))
                template = template.replace(f"strength_value{i+1}", str(val))
        return template

    # 3. 提取升级材料的辅助函数 (自动将 ItemId 替换为 名字)
    def extract_costs(obj):
        costs = []
        for i in range(1, 7):
            iid = obj.get(f'ItemId{i}', 0)
            count = obj.get(f'CostItemCount{i}', 0)
            if iid > 0 and count > 0:
                item_name = item_map.get(iid, f"Item_{iid}")
                costs.append({"Item": item_name, "Count": count})
        return costs

    cards_db = {}

    def get_card(cid):
        if cid not in cards_db:
            cards_db[cid] = {
                "Meta": {},
                "Stats": {},
                "LeaderSkill": {},
                "SpSkill": {},
                "AutoSkill": {},
                "Combination": {},
                "Revision": {},
                "UpgradeCosts": {
                    "AutoSkill": {},
                    "SpSkill": {},
                    "Combination": {},
                    "Revision": {}
                },
                "Story": [],
                "Assets": {},
                "Voice": [],
                "Gacha": []
            }
        return cards_db[cid]

    # 4. 主递归扫描函数
    def scan_obj(obj):
        if isinstance(obj, dict):
            cid = obj.get('CharacterCardId')
            if cid:
                card = get_card(cid)
                
                # 1. 基础信息
                if 'CharacterCardName' in obj:
                    rarity_code = obj.get('CardRarityCode')
                    attr_code = obj.get('CardAttributeCode')
                    char_id = obj.get('CharacterId')
                    combi_id = obj.get('CombiCharacterId')

                    card["Meta"].update({
                        "Name": obj.get('CharacterCardName'),
                        "CharId": char_id,
                        "CharName": character_map.get(char_id, f"Char_{char_id}"),
                        "Rarity": rarity_map.get(rarity_code, rarity_code),
                        "Attribute": attribute_map.get(attr_code, attr_code),
                        "CombiCharId": combi_id,
                        "CombiCharName": character_map.get(combi_id, f"Char_{combi_id}"),
                        "Release": obj.get('ReleaseDateTime')
                    })
                    card["Assets"].update({
                        "Icon": obj.get('CharacterCardIconFileName'),
                        "Illust": obj.get('CharacterCardFileName'),
                        "LiveClip": obj.get('LiveClipFileName')
                    })
                    card["SpSkill"]["Name"] = obj.get('SpSkillName')

                # 2. 基础数值
                if 'AuraInitialValue' in obj:
                    card["Stats"] = {
                        "Aura": {"Min": obj.get('AuraInitialValue'), "Max": obj.get('AuraMaxValue')},
                        "Visual": {"Min": obj.get('VisualInitialValue'), "Max": obj.get('VisualMaxValue')},
                        "Charisma": {"Min": obj.get('CharismaInitialValue'), "Max": obj.get('CharismaMaxValue')}
                    }

                # 3. 队长技能 (完美动态组装)
                if 'LeaderSkillEffectId' in obj and 'SkillValue1' in obj:
                    effect_id = obj.get('LeaderSkillEffectId')
                    values = [obj.get(f'SkillValue{i}') for i in range(1, 7) if obj.get(f'SkillValue{i}') is not None]
                    
                    effect_info = skill_effect_map.get(f"Leader_{effect_id}", {"Name": f"Leader_{effect_id}", "Desc": ""})
                    formatted_desc = format_skill_desc(effect_info["Desc"], values)

                    card["LeaderSkill"] = {
                        "Name": effect_info["Name"],
                        "Desc": formatted_desc,
                        "Values": values
                    }

                # 4. SP技能等级数据
                if 'SpSkillLevel' in obj and 'SkillDescription' in obj:
                    lv = obj['SpSkillLevel']
                    desc_raw = obj.get('SkillDescription', '')
                    values = [obj.get(f'SkillValue{i}') for i in range(1, 7) if obj.get(f'SkillValue{i}', 0) > 0]
                    formatted_desc = format_skill_desc(desc_raw, values)

                    card["SpSkill"][f"Lv{lv}"] = {
                        "Desc": formatted_desc,
                        "Value": values,
                        "Cost": obj.get('SkillCost')
                    }
                    
                    # --- 新增：在SP等级块中根据 SpSkillEffectId 向 SpSkill 结构中回写效果分类信息 ---
                    sp_effect_id = obj.get('SpSkillEffectId')
                    if sp_effect_id:
                        effect_def = sp_effect_def_map.get(sp_effect_id)
                        if effect_def:
                            card["SpSkill"]["SkillEffect"] = effect_def["SkillEffect"]
                            card["SpSkill"]["SpSkillCategoryCodeList"] = effect_def["SpSkillCategoryCodeList"]
                
                # 5. SP技能联动(Combi)附加效果
                if 'SpSkillWithCombiType' in obj:
                    desc_raw = obj.get('SkillDescription', '')
                    val = obj.get('SkillValue1')
                    formatted_desc = format_skill_desc(desc_raw, [val])

                    card["SpSkill"]["CombiBonus"] = {
                        "Desc": formatted_desc,
                        "Value": val
                    }

                # 6. 自动技能
                if 'AutoSkillLevel' in obj:
                    lv = obj['AutoSkillLevel']
                    if 'AutoSkillEffectId' in obj: # 这是数值块
                        effect_id = obj.get('AutoSkillEffectId')
                        values = [obj.get(f'SkillValue{i}') for i in range(1, 4) if obj.get(f'SkillValue{i}') is not None]
                        
                        effect_info = skill_effect_map.get(f"Auto_{effect_id}", {"Name": f"Effect_{effect_id}", "Desc": ""})
                        formatted_desc = format_skill_desc(effect_info["Desc"], values)

                        card["AutoSkill"][f"Lv{lv}"] = {
                            "Name": effect_info["Name"],
                            "Desc": formatted_desc,
                            "PieceCount": obj.get('PieceCount')
                        }
                    if 'ItemId1' in obj: # 这是消耗块
                        card["UpgradeCosts"]["AutoSkill"][f"Lv{lv}"] = extract_costs(obj)

                # 7. 协作技能 (Combination) (完美动态组装)
                if 'CombinationLevel' in obj:
                    lv = obj['CombinationLevel']
                    if 'CombinationEffectId' in obj: # 这是数值块
                        effect_id = obj.get('CombinationEffectId')
                        values = [obj.get(f'SkillValue{i}') for i in range(1, 7) if obj.get(f'SkillValue{i}') is not None]
                        
                        effect_info = skill_effect_map.get(f"Combo_{effect_id}", {"Name": f"Combo_{effect_id}", "Desc": ""})
                        formatted_desc = format_skill_desc(effect_info["Desc"], values)
                        
                        card["Combination"][f"Lv{lv}"] = {
                            "Name": effect_info["Name"],
                            "Desc": formatted_desc,
                            "Values": values
                        }
                    if 'ItemId1' in obj: # 这是消耗块
                        card["UpgradeCosts"]["Combination"][f"Lv{lv}"] = extract_costs(obj)

                # 8. 界限突破 (Revision)
                if 'RevisionRank' in obj:
                    rank = obj['RevisionRank']
                    if 'AuraAdditionalValue' in obj: # 数值成长
                        card["Revision"][f"Rank{rank}"] = {
                            "Aura+": obj.get('AuraAdditionalValue'),
                            "Visual+": obj.get('VisualAdditionalValue'),
                            "Charisma+": obj.get('CharismaAdditionalValue')
                        }
                    if 'ItemId1' in obj: # 消耗
                        card["UpgradeCosts"]["Revision"][f"Rank{rank}"] = extract_costs(obj)

                # 9. 剧情信息
                if 'CharacterCardStorySectionNo' in obj:
                    story_entry = {
                        "Section": obj.get('CharacterCardStorySectionNo'),
                        "Advice": obj.get('PopupText', '')
                    }
                    if story_entry not in card["Story"]:
                        card["Story"].append(story_entry)

                # 10. SP技能升级消耗
                if 'SpSkillLevel' in obj and 'ItemId1' in obj:
                    card["UpgradeCosts"]["SpSkill"][f"Lv{obj['SpSkillLevel']}"] = extract_costs(obj)

            # 11. 卡池信息 (特殊处理，没有CharacterCardId但在数组里)
            if 'GachaName' in obj and 'CostumeIntroductionCharacterCardIds' in obj:
                for target_cid in obj['CostumeIntroductionCharacterCardIds']:
                    get_card(target_cid)["Gacha"].append(obj['GachaName'])

            # 递归
            for v in obj.values():
                scan_obj(v)
        elif isinstance(obj, list):
            for item in obj:
                scan_obj(item)

    print("[*] 正在执行深度扫描与数据缝合...")
    scan_obj(data)

    # 5. 后处理与优化 (去重、排序)
    print("[*] 正在优化导出的数据格式并执行后处理...")
    for cid, card in cards_db.items():
        card["Gacha"] = list(dict.fromkeys(card["Gacha"]))
        card["Story"].sort(key=lambda x: x["Section"])

    # 输出结果
    if TARGET_CARD_ID:
        result = cards_db.get(TARGET_CARD_ID)
        filename = f"Comprehensive_Card_{TARGET_CARD_ID}_Data.json"
    else:
        result = cards_db
        filename = "All_Cards_Database.json"

    if result:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=4)
        print(f"[+] 抓取完成！最全档案已保存至: {filename}")
    else:
        print("[!] 未找到目标卡牌。")

if __name__ == "__main__":
    main()