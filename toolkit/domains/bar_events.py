"""营业（摇酒）活动档案：EventFormat 3 / 4 的轮班、菜单、材料、关卡掉落和营业额奖励。"""
from collections import defaultdict

from ..core.availability import assessment_time, date_window, STATUS_LABELS
from ..core.exporter import audit_path, xlsx_path, write_workbook
from ..core.output import record_warning
from ..core.rewards import RewardResolver
from ..core.scanner import save_json
from .event_common import (FORMAT_BAR, FORMAT_BAR_SPECIAL, Names, bonus_text, jst, plain_text,
                           reward_text, tier_label, tier_ranges)

KINDS = {FORMAT_BAR: '常规', FORMAT_BAR_SPECIAL: '特别版'}
RANKS = ('SS', 'S', 'A', 'B', 'C', 'D', 'E')
FACES = {1: 'A', 2: 'B', 3: 'C', 4: 'D', 5: 'E', 6: 'F'}
# Coly.S2BShared.Enums.MenuUnlockConditionCode; wording from the client's unlock hints.
UNLOCK_TEXT = {
    1: lambda v1, v2: f'上一道配方制作 {v2} 次',
    2: lambda v1, v2: f'材料({v1}) 收集 {v2} 个',
    3: lambda v1, v2: f'营业额达到 {v1:,} EN',
}
# IngredientId ranges as they appear in mst_event_ingredient (no category field exists).
INGREDIENT_RANGES = [(1, 50, '基酒'), (51, 100, '利口酒'), (101, 200, '软饮'), (201, 1000, '辅料'),
                     (10000, None, '联动限定')]


def ingredient_kind(iid):
    for low, high, label in INGREDIENT_RANGES:
        if iid >= low and (high is None or iid < high):
            return label
    return '其他'


def _stage_key(row):
    return row.get('PuzzleMapId'), row.get('PuzzleStageNo'), row.get('PuzzleType')


def extract(session, *, as_of=None):
    tables = session.tables
    now = assessment_time(as_of)
    names = Names(tables)
    rewards = RewardResolver(tables)
    issues = []

    def by_id(name, key):
        return tables.by_id(name, key, required=False)

    def grouped(name, key):
        return tables.group_by(name, key, required=False)

    event_b = by_id('mst_event_b', 'EventId')
    bonuses = by_id('mst_event_bonus', 'EventBonusId')
    shifts = grouped('mst_event_shift', 'EventId')
    specials = grouped('mst_event_special_time', 'ShiftId')
    menus = grouped('mst_event_menu', 'ShiftId')
    recipes = by_id('mst_event_recipe', 'RecipeId')
    unlocks = by_id('mst_event_menu_unlock_condition', 'MenuUnlockConditionId')
    ingredients = by_id('mst_event_ingredient', 'IngredientId')
    sales = grouped('mst_event_sales_reward', 'EventId')
    maps = grouped('mst_puzzle_map', 'EventId')
    stages = grouped('mst_puzzle_stage', 'PuzzleMapId')
    music_stages = by_id('mst_music_puzzle_stage', 'MusicPuzzleStageId')
    music = by_id('mst_music', 'MusicId')
    overlays = grouped('mst_event_puzzle_stage_ingredient', 'EventId')
    drop_groups = grouped('mst_event_puzzle_drop_reward_ingredient', 'PuzzleDropRewardIngredientGroupId')

    def ingredient_name(iid):
        return ingredients.get(iid, {}).get('IngredientName') or f'材料({iid})'

    def music_name(stage):
        relation = music_stages.get(stage.get('MusicPuzzleStageId'), {})
        return music.get(relation.get('MusicId'), {}).get('DisplayName') or f"曲目({stage.get('MusicPuzzleStageId')})"

    def drops(overlay):
        """One text per distinct rank group; ranks share a group in every current stage."""
        by_group = defaultdict(list)
        for rank in RANKS:
            by_group[overlay.get(f'PuzzleDropRewardIngredientGroupId{rank}') or 0].append(rank)
        parts = []
        for gid, ranks in by_group.items():
            rows = sorted(drop_groups.get(gid, []), key=lambda r: r.get('PuzzleDropRewardIngredientSequenceNo', 0))
            total = sum(r.get('LotteryRate') or 0 for r in rows)
            text = ' / '.join(f"{ingredient_name(r.get('RewardTargetId'))} x{r.get('RewardCount')}"
                              + (f"（{(r.get('LotteryRate') or 0) / total:.0%}）" if total and len(rows) > 1 else '')
                              for r in rows) or ('（无）' if not gid else f'掉落组({gid})')
            parts.append(text if len(by_group) == 1 else f"{'/'.join(ranks)}：{text}")
        return '；'.join(parts)

    archive = []
    for event in sorted(tables.rows('mst_event', active_only=True), key=lambda e: e.get('EventId', 0)):
        if event.get('EventFormat') not in KINDS:
            continue
        eid = event['EventId']
        raw_b = event_b.get(eid)
        if not raw_b:
            issues.append({'Status': 'missing_event_b', 'EventId': eid})
            raw_b = {}
        event_shifts = sorted(shifts.get(eid, []), key=lambda r: (r.get('StartTime', ''), r.get('ShiftId', 0)))
        shift_numbers = {s['ShiftId']: n for n, s in enumerate(event_shifts, start=1)}

        # Event-map stages carry no ShiftId; they belong to the shift whose window they share exactly.
        overlay_by_key = {_stage_key(o): o for o in overlays.get(eid, [])}
        event_map_ids = {m['PuzzleMapId'] for m in maps.get(eid, [])}
        shift_stages = defaultdict(list)
        for map_id in sorted(event_map_ids):
            for stage in stages.get(map_id, []):
                matched = [s for s in event_shifts if s.get('StartTime') == stage.get('ReleaseDateTime')
                           and s.get('EndTime') == stage.get('EndTime')]
                if len(matched) != 1:
                    issues.append({'Status': 'unmatched_stage' if not matched else 'ambiguous_stage',
                                   'EventId': eid, 'Stage': list(_stage_key(stage))})
                    continue
                overlay = overlay_by_key.get(_stage_key(stage))
                shift_stages[matched[0]['ShiftId']].append({
                    'StageNo': stage.get('PuzzleStageNo'), 'Face': FACES.get(stage.get('PuzzleType'), stage.get('PuzzleType')),
                    'MusicPuzzleStageId': stage.get('MusicPuzzleStageId'), 'Music': music_name(stage),
                    'PickUp': [ingredient_name(i) for i in (overlay or {}).get('PickUpIngredientIds') or []],
                    'Drops': drops(overlay) if overlay else '（游戏数据未配置材料掉落）', 'Raw': stage,
                })
        music_sets = [{s['MusicPuzzleStageId'] for s in shift_stages.get(sh['ShiftId'], [])} for sh in event_shifts]
        shared = set.intersection(*music_sets) if music_sets else set()
        other_overlays = [o for o in overlays.get(eid, []) if o.get('PuzzleMapId') not in event_map_ids]

        shift_entries = []
        for shift in event_shifts:
            sid = shift['ShiftId']
            menu = []
            for row in sorted(menus.get(sid, []), key=lambda r: r.get('MenuSequenceNo', 0)):
                recipe = recipes.get(row.get('RecipeId'))
                if not recipe:
                    issues.append({'Status': 'missing_recipe', 'ShiftId': sid, 'RecipeId': row.get('RecipeId')})
                    continue
                conditions = []
                for key in ('MenuUnlockConditionIdA', 'MenuUnlockConditionIdB'):
                    cond = unlocks.get(row.get(key)) if row.get(key) else None
                    if row.get(key) and not cond:
                        issues.append({'Status': 'missing_unlock_condition', 'ShiftId': sid, 'Id': row.get(key)})
                    if cond:
                        render = UNLOCK_TEXT.get(cond.get('MenuUnlockConditionCode'))
                        conditions.append(render(cond.get('Value1'), cond.get('Value2')) if render
                                          else f"条件类型{cond.get('MenuUnlockConditionCode')}")
                recommend = recipe.get('RecommendCharacterId')
                menu.append({'SequenceNo': row.get('MenuSequenceNo'), 'Recipe': recipe,
                             'Unlock': '、'.join(conditions) or '一开始即可制作',
                             'Recommend': names.character(recommend) if recommend else '',
                             'Ingredients': [ingredient_name(i) for i in recipe.get('IngredientIds') or []],
                             'Rewards': rewards.direct(recipe.get('DirectRewardGroupId'))})
            for stage in shift_stages.get(sid, []):
                stage['Shared'] = stage['MusicPuzzleStageId'] in shared
            shift_entries.append({
                'Number': shift_numbers[sid], 'Raw': shift, 'Character': names.character(shift.get('CharacterId')),
                'Availability': date_window(shift.get('StartTime'), shift.get('EndTime'), as_of=now,
                                            active=shift.get('IsActive', True)),
                'Menu': menu,
                'Stages': sorted(shift_stages.get(sid, []), key=lambda s: (s['StageNo'], str(s['Face']))),
                'SpecialTimes': [dict(r, Character=names.character(r.get('CharacterId'))) for r in
                                 sorted(specials.get(sid, []), key=lambda r: r.get('SpecialTimeSequenceNo', 0))],
            })

        sales_rows = []
        for row in sorted(sales.get(eid, []), key=lambda r: (r.get('ShiftId', 0), r.get('KeySales', 0))):
            sid = row.get('ShiftId')
            if sid and sid not in shift_numbers:
                issues.append({'Status': 'sales_reward_unknown_shift', 'EventId': eid, 'ShiftId': sid})
            sales_rows.append(dict(row, Rewards=rewards.direct(row.get('DirectRewardGroupId'))))

        archive.append({
            'EventId': eid, 'Title': event.get('EventTitle', ''), 'Kind': KINDS[event['EventFormat']],
            'RawEvent': event, 'RawEventB': raw_b, 'PickUpCard': names.card(raw_b.get('PickUpCharacterCardId'))
            if raw_b.get('PickUpCharacterCardId') else '', 'Cards': names.cards(raw_b.get('CharacterCardIds')),
            'Availability': date_window(event.get('OpenStartTime') or event.get('StartTime'), event.get('EndTime'),
                                        as_of=now, active=event.get('IsActive', True)),
            'DropBonus': bonus_text(bonuses.get(raw_b.get('DropEventBonusId'))),
            'SalesBonus': bonus_text(bonuses.get(raw_b.get('SalesEventBonusId'))),
            'SharedMusic': sorted({s['Music'] for sh in shift_entries for s in sh['Stages'] if s['Shared']}),
            'OtherStageDrops': {'StageCount': len(other_overlays), 'PickUp': sorted(
                {ingredient_name(i) for o in other_overlays for i in o.get('PickUpIngredientIds') or []})},
            'Shifts': shift_entries, 'SalesRewards': sales_rows,
        })

    used_by = defaultdict(set)
    for event in archive:
        for shift in event['Shifts']:
            for item in shift['Menu']:
                for iid in item['Recipe'].get('IngredientIds') or []:
                    used_by[iid].add(item['Recipe'].get('RecipeName', ''))
    return {'AsOf': now.isoformat(), 'Events': archive, 'Ingredients': [
        {'Raw': row, 'Kind': ingredient_kind(row['IngredientId']), 'UsedBy': sorted(used_by.get(row['IngredientId'], []))}
        for row in sorted(ingredients.values(), key=lambda r: r['IngredientId'])],
        'Issues': issues, 'RewardIssues': rewards.issues}


def export(data):
    names_note = '游戏数据里没有名称的奖励写作「类型(ID)」；清单见 待核对汇总.xlsx。'
    overview, shifts, menu, stages, specials, sales = [], [], [], [], [], []
    for event in data['Events']:
        eid, title, raw = event['EventId'], event['Title'], event['RawEvent']
        other = event['OtherStageDrops']
        overview.append([
            eid, title, event['Kind'], jst(raw.get('OpenStartTime') or raw.get('StartTime')), jst(raw.get('EndTime')),
            STATUS_LABELS[event['Availability']['Status']], len(event['Shifts']), ' / '.join(event['SharedMusic']),
            event['PickUpCard'], event['Cards'], event['DropBonus'], event['SalesBonus'],
            f"{other['StageCount']} 关：{'、'.join(other['PickUp'])}" if other['StageCount'] else '',
        ])
        shift_label = {}
        for shift in event['Shifts']:
            raw_shift = shift['Raw']
            label = f"第{shift['Number']}轮"
            shift_label[raw_shift['ShiftId']] = f"{label} {shift['Character']}"
            prefix = [eid, title, label, shift['Character']]
            rotation = sorted({f"{s['Music']}" for s in shift['Stages'] if not s['Shared']})
            shifts.append(prefix + [jst(raw_shift.get('StartTime')), jst(raw_shift.get('EndTime')),
                                    STATUS_LABELS[shift['Availability']['Status']], ' / '.join(rotation),
                                    ' → '.join(m['Recipe'].get('RecipeName', '') for m in shift['Menu']),
                                    len(shift['SpecialTimes'])])
            for item in shift['Menu']:
                recipe = item['Recipe']
                menu.append(prefix + [
                    item['SequenceNo'], recipe.get('RecipeName', ''), recipe.get('RecipeDifficulty'), item['Unlock'],
                    item['Recommend'], recipe.get('Price'), recipe.get('RequiredSecond'), '、'.join(item['Ingredients']),
                    reward_text(item['Rewards']), plain_text(recipe.get('RecipeMemo')),
                ])
            for stage in shift['Stages']:
                stages.append(prefix + [stage['StageNo'], stage['Face'], stage['Music'],
                                        '全轮班共通' if stage['Shared'] else '本轮班', '、'.join(stage['PickUp']),
                                        stage['Drops']])
            for row in shift['SpecialTimes']:
                specials.append(prefix + [row.get('SpecialTimeSequenceNo'), row['Character'],
                                          jst(row.get('StartTime')), jst(row.get('EndTime'))])
        by_scope = defaultdict(list)
        for row in event['SalesRewards']:
            by_scope[row.get('ShiftId') or 0].append(row)
        for sid, rows in sorted(by_scope.items(), key=lambda kv: (kv[0] != 0, kv[0])):
            scope = '全期累计' if not sid else shift_label.get(sid, f'轮班({sid})')
            for first, last, count, text in tier_ranges(
                    rows, 'KeySales', lambda r: (reward_text(r['Rewards']), bool(r.get('IsPickUp')))):
                sales.append([eid, title, scope, tier_label(first, last, count, ' EN'), text[0], '是' if text[1] else ''])
    ingredient_rows = [[row['Raw']['IngredientId'], row['Kind'], row['Raw'].get('IngredientName', ''),
                        plain_text(row['Raw'].get('IngredientDescription')), '、'.join(row['UsedBy'])]
                       for row in data['Ingredients']]
    shift_cols = ['活动ID', '活动名', '轮班', '轮班角色']
    return write_workbook(xlsx_path('营业活动档案.xlsx'), [
        {'title': '活动总览', 'headers': ['活动ID', '活动名', '类型', '开放(JST)', '结束(JST)', '日期状态', '轮班数',
                                       '全轮班共通曲目', 'PICKUP 卡', '活动卡牌', '关卡掉落加成', '营业额加成',
                                       '其他关卡掉落材料'],
         'rows': overview, 'col_widths': {'B': 30, 'I': 30, 'J': 50, 'K': 40, 'L': 40, 'M': 40}, 'wrap_cols': [10, 13]},
        {'title': '轮班', 'headers': shift_cols + ['开始(JST)', '结束(JST)', '日期状态', '本轮班曲目', '菜单', '特别营业次数'],
         'rows': shifts, 'col_widths': {'B': 30, 'H': 30, 'I': 50}},
        {'title': '菜单与配方', 'headers': shift_cols + ['菜单序号', '配方', '配方等级', '解锁条件', '推荐角色', '售价(EN)',
                                                    '耗时(秒)', '材料', '配方奖励', '配方说明'],
         'rows': menu, 'col_widths': {'B': 30, 'F': 24, 'L': 30, 'M': 24, 'N': 50}, 'wrap_cols': [14]},
        {'title': '材料', 'headers': ['材料ID', '分类', '材料', '说明', '用于配方'], 'rows': ingredient_rows,
         'col_widths': {'C': 20, 'D': 40, 'E': 50}, 'wrap_cols': [4, 5]},
        {'title': '关卡掉落', 'headers': shift_cols + ['关卡号', '面', '曲目', '曲目范围', '重点材料', '掉落材料（概率）'],
         'rows': stages, 'col_widths': {'B': 30, 'G': 24, 'I': 24, 'J': 50}},
        {'title': '特别营业', 'headers': shift_cols + ['序号', '登场角色', '开始(JST)', '结束(JST)'], 'rows': specials,
         'col_widths': {'B': 30}},
        {'title': '营业额奖励', 'headers': ['活动ID', '活动名', '范围', '营业额档位', '奖励', '重点奖励'], 'rows': sales,
         'col_widths': {'B': 30, 'C': 20, 'D': 36, 'E': 50}},
        {'title': '说明', 'headers': ['项目', '说明'], 'col_widths': {'A': 16, 'B': 90}, 'wrap_cols': [2], 'rows': [
            ['范围', '客户端 EventFormat 3（B，常规营业活动）与 4（BSpecial，特别版，如 Welcome! KAWAII Cafe♡）。'],
            ['核对时刻', jst(data['AsOf']) + '（JST）；所有时间均为日本时间。'],
            ['轮班', '按开始时间编号；同一轮班内的菜单共 3 道，后一道需先把上一道配方做满指定次数才解锁'
                   '（游戏内「1つ上のレシピを{0}回作って解放」）。'],
            ['配方等级', 'RecipeDifficulty 原值 1–3。配方奖励来自配方自带的奖励组，发放时机未在游戏内文字中确认。'],
            ['关卡掉落', '活动地图的关卡没有直接标明轮班，按「关卡开放/结束时间与轮班起止完全相同」归入轮班；'
                     '每轮班都出现的曲目标为「全轮班共通」。各评级掉落组相同时只写一次。'],
            ['其他关卡掉落材料', '活动期间角色地图等普通关卡也会掉落材料，这里只给关卡数和重点材料，逐关明细见审计 JSON。'],
            ['营业额奖励', '「全期累计」按整期营业额计，其余按该轮班营业额计；奖励相同的连续档位合并为一行，区间内每档各得一次。'],
            ['加成', '按 mst_event_bonus 字段名翻译（活动卡牌 / 稀有度 / 突破阶段 / 角色 / 属性 / 轮班角色），游戏内未找到逐项文字。'],
            ['材料分类', '游戏数据没有分类字段，按材料 ID 段归类：1–50 基酒、51–99 利口酒、101–199 软饮、201 起辅料、10000 起联动限定。'],
            ['名称缺失', names_note],
        ]},
    ])


def run(session=None, *, as_of=None):
    data = extract(session, as_of=as_of)
    save_json(data, audit_path('bar_events.json'))
    if data['Issues'] or data['RewardIssues']:
        record_warning(f"营业活动存在 {len(data['Issues'])} 条关系异常、{len(data['RewardIssues'])} 条奖励缺项，详见 bar_events.json")
    return export(data)
