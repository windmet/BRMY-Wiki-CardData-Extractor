"""Join optional local layouts by the declared chart filename, never by event ID."""
import hashlib
import math
from pathlib import Path

from ..core.s2b_parser import parse_s2b_file


def load_coordinates(events, tables, source=None):
    result = {'Status': 'not_loaded', 'Charts': [], 'Issues': [], 'Files': []}
    if not source:
        return result
    files = set()
    for value in source if isinstance(source, list) else [source]:
        path = Path(value).resolve()
        if path.is_dir():
            files.update(p.resolve() for p in path.rglob('*') if p.is_file() and p.suffix.lower() == '.s2bchart')
        elif path.is_file() and path.suffix.lower() == '.s2bchart':
            files.add(path)
        else:
            raise ValueError(f'OJT 坐标输入需要 .s2bchart 文件或目录: {path}')
    if not files:
        raise ValueError('OJT 坐标目录中没有 .s2bchart 文件')
    by_name = {}
    for path in sorted(files):
        by_name.setdefault(path.stem, []).append(path)
    characters = tables.group_by('mst_character', 'CharacterId', required=False)
    used = set()
    for event in events:
        for chart in event['Charts']:
            name = chart.get('ChartFileName', '')
            entry = {'EventId': event['EventId'], 'ChartFileName': name,
                     'Status': 'missing_file', 'Units': 'unconfirmed', 'Coordinates': []}
            result['Charts'].append(entry)
            matches = by_name.get(name, [])
            used.update(matches)
            if len(matches) != 1:
                entry['Status'] = 'ambiguous_file' if matches else 'missing_file'
                result['Issues'].append(dict(EventId=event['EventId'], Status=entry['Status'],
                                             ChartFileName=name, Paths=[str(p) for p in matches]))
                continue
            path = matches[0]
            entry['Path'] = str(path)
            entry['Sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            try:
                raw = parse_s2b_file(str(path), strict_extensions=True)
                entry['Raw'] = raw
                # Only the observed layout contract is accepted. Older shapes remain diagnostic.
                if not (isinstance(raw, list) and len(raw) == 1 and isinstance(raw[0], dict)
                        and isinstance(raw[0].get('IconLayouts'), dict) and raw[0]['IconLayouts']):
                    raise ValueError('unsupported or empty IconLayouts structure')
                coords = []
                ids = set()
                for key, layout in raw[0]['IconLayouts'].items():
                    cid = int(key)
                    if cid in ids or len(characters.get(cid, [])) != 1:
                        raise ValueError(f'duplicate, missing or ambiguous CharacterId: {key}')
                    ids.add(cid)
                    position = layout.get('IconPosition') if isinstance(layout, dict) else None
                    if not (isinstance(position, list) and len(position) == 2 and
                            all(type(v) in (int, float) and math.isfinite(v) for v in position)):
                        raise ValueError(f'invalid IconPosition: {key}')
                    order = layout.get('SiblingIndex')
                    if type(order) is not int or order < 0:
                        raise ValueError(f'invalid SiblingIndex: {key}')
                    coords.append({'CharacterId': cid,
                                   'CharacterName': characters[cid][0].get('CharacterNameJpn', str(cid)),
                                   'X': position[0], 'Y': position[1], 'SiblingIndex': order})
                entry['Coordinates'] = sorted(coords, key=lambda c: (c['SiblingIndex'], c['CharacterId']))
                entry['Status'] = 'loaded'
            except Exception as error:
                entry['Status'] = 'invalid_file'
                result['Issues'].append({'EventId': event['EventId'], 'Status': 'invalid_file',
                                         'Path': str(path), 'Error': str(error)})
    for path in sorted(files):
        result['Files'].append({'Path': str(path), 'Sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                'Matched': path in used})
        if path not in used:
            result['Issues'].append({'Status': 'unmatched_file', 'Path': str(path)})
    loaded = sum(c['Status'] == 'loaded' for c in result['Charts'])
    result['Status'] = ('loaded' if loaded and not result['Issues'] else 'partial' if loaded else 'not_loaded')
    return result
