import json
import re
from openpyxl import Workbook

def extract_card_data(json_file_path, output_xlsx_path):
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
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
    
    sorted_cids = sorted(data.keys(), key=lambda x: int(x))
    release_events = {}
    processed_cards = []
    
    # 第一遍扫描
    for cid in sorted_cids:
        card_info = data[cid]
        meta = card_info.get("Meta", {})
        gacha_arr = card_info.get("Gacha", [])
        raw_event_name = ""
        acq_method = ""
        
        if gacha_arr:
            birthday_pools = [g for g in gacha_arr if "バースデー" in g]
            if birthday_pools:
                acq_method = "生日限定"
                raw_event_name = birthday_pools[0]
            else:
                bracket_pool = None
                for g in gacha_arr:
                    m = re.search(r'\[(.*?)\]', g)
                    if m:
                        bracket_pool = m.group(1)
                        break
                
                if bracket_pool:
                    raw_event_name = bracket_pool
                else:
                    main_candidates = [g for g in gacha_arr if "Spotlights" not in g and "PU" not in g and "確定" not in g and "有償" not in g]
                    if main_candidates:
                        main_candidates.sort(key=len)
                        raw_event_name = main_candidates[0]
                    else:
                        raw_event_name = gacha_arr[0]
                
                raw_event_name = re.sub(r'\s*Spotlights.*', '', raw_event_name).strip()
                raw_event_name = re.sub(r'\s*PU.*', '', raw_event_name).strip()
                
                if "Anniversary" in raw_event_name:
                    acq_method = "周年卡池"
                else:
                    acq_method = "活动卡池"
                    
            if acq_method in ["活动卡池", "周年卡池"]:
                release_time = meta.get("Release", "")
                if release_time:
                    release_events[release_time] = raw_event_name
        
        processed_cards.append({
            "cid": cid, "card_id_int": int(cid), "meta": meta, "card_info": card_info,
            "has_gacha": bool(gacha_arr), "raw_event_name": raw_event_name,
            "acq_method": acq_method, "release_time": meta.get("Release", ""),
            "is_xr": str(meta.get("Rarity")) == "XR" or str(meta.get("Rarity")) == "101",
            "notice_event": meta.get("NoticeEvent", ""), "rarity": str(meta.get("Rarity"))
        })

    # 第二遍推演
    stop_inferring = False
    last_valid_event = ""
    rows = []
    
    for c in processed_cards:
        if c["card_id_int"] > 63 and c["rarity"] == "SSR" and not c["has_gacha"] and not c["is_xr"]:
            stop_inferring = True
            
        if stop_inferring:
            c["acq_method"] = ""
            c["raw_event_name"] = ""
        else:
            if c["card_id_int"] <= 63:
                c["acq_method"] = "常驻"
            else:
                if not c["has_gacha"]:
                    if c["is_xr"]:
                        c["acq_method"] = "活动报酬"
                        c["raw_event_name"] = c["notice_event"] if c["notice_event"] else release_events.get(c["release_time"], last_valid_event)
                    else:
                        c["acq_method"] = "活动报酬"
                        c["raw_event_name"] = release_events.get(c["release_time"], last_valid_event)
                else:
                    if c["acq_method"] not in ["生日限定", "常驻"]:
                        last_valid_event = c["raw_event_name"]

        card_id = c["cid"]
        card_info = c["card_info"]
        meta = c["meta"]
        stats = card_info.get("Stats", {})
        
        aura_min = stats.get("Aura", {}).get("Min", 0)
        aura_base_max = stats.get("Aura", {}).get("Max", 0)
        visual_min = stats.get("Visual", {}).get("Min", 0)
        visual_base_max = stats.get("Visual", {}).get("Max", 0)
        charisma_min = stats.get("Charisma", {}).get("Min", 0)
        charisma_base_max = stats.get("Charisma", {}).get("Max", 0)

        revisions = card_info.get("Revision", {})
        aura_bonus = sum(r.get("Aura+", 0) for r in revisions.values())
        visual_bonus = sum(r.get("Visual+", 0) for r in revisions.values())
        charisma_bonus = sum(r.get("Charisma+", 0) for r in revisions.values())

        aura_max = aura_base_max + aura_bonus
        visual_max = visual_base_max + visual_bonus
        charisma_max = charisma_base_max + charisma_bonus
        
        total_min = aura_min + visual_min + charisma_min
        total_max = aura_max + visual_max + charisma_max
        
        leader_skill = card_info.get("LeaderSkill", {}).get("Desc", "").replace('\n', '') or "/"
        auto_skill = card_info.get("AutoSkill", {})
        auto_lv_keys = sorted([k for k in auto_skill.keys() if k.startswith("Lv")], key=lambda x: int(x.replace("Lv", "")))
        auto_lv1 = auto_skill.get("Lv1", {})
        auto_lv_max = auto_skill.get(auto_lv_keys[-1], {}) if auto_lv_keys else {}
        
        sp_skill = card_info.get("SpSkill", {})
        sp_lv_keys = sorted([k for k in sp_skill.keys() if k.startswith("Lv")], key=lambda x: int(x.replace("Lv", "")))
        sp_lv1 = sp_skill.get("Lv1", {})
        sp_lv_max = sp_skill.get(sp_lv_keys[-1], {}) if sp_lv_keys else {}
        sp_effect_str = sp_skill.get("SkillEffect", "")
        sp_skill_category = sp_effect_str if sp_effect_str else "/"
        
        combi = card_info.get("Combination", {})
        combi_lv_keys = sorted([k for k in combi.keys() if k.startswith("Lv")], key=lambda x: int(x.replace("Lv", "")))
        combi_lv1 = combi.get("Lv1", {})
        combi_lv_max = combi.get(combi_lv_keys[-1], {}) if combi_lv_keys else {}
        
        attr = meta.get("Attribute", "")
        def fmt_piece(cnt): return f"{attr}属性碎片*{cnt}" if cnt else "/"

        items = []
        for cat in card_info.get("UpgradeCosts", {}).values():
            if isinstance(cat, dict):
                for lv in cat.values():
                    if isinstance(lv, list):
                        for cost in lv:
                            it = cost.get("Item", "")
                            if it and "エッセンス" not in it and "サプリ" not in it and "キー" not in it and "カクテル" not in it:
                                if it not in items: items.append(it)
        
        row = [
            f"card_{card_id}", card_id, meta.get("CharName", ""), meta.get("Name", ""), "",
            attr, meta.get("Rarity", ""), meta.get("CharId", ""), 
            c["raw_event_name"], c["acq_method"], 
            total_min, total_max, 
            aura_min, aura_max, 
            visual_min, visual_max, 
            charisma_min, charisma_max,
            leader_skill, auto_lv1.get("Name", "/"), auto_lv1.get("Desc", "").replace('\n', ''),
            fmt_piece(auto_lv1.get("PieceCount", "")), auto_lv_max.get("Desc", "").replace('\n', ''),
            fmt_piece(auto_lv_max.get("PieceCount", "")), sp_skill.get("Name", ""), sp_skill_category,
            sp_lv1.get("Desc", "").replace('\n', ''), sp_lv1.get("Cost", ""),
            sp_lv_max.get("Desc", "").replace('\n', ''), sp_lv_max.get("Cost", ""),
            meta.get("CombiCharName", "/") if meta.get("CombiCharName") != "Char_0" else "/",
            sp_skill.get("CombiBonus", {}).get("Desc", "/").replace('\n', ''),
            combi_lv1.get("Desc", "/").replace('\n', ''), combi_lv_max.get("Desc", "/").replace('\n', ''),
            "", "", "", "", "", "", "", "", "", "",
            items[0] if len(items) > 0 else "", items[1] if len(items) > 1 else "", items[2] if len(items) > 2 else ""
        ]
        rows.append(row)
        
    # 纯原生 Excel 构建逻辑
    wb = Workbook()
    ws = wb.active
    ws.title = "cards_data"
    ws.append(headers)
    
    for row in rows:
        cleaned_row = []
        for item in row:
            if isinstance(item, str) and item.isdigit():
                cleaned_row.append(int(item)) # 转化为纯数字，方便后续Excel计算
            else:
                cleaned_row.append(item)
        ws.append(cleaned_row)
        
    wb.save(output_xlsx_path)
    print(f"[+] Excel 原生格式 (.xlsx) 已生成至: {output_xlsx_path}")

def main(input_json="All_Cards_Database.json", output_xlsx="cards_data.xlsx"):
    extract_card_data(input_json, output_xlsx)

if __name__ == "__main__":
    main()