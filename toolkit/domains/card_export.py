"""Declarative Wiki-oriented card workbook projection."""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class CardColumn:
    key: str
    header: str


# The original 47 columns remain in their historical order. New mechanism and
# audit columns are appended so existing Wiki imports do not shift silently.
CARD_COLUMNS = (
    CardColumn("card_file", "卡牌"),
    CardColumn("card_id", "卡牌编号"),
    CardColumn("character_names", "卡牌角色名"),
    CardColumn("card_name", "卡牌名"),
    CardColumn("translated_name", "卡牌译名"),
    CardColumn("attribute", "卡牌属性"),
    CardColumn("rarity", "卡牌稀有度"),
    CardColumn("character_id", "卡牌角色编号"),
    CardColumn("event_name", "卡牌对应活动名"),
    CardColumn("acquisition_method", "卡牌获取方式"),
    CardColumn("total_initial", "综合力初始"),
    CardColumn("total_max", "综合力满级"),
    CardColumn("aura_initial", "气质初始"),
    CardColumn("aura_max", "气质满级"),
    CardColumn("visual_initial", "外观初始"),
    CardColumn("visual_max", "外观满级"),
    CardColumn("charisma_initial", "魅力初始"),
    CardColumn("charisma_max", "魅力满级"),
    CardColumn("leader_skill", "队长技能"),
    CardColumn("auto_name", "自动技能分类"),
    CardColumn("auto_lv1", "自动技能Lv1"),
    CardColumn("auto_lv1_pieces", "自动技能Lv1碎片数"),
    CardColumn("auto_max", "自动技能满级"),
    CardColumn("auto_max_pieces", "自动技能满级碎片数"),
    CardColumn("sp_name", "SP技能名"),
    CardColumn("sp_category", "SP技能分类"),
    CardColumn("sp_lv1", "SP技能Lv1"),
    CardColumn("sp_lv1_cost", "SP技能Lv1COST"),
    CardColumn("sp_max", "SP技能满级"),
    CardColumn("sp_max_cost", "SP技能满级COST"),
    CardColumn("combi_character", "协作技对象"),
    CardColumn("combi_sp", "协作SP技能效果"),
    CardColumn("combi_lv1", "协作效果Lv1"),
    CardColumn("combi_max", "协作效果满级"),
    CardColumn("voice_home_1_j", "卡牌语音①J"),
    CardColumn("voice_home_1_c", "卡牌语音①C"),
    CardColumn("voice_home_2_j", "卡牌语音②J"),
    CardColumn("voice_home_2_c", "卡牌语音②C"),
    CardColumn("voice_home_3_j", "卡牌语音③J"),
    CardColumn("voice_home_3_c", "卡牌语音③C"),
    CardColumn("voice_skill_j", "卡牌技能语音J"),
    CardColumn("voice_skill_c", "卡牌技能语音C"),
    CardColumn("voice_combi_j", "卡牌协作语音J"),
    CardColumn("voice_combi_c", "卡牌协作语音C"),
    CardColumn("upgrade_item_1", "卡牌升级道具1"),
    CardColumn("upgrade_item_2", "卡牌升级道具2"),
    CardColumn("upgrade_item_3", "卡牌升级道具3"),
    CardColumn("additional_characters", "卡牌附加角色名"),
    CardColumn("voice_home_4_j", "卡牌语音④J"),
    CardColumn("voice_home_4_c", "卡牌语音④C"),
    CardColumn("voice_partner_skill_j", "卡牌副角色技能语音J"),
    CardColumn("voice_partner_skill_c", "卡牌副角色技能语音C"),
)


def _level_pair(skill):
    keys = sorted(
        (key for key in skill if key.startswith("Lv")),
        key=lambda key: int(key.removeprefix("Lv")),
    )
    return skill.get("Lv1", {}), skill.get(keys[-1], {}) if keys else {}


def _piece_text(count, attribute):
    return f"{attribute}属性碎片*{count}" if count else "/"


def _upgrade_items(card):
    items = []
    excluded = ("エッセンス", "サプリ", "キー", "カクテル")
    for category in card.get("UpgradeCosts", {}).values():
        if not isinstance(category, dict):
            continue
        for level in category.values():
            if not isinstance(level, list):
                continue
            for cost in level:
                item = cost.get("Item", "")
                if item and not any(token in item for token in excluded) and item not in items:
                    items.append(item)
    return items


def _voice_projection(card, primary_character_id):
    voices = {
        voice.get("CueName"): voice
        for voice in card.get("Voice", [])
        if voice.get("CueName")
    }

    def text(cue_name):
        value = voices.get(cue_name, {}).get("TextHtml", "")
        return value.replace("<br>", "").replace("\r", "").replace("\n", "")

    primary_skill_cues = ("card_vo_skill", f"card_vo_skill_{primary_character_id}")
    primary_skill = next((text(cue) for cue in primary_skill_cues if text(cue)), "")
    partner_skill = "".join(
        voice.get("TextHtml", "").replace("<br>", "").replace("\r", "").replace("\n", "")
        for cue, voice in sorted(voices.items())
        if re.fullmatch(r"card_vo_skill_\d+", cue)
        and cue != f"card_vo_skill_{primary_character_id}"
        and voice.get("TextHtml")
    )
    return {
        "voice_home_1_j": text("card_vo_home_1"),
        "voice_home_1_c": "",
        "voice_home_2_j": text("card_vo_home_2"),
        "voice_home_2_c": "",
        "voice_home_3_j": text("card_vo_home_3"),
        "voice_home_3_c": "",
        "voice_home_4_j": text("card_vo_home_4"),
        "voice_home_4_c": "",
        "voice_skill_j": primary_skill,
        "voice_skill_c": "",
        "voice_combi_j": text("card_vo_skill_combi"),
        "voice_combi_c": "",
        "voice_partner_skill_j": partner_skill,
        "voice_partner_skill_c": "",
    }


def build_card_record(card_id, card):
    meta = card.get("Meta", {})
    acquisition = card.get("Acquisition", {})
    stats = card.get("Stats", {})
    revisions = card.get("Revision", {})
    attribute = meta.get("Attribute", "")

    aura_initial = stats.get("Aura", {}).get("Min", 0)
    aura_max = stats.get("Aura", {}).get("Max", 0) + sum(
        row.get("Aura+", 0) for row in revisions.values()
    )
    visual_initial = stats.get("Visual", {}).get("Min", 0)
    visual_max = stats.get("Visual", {}).get("Max", 0) + sum(
        row.get("Visual+", 0) for row in revisions.values()
    )
    charisma_initial = stats.get("Charisma", {}).get("Min", 0)
    charisma_max = stats.get("Charisma", {}).get("Max", 0) + sum(
        row.get("Charisma+", 0) for row in revisions.values()
    )

    auto = card.get("AutoSkill", {})
    auto_lv1, auto_max = _level_pair(auto)
    sp = card.get("SpSkill", {})
    sp_lv1, sp_max = _level_pair(sp)
    combination = card.get("Combination", {})
    combi_lv1, combi_max = _level_pair(combination)
    items = _upgrade_items(card)
    additional = card.get("Relations", {}).get("AdditionalCharacters", [])
    additional_names = [row.get("CharacterName", "") for row in additional if row.get("CharacterName")]
    character_names = [meta.get("CharName", "")] + additional_names

    record = {
        "card_file": f"card_{card_id}",
        "card_id": card_id,
        "character_names": ",".join(name for name in character_names if name),
        "card_name": meta.get("Name", ""),
        "translated_name": "",
        "attribute": attribute,
        "rarity": meta.get("Rarity", ""),
        "character_id": meta.get("CharId", ""),
        "event_name": acquisition.get("SourceName", ""),
        "acquisition_method": acquisition.get("Method", ""),
        "total_initial": aura_initial + visual_initial + charisma_initial,
        "total_max": aura_max + visual_max + charisma_max,
        "aura_initial": aura_initial,
        "aura_max": aura_max,
        "visual_initial": visual_initial,
        "visual_max": visual_max,
        "charisma_initial": charisma_initial,
        "charisma_max": charisma_max,
        "leader_skill": card.get("LeaderSkill", {}).get("Desc", "").replace("\n", "") or "/",
        "auto_name": auto_lv1.get("Name", "/"),
        "auto_lv1": auto_lv1.get("Desc", "").replace("\n", ""),
        "auto_lv1_pieces": _piece_text(auto_lv1.get("PieceCount", ""), attribute),
        "auto_max": auto_max.get("Desc", "").replace("\n", ""),
        "auto_max_pieces": _piece_text(auto_max.get("PieceCount", ""), attribute),
        "sp_name": sp.get("Name", ""),
        "sp_category": sp.get("SkillEffect", "") or "/",
        "sp_lv1": sp_lv1.get("Desc", "").replace("\n", ""),
        "sp_lv1_cost": sp_lv1.get("Cost", ""),
        "sp_max": sp_max.get("Desc", "").replace("\n", ""),
        "sp_max_cost": sp_max.get("Cost", ""),
        "combi_character": meta.get("CombiCharName", "/") if meta.get("CombiCharName") != "Char_0" else "/",
        "combi_sp": sp.get("CombiBonus", {}).get("Desc", "/").replace("\n", ""),
        "combi_lv1": combi_lv1.get("Desc", "/").replace("\n", ""),
        "combi_max": combi_max.get("Desc", "/").replace("\n", ""),
        "upgrade_item_1": items[0] if len(items) > 0 else "",
        "upgrade_item_2": items[1] if len(items) > 1 else "",
        "upgrade_item_3": items[2] if len(items) > 2 else "",
        "additional_characters": ",".join(additional_names),
    }
    record.update(_voice_projection(card, meta.get("CharId")))
    return record


def build_card_sheet(data):
    headers = [column.header for column in CARD_COLUMNS]
    rows = []
    for card_id in sorted(data, key=int):
        record = build_card_record(card_id, data[card_id])
        rows.append([record.get(column.key, "") for column in CARD_COLUMNS])
    return headers, rows
