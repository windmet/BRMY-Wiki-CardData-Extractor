"""OJT masterdata archive; chart coordinate files remain a separate input."""
import json
from datetime import datetime, timedelta, timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment

from ..core.availability import assessment_time, date_window, STATUS_LABELS
from ..core.data import RARITY_MAP
from ..core.exporter import audit_path, xlsx_path, save_workbook_safely
from ..core.scanner import save_json
from ..core.rewards import RewardResolver
from ..core.output import record_warning
from .ojt_coordinates import load_coordinates

JST = timezone(timedelta(hours=9))
# Coly.S2BShared.Enums.OjtPhase / OjtTerminalCharacterTextType in the 2.1.0 client.
PHASES = {1: '训练 Lv1', 2: '训练 Lv2', 3: '训练 Lv3', 0: '进阶'}
TEXT_TYPES = {1: '训练中台词', 2: '进阶中台词', 3: '获胜后台词', 4: '失败后台词'}
FIELD_NAME_ONLY = '按字段名翻译，游戏内未找到对应文字'
CONSTANT_LABELS = {
    'SpecialMatchPercent': ('特别对战出现率（%）', FIELD_NAME_ONLY),
    'SpecialMatchPercentVsUpperTier': ('对上位トレーナー的特别对战出现率（%）', FIELD_NAME_ONLY),
    'SpecialMatchPercentForLoser': ('失败方的特别对战出现率（%）', FIELD_NAME_ONLY),
    'SpecialMatchUpperTier': ('上位トレーナー界线', FIELD_NAME_ONLY),
    'SpecialMatchIncreaseRateWin': ('特别对战获胜时奖牌增加率', FIELD_NAME_ONLY),
    'SpecialMatchIncreaseRateLose': ('特别对战失败时奖牌增加率', FIELD_NAME_ONLY),
    'PrizeMedalDecreaseRateLose': ('失败时奖牌减少率', FIELD_NAME_ONLY),
    'PrizeMedalRewardCountByTrainer': ('担任トレーナー获得的奖牌', '游戏内提示「あなたが{0}人のトレーナーになりました」'),
    'PrizeMedalRewardCountByTrainerForWinner': ('担任トレーナー获得的奖牌（获胜方）', FIELD_NAME_ONLY),
    'PrizeMedalLimitByTrainer': ('担任トレーナー获得奖牌上限', FIELD_NAME_ONLY),
    'TrainerReLotteryCountLimit': ('每日更换トレーナー次数', '游戏内提示「トレーナーを変更しますか？※1日<val>回まで変更できます」'),
    'RentalCountLimit': ('租借编成次数上限', '游戏内显示「レンタル {0}/{1}」'),
    'MinUserCount': ('最少玩家数', FIELD_NAME_ONLY),
    'TrainerStrengthBorderScoreRates': ('トレーナー强度分界', '游戏内提示「あなたのスコアと比較した時のつよさ」'),
    'TopIconDisplayLimitRank': ('顶部图标显示名次上限', FIELD_NAME_ONLY),
}


def extract(session, *, as_of=None, source=None):
    tables = session.tables
    now = assessment_time(as_of)
    rewards = RewardResolver(tables)
    issues = []

    def grouped(name, key):
        return tables.group_by(name, key, required=False)

    events = grouped('mst_event', 'EventId')
    charts = grouped('mst_event_ojt_chart', 'EventId')
    shifts = grouped('mst_event_ojt_shift', 'EventId')
    boxes = grouped('mst_event_ojt_prize_box', 'OjtShiftId')
    stages = grouped('mst_event_ojt_puzzle_stage', 'OjtShiftId')
    training = grouped('mst_event_ojt_training_reward', 'OjtShiftId')
    texts = grouped('mst_event_ojt_terminal_character_text', 'OjtShiftId')
    fixed = grouped('mst_event_ojt_prize_box_reward', 'PrizeBoxRewardId')
    random = grouped('mst_event_ojt_prize_box_reward_random', 'PrizeBoxRewardRandomId')
    maps = grouped('mst_puzzle_map', 'PuzzleMapId')

    def expand(groups, key, table, location):
        if key in (None, 0):
            return []
        rows = groups.get(key, [])
        if not rows:
            issues.append(dict(location, Status='missing_reward_group', Table=table, Id=key))
        return [dict(rewards.resolve(row), SourceTable=table) for row in rows]

    archive = []
    for raw in tables.require('mst_event_c', active_only=True):
        eid = raw['EventId']
        matches = events.get(eid, [])
        if len(matches) != 1 or matches[0].get('EventFormat') != 5:
            issues.append({'EventId': eid, 'Status': 'invalid_event_owner', 'Raw': raw})
            continue
        event = matches[0]
        entry = {'EventId': eid, 'Title': event.get('EventTitle', ''), 'RawEvent': event,
                 'RawOjt': raw, 'Charts': charts.get(eid, []), 'Shifts': []}
        if len(entry['Charts']) != 1:
            issues.append({'EventId': eid, 'Status': 'missing_or_ambiguous_chart'})
        for shift in sorted(shifts.get(eid, []), key=lambda r: r['OjtShiftId']):
            sid = shift['OjtShiftId']
            item = {'RawShift': shift, 'Stages': stages.get(sid, []),
                    'TerminalTexts': texts.get(sid, []), 'TrainingRewards': [], 'PrizeBoxes': [], 'StageMaps': [],
                    'Availability': date_window(shift.get('StartTime'), shift.get('EndTime'), as_of=now)}
            for stage in item['Stages']:
                matches = maps.get(stage.get('PuzzleMapId'), [])
                item['StageMaps'].append({'RawStage': stage, 'Maps': matches})
                if len(matches) != 1:
                    issues.append({'Status': 'missing_or_ambiguous_map', 'OjtShiftId': sid,
                                   'OjtPhase': stage.get('OjtPhase'), 'PuzzleMapId': stage.get('PuzzleMapId')})
            for row in training.get(sid, []):
                phase_stages = [stage for stage in item['Stages'] if stage.get('OjtPhase') == row.get('OjtPhase')]
                if not phase_stages:
                    issues.append({'Status': 'missing_training_phase', 'OjtShiftId': sid, 'OjtPhase': row.get('OjtPhase')})
                item['TrainingRewards'].append({'Raw': row, 'Stages': phase_stages,
                                               'Rewards': rewards.direct(row.get('DirectRewardGroupId'))})
            for box in sorted(boxes.get(sid, []), key=lambda r: r['PrizeBoxNo']):
                loc = {'EventId': eid, 'OjtShiftId': sid, 'PrizeBoxNo': box['PrizeBoxNo']}
                item['PrizeBoxes'].append({'Raw': box,
                    'FixedRewards': expand(fixed, box.get('PrizeBoxRewardId'), 'mst_event_ojt_prize_box_reward', loc),
                    'RandomRewards': expand(random, box.get('PrizeBoxRewardRandomId'), 'mst_event_ojt_prize_box_reward_random', loc)})
            entry['Shifts'].append(item)
        archive.append(entry)
    archive.sort(key=lambda e: (str(e['RawEvent'].get('OpenStartTime') or e['RawEvent'].get('StartTime') or ''), e['EventId']))
    used_shifts = {s['RawShift']['OjtShiftId'] for e in archive for s in e['Shifts']}
    for name, groups in [('PrizeBoxes', boxes), ('Stages', stages), ('TrainingRewards', training), ('TerminalTexts', texts)]:
        for sid, rows in groups.items():
            if sid not in used_shifts:
                issues.append({'Status': 'unlinked_shift', 'Section': name, 'OjtShiftId': sid, 'Rows': rows})
    constants = [{'Raw': row, 'ChartStampConversionRewards': rewards.direct(row.get('ChartStampConvertedDirectRewardGroupId'))}
                 for row in tables.rows('mst_event_ojt_constant', active_only=True)]
    coordinates = load_coordinates(archive, tables, source)
    return {'Events': archive, 'AsOf': now.isoformat(), 'Timezone': 'UTC',
            'BreakBonus': tables.rows('mst_event_ojt_break_bonus', active_only=True), 'Constants': constants,
            'ChartCoordinates': coordinates['Status'], 'CoordinateLayouts': coordinates,
            'Labels': _labels(tables, archive),
            'Issues': issues, 'RewardIssues': rewards.issues,
            'RawTables': {name: tables.rows(name) for name in tables.names if name.startswith('mst_event_ojt_')}}


def _labels(tables, archive):
    """Readable names for the IDs the workbook shows; IDs without a record keep a typed placeholder."""
    def table(name, key):
        return tables.by_id(name, key, active_only=False, required=False)
    characters, cards = table('mst_character', 'CharacterId'), table('mst_character_card', 'CharacterCardId')
    puzzle_maps, music_maps = table('mst_puzzle_map', 'PuzzleMapId'), table('mst_music_puzzle_map', 'MusicPuzzleMapId')
    music = table('mst_music', 'MusicId')

    def character(cid):
        return characters.get(cid, {}).get('CharacterNameJpn') or f'角色({cid})'

    def card(cid):
        row = cards.get(cid)
        if not row:
            return f'卡牌({cid})'
        return f"{row.get('CharacterCardName', '')}（{character(row.get('CharacterId'))} {RARITY_MAP.get(row.get('CardRarityCode'), '')}）"

    def map_music(mid):
        link = music_maps.get(puzzle_maps.get(mid, {}).get('MusicPuzzleMapId'), {})
        return music.get(link.get('MusicId'), {}).get('DisplayName') or f'地图({mid})'

    card_ids, character_ids, map_ids = set(), set(), set()
    for event in archive:
        card_ids.update(event['RawOjt'].get('CharacterCardIds') or [])
        card_ids.add(event['RawOjt'].get('PickUpCharacterCardId'))
        for shift in event['Shifts']:
            character_ids.add(shift['RawShift'].get('CharacterId'))
            for stage in shift['Stages']:
                card_ids.update(stage.get('RentalCharacterCardIds') or [])
                map_ids.add(stage.get('PuzzleMapId'))
    return {'Characters': {i: character(i) for i in character_ids if i is not None},
            'Cards': {i: card(i) for i in card_ids if i is not None},
            'MapMusic': {i: map_music(i) for i in map_ids if i is not None}}


def _jst(value):
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(JST).strftime('%Y-%m-%d %H:%M')
    except (TypeError, ValueError):
        return value or ''


def _rewards(rows):
    return ' / '.join(f"{r['RewardName']} x{r['RewardCount']}" for r in rows)


def _score(stage):
    low, high = stage.get('BreakScoreMin'), stage.get('BreakScoreMax')
    if low is None or high is None:
        return ''
    return f'{low:,}' if low == high else f'{low:,}～{high:,}'


def _coordinate_note(chart):
    if chart is None:
        return '未读取 Chart 文件'
    if chart['Status'] == 'loaded':
        return f"{len(chart['Coordinates'])} 人"
    return {'missing_file': '缺 Chart 文件', 'ambiguous_file': 'Chart 文件重名',
            'invalid_file': 'Chart 文件无法解析'}.get(chart['Status'], chart['Status'])


def export(data):
    labels = data.get('Labels', {})
    names = labels.get('Characters', {})
    cards = labels.get('Cards', {})
    map_music = labels.get('MapMusic', {})
    wb = Workbook()
    wb.remove(wb.active)
    headers = {
        '活动总览': ['活动ID', '活动名', '开放(JST)', '结束(JST)', '关卡曲目', 'PICKUP 卡', '活动卡牌',
                 '题面', '左', '右', '下', '上', '站位坐标'],
        '轮次': ['活动ID', '活动名', '轮次', '带教角色', '开始(JST)', '结束(JST)', '日期状态',
               *TEXT_TYPES.values(), '训练开始剧情', '训练完成剧情'],
        '关卡': ['活动ID', '活动名', '轮次', '带教角色', '阶段', '关卡序号', 'BREAK 分数', '训练通关奖励', '可租借卡牌'],
        '奖箱': ['活动ID', '活动名', '轮次', '带教角色', 'BOX', '每抽消耗奖牌', '抽到箱内奖励', '抽到随机奖励',
               '箱内奖励总数', '贵重奖励'],
        '奖箱内容': ['活动ID', '活动名', '轮次', '带教角色', 'BOX', '奖励', '每份数量', '库存', '贵重'],
        '随机奖励': ['随机池', '用于', '奖励', '每份数量', '权重', '池内概率'],
        '站位坐标': ['活动ID', '题面', '角色ID', '角色名', 'X', 'Y', '叠放顺序'],
        '规则': ['规则', '数值', '说明'],
        '说明': ['项目', '内容'],
    }
    sheets = {name: wb.create_sheet(name) for name in headers}
    for name, cols in headers.items():
        sheets[name].append(cols)
    layouts = {(c['EventId'], c['ChartFileName']): c for c in data['CoordinateLayouts']['Charts']}
    random_pools, shift_count = {}, 0
    for event in data['Events']:
        eid, title, raw_ojt = event['EventId'], event['Title'], event['RawOjt']
        chart = event['Charts'][0] if event['Charts'] else {}
        music = sorted({map_music.get(s.get('PuzzleMapId'), '') for shift in event['Shifts'] for s in shift['Stages']} - {''})
        sheets['活动总览'].append([
            eid, title, _jst(event['RawEvent'].get('OpenStartTime')), _jst(event['RawEvent'].get('EndTime')),
            ' / '.join(music), cards.get(raw_ojt.get('PickUpCharacterCardId'), ''),
            '、'.join(cards.get(c, str(c)) for c in raw_ojt.get('CharacterCardIds') or []),
            *[chart.get(k, '') for k in ('ChartTitle', 'LeftString', 'RightString', 'BottomString', 'TopString')],
            _coordinate_note(layouts.get((eid, chart.get('ChartFileName'))))])
        for number, s in enumerate(event['Shifts'], start=1):
            shift_count += 1
            raw = s['RawShift']
            prefix = [eid, title, number, names.get(raw.get('CharacterId'), raw.get('CharacterId'))]
            lines = {row.get('OjtTerminalCharacterTextType'): str(row.get('Text', '')).replace('\\n', '\n')
                     for row in s['TerminalTexts']}
            sheets['轮次'].append(prefix + [_jst(raw.get('StartTime')), _jst(raw.get('EndTime')),
                                 STATUS_LABELS[s['Availability']['Status']], *[lines.get(t, '') for t in TEXT_TYPES],
                                 raw.get('TrainingPuzzleStartStoryFileName'), raw.get('TrainingPuzzleClearStoryFileName')])
            phase_rewards = {row['Raw'].get('OjtPhase'): _rewards(row['Rewards']) for row in s['TrainingRewards']}
            for row in sorted(s['Stages'], key=lambda r: r.get('PuzzleStageNo', 0)):
                phase = row.get('OjtPhase')
                sheets['关卡'].append(prefix + [PHASES.get(phase, f'阶段{phase}'), row.get('PuzzleStageNo'), _score(row),
                                    phase_rewards.get(phase, '') if phase else '',
                                    '、'.join(cards.get(c, str(c)) for c in row.get('RentalCharacterCardIds') or [])])
            for box in s['PrizeBoxes']:
                raw_box = box['Raw']
                stocks = [r['RawReward'].get('PrizeStock') or 0 for r in box['FixedRewards']]
                sheets['奖箱'].append(prefix + [raw_box['PrizeBoxNo'], raw_box.get('CostPrizeMedalCount'),
                                    f"{raw_box.get('RewardLotteryRate', 0)}%", f"{raw_box.get('RewardRandomLotteryRate', 0)}%",
                                    sum(stocks), '、'.join(r['RewardName'] for r in box['FixedRewards'] if r['RawReward'].get('IsPickUp'))])
                for reward in box['FixedRewards']:
                    rr = reward['RawReward']
                    sheets['奖箱内容'].append(prefix + [raw_box['PrizeBoxNo'], reward['RewardName'], reward['RewardCount'],
                                          rr.get('PrizeStock'), '是' if rr.get('IsPickUp') else ''])
                pool = raw_box.get('PrizeBoxRewardRandomId')
                if box['RandomRewards']:
                    entry = random_pools.setdefault(pool, {'Rewards': box['RandomRewards'], 'Shifts': {}})
                    entry['Shifts'].setdefault((eid, number), f'{title} 第{number}轮')
    for pool, entry in sorted(random_pools.items()):
        used = ('全部轮次' if len(entry['Shifts']) == shift_count else '；'.join(entry['Shifts'].values()))
        total = sum(r['RawReward'].get('LotteryRate') or 0 for r in entry['Rewards'])
        for reward in entry['Rewards']:
            weight = reward['RawReward'].get('LotteryRate') or 0
            sheets['随机奖励'].append([pool, used, reward['RewardName'], reward['RewardCount'], weight,
                                   f'{weight / total:.3%}' if total else ''])
    chart_titles = {(e['EventId'], c.get('ChartFileName')): c.get('ChartTitle', '')
                    for e in data['Events'] for c in e['Charts']}
    for chart in data['CoordinateLayouts']['Charts']:
        for row in chart['Coordinates']:
            sheets['站位坐标'].append([chart['EventId'], chart_titles.get((chart['EventId'], chart['ChartFileName']), ''),
                                   row['CharacterId'], row['CharacterName'], round(row['X'], 2), round(row['Y'], 2),
                                   row['SiblingIndex']])
    rules = sheets['规则']
    for index, row in enumerate(sorted(data.get('BreakBonus', []), key=lambda r: r.get('OjtPuzzleBreakCount', 0))):
        rules.append([f"连续 BREAK {row.get('OjtPuzzleBreakCount')} 次", f"+{row.get('PrizeMedalIncreaseRate')}%",
                      '' if index else '获得的プライズメダル按此增加；游戏内显示为「連続BREAK でプライズメダル ×倍」'])
    for entry in data.get('Constants', []):
        for key, value in entry['Raw'].items():
            if key in ('ConstantKey', 'IsActive', 'ChartStampConvertedDirectRewardGroupId'):
                continue
            label, note = CONSTANT_LABELS.get(key, (key, FIELD_NAME_ONLY))
            if isinstance(value, (list, dict)):
                value = json.dumps(value, ensure_ascii=False) if value else '（空）'
            rules.append([label, value, note])
        rules.append(['チャートスタンプ转换', _rewards(entry['ChartStampConversionRewards']),
                      '游戏内提示「イベントで獲得したチャートスタンプを変換しました」'])
    for row in [
        ('核对时刻', _jst(data['AsOf']) + '（JST）'),
        ('时间', '所有时间均为日本时间（JST）；轮次在开始时刻切换。'),
        ('日期状态', '按核对时刻与轮次起止时间判断：未开始 / 日期区间内 / 已结束。'),
        ('阶段', '训练 Lv1–Lv3 即トレーニングフェーズ，每关 BREAK 分数固定，通关得「训练通关奖励」；'
               '进阶即アドバンスフェーズ的課題ステージ，BREAK 分数为一个范围。'),
        ('奖箱', '每抽消耗プライズメダル。「抽到箱内奖励」与「抽到随机奖励」合计 100%，决定这一抽落入哪个奖池；'
               '箱内奖励按库存抽完为止，标「贵重」的即游戏内「貴重なアイテム」。'),
        ('随机奖励', '所有 BOX 共用的随机奖池。某随机奖励每抽的实际概率 = 该 BOX 的「抽到随机奖励」× 池内概率。'),
        ('站位坐标', {'not_loaded': '本次没有读取 Chart 文件，「站位坐标」页为空。',
                  'partial': '部分活动缺 Chart 文件，各活动的情况见「活动总览」最后一列。',
                  'loaded': '全部活动的 Chart 文件已读取。'}[data['ChartCoordinates']]
         + 'X/Y 取自 Chart 文件（Unity 画布坐标，Y 向上为正）；叠放顺序大的显示在上层。'),
        ('名称缺失', '游戏数据中没有名称的奖励写作「类型(ID)」，例如 Pin(10115)；清单见 待核对汇总.xlsx。'),
    ]:
        sheets['说明'].append(list(row))
    wrap = Alignment(wrap_text=True, vertical='top')
    for sheet in wb:
        sheet.freeze_panes = 'A2'
        for column in sheet.columns:
            longest = max(max((len(line) for line in str(c.value or '').split('\n')), default=0) for c in column[:80])
            sheet.column_dimensions[column[0].column_letter].width = min(60, max(10, longest + 2))
    for sheet, columns in [(sheets['轮次'], 'HIJK'), (sheets['规则'], 'C'), (sheets['说明'], 'B')]:
        for letter in columns:
            sheet.column_dimensions[letter].width = 60 if sheet.title == '说明' else 34
            for cell in sheet[letter][1:]:
                cell.alignment = wrap
    return save_workbook_safely(wb, xlsx_path('ojt_archive.xlsx'))


def run(session=None, *, as_of=None, source=None):
    data = extract(session, as_of=as_of, source=source)
    save_json(data, audit_path('ojt_archive.json'))
    problems = [i for i in data['CoordinateLayouts']['Issues'] if i['Status'] != 'unmatched_file']
    if problems:
        record_warning(f"OJT 坐标存在 {len(problems)} 条缺项或异常，详见 ojt_archive.json")
    if data['Issues'] or data['RewardIssues']:
        record_warning(f"OJT 存在 {len(data['Issues'])} 条关系异常、{len(data['RewardIssues'])} 条奖励缺项，详见 ojt_archive.json")
    return export(data)
