"""Evidence-backed Type3 supplement, separate from staff completeness."""
import hashlib
from pathlib import Path
from .audio import extract_text_metadata
from ..core.scanner import save_json
from ..core.exporter import write_xlsx
from ..core.output import record_warning

PACKAGE_BY_TARGET = {24: 'voice_rare_general.acb'}


def extract(tables, root):
    records, packages, issues = [], {}, []
    names = tables.by_id('mst_character', 'CharacterId', required=False)
    for row in tables.rows('mst_home_voice', active_only=True):
        if row.get('HomeVoiceTypeCode') != 3:
            continue
        target = row.get('HomeVoiceTargetId'); package = PACKAGE_BY_TARGET.get(target)
        if package and package not in packages:
            matches = sorted(Path(root).rglob(package))
            evidence = []
            for path in matches:
                try:
                    metadata, stable = extract_text_metadata(str(path))
                    evidence.append({'Path': str(path.resolve()), 'Sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                     'Metadata': metadata, 'Stable': stable})
                except Exception as error:
                    issues.append({'Path': str(path), 'Error': str(error)})
            packages[package] = evidence
        sources = packages.get(package, [])
        matches = [m for p in sources if p['Stable'] for m in p['Metadata']
                   if m.get('CueName') == row.get('VoiceCueName') and m.get('MatchStatus') == 'matched_by_acb_utf']
        texts = {m.get('Text') for m in matches if m.get('Text')}
        status = ('unsupported_target' if not package else 'missing_package' if not sources else
                  'resolved' if len(texts) == 1 else 'conflicting_text' if len(texts) > 1 else 'missing_cue_text')
        entry = {'Raw': row, 'CharacterName': names.get(target, {}).get('CharacterNameJpn', str(target)),
                 'Status': status, 'Text': next(iter(texts)) if status == 'resolved' else '', 'Matches': matches}
        records.append(entry)
        if status != 'resolved':
            issues.append({'TargetId': target, 'CueName': row.get('VoiceCueName'), 'Status': status})
    return {'Records': records, 'Packages': packages, 'Issues': issues, 'StaffCompleteness': 'not_applicable'}


def run(tables, root, json_dir, xlsx_dir):
    data = extract(tables, root)
    if not data['Records']:
        return None
    save_json(data, str(Path(json_dir) / 'system_voices.json'))
    rows = [[r['CharacterName'], r['Raw'].get('VoiceCueName'), r['Text'].replace('\\n', '\n'), '', r['Status']]
            for r in data['Records']]
    path = write_xlsx(rows, str(Path(xlsx_dir) / 'system_voices.xlsx'),
                      headers=['角色', '语音标识', '日文', '中文翻译', '核对状态'])
    if data['Issues']:
        record_warning(f"系统语音有 {len(data['Issues'])} 条缺项，详见 system_voices.json")
    return path
