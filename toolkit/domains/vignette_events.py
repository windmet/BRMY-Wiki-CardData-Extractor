"""Vignette 活动档案：EventFormat 6（AAccumulateItem，累积道具活动）。"""
from ..core.availability import assessment_time, date_window, STATUS_LABELS
from ..core.exporter import audit_path, xlsx_path, write_workbook
from ..core.output import record_warning
from ..core.rewards import RewardResolver
from ..core.scanner import save_json
from .event_common import FORMAT_ACCUMULATE, Names, bonus_text, jst, reward_text, tier_label, tier_ranges


def extract(session, *, as_of=None):
    tables = session.tables
    now = assessment_time(as_of)
    names = Names(tables)
    rewards = RewardResolver(tables)
    issues = []
    extension = tables.by_id('mst_event_accumulate_item', 'EventId', required=False)
    bonuses = tables.by_id('mst_event_bonus', 'EventBonusId', required=False)
    tiers = tables.group_by('mst_event_accumulate_item_reward', 'EventId', required=False)
    items = tables.by_id('mst_item', 'ItemId', active_only=False, required=False)

    archive = []
    for event in sorted(tables.rows('mst_event', active_only=True), key=lambda e: e.get('EventId', 0)):
        if event.get('EventFormat') != FORMAT_ACCUMULATE:
            continue
        eid = event['EventId']
        raw = extension.get(eid)
        if not raw:
            issues.append({'Status': 'missing_event_accumulate_item', 'EventId': eid})
            raw = {}
        item = raw.get('EventItemId')
        archive.append({
            'EventId': eid, 'Title': event.get('EventTitle', ''), 'RawEvent': event, 'RawExtension': raw,
            'Availability': date_window(event.get('OpenStartTime') or event.get('StartTime'), event.get('EndTime'),
                                        as_of=now, active=event.get('IsActive', True)),
            'Characters': '、'.join(names.character(c) for c in raw.get('CharacterIds') or []),
            'PickUpCards': names.cards(raw.get('PickUpCharacterCardIds')),
            'Cards': names.cards(raw.get('CharacterCardIds')),
            'Item': (items.get(item, {}).get('ItemName') or f'道具({item})') if item else '',
            'Bonus': bonus_text(bonuses.get(raw.get('EventBonusId'))),
            'Tiers': [dict(r, Rewards=rewards.direct(r.get('DirectRewardGroupId')))
                      for r in sorted(tiers.get(eid, []), key=lambda r: r.get('KeyCount', 0))],
        })
    return {'AsOf': now.isoformat(), 'Events': archive, 'Issues': issues, 'RewardIssues': rewards.issues}


def export(data):
    overview, tiers = [], []
    for event in data['Events']:
        eid, title, raw = event['EventId'], event['Title'], event['RawEvent']
        overview.append([eid, title, jst(raw.get('OpenStartTime') or raw.get('StartTime')), jst(raw.get('EndTime')),
                         STATUS_LABELS[event['Availability']['Status']], event['Characters'], event['PickUpCards'],
                         event['Cards'], event['Item'], event['Bonus'], len(event['Tiers'])])
        for first, last, count, text in tier_ranges(
                event['Tiers'], 'KeyCount', lambda r: (reward_text(r['Rewards']), bool(r.get('IsPickUp')))):
            tiers.append([eid, title, tier_label(first, last, count), text[0], '是' if text[1] else ''])
    return write_workbook(xlsx_path('Vignette活动档案.xlsx'), [
        {'title': '活动总览', 'headers': ['活动ID', '活动名', '开放(JST)', '结束(JST)', '日期状态', '登场角色', 'PICKUP 卡',
                                       '活动卡牌', '累积道具', '活动加成', '奖励档数'],
         'rows': overview, 'col_widths': {'B': 30, 'F': 30, 'G': 40, 'H': 50, 'I': 20, 'J': 40}, 'wrap_cols': [7, 8, 10]},
        {'title': '累积奖励', 'headers': ['活动ID', '活动名', '累积数量', '奖励', '重点奖励'], 'rows': tiers,
         'col_widths': {'B': 30, 'C': 36, 'D': 60}, 'wrap_cols': [4]},
        {'title': '说明', 'headers': ['项目', '说明'], 'col_widths': {'A': 16, 'B': 90}, 'wrap_cols': [2], 'rows': [
            ['范围', '客户端 EventFormat 6（AAccumulateItem），活动名为「Vignette -○○/○○-」的累积道具活动。'],
            ['核对时刻', jst(data['AsOf']) + '（JST）；所有时间均为日本时间。'],
            ['累积奖励', '累积道具达到数量即得；奖励相同的连续档位合并为一行，区间内每档各得一次。「重点奖励」即游戏内高亮的档位。'],
            ['加成', '按 mst_event_bonus 字段名翻译，游戏内未找到逐项文字。'],
            ['剧情与任务', '剧情章节、活动任务在「活动总表」（event_archive.xlsx）。'],
            ['名称缺失', '游戏数据里没有名称的奖励写作「类型(ID)」；清单见 待核对汇总.xlsx。'],
        ]},
    ])


def run(session=None, *, as_of=None):
    data = extract(session, as_of=as_of)
    save_json(data, audit_path('vignette_events.json'))
    if data['Issues'] or data['RewardIssues']:
        record_warning(f"Vignette 活动存在 {len(data['Issues'])} 条关系异常、{len(data['RewardIssues'])} 条奖励缺项，"
                       '详见 vignette_events.json')
    return export(data)
