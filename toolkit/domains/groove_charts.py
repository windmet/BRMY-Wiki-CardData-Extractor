"""GROOVE 谱面统计：mst_groove_music_stage.StageFileName → Score/<名>.s2bscore。

谱面是明文 MessagePack 字典（Bpm、EndTimeMs、Notes[TimeMs/Type/DurationMs/NoteType]、
Gimmicks）。正式清单把它们列在类别 8（Score/）。未上线曲目的谱面尚未发布，记为缺失。
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..core.exporter import audit_path, xlsx_path, write_workbook
from ..core.output import record_warning
from ..core.s2b_parser import parse_s2b_file
from ..core.scanner import save_json

SCORE_DIR = 'Score/'
SUFFIX = '.s2bscore'
JST = timezone(timedelta(hours=9))
SIDES = {1: 'A', 2: 'B', 3: 'C'}
MUSIC_TYPES = {1: '通常', 2: '个人曲', 3: '全员曲', 4: '组合曲', 100: '期间限定', 101: '每日'}
GIMMICK_NAMES = {'Bush': '连打', 'SeekBar': '预告'}


def resource_keys(tables):
    return sorted({SCORE_DIR + row['StageFileName'] + SUFFIX
                   for row in tables.rows('mst_groove_music_stage', active_only=True) if row.get('StageFileName')})


def summarize(score):
    notes = score.get('Notes') or []
    kinds = Counter()
    for note in notes:
        kinds[note.get('Type')] += 1
        if note.get('DurationMs'):
            kinds['long'] += 1
        if note.get('NoteType'):
            kinds[note['NoteType']] += 1
        if note.get('DivisionCount'):
            kinds['division'] += 1
    gimmicks = Counter(g.get('GimmickType') for g in score.get('Gimmicks') or [])
    seconds = (score.get('EndTimeMs') or 0) / 1000
    return {'Bpm': score.get('Bpm'), 'Seconds': round(seconds, 1), 'Notes': len(notes),
            'Left': kinds['Left'], 'Right': kinds['Right'], 'Long': kinds['long'],
            'Rare': kinds['Rare'], 'Hirameki': kinds['Hirameki'], 'Division': kinds['division'],
            'Density': round(len(notes) / seconds, 2) if seconds else None,
            'Gimmicks': dict(gimmicks), 'ComboPieceSelector': score.get('ComboPieceSelectorLabelName', ''),
            'CueName': score.get('CueName', '')}


def _index_sources(source):
    files = {}
    for entry in source if isinstance(source, list) else [source] if source else []:
        path = Path(entry)
        for file in ([path] if path.is_file() else sorted(path.rglob('*' + SUFFIX)) if path.is_dir() else []):
            files.setdefault(file.name, file)
    return files


def _jst_date(value):
    if not value or str(value).startswith('2001'):
        return ''
    return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(JST).date().isoformat()


def extract(session, source=None):
    tables = session.tables
    files = _index_sources(source)
    music = {row['MusicId']: row for row in tables.rows('mst_music')}
    groove = tables.by_id('mst_groove_music', 'MusicId', required=False)
    charts, issues = [], []
    for row in tables.require('mst_groove_music_stage', active_only=True):
        name = row.get('StageFileName', '') + SUFFIX
        owner = groove.get(row['MusicId'], {})
        item = {'MusicId': row['MusicId'], 'Side': SIDES.get(row.get('GrooveMusicStageType'), row.get('GrooveMusicStageType')),
                'Difficulty': row.get('GrooveMusicStageDifficulty'), 'File': name,
                'Title': music.get(row['MusicId'], {}).get('DisplayName', ''),
                'MusicType': MUSIC_TYPES.get(owner.get('GrooveMusicType'), owner.get('GrooveMusicType')),
                'Released': _jst_date(owner.get('ReleaseDateTime')), 'SortOrder': owner.get('SortOrder'),
                'Chart': None}
        path = files.get(name)
        if path is None:
            issues.append({'Status': 'missing_score_file', 'MusicId': row['MusicId'], 'File': name,
                           'ReleaseDateTime': owner.get('ReleaseDateTime')})
        else:
            try:
                decoded = parse_s2b_file(path, strict_extensions=True)
                if len(decoded) != 1 or not isinstance(decoded[0], dict):
                    raise ValueError('unexpected score shape')
                item['Chart'] = summarize(decoded[0])
            except Exception as error:
                issues.append({'Status': 'undecodable_score_file', 'File': name, 'Error': str(error)})
        charts.append(item)
    return {'Charts': charts, 'Issues': issues, 'Loaded': sum(1 for c in charts if c['Chart']), 'Expected': len(charts)}


HEADERS = ['上线日期(JST)', '曲目', '面', '难度', '曲目类型', 'BPM', '时长(秒)', '总音符', '左', '右',
           '长按', 'Rare', 'ヒラメキ', '分段', '密度(个/秒)', '连打机关', '预告机关', 'MusicId', '文件名']


def export(data):
    rows = []
    for item in sorted(data['Charts'], key=lambda c: (c['Released'] or '0000', c['SortOrder'] or 0, c['MusicId'], str(c['Side']))):
        chart = item['Chart'] or {}
        gimmicks = chart.get('Gimmicks', {})
        rows.append([item['Released'], item['Title'], item['Side'], item['Difficulty'], item['MusicType'],
                     chart.get('Bpm'), chart.get('Seconds'), chart.get('Notes', '谱面未发布'), chart.get('Left'),
                     chart.get('Right'), chart.get('Long'), chart.get('Rare'), chart.get('Hirameki'),
                     chart.get('Division'), chart.get('Density'), gimmicks.get('Bush', ''), gimmicks.get('SeekBar', ''),
                     item['MusicId'], item['File']])
    notes = [['面', 'GrooveMusicStageType：A/B/C'],
             ['难度', '游戏数据里的难度数值（GrooveMusicStageDifficulty），未换算'],
             ['长按', '带 DurationMs 的音符；ヒラメキ 音符同时计入长按'],
             ['分段', '带 DivisionCount 的音符（伴随 ComboPieces）'],
             ['谱面未发布', '曲目尚未上线时 CDN 没有谱面文件'],
             ['文件', f"已加载 {data['Loaded']} / {data['Expected']}"]]
    return write_workbook(xlsx_path('groove_charts.xlsx'), [
        {'title': 'GROOVE谱面', 'headers': HEADERS, 'rows': rows, 'col_widths': {'B': 28, 'S': 20}},
        {'title': '说明', 'headers': ['项目', '说明'], 'rows': notes, 'col_widths': {'A': 14, 'B': 70}},
    ])


def run(session=None, *, source=None):
    data = extract(session, source=source)
    save_json(data, audit_path('groove_charts.json'))
    missing = data['Expected'] - data['Loaded']
    if missing:
        record_warning(f"GROOVE 谱面 {missing} 个未发布或无法解析，详见 groove_charts.json")
    return export(data)
