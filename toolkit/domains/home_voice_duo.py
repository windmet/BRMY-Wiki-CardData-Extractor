"""Two-sided character home conversations with explicit masterdata keys."""
from collections import defaultdict

from ..core.exporter import audit_path, xlsx_path, write_workbook
from ..core.scanner import save_json
from ..core.output import record_warning
from ..core.review import status_of
from .home_voices import scan_character_home_voice_packages


def build(tables, scanned):
    masters = defaultdict(list)
    for row in tables.rows('mst_home_voice', active_only=True):
        if row.get('HomeVoiceTypeCode') == 1 and row.get('HomeVoiceCategory') == 11:
            masters[(row.get('HomeVoiceTargetId'), row.get('HomeVoiceNo'))].append(row)
    sources = defaultdict(list)
    for row in scanned:
        sources[(row['SpeakerCharacterId'], row['CueName'])].append(row)
    issues, pairs = [], []
    def side(cid, number):
        matches = masters.get((cid, number), [])
        entry = {'CharacterId': cid, 'HomeVoiceNo': number, 'Masters': matches, 'Sources': [], 'Text': '', 'Status': 'missing_master'}
        if len(matches) != 1:
            entry['Status'] = 'ambiguous_master' if matches else 'missing_master'
        else:
            cue = matches[0].get('VoiceCueName'); entry['CueName'] = cue
            candidates = sources.get((cid, cue), []); entry['Sources'] = candidates
            stable = [r for r in candidates if r.get('StableRead') and r.get('MetadataMatchStatus') == 'matched_by_acb_utf']
            texts = {r.get('TextWiki', '') for r in stable}
            if not candidates:
                entry['Status'] = 'missing_acb_cue'
            elif len(stable) != len(candidates):
                entry['Status'] = 'unstable_metadata'
            elif len(texts) != 1:
                entry['Status'] = 'conflicting_text'
            elif not next(iter(texts)):
                entry['Status'] = 'empty_text'
            else:
                entry.update(Status='resolved', Text=next(iter(texts)))
        if entry['Status'] != 'resolved':
            issues.append({'CharacterId': cid, 'HomeVoiceNo': number, 'Status': entry['Status']})
        return entry
    for row in tables.require('mst_character_home_voice_duo', active_only=True):
        first = side(row['CharacterId'], row['HomeVoiceNo'])
        second = side(row['PartnerCharacterId'], row['PartnerHomeVoiceNo'])
        pairs.append({'Raw': row, 'First': first, 'Partner': second,
                      'PairKey': sorted([row['CharacterId'], row['PartnerCharacterId']])})
    return {'Pairs': pairs, 'Issues': issues}


def _key_target(side):
    masters = side.get('Masters') or [{}]
    return masters[0].get('KeyTargetValue')


def build_sheets(pairs, name):
    """Lay out conversations by unordered pair (1-2…1-21, 2-3…), plus a per-character view.

    Batches rank the raw ``KeyTargetValue`` of the first speaker's master row
    (0 for the original set, 2 for the later one); the value is shown as-is
    because its meaning is unconfirmed.
    """
    batches = {value: rank for rank, value in enumerate(
        sorted({_key_target(p['First']) for p in pairs}, key=lambda v: (v is None, v)), start=1)}
    ordered = sorted(pairs, key=lambda p: (p['PairKey'], batches[_key_target(p['First'])],
                                           p['First']['HomeVoiceNo']))
    conversations, group_no, previous = [], 0, None
    for pair in ordered:
        if pair['PairKey'] != previous:
            group_no, previous = group_no + 1, pair['PairKey']
        first, second = pair['First'], pair['Partner']
        key = _key_target(first)
        conversations.append({
            'Group': group_no, 'Pair': pair['PairKey'], 'Batch': batches[key], 'KeyTargetValue': key,
            'First': first, 'Second': second, 'Start': pair['Raw'].get('PartnerVoiceStart'),
            'Status': status_of(first['Status'], second['Status']),
        })

    def lines(item):
        return [name(item['First']['CharacterId']), item['First']['Text'],
                name(item['Second']['CharacterId']), item['Second']['Text']]

    by_pair = [[c['Group'], name(c['Pair'][0]), name(c['Pair'][1]), f"第{c['Batch']}批", c['KeyTargetValue'],
                *lines(c), c['Start'], *c['Status']] for c in conversations]
    by_character = []
    characters = sorted({cid for c in conversations for cid in c['Pair']})
    for cid in characters:
        own = [c for c in conversations if cid in c['Pair']]
        own.sort(key=lambda c: (c['Pair'][1] if c['Pair'][0] == cid else c['Pair'][0], c['Batch']))
        for c in own:
            partner = c['Pair'][1] if c['Pair'][0] == cid else c['Pair'][0]
            by_character.append([name(cid), name(partner), f"第{c['Batch']}批", *lines(c), c['Group'], *c['Status']])
    summary = []
    for cid in characters:
        own = [c for c in conversations if cid in c['Pair']]
        partners = {p for c in own for p in c['Pair'] if p != cid}
        row = [name(cid), len(partners), len(own)]
        row += [sum(c['Batch'] == rank for c in own) for rank in sorted(set(batches.values()))]
        row.append(sum(c['First']['CharacterId'] == cid for c in own))
        summary.append(row)

    talk = ['先说角色', '先说台词', '接话角色', '接话台词']
    return [
        {'title': '按组合登记', 'rows': by_pair,
         'headers': ['组号', '角色A', '角色B', '批次', '触发参数（含义未确认）', *talk, '接话开始秒', '文本状态', '说明'],
         'col_widths': {'B': 12, 'C': 12, 'F': 12, 'G': 46, 'H': 12, 'I': 46}, 'wrap_cols': [7, 9]},
        {'title': '按角色查看', 'rows': by_character,
         'headers': ['角色', '对话对象', '批次', *talk, '组号', '文本状态', '说明'],
         'col_widths': {'A': 12, 'B': 12, 'D': 12, 'E': 46, 'F': 12, 'G': 46}, 'wrap_cols': [5, 7]},
        {'title': '统计', 'rows': summary,
         'headers': ['角色', '对话对象数', '对话总数', *[f'第{rank}批' for rank in sorted(set(batches.values()))],
                     '其中先开口']},
    ]


def run(acb_root, session=None):
    scanned, warnings = scan_character_home_voice_packages(acb_root, duo_only=True)
    data = build(session.tables, scanned)
    data['ScanWarnings'] = warnings
    save_json(data, audit_path('home_voice_duo.json'))
    characters = session.tables.by_id('mst_character', 'CharacterId', required=False)
    def name(cid):
        return characters.get(cid, {}).get('CharacterNameJpn', f'Character({cid})')
    write_workbook(xlsx_path('home_voice_duo.xlsx'), build_sheets(data['Pairs'], name))
    if data['Issues'] or warnings:
        record_warning(f"双人主页有 {len(data['Issues'])} 条文本缺项、{len(warnings)} 条扫描告警，详见 home_voice_duo.json")
    return data
