"""Event archive extraction and export."""
from ..core.scanner import load_json, save_json
from ..core.exporter import json_path, xlsx_path, write_workbook, audit_path
from ..core.data import clean_text
from ..core.tables import TableCatalog
from ..core.rewards import RewardResolver, REWARD_TYPE_MAP
from ..core.output import record_warning
from .event_classification import classify_event
from .event_missions import extract_event_missions
from .event_common import Names, jst, plain_text, reward_text
from ..core.availability import assessment_time, date_window, STATUS_LABELS

INPUT_JSON = 'master_data.json'

EVENT_FORMAT_MAP = {
    1: {"Key": "standard_exchange", "Label": "交换所活动（A）"},
    2: {"Key": "story_campaign_a", "Label": "无奖章活动（ANonMedal）"},
    3: {"Key": "bar_sales", "Label": "营业活动（B）"},
    4: {"Key": "special_bar_sales", "Label": "营业活动特别版（BSpecial）"},
    5: {"Key": "ojt", "Label": "OJT（C）"},
    6: {"Key": "accumulate_item", "Label": "Vignette 累积道具活动（AAccumulateItem）"},
}

SOURCE_SUBTYPE_MAP = {
    "event_a": "mst_event_a：普通活动扩展表",
    "event_b": "mst_event_b：营业/酒保活动扩展表",
    "event_c": "mst_event_c：OJT/特殊活动扩展表",
    "accumulate_item": "mst_event_accumulate_item：累积道具活动扩展表",
    "ojt": "mst_event_ojt_shift：OJT轮次表",
    "unknown": "未匹配到活动扩展表",
}


def _names(ids, mapping):
    return [mapping.get(i, f"Unknown({i})") for i in ids or []]


def extract(session=None, *, as_of=None):
    as_of = assessment_time(as_of)
    tables = session.tables if session else TableCatalog(load_json(INPUT_JSON))

    events = tables.require("mst_event", active_only=True)

    def optional_by_id(name, key):
        return tables.by_id(name, key, required=False)

    def optional_group(name, key):
        return tables.group_by(name, key, required=False)

    event_a = optional_by_id("mst_event_a", "EventId")
    event_b = optional_by_id("mst_event_b", "EventId")
    event_c = optional_by_id("mst_event_c", "EventId")
    event_acc = optional_by_id("mst_event_accumulate_item", "EventId")
    event_story = optional_by_id("mst_event_story", "EventId")
    stories = optional_group("mst_event_story_section", "EventId")
    rules = optional_group("mst_event_rule_window", "EventId")
    ojt_shifts = optional_group("mst_event_ojt_shift", "EventId")

    characters = optional_by_id("mst_character", "CharacterId")
    cards = optional_by_id("mst_character_card", "CharacterCardId")
    items = optional_by_id("mst_item", "ItemId")
    character_map = {k: v.get("CharacterNameJpn", "") for k, v in characters.items()}
    names = Names(tables)
    card_map = {k: names.card(k) for k in cards}
    item_map = {k: v.get("ItemName", "") for k, v in items.items()}
    rewards = RewardResolver(tables, card_names=card_map)
    event_missions, mission_audit = extract_event_missions(tables)
    for missions in event_missions.values():
        for mission in missions:
            raw = mission['RawMission']
            mission['Availability'] = date_window(raw.get('StartTime'), raw.get('EndTime'),
                                                  as_of=as_of, active=raw.get('IsActive', True))

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
                "ReadRewards": rewards.direct(row.get("ReadDirectRewardGroupId")),
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

        event_format = EVENT_FORMAT_MAP.get(event.get("EventFormat"), {"Key": "unknown", "Label": "未知活动类型"})
        subtype_label = SOURCE_SUBTYPE_MAP.get(subtype, SOURCE_SUBTYPE_MAP["unknown"])
        classification = classify_event(event, event_a.get(event_id))

        archive.append({
            "EventId": event_id,
            "Title": event.get("EventTitle", ""),
            "EventFormat": event.get("EventFormat"),
            "EventFormatName": event_format["Key"],
            "EventFormatLabel": event_format["Label"],
            "ActivityType": classification["DisplayLabel"],
            "Classification": classification,
            "Availability": dict(date_window(
                event.get('OpenStartTime') or event.get('StartTime'), event.get('EndTime'),
                as_of=as_of, active=event.get('IsActive', True)),
                StartField='OpenStartTime' if event.get('OpenStartTime') else 'StartTime',
                EndField='EndTime'),
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
            "Missions": event_missions.get(event_id, []),
        })

    out = json_path("Event_Archive.json")
    save_json({"Events": archive, "TimeAssessment": {
        'AsOf': as_of.isoformat(), 'Timezone': 'UTC', 'Boundary': '[start,end)',
        'AccountUnlock': 'not_assessed', 'DateFiltering': 'none',
    }}, out)
    save_json({"Issues": rewards.issues}, audit_path("event_reward_resolution.json"))
    save_json(mission_audit, audit_path("event_mission_relations.json"))
    if mission_audit['Issues']:
        record_warning(f"活动任务有 {len(mission_audit['Issues'])} 条关系或奖励缺项，详见 event_mission_relations.json")
    if rewards.issues:
        record_warning(f"活动奖励有 {len(rewards.issues)} 条解析或名称缺项，详见 event_reward_resolution.json")
    print(f"[+] extracted {len(archive)} events -> {out}")
    return archive


def _join_named(items):
    return " / ".join(item.get("Name", "") for item in items if item.get("Name"))


# Coly.S2BShared.Enums.EventStorySectionType.
STORY_SECTION_TYPES = {1: '通常', 2: 'アナザー', 3: 'アナザー（轮班营业额解锁）'}
DETAIL_WORKBOOKS = {
    'exchange': '交换所与剧情活动.xlsx', 'non_medal': '交换所与剧情活动.xlsx',
    'making': '营业活动档案.xlsx', 'ojt': 'ojt_archive.xlsx', 'vignette': 'Vignette活动档案.xlsx',
}


def export():
    data = load_json(json_path("Event_Archive.json"))
    events = data.get("Events", [])
    save_json({"Archive": data, "Mappings": {
        "EventFormat": EVENT_FORMAT_MAP,
        "SourceSubtype": SOURCE_SUBTYPE_MAP,
        "RewardType": REWARD_TYPE_MAP,
    }}, audit_path("event_archive_audit.json"))

    overview, story, missions, rules = [], [], [], []
    for e in events:
        cls = e.get("Classification", {})
        prefix = [e.get("EventId"), e.get("Title")]
        overview.append(prefix + [
            cls.get("FamilyLabel", e.get("ActivityType")), cls.get("SubtypeLabel", ""),
            jst(e.get("OpenStartTime") or e.get("StartTime")), jst(e.get("EndTime")),
            STATUS_LABELS.get(e.get('Availability', {}).get('Status'), '时间状态未知'),
            _join_named(e.get("PickUpCards", [])), len(e.get("StorySections", [])), len(e.get("Missions", [])),
            DETAIL_WORKBOOKS.get(cls.get("Family"), ""),
        ])
        for s in e.get("StorySections", []):
            story.append(prefix + [
                s.get("No"), STORY_SECTION_TYPES.get(s.get("Type"), s.get("Type")), s.get("Title"),
                jst(s.get("ReleaseDateTime")), s.get("RequiredValue"), s.get("KeyCost"),
                '有' if s.get("HasVoice") else '', plain_text(s.get("PopupText")), reward_text(s.get("ReadRewards")),
            ])
        for mission in e.get('Missions', []):
            raw = mission['RawMission']
            for seq in mission['Sequences']:
                missions.append(prefix + [
                    mission['MissionId'], seq['SequenceNo'], seq['Border'], plain_text(seq['Description']),
                    jst(raw.get('StartTime', '')), jst(raw.get('EndTime', '')), '是' if seq['IsHidden'] else '',
                    reward_text(seq['Rewards']),
                    STATUS_LABELS.get(mission.get('Availability', {}).get('Status'), '时间状态未知'),
                ])
        for r in e.get("Rules", []):
            rules.append(prefix + [r.get("SlideNo"), jst(r.get("ReleaseDateTime")), plain_text(r.get("Description"))])

    out = write_workbook(xlsx_path("event_archive.xlsx"), [
        {'title': '活动一览', 'headers': ['活动ID', '活动名', '类型', '子型', '开放(JST)', '结束(JST)', '日期状态',
                                       'PICKUP 卡', '剧情章节数', '任务数', '详细档案'],
         'rows': overview, 'col_widths': {'B': 34, 'C': 18, 'D': 18, 'H': 40, 'K': 24}},
        {'title': '剧情章节', 'headers': ['活动ID', '活动名', '章节', '章节类型', '章节标题', '开放(JST)', '解锁需求值',
                                       '钥匙消耗', '语音', '弹窗文本', '阅读奖励'],
         'rows': story, 'col_widths': {'B': 34, 'E': 24, 'J': 40, 'K': 30}, 'wrap_cols': [10]},
        {'title': '活动任务', 'headers': ['活动ID', '活动名', '任务ID', '阶段', '目标值', '任务内容', '开始(JST)',
                                       '结束(JST)', '隐藏', '奖励', '日期状态'],
         'rows': missions, 'col_widths': {'B': 34, 'F': 50, 'J': 40}},
        {'title': '规则说明', 'headers': ['活动ID', '活动名', '页', '开放(JST)', '说明文本'], 'rows': rules,
         'col_widths': {'B': 34, 'E': 80}, 'wrap_cols': [5]},
        {'title': '说明', 'headers': ['项目', '说明'], 'col_widths': {'A': 16, 'B': 90}, 'wrap_cols': [2], 'rows': [
            ['用途', '全部活动的索引：每期一行，附剧情章节、活动任务和规则说明。各类型的玩法细节在「详细档案」列所指的工作簿。'],
            ['类型', '按客户端 EventFormat：交换所活动、无奖章活动（再按 EventAType 分子型）、营业（摇酒）活动、OJT、Vignette 活动。'],
            ['核对时刻', jst(data.get('TimeAssessment', {}).get('AsOf', '')) + '（JST）；所有时间均为日本时间。'],
            ['日期状态', '按核对时刻与开放 / 结束时间判断；历史、未来和占位日期的记录全部收录。'],
            ['章节类型', '通常 / アナザー / アナザー（轮班营业额解锁，营业活动专用）。解锁需求值是活动 pt（营业活动为营业额）。'],
            ['名称缺失', '游戏数据里没有名称的奖励写作「类型(ID)」；清单见 待核对汇总.xlsx。'],
        ]},
    ])
    return out


def run(session=None, *, as_of=None):
    extract(session=session, as_of=as_of)
    export()
