"""Two-sided character home conversations with explicit masterdata keys."""
from collections import defaultdict

from ..core.exporter import audit_path, xlsx_path, write_xlsx
from ..core.scanner import save_json
from ..core.output import record_warning
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


def run(acb_root, session=None):
    scanned, warnings = scan_character_home_voice_packages(acb_root, duo_only=True)
    data = build(session.tables, scanned)
    data['ScanWarnings'] = warnings
    save_json(data, audit_path('home_voice_duo.json'))
    characters = session.tables.by_id('mst_character', 'CharacterId', required=False)
    def name(cid):
        return characters.get(cid, {}).get('CharacterNameJpn', f'Character({cid})')
    rows = []
    for pair in data['Pairs']:
        first, second = pair['First'], pair['Partner']
        rows.append([name(first['CharacterId']), name(second['CharacterId']), first['Text'], second['Text'],
                     pair['Raw'].get('PartnerVoiceStart'), first['Status'], second['Status']])
    write_xlsx(rows, xlsx_path('home_voice_duo.xlsx'),
               ['角色', '搭档', '角色台词', '搭档台词', '搭档开始时间原值', '角色文本状态', '搭档文本状态'], sheet_title='双人主页')
    if data['Issues'] or warnings:
        record_warning(f"双人主页有 {len(data['Issues'])} 条文本缺项、{len(warnings)} 条扫描告警，详见 home_voice_duo.json")
    return data
