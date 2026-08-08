"""Event archive extraction and export."""
from collections import defaultdict

from ..core.scanner import load_json, save_json
from ..core.exporter import json_path, xlsx_path
from ..core.data import clean_text

INPUT_JSON = 'master_data.json'

EVENT_FORMAT_MAP = {
    1: {"Key": "standard_exchange", "Label": "普通点数/交换所活动"},
    2: {"Key": "story_campaign_a", "Label": "活动A类/剧情活动"},
    3: {"Key": "bar_sales", "Label": "酒保营业活动"},
    4: {"Key": "special_bar_sales", "Label": "特殊营业活动"},
    5: {"Key": "ojt", "Label": "OJT活动"},
    6: {"Key": "accumulate_item", "Label": "累积道具活动"},
}

SOURCE_SUBTYPE_MAP = {
    "event_a": "mst_event_a：普通活动扩展表",
    "event_b": "mst_event_b：营业/酒保活动扩展表",
    "event_c": "mst_event_c：OJT/特殊活动扩展表",
    "accumulate_item": "mst_event_accumulate_item：累积道具活动扩展表",
    "ojt": "mst_event_ojt_shift：OJT轮次表",
    "unknown": "未匹配到活动扩展表",
}

RARITY_MAP = {1: "R", 2: "SR", 3: "SSR", 101: "XR", 102: "CR"}
ATTRIBUTE_MAP = {1: "Sun", 2: "Moon", 3: "Star"}
REWARD_TYPE_MAP = {
    1: {"Key": "card", "Label": "卡牌"},
    2: {"Key": "item", "Label": "道具"},
    3: {"Key": "home_background", "Label": "主页背景"},
    4: {"Key": "costume_model", "Label": "角色服装"},
    5: {"Key": "costume_mini", "Label": "迷你角色服装"},
    6: {"Key": "honor", "Label": "称号"},
    7: {"Key": "pin", "Label": "Pin"},
    8: {"Key": "music", "Label": "音乐"},
    9: {"Key": "spin_album_release_item", "Label": "Spin相册解锁道具"},
    99: {"Key": "information", "Label": "信息"},
    100: {"Key": "event_item", "Label": "活动道具"},
    101: {"Key": "ingredient", "Label": "活动材料"},
    102: {"Key": "travel_coin", "Label": "旅行币"},
}


def _tables(data):
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        return {}
    names = list(data[0].keys())
    return {name: data[i + 1] for i, name in enumerate(names) if i + 1 < len(data)}


def _active(rows):
    return [row for row in rows if isinstance(row, dict) and row.get("IsActive", True)]


def _group(rows, key):
    grouped = defaultdict(list)
    for row in _active(rows):
        grouped[row.get(key)].append(row)
    return grouped


def _by_id(rows, key):
    return {row.get(key): row for row in _active(rows) if key in row}


def _names(ids, mapping):
    return [mapping.get(i, f"Unknown({i})") for i in ids or []]


def _card_summary(card, character_map):
    if not card:
        return ""
    char_name = character_map.get(card.get("CharacterId"), f"Char_{card.get('CharacterId')}")
    rarity = RARITY_MAP.get(card.get("CardRarityCode"), card.get("CardRarityCode"))
    attr = ATTRIBUTE_MAP.get(card.get("CardAttributeCode"), card.get("CardAttributeCode"))
    return f"{card.get('CharacterCardName', '')} / {char_name} / {rarity} / {attr}"


def _resolve_reward(row, maps):
    rtype = row.get("RewardTypeCode")
    target = row.get("RewardTargetId")
    count = row.get("RewardCount")
    reward_type = REWARD_TYPE_MAP.get(rtype, {"Key": f"type_{rtype}", "Label": f"未知类型{rtype}"})
    key = reward_type["Key"]
    label = reward_type["Label"]

    if rtype == 1:
        name = maps["cards"].get(target, f"Card_{target}")
    elif rtype in (2, 100, 101, 102):
        name = maps["items"].get(target) or maps["ingredients"].get(target) or label
    elif rtype == 6:
        name = maps["titles"].get(target, f"Title_{target}")
    elif rtype == 7:
        name = maps["pins"].get(target, f"Pin_{target}")
    else:
        name = f"{label}({target})"

    return {
        "RewardTypeCode": rtype,
        "RewardType": key,
        "RewardTypeLabel": label,
        "RewardTargetId": target,
        "RewardName": name,
        "RewardCount": count,
    }


def _direct_rewards(group_id, direct_by_group, maps):
    if not group_id:
        return []
    rows = sorted(direct_by_group.get(group_id, []), key=lambda r: r.get("DirectRewardSequenceNo", 0))
    return [_resolve_reward(row, maps) for row in rows]


def _present_rewards(present_id, present_by_id, maps):
    if not present_id:
        return []
    rows = sorted(present_by_id.get(present_id, []), key=lambda r: r.get("PresentSequenceNo", 0))
    return [_resolve_reward(row, maps) for row in rows]


def extract():
    data = load_json(INPUT_JSON)
    tables = _tables(data)

    events = _active(tables.get("mst_event", []))
    event_a = _by_id(tables.get("mst_event_a", []), "EventId")
    event_b = _by_id(tables.get("mst_event_b", []), "EventId")
    event_c = _by_id(tables.get("mst_event_c", []), "EventId")
    event_acc = _by_id(tables.get("mst_event_accumulate_item", []), "EventId")
    event_story = _by_id(tables.get("mst_event_story", []), "EventId")
    stories = _group(tables.get("mst_event_story_section", []), "EventId")
    rules = _group(tables.get("mst_event_rule_window", []), "EventId")
    shifts = _group(tables.get("mst_event_shift", []), "EventId")
    ojt_shifts = _group(tables.get("mst_event_ojt_shift", []), "EventId")
    special_by_shift = _group(tables.get("mst_event_special_time", []), "ShiftId")
    recipes = _group(tables.get("mst_event_recipe", []), "EventId")
    accumulate_rewards = _group(tables.get("mst_event_accumulate_item_reward", []), "EventId")
    sales_rewards = _group(tables.get("mst_event_sales_reward", []), "EventId")
    ranking_rewards = _group(tables.get("mst_event_ranking_reward", []), "EventId")
    ingredient_stages = _group(tables.get("mst_event_puzzle_stage_ingredient", []), "EventId")
    direct_by_group = _group(tables.get("mst_direct_reward", []), "DirectRewardGroupId")
    present_by_id = _group(tables.get("mst_present", []), "PresentId")

    characters = _by_id(tables.get("mst_character", []), "CharacterId")
    cards = _by_id(tables.get("mst_character_card", []), "CharacterCardId")
    items = _by_id(tables.get("mst_item", []), "ItemId")
    ingredients = _by_id(tables.get("mst_event_ingredient", []), "IngredientId")
    titles = _by_id(tables.get("mst_title", []), "TitleId")
    pins = _by_id(tables.get("mst_pin", []), "PinId")
    honors = _by_id(tables.get("mst_honor", []), "HonorId")
    home_voice_products = _by_id(tables.get("mst_home_voice_product", []), "HomeVoiceProductId")

    character_map = {k: v.get("CharacterNameJpn", "") for k, v in characters.items()}
    card_map = {k: _card_summary(v, character_map) for k, v in cards.items()}
    item_map = {k: v.get("ItemName", "") for k, v in items.items()}
    ingredient_map = {k: v.get("IngredientName", "") for k, v in ingredients.items()}
    maps = {
        "items": item_map,
        "ingredients": ingredient_map,
        "cards": card_map,
        "titles": {k: v.get("TitleFileName", "") for k, v in titles.items()},
        "pins": {k: v.get("PinName") or v.get("PinFileName", "") for k, v in pins.items()},
        "honors": {k: v.get("HonorFileName", "") for k, v in honors.items()},
        "home_voice_products": {k: v.get("DisplayName", "") for k, v in home_voice_products.items()},
    }

    archive = []
    for event in sorted(events, key=lambda e: e.get("EventId", 0)):
        event_id = event.get("EventId")
        subtype_rows = [r for r in (event_a.get(event_id), event_b.get(event_id), event_c.get(event_id), event_acc.get(event_id)) if r]
        subtype = (
            "event_a" if event_id in event_a else
            "event_b" if event_id in event_b else
            "event_c" if event_id in event_c else
            "accumulate_item" if event_id in event_acc else
            "ojt" if event_id in ojt_shifts else
            "unknown"
        )
        main_sub = subtype_rows[0] if subtype_rows else {}
        character_ids = main_sub.get("CharacterIds", [])
        card_ids = main_sub.get("CharacterCardIds", []) or main_sub.get("PickUpCharacterCardIds", [])
        pickup_ids = []
        if main_sub.get("PickUpCharacterCardId"):
            pickup_ids.append(main_sub.get("PickUpCharacterCardId"))
        pickup_ids.extend(main_sub.get("PickUpCharacterCardIds", []) or [])

        story_meta = event_story.get(event_id, {})
        story_sections = []
        for row in sorted(stories.get(event_id, []), key=lambda r: r.get("EventStorySectionNo", 0)):
            story_sections.append({
                "No": row.get("EventStorySectionNo"),
                "Group": row.get("EventStorySectionGroup"),
                "Type": row.get("EventStorySectionType"),
                "Title": row.get("TitleName", ""),
                "ReleaseDateTime": row.get("ReleaseDateTime", ""),
                "RequiredValue": row.get("KeyTargetValue", 0),
                "KeyCost": row.get("KeyEventStoryKeyUnlockCost", 0),
                "HasVoice": row.get("HasVoiceFile", False),
                "PopupText": clean_text(row.get("PopupText", "")),
                "ReadRewards": _direct_rewards(row.get("ReadDirectRewardGroupId"), direct_by_group, maps),
            })

        rule_sections = []
        for row in sorted(rules.get(event_id, []), key=lambda r: r.get("SlideNo", 0)):
            rule_sections.append({
                "SlideNo": row.get("SlideNo"),
                "Type": row.get("RuleWindowSlideType"),
                "ReleaseDateTime": row.get("ReleaseDateTime", ""),
                "DescriptionFileName": row.get("DescriptionFileName", ""),
                "Description": clean_text(row.get("Description", "")),
            })

        shift_sections = []
        for row in sorted(shifts.get(event_id, []), key=lambda r: r.get("ShiftId", 0)):
            shift_sections.append({
                "ShiftId": row.get("ShiftId"),
                "CharacterId": row.get("CharacterId"),
                "CharacterName": character_map.get(row.get("CharacterId"), ""),
                "StartTime": row.get("StartTime", ""),
                "EndTime": row.get("EndTime", ""),
                "SpecialTimes": sorted(special_by_shift.get(row.get("ShiftId"), []), key=lambda r: r.get("SpecialTimeSequenceNo", 0)),
            })
        for row in sorted(ojt_shifts.get(event_id, []), key=lambda r: r.get("OjtShiftId", 0)):
            shift_sections.append({
                "ShiftId": row.get("OjtShiftId"),
                "CharacterId": row.get("CharacterId"),
                "CharacterName": character_map.get(row.get("CharacterId"), ""),
                "StartTime": row.get("StartTime", ""),
                "EndTime": row.get("EndTime", ""),
                "TrainingStartScript": row.get("TrainingPuzzleStartStoryFileName", ""),
                "TrainingClearScript": row.get("TrainingPuzzleClearStoryFileName", ""),
            })

        reward_summary = {
            "Ranking": [
                {
                    "RankingType": r.get("RankingType"),
                    "StartRank": r.get("StartRank"),
                    "WappenCount": r.get("RewardWappenCount"),
                    "Rewards": _present_rewards(r.get("PresentId"), present_by_id, maps),
                }
                for r in sorted(ranking_rewards.get(event_id, []), key=lambda r: (r.get("RankingType", 0), r.get("StartRank", 0)))
            ],
            "Sales": [
                {
                    "ShiftId": r.get("ShiftId"),
                    "KeySales": r.get("KeySales"),
                    "IsPickUp": r.get("IsPickUp"),
                    "Rewards": _direct_rewards(r.get("DirectRewardGroupId"), direct_by_group, maps),
                }
                for r in sorted(sales_rewards.get(event_id, []), key=lambda r: (r.get("ShiftId", 0), r.get("KeySales", 0)))
            ],
            "Accumulate": [
                {
                    "KeyCount": r.get("KeyCount"),
                    "IsPickUp": r.get("IsPickUp"),
                    "Rewards": _direct_rewards(r.get("DirectRewardGroupId"), direct_by_group, maps),
                }
                for r in sorted(accumulate_rewards.get(event_id, []), key=lambda r: r.get("KeyCount", 0))
            ],
        }
        event_format = EVENT_FORMAT_MAP.get(event.get("EventFormat"), {"Key": "unknown", "Label": "未知活动类型"})
        subtype_label = SOURCE_SUBTYPE_MAP.get(subtype, SOURCE_SUBTYPE_MAP["unknown"])

        archive.append({
            "EventId": event_id,
            "Title": event.get("EventTitle", ""),
            "EventFormat": event.get("EventFormat"),
            "EventFormatName": event_format["Key"],
            "EventFormatLabel": event_format["Label"],
            "ActivityType": event_format["Label"],
            "SourceSubtype": subtype,
            "SourceSubtypeLabel": subtype_label,
            "Subtype": subtype,
            "SubtypeLabel": subtype_label,
            "StartTime": event.get("StartTime", ""),
            "OpenStartTime": event.get("OpenStartTime", ""),
            "SecondHalfStartTime": event.get("SecondHalfStartTime", ""),
            "RankingEndTime": event.get("EventRankingEndTime", ""),
            "HighScoreRankingEndTime": event.get("HighScoreRankingEndTime", ""),
            "AnnouncementStartTime": event.get("AnnouncementStartTime", ""),
            "EndTime": event.get("EndTime", ""),
            "NoticeId": event.get("NoticeId", 0),
            "Assets": {
                "Logo": event.get("LogoFileName", ""),
                "PromotionalPopup": event.get("PromotionalPopupFileName", ""),
                "PuzzleTerminalBackground": event.get("PuzzleTerminalBackgroundFileName", ""),
                "PuzzleTerminalCharacters": event.get("PuzzleTerminalCharacterFileNames", []),
                "StoryBanner": story_meta.get("BannerFileName", ""),
                "StoryButton": story_meta.get("StoryButtonFileName", ""),
            },
            "Colors": {
                "Main": event.get("MainColor", ""),
                "Accent": event.get("AccentColor", ""),
                "Spectrum": event.get("SpectrumColor", ""),
            },
            "Characters": [{"Id": cid, "Name": character_map.get(cid, f"Unknown({cid})")} for cid in character_ids],
            "Cards": [{"Id": cid, "Name": card_map.get(cid, f"Unknown({cid})")} for cid in card_ids],
            "PickUpCards": [{"Id": cid, "Name": card_map.get(cid, f"Unknown({cid})")} for cid in pickup_ids],
            "EventItems": _names([main_sub.get("EventItemId"), main_sub.get("TravelCoinItemId"), main_sub.get("EventStaminaItemId"), main_sub.get("PrizeMedalItemId"), main_sub.get("ChartStampItemId")], item_map),
            "ExchangeId": main_sub.get("ExchangeId", 0),
            "StorySynopsis": clean_text(story_meta.get("Synopsis", "")),
            "StoryUnlockStartTime": story_meta.get("UnlockStartTime", ""),
            "StorySections": story_sections,
            "Rules": rule_sections,
            "Shifts": shift_sections,
            "Recipes": [
                {
                    "RecipeId": r.get("RecipeId"),
                    "RecipeName": r.get("RecipeName", ""),
                    "RecommendCharacter": character_map.get(r.get("RecommendCharacterId"), ""),
                    "IngredientIds": r.get("IngredientIds", []),
                    "Memo": clean_text(r.get("RecipeMemo", "")),
                    "FileName": r.get("RecipeFileName", ""),
                }
                for r in sorted(recipes.get(event_id, []), key=lambda r: r.get("RecipeId", 0))
            ],
            "PuzzleIngredientStageCount": len(ingredient_stages.get(event_id, [])),
            "Rewards": reward_summary,
        })

    out = json_path("Event_Archive.json")
    save_json({"Events": archive}, out)
    print(f"[+] extracted {len(archive)} events -> {out}")
    return archive


def _join_named(items):
    return " / ".join(item.get("Name", "") for item in items if item.get("Name"))


def _reward_text(rewards):
    parts = []
    for reward in rewards or []:
        name = reward.get("RewardName") or reward.get("RewardType")
        count = reward.get("RewardCount")
        label = reward.get("RewardTypeLabel") or reward.get("RewardType")
        parts.append(f"{name} x{count} [{label}]")
    return " / ".join(parts)


def export():
    from openpyxl import Workbook
    from openpyxl.styles import Alignment

    data = load_json(json_path("Event_Archive.json"))
    events = data.get("Events", [])
    out = xlsx_path("event_archive.xlsx")

    wb = Workbook()
    overview = wb.active
    overview.title = "Overview"
    overview.append([
        "活动ID", "活动名", "活动类型", "活动类型码", "数据来源分支", "数据来源说明",
        "开始", "开放", "后半开放", "排名结束", "结束", "关联角色", "关联卡牌",
        "PickUp卡牌", "兑换所ID", "剧情章节数", "规则页数", "活动材料关卡数", "Logo", "弹窗图",
    ])
    for e in events:
        overview.append([
            e.get("EventId"), e.get("Title"), e.get("ActivityType"), e.get("EventFormat"),
            e.get("SourceSubtype"), e.get("SourceSubtypeLabel"), e.get("StartTime"),
            e.get("OpenStartTime"), e.get("SecondHalfStartTime"),
            e.get("RankingEndTime"), e.get("EndTime"), _join_named(e.get("Characters", [])),
            _join_named(e.get("Cards", [])), _join_named(e.get("PickUpCards", [])),
            e.get("ExchangeId"), len(e.get("StorySections", [])), len(e.get("Rules", [])),
            e.get("PuzzleIngredientStageCount"), e.get("Assets", {}).get("Logo"),
            e.get("Assets", {}).get("PromotionalPopup"),
        ])

    story = wb.create_sheet("Story")
    story.append(["活动ID", "活动名", "章节序号", "章节组", "章节类型码", "章节标题", "开放时间", "解锁需求值", "钥匙消耗", "是否有语音", "弹窗文本", "阅读奖励"])
    for e in events:
        for s in e.get("StorySections", []):
            story.append([
                e.get("EventId"), e.get("Title"), s.get("No"), s.get("Group"), s.get("Type"),
                s.get("Title"), s.get("ReleaseDateTime"), s.get("RequiredValue"), s.get("KeyCost"),
                s.get("HasVoice"), s.get("PopupText"), _reward_text(s.get("ReadRewards")),
            ])

    rules = wb.create_sheet("Rules")
    rules.append(["活动ID", "活动名", "规则页序号", "规则类型码", "开放时间", "说明图文件", "说明文本"])
    for e in events:
        for r in e.get("Rules", []):
            rules.append([
                e.get("EventId"), e.get("Title"), r.get("SlideNo"), r.get("Type"),
                r.get("ReleaseDateTime"), r.get("DescriptionFileName"), r.get("Description"),
            ])

    shifts = wb.create_sheet("Shifts")
    shifts.append(["活动ID", "活动名", "轮班/OJT ID", "角色", "开始", "结束", "训练开始脚本", "训练完成脚本"])
    for e in events:
        for s in e.get("Shifts", []):
            shifts.append([
                e.get("EventId"), e.get("Title"), s.get("ShiftId"), s.get("CharacterName"),
                s.get("StartTime"), s.get("EndTime"), s.get("TrainingStartScript", ""), s.get("TrainingClearScript", ""),
            ])

    rewards = wb.create_sheet("RewardSummary")
    rewards.append(["活动ID", "活动名", "奖励类别", "条件/档位", "是否重点奖励", "奖励内容"])
    for e in events:
        for r in e.get("Rewards", {}).get("Ranking", []):
            rewards.append([e.get("EventId"), e.get("Title"), "Ranking", f"type {r.get('RankingType')} rank {r.get('StartRank')}", "", _reward_text(r.get("Rewards"))])
        for r in e.get("Rewards", {}).get("Sales", []):
            rewards.append([e.get("EventId"), e.get("Title"), "Sales", f"shift {r.get('ShiftId')} sales {r.get('KeySales')}", r.get("IsPickUp"), _reward_text(r.get("Rewards"))])
        for r in e.get("Rewards", {}).get("Accumulate", []):
            rewards.append([e.get("EventId"), e.get("Title"), "Accumulate", r.get("KeyCount"), r.get("IsPickUp"), _reward_text(r.get("Rewards"))])

    mappings = wb.create_sheet("Mappings")
    mappings.append(["类别", "码值/Key", "说明"])
    for code, info in sorted(EVENT_FORMAT_MAP.items()):
        mappings.append(["活动类型 EventFormat", code, f"{info['Label']} ({info['Key']})"])
    for key, label in SOURCE_SUBTYPE_MAP.items():
        mappings.append(["数据来源分支 SourceSubtype", key, label])
    for code, info in sorted(REWARD_TYPE_MAP.items()):
        mappings.append(["奖励类型 RewardTypeCode", code, f"{info['Label']} ({info['Key']})"])

    for ws in wb.worksheets:
        ws.freeze_panes = "A2"
        for col in ws.columns:
            letter = col[0].column_letter
            ws.column_dimensions[letter].width = min(max(len(str(cell.value or "")) for cell in col[:80]) + 2, 60)
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and ("<br>" in cell.value or "\n" in cell.value):
                    cell.alignment = Alignment(wrap_text=True, vertical="top")

    wb.save(out)
    print(f"  [xlsx] {out}")


def run():
    extract()
    export()
