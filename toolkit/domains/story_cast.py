"""剧情分话出场表：结合 masterdata 与 .s2bscript 剧本，精确统计每篇与每话的出场人物。

核心口径（V3）：
- 不做别名归并，严格保留剧本原样署名（仅去除已知角色名内部空白，外文/组合署名原样保留）；
- 保留全部 NPC，仅剔除玩家占位符（<Self...>）与纯标点/纯数字脏署名；
- 精确到每一话：输出《剧情总表》《分话出场表》《分话角色明细》《说明》四张工作表；
- 主线含拼图关的章节（mst_puzzle_story_stage）优先读取完整重读脚本（RereadStoryFileName）；
- Prequel 全语音重读入口不重复计入台词数；
- 未公开占位（如个人故事第 2~5 话 3001-01-01）在源头标为「未公开」，不报缺失异常。
"""
from collections import Counter, defaultdict, deque
from datetime import datetime
import lzma
from pathlib import Path
import re
import tempfile

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import range_boundaries

from ..core.exporter import audit_path, xlsx_path, save_workbook_safely
from ..core.output import record_warning
from ..core.s2b_parser import parse_s2b_file
from ..core.scanner import save_json
from .story_catalog import extract as extract_catalog

SCRIPT_DIR = 'Scripts/'
SUFFIX = '.s2bscript'

PLACEHOLDER_PREFIXES = ('2001-', '3001-', '9999-')
LAUNCH_DATE = '2024-05-09'
LAUNCH_CARD_MAX_ID = 63
GARBAGE_SPEAKERS = frozenset({'・', '2'})
TYPE_SORT_ORDER = {'主线': 1, '活动': 2, '个人': 3, '卡牌': 4, '其他': 5}
BANNER_PREFIXES = ('Prequel', 'Travelogue')
EVENT_CARD_TABLES = ('mst_event_a', 'mst_event_b', 'mst_event_c', 'mst_event_accumulate_item')
EVENT_CARD_FIELDS = ('CharacterCardIds', 'PickUpCharacterCardIds', 'PickUpCharacterCardId')
ANNIVERSARY_CARD_SERIES = {
    "Here's to Aporia!": '1st Anniversary',
    'what-if': '2nd Anniversary',
}
BIRTHDAY_SERIES_RULES = (
    (re.compile(r'^#[0-9a-f]{6}$', re.I), '一轮生日'),
    (re.compile(r'\bspecial\s+day\b', re.I), '二轮生日'),
    (re.compile(r'^Present\s+for\b', re.I), '三轮生日'),
)


def card_series(title):
    for pattern, label in BIRTHDAY_SERIES_RULES:
        if pattern.search(title or ''):
            return label
    return ANNIVERSARY_CARD_SERIES.get(title or '', '')


def card_relation(event, card_date, has_earlier):
    title = event.get('EventTitle') or ''
    if 'anniversary' not in title.casefold():
        return '活动关联' if has_earlier else '首发活动候选'
    opening = (event.get('OpenStartTime') or event.get('StartTime') or '')[:10]
    if has_earlier or (opening and card_date and card_date < opening):
        return '复刻/精选'
    if opening and card_date == opening:
        return '首发活动候选'
    return '周年关联待定'


def normalize_speaker(raw_name, known_characters):
    """Return (display_name, character_id, is_playable) or None if dropped."""
    text = str(raw_name or '').strip()
    if not text or '<Self' in text or text in GARBAGE_SPEAKERS:
        return None
    compact = re.sub(r'[\s\u3000]+', '', text)
    if not compact or compact in GARBAGE_SPEAKERS:
        return None
    if compact in known_characters:
        cid, canonical, is_playable = known_characters[compact]
        return canonical, cid, is_playable
    # Keep ASCII/foreign names with internal spaces intact; strip spaces inside CJK names.
    display = compact if (' ' not in text or any(ord(ch) > 127 for ch in text)) else text
    return display, None, False


def _puzzle_reread_map(tables):
    mapping = {}
    for row in tables.rows('mst_puzzle_story_stage', active_only=True):
        if row.get('StoryTypeCode') != 1:
            continue
        reread = (row.get('RereadStoryFileName') or '').strip()
        if reread:
            key = (row.get('StoryTargetBaseId'), row.get('StoryTargetChapterId'), row.get('StoryTargetSectionNo'))
            mapping[key] = reread
    return mapping


def _episode_script_stem(section, cards, puzzle_rereads):
    table, key = section['SourceTable'], section['Key']
    if table == 'mst_main_story_section':
        return puzzle_rereads.get(tuple(key)) or f'main_{key[0]}_{key[1]}_{key[2]}'
    if table == 'mst_event_story_section':
        return f'event_{key[0]}_{key[1]}'
    if table == 'mst_character_card_story_section':
        card = cards.get(key[0])
        if not card or card.get('CharacterId') is None:
            return None
        return f"card_{key[0]}_{card['CharacterId']}_{key[1]}"
    if table == 'mst_character_story_section':
        return f'personal_{key[1]}_{key[0]}_{key[2]}'
    if table == 'mst_campaign_story_section':
        return f'campaign_{key[0]}_{key[1]}'
    if table == 'mst_login_story_section':
        return f'login_{key[0]}_{key[1]}'
    return None


def resource_keys(tables):
    """Script keys for all active story episodes (preferring unified puzzle reread scripts)."""
    cards = tables.by_id('mst_character_card', 'CharacterCardId', required=False)
    puzzle_rereads = _puzzle_reread_map(tables)
    keys = set()
    for row in tables.rows('mst_main_story_section', active_only=True):
        k = (row.get('MainStoryThreadNo'), row.get('MainStoryChapterNo'), row.get('MainStorySectionNo'))
        if None not in k:
            stem = puzzle_rereads.get(k) or f'main_{k[0]}_{k[1]}_{k[2]}'
            keys.add(f'{SCRIPT_DIR}{stem}{SUFFIX}')
    for row in tables.rows('mst_event_story_section', active_only=True):
        k = (row.get('EventId'), row.get('EventStorySectionNo'))
        if None not in k:
            keys.add(f'{SCRIPT_DIR}event_{k[0]}_{k[1]}{SUFFIX}')
    for row in tables.rows('mst_character_card_story_section', active_only=True):
        cid_card, sec = row.get('CharacterCardId'), row.get('CharacterCardStorySectionNo')
        card = cards.get(cid_card)
        if cid_card is not None and sec is not None and card and card.get('CharacterId') is not None:
            keys.add(f"{SCRIPT_DIR}card_{cid_card}_{card['CharacterId']}_{sec}{SUFFIX}")
    for row in tables.rows('mst_character_story_section', active_only=True):
        k = (row.get('CharacterStoryChapterNo'), row.get('CharacterId'), row.get('CharacterStorySectionNo'))
        if None not in k:
            keys.add(f'{SCRIPT_DIR}personal_{k[0]}_{k[1]}_{k[2]}{SUFFIX}')
    for row in tables.rows('mst_campaign_story_section', active_only=True):
        k = (row.get('CampaignId'), row.get('CampaignStorySectionNo'))
        if None not in k:
            keys.add(f'{SCRIPT_DIR}campaign_{k[0]}_{k[1]}{SUFFIX}')
    for row in tables.rows('mst_login_story_section', active_only=True):
        k = (row.get('LoginStoryId'), row.get('LoginStorySectionNo'))
        if None not in k:
            keys.add(f'{SCRIPT_DIR}login_{k[0]}_{k[1]}{SUFFIX}')
    return sorted(keys)


def _index_sources(source):
    files = {}
    for entry in source if isinstance(source, list) else [source] if source else []:
        path = Path(entry)
        for file in ([path] if path.is_file() else sorted(path.rglob('*' + SUFFIX)) if path.is_dir() else []):
            files.setdefault(file.name, file)
    return files


def _load_script(path):
    raw = Path(path).read_bytes()
    if raw.startswith(b'\x5d'):
        data = raw
        layers = 0
        while data.startswith(b'\x5d') and layers < 2:
            decoder = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE, memlimit=256 * 1024 * 1024)
            data = decoder.decompress(data, max_length=64 * 1024 * 1024 + 1)
            layers += 1
        with tempfile.NamedTemporaryFile(suffix='.s2bscript', delete=False) as stream:
            tmp = Path(stream.name)
            stream.write(data)
        try:
            return parse_s2b_file(tmp, strict_extensions=True)
        finally:
            tmp.unlink(missing_ok=True)
    return parse_s2b_file(path, strict_extensions=True)


def extract_script_speakers(script):
    """Count Chat.Show speakers across all reachable commands (covering Selection branches)."""
    if not script:
        return Counter(), {}
    root = script[0]
    commands = root[0] if root and isinstance(root[0], list) and root[0] and isinstance(root[0][0], list) else root
    if not commands or not isinstance(commands, list):
        return Counter(), {}
    by_id = {cmd[0]: cmd for cmd in commands if isinstance(cmd, list) and cmd}
    start = commands[0][0]
    queue = deque([start])
    visited = {start}
    counts = Counter()
    first_pos = {}
    step = 0
    while queue:
        cid = queue.popleft()
        cmd = by_id.get(cid)
        if not cmd:
            continue
        step += 1
        if len(cmd) >= 5 and cmd[2] == 'Chat' and cmd[3] == 'Show' and isinstance(cmd[4], dict):
            speaker = str(cmd[4].get('chatTitle') or '').strip()
            if speaker:
                counts[speaker] += 1
                first_pos.setdefault(speaker, step)
        if len(cmd) >= 2 and isinstance(cmd[1], list):
            for nxt in cmd[1]:
                if nxt != -1 and nxt not in visited and nxt in by_id:
                    visited.add(nxt)
                    queue.append(nxt)
    return counts, first_pos


def _valid_date(value):
    text = str(value or '').strip()
    if not text or text.startswith(PLACEHOLDER_PREFIXES):
        return ''
    return text[:10]


def _earliest_gacha_dates(tables):
    """Map CharacterCardId -> earliest valid mst_gacha.StartTime[:10] from masterdata."""
    gacha_by_id = tables.by_id('mst_gacha', 'GachaId', required=False)
    if not gacha_by_id:
        return {}
    lot_to_gachas = defaultdict(set)
    for btn in tables.rows('mst_gacha_button', active_only=True):
        gid = btn.get('GachaId')
        if gid is None:
            continue
        for field in ('GachaLotteryGroupId', 'FixedGachaLotteryGroupId'):
            if btn.get(field):
                lot_to_gachas[btn[field]].add(gid)
    rg_to_gachas = defaultdict(set)
    for lot in tables.rows('mst_gacha_lottery', active_only=True):
        rg = lot.get('GachaReturnGroupId')
        if rg is None:
            continue
        for gid in lot_to_gachas.get(lot.get('GachaLotteryGroupId'), ()):
            rg_to_gachas[rg].add(gid)
    earliest = {}
    for ret in tables.rows('mst_gacha_return', active_only=True):
        cid = ret.get('CharacterCardId')
        if cid is None:
            continue
        for gid in rg_to_gachas.get(ret.get('GachaReturnGroupId'), ()):
            dt = _valid_date(gacha_by_id.get(gid, {}).get('StartTime'))
            if dt and (cid not in earliest or dt < earliest[cid]):
                earliest[cid] = dt
    return earliest


def _numeric_id_parts(story_id):
    return tuple(int(part) if part.isdigit() else 0 for part in str(story_id).split('-')[1:])


def story_sort_key(story):
    """Natural display order per top-level category (never string-sorting numeric IDs)."""
    stype = story['type']
    sid = story['story_id']
    nums = _numeric_id_parts(sid)
    date_str = str(story.get('release_date') or '')[:10]
    t_rank = TYPE_SORT_ORDER.get(stype, 99)
    if stype == '主线':
        return (t_rank, 0, '', nums, sid)
    if stype == '个人':
        return (t_rank, 0, '', nums, sid)
    if stype == '活动':
        return (t_rank, 0 if date_str else 1, date_str or '9999-99-99', nums, sid)
    if stype == '卡牌':
        return (t_rank, 0 if date_str else 1, date_str or '9999-99-99', nums, sid)
    kind_rank = 0 if sid.startswith('campaign-') else 1
    return (t_rank, 0 if date_str else 1, date_str or '9999-99-99', (kind_rank, *nums), sid)


def extract(session, source=None, *, as_of=None):
    tables = session.tables
    catalog = extract_catalog(session, as_of=as_of)
    files = _index_sources(source)

    cards = tables.by_id('mst_character_card', 'CharacterCardId', required=False)
    people = tables.by_id('mst_character', 'CharacterId', required=False)
    events = tables.by_id('mst_event', 'EventId', required=False)
    threads = tables.by_id('mst_main_story', 'MainStoryThreadNo', required=False)
    puzzle_rereads = _puzzle_reread_map(tables)

    known_characters = {}
    char_id_to_name = {}
    for cid, row in people.items():
        canonical = re.sub(r'[\s\u3000]+', '', str(row.get('CharacterNameJpn') or ''))
        if not canonical:
            continue
        group_code = row.get('CharacterGroupCode')
        is_playable = (group_code != 99) if group_code is not None else (cid <= 21)
        known_characters[canonical] = (cid, canonical, is_playable)
        char_id_to_name[cid] = canonical

    labels = {'main': '主线', 'character': '个人', 'event': '活动', 'card': '卡牌', 'campaign': '其他', 'login': '其他'}
    stories = {}
    episodes = []
    episodes_by_story = defaultdict(list)

    for section in catalog['Sections']:
        kind, key, raw = section['Kind'], section['Key'], section['Raw']
        table = section['SourceTable']
        if kind == 'puzzle' or 'from_other_story_type' in table:
            continue
        parent = next(iter(section['Parents']), {})
        first = key[0]
        sid = '-'.join([kind, *map(str, key[:-1])])
        eid = f'{sid}-{key[-1]}'
        owner_id = first if kind == 'character' else cards.get(first, {}).get('CharacterId') if kind == 'card' else None
        series = ''
        title = parent.get('TitleName') or ''
        event = events.get(first, {}) if kind == 'event' else {}
        raw_date = raw.get('ReleaseDateTime') or raw.get('StartTime') or parent.get('ReleaseDateTime') or ''

        if kind == 'main':
            thread = threads.get(first, {})
            t_name = thread.get('TitleName') or str(first)
            series = ('Interlude ' if thread.get('MainStoryTypeCode') == 2 else 'Thread ') + t_name
            title = title or series
        elif kind == 'card':
            card = cards.get(first, {})
            title = card.get('CharacterCardName') or f'Card {first}'
            raw_date = raw_date or card.get('ReleaseDateTime') or ''
        elif kind == 'character' and not title:
            title = f"{char_id_to_name.get(first, f'角色{first}')} / 第{key[1]}章"
        elif kind == 'event':
            title = event.get('EventTitle') or f'活动{first}'
            series = next((word for word in ('Prequel', 'Travelogue', 'Vignette')
                           if title.casefold().startswith(word.casefold())), '')
        elif kind == 'campaign':
            title = parent.get('CampaignTitle') or f'纪念活动{first}'
        elif kind == 'login':
            title = re.sub(r'\s*\[\d+日目\]$', '', section['Title'] or '') or f'登录剧情{first}'

        if sid not in stories:
            stories[sid] = {
                'story_id': sid,
                'kind': kind,
                'type': labels[kind],
                'jp_title': title,
                'series': series,
                'owner_id': owner_id,
                'owner_name': char_id_to_name.get(owner_id, '') if owner_id is not None else '',
                'event_id': first if kind == 'event' else None,
                'card_id': first if kind == 'card' else None,
                'release_date': '',
                'date_basis': '',
                'banner': False,
            }

        stem = _episode_script_stem(section, cards, puzzle_rereads)
        ep = {
            'story_id': sid,
            'episode_id': eid,
            'seq': int(key[-1]),
            'ep_title': (section['Title'] or f'第{key[-1]}話').strip(),
            'raw_date': raw_date,
            'availability': section['Availability']['Status'],
            'script_file': f'{stem}{SUFFIX}' if stem else None,
            'used_puzzle_reread': table == 'mst_main_story_section' and tuple(key) in puzzle_rereads,
        }
        episodes.append(ep)
        episodes_by_story[sid].append(ep)

    # Mark Prequel via CrossStoryLinks as well
    for link in catalog.get('CrossStoryLinks', []):
        if 'from_other_story_type' in link['SourceTable'] and link['Status'] == 'resolved' and link.get('TargetKey'):
            target_sid = f"event-{link['TargetKey'][0]}"
            if target_sid in stories:
                stories[target_sid]['series'] = 'Prequel'

    # Event-card links (strip rerun/pickup so origin event stays clean)
    memberships = defaultdict(set)
    for table_name in EVENT_CARD_TABLES:
        for row in tables.rows(table_name, active_only=True):
            eid = row.get('EventId')
            if eid not in events:
                continue
            for field in EVENT_CARD_FIELDS:
                values = row.get(field) or []
                for number in (values if isinstance(values, list) else [values]):
                    sid = f'card-{number}'
                    if sid in stories:
                        memberships[sid].add(eid)

    origins = defaultdict(set)
    for sid, ev_ids in memberships.items():
        card_id = stories[sid]['card_id']
        release = _valid_date(cards.get(card_id, {}).get('ReleaseDateTime'))
        for eid in ev_ids:
            ev = events[eid]
            start = ev.get('OpenStartTime') or ev.get('StartTime') or ''
            earlier = any(
                (other_start := events[other].get('OpenStartTime') or events[other].get('StartTime'))
                and other_start < start
                for other in ev_ids
            )
            if card_relation(ev, release, earlier) == '首发活动候选':
                origins[sid].add(eid)

    # Classify stories & resolve release dates (including launch-day 2024-05-09 & gacha fallback)
    gacha_dates = _earliest_gacha_dates(tables)
    for sid, story in stories.items():
        eps = episodes_by_story[sid]
        valid_dates = sorted(d for ep in eps if (d := _valid_date(ep['raw_date'])))
        has_launch_sentinel = any(str(ep['raw_date'] or '').startswith('2001-') for ep in eps)
        if valid_dates:
            story['release_date'] = valid_dates[0]
            story['date_basis'] = '原表'
        original_type = story['type']
        if original_type == '卡牌':
            card_id = story['card_id']
            card_raw_date = str(cards.get(card_id, {}).get('ReleaseDateTime') or '')
            story['series'] = card_series(story['jp_title'])
            if card_id is not None and card_id <= LAUNCH_CARD_MAX_ID and not story['release_date'] and (has_launch_sentinel or card_raw_date.startswith('2001-')):
                story['series'] = story['series'] or '初始常驻'
                story['release_date'] = LAUNCH_DATE
                story['date_basis'] = '开服日（2024-05-09）'
            elif len(origins[sid]) == 1:
                ev_id = next(iter(origins[sid]))
                ev = events[ev_id]
                story['event_id'] = ev_id
                story['series'] = story['series'] or (ev.get('EventTitle') or '')
                if not story['release_date']:
                    inherited = _valid_date(ev.get('OpenStartTime') or ev.get('StartTime'))
                    if inherited:
                        story['release_date'] = inherited
                        story['date_basis'] = '关联活动开放日（推定）'
            if not story['release_date'] and card_id in gacha_dates:
                story['release_date'] = gacha_dates[card_id]
                story['date_basis'] = '卡池开放日（mst_gacha）'
        elif original_type in ('活动', '其他') and 'anniversary' in story['jp_title'].casefold():
            story['series'] = '周年活动'
        elif original_type == '活动' and story['series'] in BANNER_PREFIXES:
            story['banner'] = True
            story['series'] = f"部门箱活（banner） / {story['series']}"
        elif original_type in ('主线', '个人') and not story['release_date'] and has_launch_sentinel:
            story['release_date'] = LAUNCH_DATE
            story['date_basis'] = '开服日（2024-05-09）'

    ordered_stories = sorted(stories.values(), key=story_sort_key)
    story_order = {s['story_id']: idx for idx, s in enumerate(ordered_stories)}
    episodes.sort(key=lambda ep: (story_order.get(ep['story_id'], 999999), ep['seq']))

    # Parse scripts and accumulate per-episode & per-story cast
    story_speakers = defaultdict(lambda: defaultdict(lambda: {'lines': 0, 'is_playable': False, 'episodes': set()}))
    episode_results = []
    cast_rows = []
    issues = []
    loaded = 0
    unreleased = 0

    for ep in episodes:
        sid = ep['story_id']
        eid = ep['episode_id']
        story = stories[sid]
        script_name = ep['script_file']
        path = files.get(script_name) if script_name else None
        is_unreleased = ep['availability'] in ('unreleased_placeholder', 'upcoming')

        ep_counts = defaultdict(lambda: {'lines': 0, 'is_playable': False, 'character_id': None})
        status = '待复核'

        if path is None:
            if is_unreleased:
                status = '未公开'
                unreleased += 1
            else:
                issues.append({
                    'Status': 'missing_script_file',
                    'StoryId': sid,
                    'EpisodeId': eid,
                    'File': script_name,
                    'Availability': ep['availability'],
                })
        else:
            try:
                parsed = _load_script(path)
                raw_counts, _ = extract_script_speakers(parsed)
                loaded += 1
                for raw_speaker, count in raw_counts.items():
                    normalized = normalize_speaker(raw_speaker, known_characters)
                    if normalized is None:
                        continue
                    display, cid, is_playable = normalized
                    bucket = ep_counts[display]
                    bucket['lines'] += count
                    if is_playable:
                        bucket['is_playable'] = True
                    if cid is not None:
                        bucket['character_id'] = cid
                if ep_counts:
                    status = '已解析'
                else:
                    status = '待复核'
                    issues.append({
                        'Status': 'no_named_speakers',
                        'StoryId': sid,
                        'EpisodeId': eid,
                        'File': script_name,
                    })
            except Exception as error:
                issues.append({
                    'Status': 'undecodable_script_file',
                    'StoryId': sid,
                    'EpisodeId': eid,
                    'File': script_name,
                    'Error': str(error),
                })

        sorted_ep = sorted(
            ep_counts.items(),
            key=lambda kv: (-kv[1]['lines'], 0 if kv[1]['is_playable'] else 1, kv[0]),
        )
        for name, info in sorted_ep:
            s_bucket = story_speakers[sid][name]
            s_bucket['lines'] += info['lines']
            s_bucket['episodes'].add(eid)
            if info['is_playable']:
                s_bucket['is_playable'] = True
            cast_rows.append({
                'type': story['type'],
                'jp_title': story['jp_title'],
                'seq': ep['seq'],
                'ep_title': ep['ep_title'],
                'speaker': name,
                'category': '主要角色' if info['is_playable'] else 'NPC',
                'lines': info['lines'],
                'story_id': sid,
                'episode_id': eid,
            })

        episode_results.append({
            'type': story['type'],
            'jp_title': story['jp_title'],
            'seq': ep['seq'],
            'ep_title': ep['ep_title'],
            'speakers': [
                {'name': name, 'category': '主要角色' if info['is_playable'] else 'NPC', 'lines': info['lines']}
                for name, info in sorted_ep
            ],
            'speaker_text': '、'.join(name for name, _ in sorted_ep),
            'speaker_count': len(sorted_ep),
            'status': status,
            'story_id': sid,
            'episode_id': eid,
            'script_file': script_name,
            'used_puzzle_reread': ep['used_puzzle_reread'],
        })

    ep_status_by_story = defaultdict(Counter)
    for ep in episode_results:
        ep_status_by_story[ep['story_id']][ep['status']] += 1

    story_results = []
    for story in ordered_stories:
        sid = story['story_id']
        cmap = story_speakers.get(sid, {})
        sorted_chars = sorted(
            cmap.items(),
            key=lambda kv: (-kv[1]['lines'], 0 if kv[1]['is_playable'] else 1, kv[0]),
        )
        ep_total = len(episodes_by_story[sid])
        parsed_count = ep_status_by_story[sid]['已解析']
        story_results.append({
            **story,
            'episode_count': ep_total,
            'parsed_episodes': parsed_count,
            'unreleased_episodes': ep_status_by_story[sid]['未公开'],
            'speakers_all': [name for name, _ in sorted_chars],
            'speaker_text': '、'.join(name for name, _ in sorted_chars),
        })

    return {
        'Stories': story_results,
        'Episodes': episode_results,
        'CastRows': cast_rows,
        'Issues': issues,
        'Loaded': loaded,
        'Expected': len(episodes) - unreleased,
        'TotalEpisodes': len(episodes),
        'Unreleased': unreleased,
        'AsOf': catalog['AsOf'],
    }


def _display_width(text):
    return sum(1.85 if ord(ch) > 127 else 1.0 for ch in str(text or ''))


def _style_merged(ws, cell_range, *, font=None, fill=None, alignment=None, border=None):
    min_col, min_row, max_col, max_row = range_boundaries(cell_range)
    for row in ws.iter_rows(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col):
        for cell in row:
            if font:
                cell.font = font
            if fill:
                cell.fill = fill
            if alignment:
                cell.alignment = alignment
            if border:
                cell.border = border


def export(data):
    wb = Workbook()

    navy = '1F4E79'
    banner_bg = '163A59'
    alt_bg = 'F4F7FA'
    border_clr = 'D6DEE6'
    muted_clr = '6B7A8C'
    font_name = 'Microsoft YaHei'

    thin = Side(style='thin', color=border_clr)
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    f_banner = Font(name=font_name, size=12, bold=True, color='FFFFFF')
    f_header = Font(name=font_name, size=10, bold=True, color='FFFFFF')
    f_body = Font(name=font_name, size=10, color='1E293B')
    f_muted = Font(name=font_name, size=9, color=muted_clr)
    fill_banner = PatternFill('solid', fgColor=banner_bg)
    fill_navy = PatternFill('solid', fgColor=navy)
    fill_alt = PatternFill('solid', fgColor=alt_bg)

    # ── Sheet 1: 剧情总表 ──
    ws1 = wb.active
    ws1.title = '剧情总表'
    ws1.merge_cells('A1:I1')
    ws1['A1'] = 'Break My Case 剧情分话出场总表  ｜  不做别名归并、保留全部 NPC；主线拼图关自动取完整重读脚本'
    _style_merged(ws1, 'A1:I1', font=f_banner, fill=fill_banner,
                  alignment=Alignment(horizontal='left', vertical='center', indent=1))
    ws1.row_dimensions[1].height = 28

    headers_1 = ['类型', '系列 / 关联活动', '日文标题', '归属角色', '实装日期', '话数', '已解析话数',
                 '出场人物（含全部NPC·原样署名）', '剧情ID']
    ws1.row_dimensions[2].height = 24
    for col_idx, text in enumerate(headers_1, 1):
        c = ws1.cell(2, col_idx, text)
        c.font = f_header
        c.fill = fill_navy
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border = border

    for r_idx, story in enumerate(data['Stories'], start=3):
        dt = datetime.fromisoformat(story['release_date']).date() if story['release_date'] else None
        vals = [
            story['type'],
            story['series'] or None,
            story['jp_title'],
            story['owner_name'] or None,
            dt,
            story['episode_count'],
            story['parsed_episodes'],
            story['speaker_text'] or None,
            story['story_id'],
        ]
        is_alt = r_idx % 2 == 0
        for col_idx, val in enumerate(vals, 1):
            c = ws1.cell(r_idx, col_idx, val)
            c.border = border
            c.font = f_muted if col_idx == 9 else f_body
            if is_alt:
                c.fill = fill_alt
            if col_idx in (1, 4, 5):
                c.alignment = Alignment(horizontal='center', vertical='center')
            elif col_idx in (6, 7):
                c.alignment = Alignment(horizontal='right', vertical='center')
                c.number_format = '#,##0'
            elif col_idx == 8:
                c.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
            else:
                c.alignment = Alignment(horizontal='left', vertical='center')
            if col_idx == 5 and val is not None:
                c.number_format = 'YYYY-MM-DD'
        lines = max(1, int(_display_width(story['speaker_text']) / 44) + 1) if story['speaker_text'] else 1
        ws1.row_dimensions[r_idx].height = max(21, min(lines * 17 + 8, 110))

    ws1.freeze_panes = 'A3'
    ws1.auto_filter.ref = f'A2:I{max(2, ws1.max_row)}'
    for col_idx, width in {1: 11, 2: 30, 3: 32, 4: 12, 5: 13, 6: 8, 7: 11, 8: 50, 9: 15}.items():
        ws1.column_dimensions[get_column_letter(col_idx)].width = width

    # ── Sheet 2: 分话出场表 ──
    ws2 = wb.create_sheet('分话出场表')
    ws2.merge_cells('A1:I1')
    ws2['A1'] = '分话出场表（精确到每一话）  ｜  不做别名归并、保留全部 NPC；未实装占位标记为「未公开」'
    _style_merged(ws2, 'A1:I1', font=f_banner, fill=fill_banner,
                  alignment=Alignment(horizontal='left', vertical='center', indent=1))
    ws2.row_dimensions[1].height = 28

    headers_2 = ['类型', '剧情标题', '话序', '本话标题', '本话出场人物（含全部NPC）', '出场人数', '本话状态', '剧情ID', '话ID']
    ws2.row_dimensions[2].height = 24
    for col_idx, text in enumerate(headers_2, 1):
        c = ws2.cell(2, col_idx, text)
        c.font = f_header
        c.fill = fill_navy
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border = border

    for r_idx, ep in enumerate(data['Episodes'], start=3):
        vals = [
            ep['type'],
            ep['jp_title'],
            ep['seq'],
            ep['ep_title'],
            ep['speaker_text'] or None,
            ep['speaker_count'],
            ep['status'],
            ep['story_id'],
            ep['episode_id'],
        ]
        is_alt = r_idx % 2 == 0
        for col_idx, val in enumerate(vals, 1):
            c = ws2.cell(r_idx, col_idx, val)
            c.border = border
            c.font = f_muted if col_idx in (8, 9) else f_body
            if is_alt:
                c.fill = fill_alt
            if col_idx in (1, 7):
                c.alignment = Alignment(horizontal='center', vertical='center')
            elif col_idx in (3, 6):
                c.alignment = Alignment(horizontal='right', vertical='center')
                c.number_format = '#,##0'
            elif col_idx == 5:
                c.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
            else:
                c.alignment = Alignment(horizontal='left', vertical='center')
        lines = max(1, int(_display_width(ep['speaker_text']) / 46) + 1) if ep['speaker_text'] else 1
        ws2.row_dimensions[r_idx].height = max(21, min(lines * 17 + 8, 96))

    ws2.freeze_panes = 'A3'
    last_ep = max(2, ws2.max_row)
    ws2.auto_filter.ref = f'A2:I{last_ep}'
    if last_ep >= 3:
        stat_rng = f'G3:G{last_ep}'
        ws2.conditional_formatting.add(
            stat_rng,
            CellIsRule(operator='equal', formula=['"已解析"'],
                       fill=PatternFill('solid', fgColor='D1E7DD'),
                       font=Font(name=font_name, size=10, color='0F5132')),
        )
        ws2.conditional_formatting.add(
            stat_rng,
            CellIsRule(operator='equal', formula=['"未公开"'],
                       fill=PatternFill('solid', fgColor='E2E8F0'),
                       font=Font(name=font_name, size=10, color='475569')),
        )
        ws2.conditional_formatting.add(
            stat_rng,
            CellIsRule(operator='equal', formula=['"待复核"'],
                       fill=PatternFill('solid', fgColor='F8D7DA'),
                       font=Font(name=font_name, size=10, bold=True, color='842029')),
        )
    for col_idx, width in {1: 11, 2: 32, 3: 8, 4: 26, 5: 52, 6: 10, 7: 11, 8: 15, 9: 18}.items():
        ws2.column_dimensions[get_column_letter(col_idx)].width = width

    # ── Sheet 3: 分话角色明细 ──
    ws3 = wb.create_sheet('分话角色明细')
    ws3.merge_cells('A1:I1')
    ws3['A1'] = '分话角色明细  ｜  1 行 = 1 话 × 1 人物，按台词数降序，方便按角色反查精确到话的出场位置'
    _style_merged(ws3, 'A1:I1', font=f_banner, fill=fill_banner,
                  alignment=Alignment(horizontal='left', vertical='center', indent=1))
    ws3.row_dimensions[1].height = 28

    headers_3 = ['类型', '剧情标题', '话序', '本话标题', '剧本署名', '身份分类', '台词数', '剧情ID', '话ID']
    ws3.row_dimensions[2].height = 24
    for col_idx, text in enumerate(headers_3, 1):
        c = ws3.cell(2, col_idx, text)
        c.font = f_header
        c.fill = fill_navy
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border = border

    for r_idx, row in enumerate(data['CastRows'], start=3):
        vals = [
            row['type'],
            row['jp_title'],
            row['seq'],
            row['ep_title'],
            row['speaker'],
            row['category'],
            row['lines'],
            row['story_id'],
            row['episode_id'],
        ]
        is_alt = r_idx % 2 == 0
        for col_idx, val in enumerate(vals, 1):
            c = ws3.cell(r_idx, col_idx, val)
            c.border = border
            c.font = f_muted if col_idx in (8, 9) else f_body
            if is_alt:
                c.fill = fill_alt
            if col_idx in (1, 6):
                c.alignment = Alignment(horizontal='center', vertical='center')
            elif col_idx in (3, 7):
                c.alignment = Alignment(horizontal='right', vertical='center')
                c.number_format = '#,##0'
            else:
                c.alignment = Alignment(horizontal='left', vertical='center')
        ws3.row_dimensions[r_idx].height = 20

    ws3.freeze_panes = 'A3'
    ws3.auto_filter.ref = f'A2:I{max(2, ws3.max_row)}'
    for col_idx, width in {1: 11, 2: 32, 3: 8, 4: 24, 5: 20, 6: 11, 7: 10, 8: 15, 9: 18}.items():
        ws3.column_dimensions[get_column_letter(col_idx)].width = width

    # ── Sheet 4: 说明 ──
    ws4 = wb.create_sheet('说明')
    ws4.append(['项目', '说明'])
    for c in ws4[1]:
        c.font = f_header
        c.fill = fill_navy
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border = border
    notes = [
        ['核对时刻 UTC', data['AsOf']],
        ['总计', f"共 {len(data['Stories'])} 篇剧情、{data['TotalEpisodes']} 话：已解析 {data['Loaded']} 话，未公开 {data['Unreleased']} 话，待复核 {len(data['Issues'])} 话"],
        ['署名口径', '严格保留剧本原样署名，不做别名归并；仅剔除玩家占位符及纯标点脏署名，全部 NPC 原样保留'],
        ['身份分类', '主要角色（21 位 Aporia 成员）与 NPC（含配角与路人署名）分列，按台词数降序'],
        ['分类口径', '大分类统一为「主线 / 活动 / 个人 / 卡牌 / 其他」；周年活动归入「活动」并在系列标「周年活动」，Prequel / Travelogue 归入「活动 → 部门箱活（banner）」，全语音重读不重复计数；初始常驻卡与开服主线/个人故事补齐开服日 2024-05-09'],
        ['排序规则', '主线按部/章顺序，个人按官方角色编号（1–21），活动与卡牌按实装日期+数值ID正序，不再因开服占位或字符串字典序错位'],
        ['主线拼图关', '含剧情内拼图关的主线话优先读取完整重读脚本（RereadStoryFileName），避免截断拼图后半段对话'],
        ['分支台词', '沿剧情命令图广度遍历全部可达分支，不遗漏选项分支内的出场角色'],
    ]
    for r_idx, row in enumerate(notes, start=2):
        for col_idx, val in enumerate(row, 1):
            c = ws4.cell(r_idx, col_idx, val)
            c.font = f_body
            c.border = border
            c.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
        ws4.row_dimensions[r_idx].height = 22
    ws4.freeze_panes = 'A2'
    ws4.column_dimensions['A'].width = 16
    ws4.column_dimensions['B'].width = 88

    for sheet in wb:
        sheet.page_setup.orientation = 'landscape'
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0

    return save_workbook_safely(wb, xlsx_path('story_cast.xlsx'))


def run(session=None, *, source=None, as_of=None):
    data = extract(session, source=source, as_of=as_of)
    save_json(data, audit_path('story_cast.json'))
    if data['Issues']:
        record_warning(f"剧情分话出场有 {len(data['Issues'])} 话待复核（缺脚本或无署名台词），详见 story_cast.json")
    return export(data)
