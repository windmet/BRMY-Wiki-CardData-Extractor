"""交换所与剧情活动档案：EventFormat 1（交换所）与 2（无奖章：Prequel / Travelogue / 周年等）。"""
from collections import defaultdict

from ..core.availability import assessment_time, date_window, STATUS_LABELS
from ..core.exporter import audit_path, xlsx_path, write_workbook
from ..core.output import record_warning
from ..core.rewards import RewardResolver
from ..core.scanner import save_json
from .event_classification import classify_event
from .event_common import FORMAT_EXCHANGE, FORMAT_NON_MEDAL, Names, bonus_text, jst, reward_text

# Coly.S2BShared.Enums.RankingType.
RANKING_TYPES = {1: '高分排名', 2: '活动 pt 排名'}
OPEN_END = '9999'


def _ranges(rows):
    """StartRank tiers → (first, last) ranks; a closing row without a present only marks the bound."""
    result = []
    for index, row in enumerate(rows):
        following = rows[index + 1]['StartRank'] if index + 1 < len(rows) else None
        if not row.get('PresentId'):
            continue
        result.append((row, row['StartRank'], following - 1 if following else None))
    return result


def extract(session, *, as_of=None):
    tables = session.tables
    now = assessment_time(as_of)
    names = Names(tables)
    rewards = RewardResolver(tables)
    issues = []
    event_a = tables.by_id('mst_event_a', 'EventId', required=False)
    bonuses = tables.by_id('mst_event_bonus', 'EventBonusId', required=False)
    campaigns = tables.by_id('mst_campaign', 'CampaignId', required=False)
    exchanges = tables.by_id('mst_exchange', 'ExchangeId', required=False)
    products = tables.group_by('mst_exchange_product', 'ExchangeId', required=False)
    rankings = tables.group_by('mst_event_ranking_reward', 'EventId', required=False)
    items = tables.by_id('mst_item', 'ItemId', active_only=False, required=False)

    def item_name(iid):
        return items.get(iid, {}).get('ItemName') or f'道具({iid})'

    archive = []
    for event in sorted(tables.rows('mst_event', active_only=True), key=lambda e: e.get('EventId', 0)):
        if event.get('EventFormat') not in (FORMAT_EXCHANGE, FORMAT_NON_MEDAL):
            continue
        eid = event['EventId']
        raw_a = event_a.get(eid)
        if not raw_a:
            issues.append({'Status': 'missing_event_a', 'EventId': eid})
            raw_a = {}
        exchange = exchanges.get(raw_a.get('ExchangeId'))
        if raw_a.get('ExchangeId') and not exchange:
            issues.append({'Status': 'missing_exchange', 'EventId': eid, 'ExchangeId': raw_a.get('ExchangeId')})
        shop = []
        for row in sorted(products.get(raw_a.get('ExchangeId'), []) if exchange else [],
                          key=lambda r: r.get('ExchangeProductNo', 0)):
            cost_item = exchange.get(f"CostItemId{row.get('CostItemIdNumber') or 1}")
            shop.append(dict(row, Rewards=rewards.direct(row.get('DirectRewardGroupId')),
                             CostText=f"{item_name(cost_item)} x{row.get('CostItemCount')}"))
        ranking = defaultdict(list)
        for row in sorted(rankings.get(eid, []), key=lambda r: (r.get('RankingType', 0), r.get('StartRank', 0))):
            ranking[row.get('RankingType')].append(row)
        ranking_rows = []
        for kind, rows in sorted(ranking.items()):
            for row, first, last in _ranges(rows):
                ranking_rows.append({'Type': RANKING_TYPES.get(kind, f'排名类型{kind}'), 'First': first, 'Last': last,
                                     'Wappen': row.get('RewardWappenCount') or 0,
                                     'Rewards': rewards.present(row.get('PresentId'))})
        campaign = campaigns.get(raw_a.get('CampaignId')) if raw_a.get('CampaignId') else None
        archive.append({
            'EventId': eid, 'Title': event.get('EventTitle', ''), 'RawEvent': event, 'RawEventA': raw_a,
            'Classification': classify_event(event, raw_a or None),
            'Availability': date_window(event.get('OpenStartTime') or event.get('StartTime'), event.get('EndTime'),
                                        as_of=now, active=event.get('IsActive', True)),
            'PickUpCard': names.card(raw_a['PickUpCharacterCardId']) if raw_a.get('PickUpCharacterCardId') else '',
            'Cards': names.cards(raw_a.get('CharacterCardIds')),
            'Bonus': bonus_text(bonuses.get(raw_a.get('EventBonusId'))),
            'EventItem': item_name(raw_a['EventItemId']) if raw_a.get('EventItemId') else '',
            'Campaign': (campaign or {}).get('CampaignTitle', ''),
            'Exchange': (exchange or {}).get('ExchangeName', ''), 'Shop': shop, 'Rankings': ranking_rows,
        })
    return {'AsOf': now.isoformat(), 'Events': archive, 'Issues': issues, 'RewardIssues': rewards.issues}


def _rank_text(first, last):
    if last is None:
        return f'{first:,} 名以后'
    return f'第 {first:,} 名' if first == last else f'{first:,}～{last:,} 名'


def export(data):
    overview, ranking, shop = [], [], []
    for event in data['Events']:
        eid, title, raw = event['EventId'], event['Title'], event['RawEvent']
        cls = event['Classification']
        prefix = [eid, title]
        overview.append(prefix + [
            cls['FamilyLabel'], cls['SubtypeLabel'], jst(raw.get('OpenStartTime') or raw.get('StartTime')),
            jst(raw.get('SecondHalfStartTime')), jst(raw.get('EventRankingEndTime')), jst(raw.get('EndTime')),
            STATUS_LABELS[event['Availability']['Status']], event['PickUpCard'], event['Cards'], event['EventItem'],
            event['Bonus'], event['Exchange'], len(event['Shop']), event['Campaign'],
        ])
        for row in event['Rankings']:
            ranking.append(prefix + [cls['SubtypeLabel'], row['Type'], _rank_text(row['First'], row['Last']),
                                     reward_text(row['Rewards']), row['Wappen'] or ''])
        opened = raw.get('OpenStartTime') or raw.get('StartTime')
        for row in event['Shop']:
            stock = row.get('ProductAllStock')
            start, end = row.get('StartTime', ''), row.get('EndTime', '')
            shop.append(prefix + [row.get('ExchangeProductNo'), reward_text(row['Rewards']), row['CostText'],
                                  stock if stock else '不限',
                                  '' if not start or start <= (opened or '') else jst(start),
                                  '' if not end or end.startswith(OPEN_END) or end == raw.get('EndTime') else jst(end)])
    return write_workbook(xlsx_path('交换所与剧情活动.xlsx'), [
        {'title': '活动总览', 'headers': ['活动ID', '活动名', '类型', '子型', '开放(JST)', '后半开始(JST)', '排名结束(JST)',
                                       '结束(JST)', '日期状态', 'PICKUP 卡', '活动卡牌', '活动 pt 道具', '活动加成',
                                       '兑换所', '商品数', '同期活动'],
         'rows': overview, 'col_widths': {'B': 30, 'D': 16, 'J': 30, 'K': 50, 'M': 40, 'N': 30}, 'wrap_cols': [11, 13]},
        {'title': '排名奖励', 'headers': ['活动ID', '活动名', '子型', '排名种类', '名次', '奖励', 'ワッペン'],
         'rows': ranking, 'col_widths': {'B': 30, 'E': 18, 'F': 60}, 'wrap_cols': [6]},
        {'title': '兑换所', 'headers': ['活动ID', '活动名', '商品序号', '商品', '消耗', '可兑换次数', '追加上架(JST)', '提前下架(JST)'],
         'rows': shop, 'col_widths': {'B': 30, 'D': 50, 'E': 24}, 'wrap_cols': [4]},
        {'title': '说明', 'headers': ['项目', '说明'], 'col_widths': {'A': 16, 'B': 90}, 'wrap_cols': [2], 'rows': [
            ['范围', '客户端 EventFormat 1（A，交换所活动）与 2（ANonMedal，无奖章活动）。营业（摇酒）、OJT、Vignette 各有单独档案。'],
            ['子型', '无奖章活动按 mst_event_a.EventAType 分：2 = Travel / Prequel（有排名，按标题前缀再分 Prequel / Travelogue）、'
                   '4 = 无排名特别活动（半周年、新年、RMX FES 等）、5 = 阶段任务周年活动（1st / 2nd Anniversary）。'],
            ['核对时刻', jst(data['AsOf']) + '（JST）；所有时间均为日本时间。'],
            ['排名奖励', '名次区间由相邻两档的起始名次推出；最后一档没有奖励时只作为区间终点，不单列。ワッペン为该档另发的ワッペン数。'],
            ['兑换所', '「可兑换次数」为 ProductAllStock，0 写作「不限」。商品在活动开放后才追加上架、或早于活动结束下架时，才写对应时间。'],
            ['加成', '按 mst_event_bonus 字段名翻译（活动卡牌 / 稀有度 / 突破阶段 / 角色 / 属性），游戏内未找到逐项文字。'],
            ['同期活动', 'mst_event_a.CampaignId 指向的キャンペーン名称，只有周年等少数活动有。'],
            ['名称缺失', '游戏数据里没有名称的奖励写作「类型(ID)」；清单见 待核对汇总.xlsx。'],
        ]},
    ])


def run(session=None, *, as_of=None):
    data = extract(session, as_of=as_of)
    save_json(data, audit_path('exchange_events.json'))
    if data['Issues'] or data['RewardIssues']:
        record_warning(f"交换所与剧情活动存在 {len(data['Issues'])} 条关系异常、{len(data['RewardIssues'])} 条奖励缺项，"
                       '详见 exchange_events.json')
    return export(data)
