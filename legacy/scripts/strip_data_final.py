import json
import csv
import re

def extract_card_data(json_file_path, output_tsv_path):
    # 读取源JSON数据
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    # 定义表头
    headers = [
        "卡牌", "卡牌编号", "卡牌角色名", "卡牌名", "卡牌译名", "卡牌属性", "卡牌稀有度",
        "卡牌角色编号", "卡牌对应活动名", "卡牌获取方式", "综合力初始", "综合力满级",
        "气质初始", "气质满级", "外观初始", "外观满级", "魅力初始", "魅力满级", "队长技能",
        "自动技能分类", "自动技能Lv1", "自动技能Lv1碎片数", "自动技能满级", "自动技能满级碎片数",
        "SP技能名", "SP技能分类", "SP技能Lv1", "SP技能Lv1COST", "SP技能满级", "SP技能满级COST",
        "协作技对象", "协作SP技能效果", "协作效果Lv1", "协作效果满级", 
        "卡牌语音①J", "卡牌语音①C", "卡牌语音②J", "卡牌语音②C", "卡牌语音③J", "卡牌语音③C", 
        "卡牌技能语音J", "卡牌技能语音C", "卡牌协作语音J", "卡牌协作语音C", 
        "卡牌升级道具1", "卡牌升级道具2", "卡牌升级道具3"
    ]
    
    rows = []
    
    for card_id, card_info in data.items():
        meta = card_info.get("Meta", {})
        stats = card_info.get("Stats", {})
        
        # 1. 属性与综合力
        aura_min = stats.get("Aura", {}).get("Min", 0)
        aura_max = stats.get("Aura", {}).get("Max", 0)
        visual_min = stats.get("Visual", {}).get("Min", 0)
        visual_max = stats.get("Visual", {}).get("Max", 0)
        charisma_min = stats.get("Charisma", {}).get("Min", 0)
        charisma_max = stats.get("Charisma", {}).get("Max", 0)
        
        total_min = aura_min + visual_min + charisma_min
        total_max = aura_max + visual_max + charisma_max
        
        # 2. 队长技能
        leader_skill = card_info.get("LeaderSkill", {}).get("Desc", "").replace('\n', '')
        if not leader_skill:
            leader_skill = "/"
            
        # 3. 自动技能（定位Lv1与最高Lv）
        auto_skill = card_info.get("AutoSkill", {})
        auto_lv_keys = [k for k in auto_skill.keys() if k.startswith("Lv")]
        auto_lv_keys.sort(key=lambda x: int(x.replace("Lv", "")))
        auto_lv1 = auto_skill.get("Lv1", {})
        auto_lv_max = auto_skill.get(auto_lv_keys[-1], {}) if auto_lv_keys else {}
        
        # 4. SP技能（定位Lv1与最高Lv）
        sp_skill = card_info.get("SpSkill", {})
        sp_lv_keys = [k for k in sp_skill.keys() if k.startswith("Lv")]
        sp_lv_keys.sort(key=lambda x: int(x.replace("Lv", "")))
        sp_lv1 = sp_skill.get("Lv1", {})
        sp_lv_max = sp_skill.get(sp_lv_keys[-1], {}) if sp_lv_keys else {}
        
        # --- 提取 SP 技能分类（同步兼容格式化输出） ---
        sp_effect_str = sp_skill.get("SkillEffect", "")
        sp_category_codes = sp_skill.get("SpSkillCategoryCodeList", [])
        if sp_category_codes:
            codes_str = ",".join(map(str, sp_category_codes))
            sp_skill_category = f"{sp_effect_str} ({codes_str})" if sp_effect_str else codes_str
        else:
            sp_skill_category = sp_effect_str if sp_effect_str else "/"
        
        # 5. 协作技能（定位Lv1与最高Lv）
        combi = card_info.get("Combination", {})
        combi_lv_keys = [k for k in combi.keys() if k.startswith("Lv")]
        combi_lv_keys.sort(key=lambda x: int(x.replace("Lv", "")))
        combi_lv1 = combi.get("Lv1", {})
        combi_lv_max = combi.get(combi_lv_keys[-1], {}) if combi_lv_keys else {}
        
        # 6. 获取碎片所需数辅助函数
        attribute = meta.get("Attribute", "")
        def format_piece_count(count):
            if count == "" or count is None:
                return "/"
            return f"{attribute}属性碎片*{count}"
            
        # 7. 协作角色名与描述
        combi_char_name = meta.get("CombiCharName", "")
        if combi_char_name == "Char_0" or not combi_char_name:
            combi_char_name = "/"
            
        combi_sp_desc = sp_skill.get("CombiBonus", {}).get("Desc", "").replace('\n', '')
        if not combi_sp_desc: combi_sp_desc = "/"
        
        combi_lv1_desc = combi_lv1.get("Desc", "").replace('\n', '')
        if not combi_lv1_desc: combi_lv1_desc = "/"
            
        combi_lv_max_desc = combi_lv_max.get("Desc", "").replace('\n', '')
        if not combi_lv_max_desc: combi_lv_max_desc = "/"

        # 8. 获取个人专属突破材料
        items = []
        upgrade_costs = card_info.get("UpgradeCosts", {})
        for category in upgrade_costs.values():
            if not isinstance(category, dict):
                continue
            for level in category.values():
                if not isinstance(level, list):
                    continue
                for cost in level:
                    item_name = cost.get("Item", "")
                    if item_name and "エッセンス" not in item_name and "サプリ" not in item_name and "キー" not in item_name and "カクテル" not in item_name:
                        if item_name not in items:
                            items.append(item_name)
        
        item1 = items[0] if len(items) > 0 else ""
        item2 = items[1] if len(items) > 1 else ""
        item3 = items[2] if len(items) > 2 else ""

        # 9. 来源与活动名提取 (修复层级：Gacha 实际挂载在 card_info 根节点，而非 Meta 内部)
        gacha_arr = card_info.get("Gacha", [])
        acq_method = "活动卡池" if gacha_arr else ""

        # --- 新增：主卡池名称过滤提取逻辑 ---
        gacha_event_name = ""
        if gacha_arr:
            # 优先在可能存在的卡池列表中寻找带有方括号 `[...]` 的主活动卡池，排除普通的生日池等
            main_gacha = None
            for g in gacha_arr:
                if "[" in g and "]" in g:
                    main_gacha = g
                    break
            if not main_gacha:
                main_gacha = gacha_arr[0]
            
            # 使用正则抓取方括号内的主活动名，去掉单独UP的角色后缀
            match = re.search(r'(\[.*?\])', main_gacha)
            if match:
                gacha_event_name = match.group(1)
            else:
                gacha_event_name = main_gacha

        # 构建本行数据
        row = [
            f"card_{card_id}",                                  # 卡牌
            card_id,                                            # 卡牌编号
            meta.get("CharName", ""),                           # 卡牌角色名
            meta.get("Name", ""),                               # 卡牌名
            "",                                                 # 卡牌译名
            attribute,                                          # 卡牌属性
            meta.get("Rarity", ""),                             # 卡牌稀有度 (由 test.py 映射产出)
            meta.get("CharId", ""),                             # 卡牌角色编号
            gacha_event_name,                                   # 卡牌对应活动名 (更新)
            acq_method,                                         # 卡牌获取方式 (更新)
            total_min,                                          # 综合力初始
            total_max,                                          # 综合力满级
            aura_min,                                           # 气质初始
            aura_max,                                           # 气质满级
            visual_min,                                         # 外观初始
            visual_max,                                         # 外观满级
            charisma_min,                                       # 魅力初始
            charisma_max,                                       # 魅力满级
            leader_skill,                                       # 队长技能
            auto_lv1.get("Name", "/"),                          # 自动技能分类
            auto_lv1.get("Desc", "").replace('\n', ''),         # 自动技能Lv1
            format_piece_count(auto_lv1.get("PieceCount", "")), # 自动技能Lv1碎片数
            auto_lv_max.get("Desc", "").replace('\n', ''),      # 自动技能满级
            format_piece_count(auto_lv_max.get("PieceCount", "")), # 自动技能满级碎片数
            sp_skill.get("Name", ""),                           # SP技能名
            sp_skill_category,                                  # SP技能分类 (更新)
            sp_lv1.get("Desc", "").replace('\n', ''),           # SP技能Lv1
            sp_lv1.get("Cost", ""),                             # SP技能Lv1COST
            sp_lv_max.get("Desc", "").replace('\n', ''),        # SP技能满级
            sp_lv_max.get("Cost", ""),                          # SP技能满级COST
            combi_char_name,                                    # 协作技对象
            combi_sp_desc,                                      # 协作SP技能效果
            combi_lv1_desc,                                     # 协作效果Lv1
            combi_lv_max_desc,                                  # 协作效果满级
            "", "", "", "", "", "", "", "", "", "",             # 语音及翻译留空
            item1, item2, item3                                 # 卡牌升级道具1~3
        ]
        
        rows.append(row)
        
    # 保存为tsv文件
    with open(output_tsv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(headers)
        writer.writerows(rows)
        
    print(f"解析完成！数据已成功提取并保存至: {output_tsv_path}")

# 执行脚本
extract_card_data('All_Cards_Database.json', 'cards_data.tsv')