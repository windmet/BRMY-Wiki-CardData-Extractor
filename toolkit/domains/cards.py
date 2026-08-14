"""卡牌数据提取 + 导出。

这是最复杂的域，包含：
- 全局映射预扫描（道具、技能效果、角色、公告）
- 卡牌数据深扫描
- 后处理：概率精修、颜色匹配、活动溯源、获取方式推断
"""
import re

from ..core.scanner import load_json, save_json
from ..core.exporter import write_xlsx, json_path, xlsx_path
from ..core.tables import TableCatalog
from ..core.data import (
    RARITY_MAP, ATTRIBUTE_MAP, DEPT_MAP, PIECE_MAP, MAGNITUDE_MAP,
)
from .card_relations import enrich_card_relations
from .card_export import build_card_sheet
from .audio import CARD_CUE_ORDER, scan_card_voices

INPUT_JSON = 'master_data.json'
PIECE_COLOR_RE = re.compile(
    r'(サンピース（赤色）|サンピース（桃色）|ムーンピース（空色）|ムーンピース（青色）|スターピース（黄色）|スターピース（緑色）)'
)


def skill_values(obj, count=6):
    """Keep original SkillValue indexes so sparse future rows cannot shift values."""
    return {index: obj.get(f"SkillValue{index}") for index in range(1, count + 1)}


def format_skill_desc(template, values, character_map=None):
    if not template:
        return ""
    if template.startswith("text:{") and template.endswith("}"):
        template = template[6:-1]

    template = template.replace("<sprite name=piece_1><sprite name=piece_2>", "サンピース")
    template = template.replace("<sprite name=piece_3><sprite name=piece_4>", "ムーンピース")
    template = template.replace("<sprite name=piece_5><sprite name=piece_6>", "スターピース")
    template = template.replace("サン属性ピースサンピース", "サンピース")
    template = template.replace("ムーン属性ピースムーンピース", "ムーンピース")
    template = template.replace("スター属性ピーススターピース", "スターピース")
    template = template.replace("サン属性ピース", "サンピース")
    template = template.replace("ムーン属性ピース", "ムーンピース")
    template = template.replace("スター属性ピース", "スターピース")
    template = template.replace("属性ピース", "ピース")
    template = template.replace("combopiece_1", "コンボピース")
    template = template.replace("combopiece_2", "ダブルコンボピース")
    template = template.replace("combopiece_3", "トリプルコンボピース")
    template = re.sub(r'hiramekipiece_\d+', 'ひらめきピース', template)
    template = re.sub(r'combopiece_\d+', 'コンボピース', template)

    indexed_values = values.items() if hasattr(values, "items") else enumerate(values, start=1)
    character_map = character_map or {}
    for index, val in indexed_values:
        if val is None:
            continue
        val_str = str(val)
        key = f"skill_value{index}"
        if key in template:
            template = template.replace(key, val_str)
        elif f"piece_value{index}" in template and isinstance(val, int) and val in PIECE_MAP:
            template = template.replace(f"piece_value{index}", PIECE_MAP[val])
        elif f"strength_value{index}" in template:
            template = template.replace(f"strength_value{index}", MAGNITUDE_MAP.get(val, val_str))
        elif f"group_value{index}" in template:
            template = template.replace(f"group_value{index}", DEPT_MAP.get(val, val_str))
        elif f"character_value{index}" in template:
            template = template.replace(f"character_value{index}", character_map.get(val, val_str))
    return template


def extract(audio_dir=None, session=None):
    data = session.data if session else load_json(INPUT_JSON)
    tables = session.tables if session else TableCatalog(data)

    # ============ 预扫描：全局映射表 ============
    item_map = {}
    skill_effect_map = {}
    character_map = {}
    sp_effect_def_map = {}
    notice_list = []
    card_home_voice_map = {}

    main_card_rows = tables.require('mst_character_card')
    mapping_rows = (
        tables.require('mst_home_voice')
        + tables.require('mst_item')
        + tables.require('mst_character')
        + tables.rows('mst_character_collaboration')
        + tables.require('mst_sp_skill_effect')
        + tables.require('mst_notice')
        + tables.require('mst_auto_skill_effect')
        + tables.require('mst_combination_effect')
        + tables.require('mst_leader_skill_effect')
    )
    for obj in mapping_rows:
        if obj.get('HomeVoiceTypeCode') == 2 and obj.get('HomeVoiceTargetId') and obj.get('VoiceCueName'):
            card_id = obj['HomeVoiceTargetId']
            card_home_voice_map.setdefault(card_id, {})[obj['VoiceCueName']] = {
                "CueName": obj['VoiceCueName'],
                "HomeVoiceNo": obj.get('HomeVoiceNo'),
                "HomeVoiceCategory": obj.get('HomeVoiceCategory'),
                "KeyTargetValue": obj.get('KeyTargetValue'),
                "TimeDivisionId": obj.get('TimeDivisionId'),
                "IsActive": obj.get('IsActive'),
                "MotionCharacterId": obj.get('MotionCharacterId'),
                "Title": "",
                "Text": "",
                "TextHtml": "",
                "HasText": False,
                "AcbFile": "",
            }
        if 'ItemId' in obj and 'ItemName' in obj:
            item_map[obj['ItemId']] = obj['ItemName']
        if 'CharacterId' in obj and 'CharacterNameJpn' in obj:
            character_map[obj['CharacterId']] = obj['CharacterNameJpn']
        if 'SpSkillEffectId' in obj and 'SkillEffect' in obj:
            sp_effect_def_map[obj['SpSkillEffectId']] = {
                "SkillEffect": obj['SkillEffect'],
                "SpSkillCategoryCodeList": obj.get('SpSkillCategoryCodeList', []),
            }
        if 'NoticeId' in obj and 'TitleName' in obj and 'FileDesc' in obj:
            notice_list.append((obj['TitleName'], obj['FileDesc']))
        if 'AutoSkillEffectId' in obj and 'SkillName' in obj:
            skill_effect_map[f"Auto_{obj['AutoSkillEffectId']}"] = {
                "Name": obj['SkillName'], "Desc": obj.get('SkillDescription', ''),
            }
        elif 'SkillEffectId' in obj and 'SkillName' in obj:
            skill_effect_map[f"Sp_{obj['SkillEffectId']}"] = {
                "Name": obj['SkillName'], "Desc": obj.get('SkillDescription', ''),
            }
        elif 'CombinationEffectId' in obj and 'SkillDescription' in obj:
            skill_effect_map[f"Combo_{obj['CombinationEffectId']}"] = {
                "Name": obj.get('SkillEffect', f"Combo_{obj['CombinationEffectId']}"),
                "Desc": obj.get('SkillDescription', ''),
            }
        elif 'LeaderSkillEffectId' in obj and 'SkillDescription' in obj:
            skill_effect_map[f"Leader_{obj['LeaderSkillEffectId']}"] = {
                "Name": obj.get('SkillName', f"Leader_{obj['LeaderSkillEffectId']}"),
                "Desc": obj.get('SkillDescription', ''),
            }

    def extract_costs(obj):
        costs = []
        for i in range(1, 7):
            iid = obj.get(f'ItemId{i}', 0)
            count = obj.get(f'CostItemCount{i}', 0)
            if iid > 0 and count > 0:
                costs.append({"Item": item_map.get(iid, f"Item_{iid}"), "Count": count})
        return costs

    # ============ 主扫描：卡牌数据 ============
    cards_db = {}

    def get_card(cid):
        if cid not in cards_db:
            cards_db[cid] = {
                "Meta": {}, "Stats": {}, "LeaderSkill": {}, "SpSkill": {},
                "AutoSkill": {}, "Combination": {}, "Revision": {},
                "UpgradeCosts": {"AutoSkill": {}, "SpSkill": {}, "Combination": {}, "Revision": {}},
                "Story": [], "Assets": {}, "Voice": [], "Gacha": [],
                "Raw": {}, "Relations": {}, "Acquisition": {},
            }
        return cards_db[cid]

    card_rows = (
        main_card_rows
        + tables.require('mst_character_card_parameter')
        + tables.require('mst_character_card_revision')
        + tables.require('mst_item_card_revision')
        + tables.require('mst_character_card_leader_skill')
        + tables.require('mst_character_card_sp_skill_level')
        + tables.require('mst_item_card_sp_skill_level_up')
        + tables.require('mst_character_card_sp_skill_with_combi')
        + tables.require('mst_character_card_auto_skill_level')
        + tables.require('mst_item_card_auto_skill_level_up')
        + tables.require('mst_character_card_combination_level')
        + tables.require('mst_item_card_combination_level_up')
    )
    for obj in card_rows:
        cid = obj.get('CharacterCardId')
        if not cid:
            continue
        card = get_card(cid)
        if 'CharacterCardName' in obj:
            card["Raw"] = dict(obj)
            card["Meta"].update({
                "Name": obj.get('CharacterCardName'),
                "CharId": obj.get('CharacterId'),
                "CharName": character_map.get(obj.get('CharacterId'), f"Char_{obj.get('CharacterId')}"),
                "Rarity": RARITY_MAP.get(obj.get('CardRarityCode'), obj.get('CardRarityCode')),
                "RarityCode": obj.get('CardRarityCode'),
                "Attribute": ATTRIBUTE_MAP.get(obj.get('CardAttributeCode'), obj.get('CardAttributeCode')),
                "AttributeCode": obj.get('CardAttributeCode'),
                "RouteCode": obj.get('CardRouteCode'),
                "CombiCharName": character_map.get(obj.get('CombiCharacterId'), f"Char_{obj.get('CombiCharacterId')}"),
                "Release": obj.get('ReleaseDateTime'),
            })
            card["Assets"] = {
                "CardIcon": obj.get('CharacterCardIconFileName', ''),
                "CardIllustration": obj.get('CharacterCardFileName', ''),
                "LiveClip": obj.get('LiveClipFileName', ''),
                "SpSkillEffect": obj.get('SpSkillEffectFileName', ''),
                "VoiceCueSheet": obj.get('VoiceCueSheetName', ''),
            }
            card["SpSkill"]["Name"] = obj.get('SpSkillName')

        if 'AuraInitialValue' in obj:
            card["Stats"] = {
                "Aura": {"Min": obj.get('AuraInitialValue'), "Max": obj.get('AuraMaxValue')},
                "Visual": {"Min": obj.get('VisualInitialValue'), "Max": obj.get('VisualMaxValue')},
                "Charisma": {"Min": obj.get('CharismaInitialValue'), "Max": obj.get('CharismaMaxValue')},
            }

        if 'RevisionRank' in obj:
            rank = obj['RevisionRank']
            if 'AuraAdditionalValue' in obj:
                card["Revision"][f"Rank{rank}"] = {
                    "Aura+": obj.get('AuraAdditionalValue', 0),
                    "Visual+": obj.get('VisualAdditionalValue', 0),
                    "Charisma+": obj.get('CharismaAdditionalValue', 0),
                }
            if 'ItemId1' in obj:
                card["UpgradeCosts"]["Revision"][f"Rank{rank}"] = extract_costs(obj)

        if 'LeaderSkillEffectId' in obj:
            effect_id = obj.get('LeaderSkillEffectId')
            values = skill_values(obj)
            effect_info = skill_effect_map.get(f"Leader_{effect_id}", {"Name": f"Leader_{effect_id}", "Desc": ""})
            card["LeaderSkill"] = {
                "Name": effect_info["Name"],
                "Desc": format_skill_desc(effect_info["Desc"], values, character_map),
            }

        if 'SpSkillLevel' in obj and 'SkillDescription' in obj:
            lv = obj['SpSkillLevel']
            values = skill_values(obj)
            card["SpSkill"][f"Lv{lv}"] = {
                "Desc": format_skill_desc(obj.get('SkillDescription', ''), values, character_map),
                "Cost": obj.get('SkillCost'),
            }
            sp_effect_id = obj.get('SpSkillEffectId')
            if sp_effect_id and sp_effect_id in sp_effect_def_map:
                card["SpSkill"]["SkillEffect"] = sp_effect_def_map[sp_effect_id]["SkillEffect"]
                card["SpSkill"]["SpSkillCategoryCodeList"] = sp_effect_def_map[sp_effect_id]["SpSkillCategoryCodeList"]
        if 'SpSkillLevel' in obj and 'ItemId1' in obj:
            card["UpgradeCosts"]["SpSkill"][f"Lv{obj['SpSkillLevel']}"] = extract_costs(obj)

        if 'SpSkillWithCombiType' in obj:
            card["SpSkill"]["CombiBonus"] = {
                "Desc": format_skill_desc(obj.get('SkillDescription', ''), skill_values(obj, 1), character_map),
                "Value": obj.get('SkillValue1'),
            }

        if 'AutoSkillLevel' in obj:
            lv = obj['AutoSkillLevel']
            if 'AutoSkillEffectId' in obj:
                values = skill_values(obj, 3)
                effect_info = skill_effect_map.get(f"Auto_{obj.get('AutoSkillEffectId')}", {"Name": "Auto", "Desc": ""})
                card["AutoSkill"][f"Lv{lv}"] = {
                    "Name": effect_info["Name"],
                    "Desc": format_skill_desc(effect_info["Desc"], values, character_map),
                    "PieceCount": obj.get('PieceCount'),
                }
            if 'ItemId1' in obj:
                card["UpgradeCosts"]["AutoSkill"][f"Lv{lv}"] = extract_costs(obj)

        if 'CombinationLevel' in obj:
            lv = obj['CombinationLevel']
            if 'CombinationEffectId' in obj:
                values = skill_values(obj)
                effect_info = skill_effect_map.get(f"Combo_{obj.get('CombinationEffectId')}", {"Desc": ""})
                card["Combination"][f"Lv{lv}"] = {
                    "Desc": format_skill_desc(effect_info["Desc"], values, character_map),
                }
            if 'ItemId1' in obj:
                card["UpgradeCosts"]["Combination"][f"Lv{lv}"] = extract_costs(obj)

    for obj in tables.rows('mst_character_card_story_section', active_only=True):
        cid = obj.get('CharacterCardId')
        if cid in cards_db:
            cards_db[cid]["Story"].append(dict(obj))

    # ============ 独立扫描：卡池关联（gacha 对象没有 CharacterCardId，需单独 walk）============
    for obj in tables.require('mst_gacha'):
        if 'GachaName' in obj and 'CostumeIntroductionCharacterCardIds' in obj:
            for target_cid in obj['CostumeIntroductionCharacterCardIds']:
                get_card(target_cid)["Gacha"].append(obj['GachaName'])

    # ============ 后处理 ============
    def apply_percentage_fix(desc, rarity):
        if not desc:
            return desc
        desc = desc.replace("超特大アップ", "20%UP").replace("特大アップ", "14%UP")
        desc = desc.replace("大アップ", "12%UP").replace("中アップ", "10%UP").replace("小アップ", "8%UP")
        desc = desc.replace("大ダウン", "4%DOWN").replace("中ダウン", "2%DOWN").replace("小ダウン", "1%DOWN")
        return desc

    for cid, card in cards_db.items():
        card["Gacha"] = list(dict.fromkeys(card["Gacha"]))
        rarity = card["Meta"].get("Rarity", "")

        # 活动名溯源
        if str(cid) in ["160", "161"]:
            card["Meta"]["NoticeEvent"] = "2025 HAPPY NEW YEAR!"
        elif rarity in ["XR", "101", 101]:
            c_name = card["Meta"].get("Name", "")
            found = ""
            for title, desc in notice_list:
                if c_name and c_name in desc:
                    found = re.sub(r'^【.*?】', '', title).strip()
                    break
            card["Meta"]["NoticeEvent"] = found

        # 颜色提取
        card_sp_color = None
        for lv, sp_data in card.get("SpSkill", {}).items():
            if lv.startswith("Lv") and "Desc" in sp_data:
                match = PIECE_COLOR_RE.search(sp_data["Desc"])
                if match:
                    card_sp_color = match.group(1)
                    break
        if not card_sp_color:
            attr = card["Meta"].get("Attribute", "")
            card_sp_color = {"日": "サンピース（赤色）", "月": "ムーンピース（空色）", "星": "スターピース（黄色）"}.get(attr, "ピース")

        # 技能精修
        for lv, sp in card.get("SpSkill", {}).items():
            if lv.startswith("Lv") and "Desc" in sp:
                sp["Desc"] = apply_percentage_fix(sp["Desc"], rarity)
        cb = card.get("SpSkill", {}).get("CombiBonus", {})
        if "Desc" in cb:
            desc = re.sub(r'^さらに\s*', '', cb["Desc"])
            desc = re.sub(r'piece_value\d+', card_sp_color, desc)
            cb["Desc"] = apply_percentage_fix(desc, rarity)
        for lv, auto in card.get("AutoSkill", {}).items():
            if lv.startswith("Lv") and "Desc" in auto:
                desc = re.sub(r'piece_value\d+', card_sp_color, auto["Desc"])
                auto["Desc"] = apply_percentage_fix(desc, rarity)
        for lv, combo in card.get("Combination", {}).items():
            if lv.startswith("Lv") and "Desc" in combo:
                desc = re.sub(r'^さらに\s*', '', combo["Desc"])
                desc = re.sub(r'piece_value\d+', card_sp_color, desc)
                combo["Desc"] = apply_percentage_fix(desc, rarity)
        if "Desc" in card.get("LeaderSkill", {}):
            card["LeaderSkill"]["Desc"] = apply_percentage_fix(card["LeaderSkill"]["Desc"], rarity)

    # ============ 关系证据与获取方式 ============
    acquisition_warnings = enrich_card_relations(cards_db, tables, character_map)
    for cid, card in cards_db.items():
        card["Meta"]["AdditionalCharacters"] = card["Relations"].get("AdditionalCharacters", [])
    if acquisition_warnings:
        print(f"[!] {len(acquisition_warnings)} 条卡牌获取关系尚未完整解析")

    # ============ 语音关联 ============
    # masterdata 负责 cue、编号和解锁条件；ACB 负责标题与正文。
    for cid, card in cards_db.items():
        voices = card_home_voice_map.get(cid, {})
        card["Voice"] = sorted(
            voices.values(),
            key=lambda item: (item.get("HomeVoiceNo") or 999, item.get("CueName") or ""),
        )

    if audio_dir:
        audio_cards, audio_warnings = scan_card_voices(audio_dir)
        linked_count = 0
        for cid_text, audio_card in audio_cards.items():
            cid = int(cid_text)
            card = cards_db.get(cid)
            if not card:
                continue

            voices = {item.get("CueName"): item for item in card.get("Voice", [])}
            for audio_entry in audio_card["Entries"]:
                cue_name = audio_entry["CueName"]
                merged = dict(voices.get(cue_name, {}))
                merged.update(audio_entry)
                merged["AcbFile"] = audio_card["AcbFile"]
                voices[cue_name] = merged
                if audio_entry.get("HasText"):
                    linked_count += 1
            card["Voice"] = sorted(
                voices.values(),
                key=lambda item: (
                    CARD_CUE_ORDER.get(item.get("CueName"), 100),
                    item.get("HomeVoiceNo") or 999,
                ),
            )

        print(f"[+] 关联卡面 ACB {len(audio_cards)} 包，填入 {linked_count} 条非空语音文本")
        if audio_warnings:
            print(f"[!] ACB 扫描警告 {len(audio_warnings)} 条")

    out = json_path('All_Cards_Database.json')
    save_json(cards_db, out)
    print(f"[+] 提取 {len(cards_db)} 张卡牌 → {out}")
    return cards_db


def export(json_file=None):
    if json_file is None:
        json_file = json_path('All_Cards_Database.json')
    data = load_json(json_file)
    headers, rows = build_card_sheet(data)
    out = xlsx_path('cards_data.xlsx')
    write_xlsx(rows, out, headers, sheet_title="cards_data")


def run(audio_dir=None, session=None):
    extract(audio_dir=audio_dir, session=session)
    export()
