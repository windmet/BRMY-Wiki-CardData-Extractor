"""Spin 相片备忘录检索表：按“备忘录卡”（同一主角的 R/SR/SSR 三联）去重。

mst_spin_snapshot 中每个 SpinSet 按 SnapshotId 顺序以 N→R→SR（Wiki 称 R/SR/SSR）三张
为一组；同一组内容会因抽取时间、姿势、相框不同而重复多次。本表把内容相同的三联合并为
一行，分类维度都放在列里，便于筛选；不改动 snap 任务的旧表。
"""
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from ..core.data import CHAR_MAP, translate_scene
from ..core.exporter import audit_path, xlsx_path, write_workbook
from ..core.scanner import save_json

JST = timezone(timedelta(hours=9))
# SpinBaseCode (client: Casino / Factory / AmusementPark / AmericanDiner); Wiki names.
SCENES = {1: '太空赌场', 2: '电玩城', 3: '游乐园', 4: '美式餐厅'}
RARITIES = {1: 'R', 2: 'SR', 3: 'SSR'}
# Film rarity is the colour the reel lands on before the shot; it is what triggers the snap.
FILM_COLOURS = {1: '灰色', 2: '金色', 3: '彩色'}
# Masterdata has no addition date for regular sets; dates come from the in-game update banners
# (spin_diner_info "2025.3.31 アップデート"; 2nd_anniv_update_cp_info_1 from 2026-05-01).
# Sets outside these ranges and not limited are reported as unknown_spin_set_batch.
BATCHES = [
    (100001, 100999, '初始', ''), (200001, 200024, '初始', ''), (300001, 300006, '初始', ''),
    (400001, 400070, '美式餐厅追加', '2025-03-31'),
    (200025, 200029, '二周年新胶卷', '2026-05-01'), (300007, 300010, '二周年新胶卷', '2026-05-01'),
]
PARTY = {1: '单人', 2: '双人', 3: '三人', 4: '四人'}
TOPIC = re.compile(r'^〜(.+?)〜\s*(.*)$', re.S)


def _name(character_id):
    return CHAR_MAP.get(character_id, f'角色{character_id}')


def _jst_date(value):
    if not value or str(value).startswith('2001'):
        return ''
    return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(JST).date().isoformat()


def _trios(snapshots):
    """Split snapshots (SnapshotId order) into N→R→SR groups.

    A few groups straddle two SpinSets (e.g. 2485–2487: N in 400038, R/SR in 400039) with
    identical content, so only the cast has to match inside a group.
    """
    trios, issues, current = [], [], []
    for row in sorted(snapshots, key=lambda r: r['SnapshotId']):
        if row.get('SnapshotRarityCode') == 1 and current:
            trios.append(current)
            current = []
        current.append(row)
    if current:
        trios.append(current)
    valid = []
    for trio in trios:
        rarities = [row.get('SnapshotRarityCode') for row in trio]
        casts = {tuple(row.get('SnapshotCharacterIds') or []) for row in trio}
        if rarities != [1, 2, 3] or len(casts) != 1:
            issues.append({'Status': 'irregular_snapshot_group', 'SnapshotIds': [r['SnapshotId'] for r in trio]})
            continue
        valid.append(trio)
    return valid, issues


def _batch(set_id):
    return next(((label, date) for first, last, label, date in BATCHES if first <= set_id <= last), None)


def _trigger(film):
    names = [_name(c) for c in film.get('CharacterIds') or []]
    return f"{FILM_COLOURS.get(film.get('FilmRarityCode'), '?')}·{'＋'.join(names)}"


def _positions(tables):
    """SpinSetId → Wiki position labels taken from its character motion files."""
    motions = tables.by_id('mst_spin_motion', 'SpinMotionId', required=False)
    files = {row['SpinCharacterMotionId']: row.get('SpinCharacterMotionFileName', '')
             for row in tables.rows('mst_spin_character_motion', active_only=True)}
    positions = {}
    for row in tables.rows('mst_spin_set', active_only=True):
        labels = []
        for motion_id in row.get('SpinMotionIds') or []:
            for character_motion in motions.get(motion_id, {}).get('SpinCharacterMotionIds') or []:
                label = translate_scene(files.get(character_motion, '').split('/')[-1])
                label = label.split('-', 1)[1] if '-' in label else ''
                if label and label not in labels:
                    labels.append(label)
        positions[row['SpinSetId']] = labels
    return positions


def _limited_sets(tables):
    """Sets that only a limited-costume film variant adds, with the costume that unlocks them."""
    films = tables.by_id('mst_spin_film', 'FilmId', required=False)
    regulations = tables.by_id('mst_spin_costume_mini_regulation', 'SpinCostumeMiniRegulationId', required=False)
    costumes = tables.by_id('mst_costume_mini', 'CostumeMiniId', required=False)
    limited = {}
    for row in tables.rows('mst_spin_film_limited_costume_mini', active_only=True):
        base = set(films.get(row['FilmId'], {}).get('SpinSetIds') or [])
        names, dates = [], []
        for costume_id in regulations.get(row.get('SpinCostumeMiniRegulationId'), {}).get('CostumeMiniIds') or []:
            costume = costumes.get(costume_id, {})
            names.append(costume.get('CostumeMiniName', f'服装{costume_id}'))
            dates.append(_jst_date(costume.get('ReleaseDateTime')))
        for set_id in set(row.get('SpinSetIds') or []) - base:
            entry = limited.setdefault(set_id, {'Costumes': [], 'Date': ''})
            entry['Costumes'] += [n for n in names if n not in entry['Costumes']]
            entry['Date'] = min([d for d in [entry['Date'], *dates] if d], default='')
    return limited


def extract(session):
    tables = session.tables
    notes = tables.by_id('mst_spin_sticky_note', 'StickyNoteId', required=False)
    sets = tables.by_id('mst_spin_set', 'SpinSetId')
    positions = _positions(tables)
    limited = _limited_sets(tables)
    films = tables.by_id('mst_spin_film', 'FilmId', required=False)
    films_by_set = defaultdict(list)
    for film in films.values():
        for set_id in film.get('SpinSetIds') or []:
            films_by_set[set_id].append(film)
    for row in tables.rows('mst_spin_film_limited_costume_mini', active_only=True):
        for set_id in row.get('SpinSetIds') or []:
            film = films.get(row['FilmId'])
            if film and film not in films_by_set[set_id]:
                films_by_set[set_id].append(film)
    trios, issues = _trios(tables.require('mst_spin_snapshot', active_only=True))

    def memo(row):
        stickies = []
        for slot in range(1, 5):
            note_id = row.get(f'StickyNoteId{slot}')
            if not note_id:
                continue
            note = notes.get(note_id)
            if not note:
                issues.append({'Status': 'missing_sticky_note', 'SnapshotId': row['SnapshotId'], 'StickyNoteId': note_id})
                continue
            stickies.append({'StickyNoteId': note_id, 'CharacterId': note.get('CharacterId'),
                             'Character': _name(note.get('CharacterId')), 'Text': note.get('Comment', '')})
        return {'Rarity': RARITIES[row['SnapshotRarityCode']], 'Text': row.get('Comment', ''), 'Comments': stickies}

    cards = {}
    for trio in trios:
        memos = [memo(row) for row in trio]
        cast = list(trio[0].get('SnapshotCharacterIds') or [])
        # The same sentence in another corner has its own StickyNoteId; compare speaker and text.
        key = (tuple(cast), *((m['Text'], tuple((c['CharacterId'], c['Text']) for c in m['Comments'])) for m in memos))
        card = cards.get(key)
        if card is None:
            topic = next((TOPIC.match(m['Text']) for m in memos if TOPIC.match(m['Text'])), None)
            card = cards[key] = {
                'Id': trio[0]['SnapshotId'], 'CharacterIds': cast, 'Cast': [_name(c) for c in cast],
                'Topic': topic.group(1) if topic else '', 'TopicAnswer': topic.group(2) if topic else '',
                'Memos': memos, 'SpinSetIds': [], 'SnapshotIds': [], 'Scenes': [], 'Positions': [],
                'LimitedCostumes': [], 'Date': '', 'Batch': '', 'Films': []}
        card['SnapshotIds'] += [row['SnapshotId'] for row in trio]
        for set_id in dict.fromkeys(row['SpinSetId'] for row in trio):
            if set_id in card['SpinSetIds']:
                continue
            card['SpinSetIds'].append(set_id)
            scene = SCENES.get(sets.get(set_id, {}).get('SpinBaseCode'), '')
            if scene and scene not in card['Scenes']:
                card['Scenes'].append(scene)
            card['Positions'] = sorted(set(card['Positions']) | set(positions.get(set_id, [])))
            if set_id in limited and limited[set_id]['Costumes']:
                card['LimitedCostumes'] += [c for c in limited[set_id]['Costumes'] if c not in card['LimitedCostumes']]
                card['Date'] = min([d for d in [card['Date'], limited[set_id]['Date']] if d], default='')
            for film in films_by_set.get(set_id, []):
                label = _trigger(film)
                if label not in card['Films']:
                    card['Films'].append(label)
    for card in cards.values():
        if card['LimitedCostumes']:
            card['Batch'] = '生日限定'
            continue
        # A trio shared by launch and later sets counts from its earliest batch.
        batches = [_batch(set_id) for set_id in card['SpinSetIds']]
        if None in batches:
            issues.append({'Status': 'unknown_spin_set_batch', 'SnapshotId': card['Id'], 'SpinSetIds': card['SpinSetIds']})
        card['Batch'], card['Date'] = min((b for b in batches if b), key=lambda b: b[1], default=('', ''))
    # Release order; launch cards have no date and come first.
    ordered = sorted(cards.values(), key=lambda c: (c['Date'], min(c['SpinSetIds']), c['Id']))
    for card in ordered:
        card['Category'] = ('限定' if card['LimitedCostumes'] else '通常') + '·' + PARTY.get(len(card['CharacterIds']), f"{len(card['CharacterIds'])}人")
    return {'Cards': ordered, 'Issues': issues, 'SnapshotCount': sum(len(c['SnapshotIds']) for c in ordered)}


def _comment_slots(cards):
    return {rarity: max([len(m['Comments']) for c in cards for m in c['Memos'] if m['Rarity'] == rarity], default=0)
            for rarity in RARITIES.values()}


def export(data):
    cards = data['Cards']
    slots = _comment_slots(cards)
    circled = '①②③④'
    headers = ['编号', '日期(JST)', '追加批次', '场景', '位置', '类别', '主角', '话题']
    for rarity in RARITIES.values():
        headers.append(f'{rarity}备忘录')
        for index in range(slots[rarity]):
            headers += [f'{rarity}评论{circled[index]}角色', f'{rarity}评论{circled[index]}']
    headers += ['限定服装', '触发胶卷', 'SpinSetId']
    rows = []
    for card in cards:
        row = [card['Id'], card['Date'], card['Batch'], ' / '.join(card['Scenes']), ' / '.join(card['Positions']), card['Category'],
               '・'.join(card['Cast']), card['Topic']]
        for memo in card['Memos']:
            row.append(memo['Text'])
            for index in range(slots[memo['Rarity']]):
                comment = memo['Comments'][index] if index < len(memo['Comments']) else {}
                row += [comment.get('Character', ''), comment.get('Text', '')]
        row += [' / '.join(card['LimitedCostumes']), ' / '.join(card['Films']), ', '.join(map(str, card['SpinSetIds']))]
        rows.append(row)

    topics = Counter(card['Topic'] for card in cards if card['Topic'])
    topic_order = [topic for topic, _ in topics.most_common()]
    answers = defaultdict(lambda: defaultdict(list))
    for card in cards:
        if card['Topic'] and len(card['CharacterIds']) == 1:
            found = answers[card['CharacterIds'][0]][card['Topic']]
            if card['TopicAnswer'] not in found:
                found.append(card['TopicAnswer'])
    topic_rows = [[_name(cid), *[' / '.join(answers[cid].get(topic, [])) for topic in topic_order]]
                  for cid in sorted(answers)]

    comment_rows, written, received = [], Counter(), Counter()
    subject_single, subject_group = Counter(), Counter()
    for card in cards:
        for cid in card['CharacterIds']:
            (subject_single if len(card['CharacterIds']) == 1 else subject_group)[cid] += 1
        for memo in card['Memos']:
            for comment in memo['Comments']:
                written[comment['CharacterId']] += 1
                for cid in card['CharacterIds']:
                    received[cid] += 1
                comment_rows.append([comment['Character'], comment['Text'], memo['Rarity'], '・'.join(card['Cast']),
                                     memo['Text'], ' / '.join(card['Scenes']), card['Id'], comment['CharacterId']])
    comment_rows.sort(key=lambda r: (r[7], r[6]))
    stats = [[_name(cid), subject_single[cid], subject_group[cid], written[cid], received[cid]]
             for cid in sorted(set(subject_single) | set(subject_group) | set(written))]

    memo_columns = [i + 1 for i, h in enumerate(headers) if '备忘录' in h or ('评论' in h and not h.endswith('角色'))]
    return write_workbook(xlsx_path('spin_memos.xlsx'), [
        {'title': '备忘录', 'headers': headers, 'rows': rows, 'wrap_cols': memo_columns,
         'col_widths': {'C': 14, 'D': 12, 'E': 18, 'F': 12, 'G': 18, 'H': 22}},
        {'title': '话题对照', 'headers': ['角色', *topic_order], 'rows': topic_rows, 'wrap_cols': list(range(2, len(topic_order) + 2)),
         'col_widths': {'A': 12}},
        {'title': '评论检索', 'headers': ['评论角色', '评论', '稀有度', '相片主角', '被评论的备忘录', '场景', '编号', '评论角色ID'],
         'rows': comment_rows, 'wrap_cols': [2, 5], 'col_widths': {'A': 12, 'B': 40, 'D': 18, 'E': 40}},
        {'title': '角色统计', 'headers': ['角色', '单人备忘录卡', '多人备忘录卡', '写下的评论', '收到的评论'], 'rows': stats},
        {'title': '说明', 'headers': ['项目', '说明'], 'col_widths': {'A': 14, 'B': 90}, 'rows': [
            ['备忘录卡', '同一主角、同一组 R/SR/SSR 备忘录与评论算一张；不同抽取时间、姿势、相框的重复相片已合并'],
            ['稀有度', 'Wiki 称 R/SR/SSR；客户端 SnapshotRarityCode 为 N/R/SR'],
            ['场景', 'SpinBaseCode 1–4（客户端 Casino / Factory / AmusementPark / AmericanDiner），沿用 Wiki 译名'],
            ['位置', '所属 SpinSet 的角色动作文件推断；一张卡出现在多个位置时全部列出'],
            ['类别', '通常 / 限定 × 人数；限定指只在限定服装胶卷中追加的 SpinSet（生日服装等）'],
            ['日期', '限定卡：解锁该卡的限定服装 ReleaseDateTime（日本时间）；美式餐厅与二周年新胶卷：游戏内更新公告日期；初始卡留空。全表按日期排列'],
            ['追加批次', '初始 / 美式餐厅追加（2025-03-31）/ 二周年新胶卷（2026-05-01，电玩城双人与游乐园三四人新组合）/ 生日限定'],
            ['触发胶卷', '拍摄前胶卷滚动转到的颜色：灰色＝单人，金色＝指定双人组合（电玩城），彩色＝三四人组合（游乐园）或二周年生日 Present；“＋”连接的角色需同时编成，转到其中一人的金色/彩色胶卷即触发全员'],
            ['话题', '备忘录以“〜话题〜”开头时提取；“话题对照”表只收单人卡'],
            ['评论顺序', 'StickyNoteId1–4 = 左上、右上、左下、右下'],
            ['统计', f"{len(cards)} 张备忘录卡，来自 {data['SnapshotCount']} 张相片"],
        ]},
    ])


def run(session=None):
    data = extract(session)
    save_json(data, audit_path('spin_memos.json'))
    return export(data)
