"""卡牌数据提取 + 导出。

流程：
1. ``_build_lookups``：从具名映射表建立道具、角色、技能效果、公告等字典。
2. ``CARD_TABLES``：逐张卡牌表调用对应的 ``_apply_*``，不再按字段名猜表。
   技能文本由 core/skill_text.py 按客户端 SkillDescriptionParser 的规则渲染。
3. 后处理：活动名溯源、Wiki 用语（去掉“さらに”、强度换算百分比）。
4. 关系证据（card_relations）与语音（masterdata + ACB）合并。
"""
import re
from dataclasses import dataclass

from ..core.scanner import load_json, save_json
from ..core.exporter import write_xlsx, json_path, xlsx_path, audit_path
from ..core.tables import TableCatalog
from ..core.data import RARITY_MAP, ATTRIBUTE_MAP, PIECE_MAP
from ..core.skill_text import SkillTextRenderer
from .card_relations import enrich_card_relations
from .card_export import build_card_sheet
from .audio import CARD_CUE_ORDER, scan_card_voices
from . import card_voice_review
from ..core.output import record_warning

INPUT_JSON = 'master_data.json'
# ============ 映射表 ============

@dataclass
class CardLookups:
    items: dict
    characters: dict
    sp_effects: dict
    auto_effects: dict
    combination_effects: dict
    leader_effects: dict
    notices: list
    home_voices: dict
    skill_text: SkillTextRenderer


def _home_voice_entry(row):
    return {
        "CueName": row['VoiceCueName'],
        "HomeVoiceNo": row.get('HomeVoiceNo'),
        "HomeVoiceCategory": row.get('HomeVoiceCategory'),
        "KeyTargetValue": row.get('KeyTargetValue'),
        "TimeDivisionId": row.get('TimeDivisionId'),
        "IsActive": row.get('IsActive'),
        "MotionCharacterId": row.get('MotionCharacterId'),
        "Title": "",
        "Text": "",
        "TextHtml": "",
        "HasText": False,
        "AcbFile": "",
    }


def _build_lookups(tables):
    home_voices = {}
    for row in tables.require('mst_home_voice'):
        if row.get('HomeVoiceTypeCode') == 2 and row.get('HomeVoiceTargetId') and row.get('VoiceCueName'):
            home_voices.setdefault(row['HomeVoiceTargetId'], {})[row['VoiceCueName']] = _home_voice_entry(row)

    characters = {}
    for row in tables.require('mst_character') + tables.rows('mst_character_collaboration'):
        if 'CharacterId' in row and 'CharacterNameJpn' in row:
            characters[row['CharacterId']] = row['CharacterNameJpn']

    return CardLookups(
        items={
            row['ItemId']: row['ItemName']
            for row in tables.require('mst_item') if 'ItemId' in row and 'ItemName' in row
        },
        characters=characters,
        sp_effects={
            row['SpSkillEffectId']: {
                "SkillEffect": row['SkillEffect'],
                "SpSkillCategoryCodeList": row.get('SpSkillCategoryCodeList', []),
            }
            for row in tables.require('mst_sp_skill_effect')
            if 'SpSkillEffectId' in row and 'SkillEffect' in row
        },
        auto_effects={
            row['AutoSkillEffectId']: {"Name": row['SkillName'], "Desc": row.get('SkillDescription', '')}
            for row in tables.require('mst_auto_skill_effect')
            if 'AutoSkillEffectId' in row and 'SkillName' in row
        },
        combination_effects={
            row['CombinationEffectId']: {
                "Name": row.get('SkillEffect', f"Combo_{row['CombinationEffectId']}"),
                "Desc": row.get('SkillDescription', ''),
            }
            for row in tables.require('mst_combination_effect')
            if 'CombinationEffectId' in row and 'SkillDescription' in row
        },
        leader_effects={
            row['LeaderSkillEffectId']: {
                "Name": row.get('SkillName') or row.get('SkillEffect') or f"Leader_{row['LeaderSkillEffectId']}",
                "Desc": row.get('SkillDescription', ''),
            }
            for row in tables.require('mst_leader_skill_effect')
            if 'LeaderSkillEffectId' in row and 'SkillDescription' in row
        },
        notices=[
            (row['TitleName'], row['FileDesc'])
            for row in tables.require('mst_notice')
            if 'NoticeId' in row and 'TitleName' in row and 'FileDesc' in row
        ],
        home_voices=home_voices,
        skill_text=SkillTextRenderer(tables, piece_labels=PIECE_MAP),
    )


# ============ 卡牌表 ============

def _new_card():
    return {
        "Meta": {}, "Stats": {}, "LeaderSkill": {}, "SpSkill": {},
        "AutoSkill": {}, "Combination": {}, "Revision": {},
        "UpgradeCosts": {"AutoSkill": {}, "SpSkill": {}, "Combination": {}, "Revision": {}},
        "Story": [], "Assets": {}, "Voice": [], "Gacha": [],
        "Raw": {}, "Relations": {}, "Acquisition": {},
    }


def _costs(row, lookups):
    costs = []
    for i in range(1, 7):
        iid = row.get(f'CostItemId{i}', 0)
        count = row.get(f'CostItemCount{i}', 0)
        if iid > 0 and count > 0:
            costs.append({"Item": lookups.items.get(iid, f"Item_{iid}"), "Count": count})
    return costs


def _apply_card(card, row, lookups):
    characters = lookups.characters
    card["Raw"] = dict(row)
    card["Meta"].update({
        "Name": row.get('CharacterCardName'),
        "CharId": row.get('CharacterId'),
        "CharName": characters.get(row.get('CharacterId'), f"Char_{row.get('CharacterId')}"),
        "Rarity": RARITY_MAP.get(row.get('CardRarityCode'), row.get('CardRarityCode')),
        "RarityCode": row.get('CardRarityCode'),
        "Attribute": ATTRIBUTE_MAP.get(row.get('CardAttributeCode'), row.get('CardAttributeCode')),
        "AttributeCode": row.get('CardAttributeCode'),
        "RouteCode": row.get('CardRouteCode'),
        "CombiCharName": characters.get(row.get('CombiCharacterId'), f"Char_{row.get('CombiCharacterId')}"),
        "Release": row.get('ReleaseDateTime'),
    })
    card["Assets"] = {
        "CardIcon": row.get('CharacterCardIconFileName', ''),
        "CardIllustration": row.get('CharacterCardFileName', ''),
        "LiveClip": row.get('LiveClipFileName', ''),
        "SpSkillEffect": row.get('SpSkillEffectFileName', ''),
        "VoiceCueSheet": row.get('VoiceCueSheetName', ''),
    }
    card["SpSkill"]["Name"] = row.get('SpSkillName')


def _apply_parameter(card, row, lookups):
    card["Stats"] = {
        "Aura": {"Min": row.get('AuraInitialValue'), "Max": row.get('AuraMaxValue')},
        "Visual": {"Min": row.get('VisualInitialValue'), "Max": row.get('VisualMaxValue')},
        "Charisma": {"Min": row.get('CharismaInitialValue'), "Max": row.get('CharismaMaxValue')},
    }


def _apply_revision(card, row, lookups):
    card["Revision"][f"Rank{row['RevisionRank']}"] = {
        "Aura+": row.get('AuraAdditionalValue', 0),
        "Visual+": row.get('VisualAdditionalValue', 0),
        "Charisma+": row.get('CharismaAdditionalValue', 0),
    }


def _cost_applier(category, level_key, prefix):
    def apply(card, row, lookups):
        card["UpgradeCosts"][category][f"{prefix}{row[level_key]}"] = _costs(row, lookups)
    return apply


def _apply_leader_skill(card, row, lookups):
    effect_id = row.get('LeaderSkillEffectId')
    effect = lookups.leader_effects.get(effect_id, {"Name": f"Leader_{effect_id}", "Desc": ""})
    card["LeaderSkill"] = {
        "Name": effect["Name"],
        "Desc": lookups.skill_text.wiki_text(effect["Desc"], row),
    }


def _apply_sp_level(card, row, lookups):
    card["SpSkill"][f"Lv{row['SpSkillLevel']}"] = {
        "Desc": lookups.skill_text.wiki_text(row.get('SkillDescription', ''), row),
        "Cost": row.get('SkillCost'),
    }
    effect = lookups.sp_effects.get(row.get('SpSkillEffectId'))
    if effect:
        card["SpSkill"]["SkillEffect"] = effect["SkillEffect"]
        card["SpSkill"]["SpSkillCategoryCodeList"] = effect["SpSkillCategoryCodeList"]


def _apply_sp_with_combi(card, row, lookups):
    card["SpSkill"]["CombiBonus"] = {
        "Desc": lookups.skill_text.wiki_text(row.get('SkillDescription', ''), row),
        "Value": row.get('SkillValue1'),
    }


def _apply_auto_level(card, row, lookups):
    effect = lookups.auto_effects.get(row.get('AutoSkillEffectId'), {"Name": "Auto", "Desc": ""})
    card["AutoSkill"][f"Lv{row['AutoSkillLevel']}"] = {
        "Name": effect["Name"],
        "Desc": lookups.skill_text.wiki_text(effect["Desc"], row),
        "PieceCount": row.get('PieceCount'),
    }


def _apply_combination_level(card, row, lookups):
    effect = lookups.combination_effects.get(row.get('CombinationEffectId'), {"Desc": ""})
    card["Combination"][f"Lv{row['CombinationLevel']}"] = {
        "Desc": lookups.skill_text.wiki_text(effect["Desc"], row),
    }


# 顺序即合并顺序；同一卡同一等级出现多行时以后读到的为准。
CARD_TABLES = (
    ('mst_character_card', _apply_card),
    ('mst_character_card_parameter', _apply_parameter),
    ('mst_character_card_revision', _apply_revision),
    ('mst_item_card_revision', _cost_applier("Revision", 'RevisionRank', "Rank")),
    ('mst_character_card_leader_skill', _apply_leader_skill),
    ('mst_character_card_sp_skill_level', _apply_sp_level),
    ('mst_item_card_sp_skill_level_up', _cost_applier("SpSkill", 'SpSkillLevel', "Lv")),
    ('mst_character_card_sp_skill_with_combi', _apply_sp_with_combi),
    ('mst_character_card_auto_skill_level', _apply_auto_level),
    ('mst_item_card_auto_skill_level_up', _cost_applier("AutoSkill", 'AutoSkillLevel', "Lv")),
    ('mst_character_card_combination_level', _apply_combination_level),
    ('mst_item_card_combination_level_up', _cost_applier("Combination", 'CombinationLevel', "Lv")),
)


def _build_cards(tables, lookups):
    cards_db = {}
    for table_name, apply in CARD_TABLES:
        for row in tables.require(table_name):
            cid = row.get('CharacterCardId')
            if cid:
                apply(cards_db.setdefault(cid, _new_card()), row, lookups)

    for row in tables.rows('mst_character_card_story_section', active_only=True):
        cid = row.get('CharacterCardId')
        if cid in cards_db:
            cards_db[cid]["Story"].append(dict(row))

    # 旧卡池字段：CostumeIntroductionCharacterCardIds 只作为卡池名回退。
    for row in tables.require('mst_gacha'):
        if 'GachaName' in row and 'CostumeIntroductionCharacterCardIds' in row:
            for target_cid in row['CostumeIntroductionCharacterCardIds']:
                cards_db.setdefault(target_cid, _new_card())["Gacha"].append(row['GachaName'])
    return cards_db


# ============ 后处理 ============

def _apply_percentage_fix(desc):
    if not desc:
        return desc
    desc = desc.replace("超特大アップ", "20%UP").replace("特大アップ", "14%UP")
    desc = desc.replace("大アップ", "12%UP").replace("中アップ", "10%UP").replace("小アップ", "8%UP")
    desc = desc.replace("大ダウン", "4%DOWN").replace("中ダウン", "2%DOWN").replace("小ダウン", "1%DOWN")
    return desc


def _notice_event(cid, card, notices):
    if str(cid) in ["160", "161"]:
        return "2025 HAPPY NEW YEAR!"
    name = card["Meta"].get("Name", "")
    for title, desc in notices:
        if name and name in desc:
            return re.sub(r'^【.*?】', '', title).strip()
    return ""


def _polish_skill_text(card):
    def polish(desc, strip_more=False):
        if strip_more:
            desc = re.sub(r'^さらに\s*', '', desc)
        return _apply_percentage_fix(desc)

    for level, sp in card["SpSkill"].items():
        if level.startswith("Lv") and "Desc" in sp:
            sp["Desc"] = polish(sp["Desc"])
    combi_bonus = card["SpSkill"].get("CombiBonus", {})
    if "Desc" in combi_bonus:
        combi_bonus["Desc"] = polish(combi_bonus["Desc"], strip_more=True)
    for level, auto in card["AutoSkill"].items():
        if level.startswith("Lv") and "Desc" in auto:
            auto["Desc"] = polish(auto["Desc"])
    for level, combo in card["Combination"].items():
        if level.startswith("Lv") and "Desc" in combo:
            combo["Desc"] = polish(combo["Desc"], strip_more=True)
    if "Desc" in card["LeaderSkill"]:
        card["LeaderSkill"]["Desc"] = polish(card["LeaderSkill"]["Desc"])


def _post_process(cards_db, lookups):
    for cid, card in cards_db.items():
        card["Gacha"] = list(dict.fromkeys(card["Gacha"]))
        if str(cid) in ["160", "161"] or card["Meta"].get("Rarity", "") in ["XR", "101", 101]:
            card["Meta"]["NoticeEvent"] = _notice_event(cid, card, lookups.notices)
        _polish_skill_text(card)
    if lookups.skill_text.unresolved:
        record_warning(f"技能文本有 {len(lookups.skill_text.unresolved)} 种占位符无法解析: "
                       f"{sorted(lookups.skill_text.unresolved)[:10]}")


# ============ 语音 ============

def _attach_voices(cards_db, lookups, tables, audio_dir):
    # masterdata 负责 cue、编号和解锁条件；ACB 负责标题与正文。
    for cid, card in cards_db.items():
        voices = lookups.home_voices.get(cid, {})
        card["Voice"] = sorted(
            voices.values(),
            key=lambda item: (item.get("HomeVoiceNo") or 999, item.get("CueName") or ""),
        )
    if not audio_dir:
        return

    audio_cards, audio_warnings = scan_card_voices(audio_dir)
    linked_count = 0
    for cid_text, audio_card in audio_cards.items():
        card = cards_db.get(int(cid_text))
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
        record_warning(f"卡牌 ACB 扫描警告 {len(audio_warnings)} 条")
    card_voice_review.run(audio_dir, tables, lambda cid: lookups.characters.get(cid, '/'))


# ============ 入口 ============

def extract(audio_dir=None, session=None):
    tables = session.tables if session else TableCatalog(load_json(INPUT_JSON))
    lookups = _build_lookups(tables)
    cards_db = _build_cards(tables, lookups)
    _post_process(cards_db, lookups)

    relation_audit = {}
    acquisition_warnings = enrich_card_relations(
        cards_db, tables, lookups.characters, relation_audit=relation_audit
    )
    save_json(relation_audit, audit_path('card_serial_present.json'))
    if relation_audit.get('Issues'):
        record_warning(f"序列码礼物有 {len(relation_audit['Issues'])} 条关系缺项；详见 card_serial_present.json")
    for card in cards_db.values():
        card["Meta"]["AdditionalCharacters"] = card["Relations"].get("AdditionalCharacters", [])
    if acquisition_warnings:
        print(f"[!] {len(acquisition_warnings)} 条卡牌获取关系尚未完整解析")
        record_warning(f"{len(acquisition_warnings)} 条卡牌获取关系尚未完整解析；详见卡牌审计")

    _attach_voices(cards_db, lookups, tables, audio_dir)

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
    write_xlsx(
        rows,
        out,
        headers,
        sheet_title="cards_data",
        column_types={1: "integer"},
    )


def run(audio_dir=None, session=None):
    extract(audio_dir=audio_dir, session=session)
    export()
