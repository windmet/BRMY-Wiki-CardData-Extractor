"""消消乐关卡目录：mst_puzzle_stage 行 + 对应 .s2bStage 文件里的目标、生命、步数与机关。

文件名来自 2.1.0 客户端格式串 ``Stage{0}_{1}_{2}``（PuzzleMapId, PuzzleStageNo,
PuzzleType）与 ``StoryStage{0}_{1}_{2}_{3}``（主线剧情关卡）。这些文件不在正式清单
里，CDN 的 ``Stages/`` 路径按此名称直接提供。字段位置见 docs/PUZZLE_STAGES.md。
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..core.data import ATTRIBUTE_MAP, CHAR_MAP
from ..core.exporter import audit_path, xlsx_path, write_workbook
from ..core.output import record_warning
from ..core.s2b_parser import parse_s2b_file
from ..core.scanner import save_json

STAGE_DIR = 'Stages/'
SUFFIX = '.s2bStage'
JST = timezone(timedelta(hours=9))
PLACEHOLDER_YEAR = '2001'

# Coly PuzzleType / PuzzleStageType enums in the 2.1.0 dump.cs.
FACES = {1: 'A', 2: 'B', 3: 'C', 4: 'D', 5: 'E', 6: 'F'}
STAGE_TYPES = {1: '通常', 2: '挑战', 3: '每日', 4: '指定编成', 5: '个人曲', 6: '个人曲Remix',
               7: 'OJT', 8: '全员曲', 9: 'Shuffle曲'}
SPECIAL_PIECES = {0: 'コンボピース', 1: 'スペシャルピース'}

# Puzzle.StageInfoDefinition.StageInfo [Key(n)] positions (2.1.0 dump.cs).
MAP, SPAWNER_TYPE, FIX_GIMMICK, PHASES = 1, 3, 4, 5
ATTRIBUTE_INFO, TARGETS, SCORE_INFO, LIFE, TUTORIAL = 7, 8, 9, 10, 11
FIX_GIMMICK_2, FIX_GIMMICK_3, WALL_LINE, WALL_COLUMN, RULE, FIX_ON_MAIN = 14, 15, 16, 17, 18, 19
BOARD_LAYERS = (MAP, FIX_GIMMICK, FIX_GIMMICK_2, FIX_GIMMICK_3, WALL_LINE, WALL_COLUMN, FIX_ON_MAIN)


def stage_file_name(row):
    return f"Stage{row['PuzzleMapId']}_{row['PuzzleStageNo']}_{row['PuzzleType']}{SUFFIX}"


def story_stage_file_name(row):
    return (f"StoryStage{row['StoryTypeCode']}_{row['StoryTargetBaseId']}_"
            f"{row['StoryTargetChapterId']}_{row['StoryTargetSectionNo']}{SUFFIX}")


def resource_keys(tables):
    """CDN keys of every active stage; derived from masterdata, not the manifest."""
    names = [stage_file_name(row) for row in tables.rows('mst_puzzle_stage', active_only=True)]
    names += [story_stage_file_name(row) for row in tables.rows('mst_puzzle_story_stage', active_only=True)]
    return sorted({STAGE_DIR + name for name in names})


def _at(values, index, default=None):
    return values[index] if isinstance(values, list) and len(values) > index and values[index] is not None else default


def _jst_date(value):
    if not value or str(value).startswith(PLACEHOLDER_YEAR):
        return ''
    moment = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    return moment.astimezone(JST).date().isoformat()


class Names:
    def __init__(self, tables):
        self.pieces = {row['PieceInfoId']: row.get('Name', '') for row in tables.rows('mst_piece_info')}
        self.tutorials = {}
        for row in sorted(tables.rows('mst_gimmick_tutorial', active_only=True), key=lambda r: r.get('GimmickSlideNo', 0)):
            self.tutorials.setdefault(row['TutorialId'], row.get('GimmickName', ''))
        music = {row['MusicId']: row.get('DisplayName', '') for row in tables.rows('mst_music')}
        self.music_info = {row['MusicInfoId']: music.get(row.get('MusicId'), '') for row in tables.rows('mst_music_info')}

    def piece(self, piece_id):
        return self.pieces.get(piece_id) or f'#{piece_id}'

    def target(self, piece_id, count):
        # targetId 0 is a score goal (story stages: "スコアランクBを達成！").
        return f'分数≥{count}' if piece_id == 0 else f'{self.piece(piece_id)}×{count}'

    def counted(self, counter):
        return ' / '.join(f'{self.piece(pid)}×{count}' for pid, count in sorted(counter.items()))


def digest(info, names):
    """Wiki-facing summary of one decoded StageInfo array."""
    targets = [(_at(t, 0), _at(t, 1)) for t in _at(info, TARGETS, [])]
    score = _at(info, SCORE_INFO, [])
    ranks = _at(score, 0, {}) or {}
    life = _at(info, LIFE, [])
    rule = _at(info, RULE, [])
    move_limit = _at(rule, 3)
    board = Counter()
    for layer in BOARD_LAYERS:
        board.update(v for v in _at(info, layer, []) if isinstance(v, int) and v > 0)
    colors, drops = set(), set()
    for cell in _at(info, SPAWNER_TYPE, []):
        colors.update(_at(d, 0) for d in _at(cell, 0, []) if _at(d, 1, 0))
        drops.update(_at(d, 0) for d in _at(cell, 1, []) if _at(d, 1, 0))
    tutorials = [_at(t, 0) for t in _at(_at(info, TUTORIAL, []), 0, [])]
    phases = _at(info, PHASES, [])
    bgm = _at(_at(phases, 0, []), 2, [])
    return {
        'Targets': [{'PieceInfoId': pid, 'Name': names.piece(pid), 'Count': count} for pid, count in targets],
        'TargetText': ' / '.join(names.target(pid, count) for pid, count in targets) or '分数',
        'ScoreRanks': ranks,
        'FileAverageCombo': _at(score, 1),
        'Life': _at(life, 0),
        'LifeDamage': _at(life, 1),
        'MoveLimit': move_limit if isinstance(move_limit, int) and move_limit > 0 else None,
        'SpecialPiece': SPECIAL_PIECES.get(_at(rule, 0), _at(rule, 0)),
        'NoSeekBar': bool(_at(rule, 2, False)),
        'Gravity': bool(_at(rule, 1, False)),
        'BoardPieces': dict(board),
        'BoardText': names.counted(board),
        'DropColors': sorted(c for c in colors if c is not None),
        'DropGimmicks': sorted(d for d in drops if d is not None),
        'DropGimmickText': ' / '.join(names.piece(d) for d in sorted(d for d in drops if d is not None)),
        'Tutorials': tutorials,
        'TutorialText': ' / '.join(names.tutorials.get(t) or names.piece(t) for t in tutorials if t),
        'StageAttribute': ATTRIBUTE_MAP.get(_at(_at(info, ATTRIBUTE_INFO, []), 0), ''),
        'MusicInfoId': _at(bgm, 1),
        'Bars': [_at(bgm, 4), _at(bgm, 5)],
        'PhaseCount': len(phases),
    }


def _index_sources(source):
    files = {}
    for entry in source if isinstance(source, list) else [source] if source else []:
        path = Path(entry)
        for file in ([path] if path.is_file() else sorted(path.rglob('*' + SUFFIX)) if path.is_dir() else []):
            files.setdefault(file.name, file)
    return files


def _load(files, name, issues, owner):
    path = files.get(name)
    if path is None:
        issues.append({**owner, 'Status': 'missing_stage_file', 'File': name})
        return None
    try:
        decoded = parse_s2b_file(path, strict_extensions=True)
    except Exception as error:
        issues.append({**owner, 'Status': 'undecodable_stage_file', 'File': name, 'Error': str(error)})
        return None
    if len(decoded) != 1 or not isinstance(decoded[0], list):
        issues.append({**owner, 'Status': 'unexpected_stage_shape', 'File': name})
        return None
    return decoded[0]


def extract(session, source=None):
    tables = session.tables
    names = Names(tables)
    files = _index_sources(source)
    issues = []
    maps = tables.by_id('mst_puzzle_map', 'PuzzleMapId', required=False)
    events = tables.by_id('mst_event', 'EventId', required=False)
    campaigns = tables.by_id('mst_campaign', 'CampaignId', required=False)
    music_stage = tables.by_id('mst_music_puzzle_stage', 'MusicPuzzleStageId', required=False)
    music = {row['MusicId']: row.get('DisplayName', '') for row in tables.rows('mst_music')}

    def owner(map_row):
        if map_row.get('EventId'):
            event = events.get(map_row['EventId'], {})
            return '活动', event.get('EventTitle', f"活动{map_row['EventId']}"), event.get('StartTime')
        if map_row.get('CampaignId'):
            campaign = campaigns.get(map_row['CampaignId'], {})
            return 'CP', campaign.get('CampaignTitle', f"CP{map_row['CampaignId']}"), campaign.get('StartTime')
        if map_row.get('CharacterId'):
            return '角色', CHAR_MAP.get(map_row['CharacterId'], f"角色{map_row['CharacterId']}"), None
        return '其他', '', None

    stages = []
    for row in tables.require('mst_puzzle_stage', active_only=True):
        map_row = maps.get(row['PuzzleMapId'], {})
        if not map_row:
            issues.append({'Status': 'missing_map', 'PuzzleMapId': row['PuzzleMapId']})
        kind, title, owner_start = owner(map_row)
        name = stage_file_name(row)
        key = {k: row[k] for k in ('PuzzleMapId', 'PuzzleStageNo', 'PuzzleType')}
        info = _load(files, name, issues, key)
        song = music.get(music_stage.get(row.get('MusicPuzzleStageId'), {}).get('MusicId'), '')
        released = _jst_date(row.get('ReleaseDateTime')) or _jst_date(owner_start)
        stages.append({**key, 'Kind': kind, 'Owner': title, 'Released': released,
                       'Face': FACES.get(row['PuzzleType'], row['PuzzleType']),
                       'StageType': STAGE_TYPES.get(row.get('PuzzleStageType'), row.get('PuzzleStageType')),
                       'Music': song, 'Attribute': ATTRIBUTE_MAP.get(row.get('CardAttributeCode'), ''),
                       'SSRankScore': row.get('SSRankScore'), 'AverageCombo': row.get('AverageCombo'),
                       'Stamina': row.get('ConsumeStamina'),
                       'IsHidden': bool(row.get('IsHidden')), 'IsCoinStage': bool(row.get('IsCoinStage')),
                       'SortOrder': row.get('SortOrder'), 'File': name,
                       'Stage': digest(info, names) if info is not None else None})

    story_stages = []
    for row in tables.rows('mst_puzzle_story_stage', active_only=True):
        name = story_stage_file_name(row)
        key = {k: row[k] for k in ('StoryTypeCode', 'StoryTargetBaseId', 'StoryTargetChapterId', 'StoryTargetSectionNo')}
        info = _load(files, name, issues, key)
        story_stages.append({**key, 'SSRankScore': row.get('SSRankScore'),
                             'Attribute': ATTRIBUTE_MAP.get(row.get('CardAttributeCode'), ''),
                             'TargetTexts': [row.get(f'Target{i}Text', '') for i in (1, 2, 3) if row.get(f'Target{i}Text')],
                             'File': name, 'Stage': digest(info, names) if info is not None else None})
    for item in stages + story_stages:
        if item['Stage'] and item['Stage']['MusicInfoId']:
            item['Stage']['Music'] = names.music_info.get(item['Stage']['MusicInfoId'], '')
    return {'Stages': stages, 'StoryStages': story_stages, 'Issues': issues,
            'Loaded': sum(1 for item in stages + story_stages if item['Stage']),
            'Expected': len(stages) + len(story_stages)}


HEADERS = ['开放日期(JST)', '归属', '关卡号', '面', '曲目', '关卡种类', '属性', '通关目标', 'SS分数线',
           '平均连击', '生命', '步数上限', '盘面初始机关', '掉落机关', '新机关提示', '消耗体力',
           '隐藏关', '金币关', '地图ID', '文件名']


def _row(item):
    stage = item['Stage'] or {}
    return [item['Released'], item['Owner'], item['PuzzleStageNo'], item['Face'], item['Music'] or stage.get('Music', ''),
            item['StageType'], item['Attribute'] or stage.get('StageAttribute', ''),
            stage.get('TargetText', '文件缺失'), item['SSRankScore'], item['AverageCombo'],
            stage.get('Life'), stage.get('MoveLimit') or '', stage.get('BoardText', ''),
            stage.get('DropGimmickText', ''), stage.get('TutorialText', ''), item['Stamina'],
            '是' if item['IsHidden'] else '', '是' if item['IsCoinStage'] else '', item['PuzzleMapId'], item['File']]


def _sheet_key(item):
    if item['StageType'] == '通常':
        return f"通常·{item['Kind']}"
    return item['StageType']


SHEET_ORDER = ['通常·角色', '通常·活动', '通常·CP', '通常·其他', '挑战', '每日', '指定编成', '个人曲',
               '个人曲Remix', 'OJT', '全员曲', 'Shuffle曲']


def export(data):
    groups = {}
    for item in data['Stages']:
        groups.setdefault(_sheet_key(item), []).append(item)
    sheets = []
    for title in SHEET_ORDER + sorted(set(groups) - set(SHEET_ORDER), key=str):
        items = groups.get(title)
        if not items:
            continue
        items.sort(key=lambda i: (i['Released'] or '0000', i['PuzzleMapId'], i['PuzzleStageNo'], i['PuzzleType']))
        sheets.append({'title': title, 'headers': HEADERS, 'rows': [_row(i) for i in items],
                       'col_widths': {'B': 28, 'E': 22, 'H': 30, 'M': 36, 'N': 24, 'O': 24, 'T': 24}})
    story_rows = []
    for item in data['StoryStages']:
        stage = item['Stage'] or {}
        story_rows.append([f"{item['StoryTargetBaseId']}-{item['StoryTargetChapterId']}-{item['StoryTargetSectionNo']}",
                           stage.get('Music', ''), item['Attribute'], ' / '.join(item['TargetTexts']),
                           stage.get('TargetText', '文件缺失'), item['SSRankScore'], stage.get('Life'),
                           stage.get('MoveLimit') or '', stage.get('BoardText', ''), stage.get('TutorialText', ''), item['File']])
    if story_rows:
        sheets.append({'title': '主线剧情', 'rows': story_rows, 'col_widths': {'D': 30, 'E': 30, 'I': 36, 'K': 28},
                       'headers': ['主线-章-节', '曲目', '属性', '游戏内目标文本', '通关目标', 'SS分数线', '生命',
                                   '步数上限', '盘面初始机关', '新机关提示', '文件名']})
    sheets.append({'title': '说明', 'headers': ['项目', '说明'], 'col_widths': {'A': 16, 'B': 90}, 'rows': [
        ['面', 'PuzzleType：A/B/C 为常规三面，D/E/F 为少数特殊关卡'],
        ['通关目标', '关卡文件 targetInfoList；为空时以分数结算，写作“分数”'],
        ['SS分数线 / 平均连击', '取自游戏数据（SSRankScore / AverageCombo）；关卡文件自带的分数线与平均连击保留在 JSON'],
        ['步数上限', 'rule.moveLimitCount；-1 或缺省表示不限，留空'],
        ['盘面初始机关', '盘面各层（map、fixGimmickMap 1–3、墙、主棋子上层）中非空格的棋子/机关计数'],
        ['开放日期', '关卡自身 ReleaseDateTime；为 2001 占位时取所属活动/CP 开始时间，常驻留空；按日本时间'],
        ['文件', f"已加载 {data['Loaded']} / {data['Expected']}；缺失见 puzzle_stages.json 的 Issues"],
    ]})
    return write_workbook(xlsx_path('puzzle_stages.xlsx'), sheets)


def run(session=None, *, source=None):
    data = extract(session, source=source)
    save_json(data, audit_path('puzzle_stages.json'))
    if data['Loaded'] < data['Expected']:
        record_warning(f"消消乐关卡文件 {data['Expected'] - data['Loaded']} 个缺失或无法解析，详见 puzzle_stages.json")
    return export(data)
