"""Campaign page lines and ordered Shuffle Talk, joined by speaker and cue."""
from collections import Counter, defaultdict
from pathlib import Path
import hashlib

from ..core.availability import assessment_time, date_window, STATUS_LABELS
from ..core.exporter import audit_path, xlsx_path, write_workbook
from ..core.output import record_warning
from ..core.scanner import save_json
from .audio import extract_text_metadata, text_to_html
from .event_common import Names, jst
from .home_voices import CHARACTER_ACB_STEMS


def references(tables):
    talks = tables.by_id('mst_shuffle_talk', 'ShuffleTalkId', required=False)
    rows = []
    for raw in tables.rows('mst_campaign_character_voice', active_only=True):
        rows.append({'Kind': 'page', 'CampaignId': raw.get('CampaignId'), 'Raw': raw})
    for raw in tables.rows('mst_shuffle_talk_sequence', active_only=True):
        talk = talks.get(raw.get('ShuffleTalkId'), {})
        rows.append({'Kind': 'talk', 'CampaignId': talk.get('CampaignId'), 'Raw': raw,
                     'Talk': talk})
    return rows


def package_names(character_id, cue):
    stem = CHARACTER_ACB_STEMS.get(character_id)
    if not stem or not cue:
        return []
    if cue.startswith('vo_campaign_'):
        return [f'voice_{stem}_campaign.acb']
    if cue.startswith('vo_home_'):
        return [f'voice_{stem}_{bucket}.acb' for bucket in ('general', 1, 2, 3)]
    return []


def resource_keys(tables):
    return sorted({f'Musics/{name}' for ref in references(tables)
                   for name in package_names(ref['Raw'].get('CharacterId'), ref['Raw'].get('VoiceCueName'))})


def readable(text):
    return text_to_html(text or '').replace('<br>', '\n').strip()


def extract(tables, root, *, as_of=None):
    now = assessment_time(as_of)
    names = Names(tables)
    campaigns = tables.by_id('mst_campaign', 'CampaignId', required=False)
    files = defaultdict(list)
    for path in sorted(Path(root).rglob('*.acb')):
        files[path.name].append(path)
    packages = {}

    def load(name):
        if name not in packages:
            sources = []
            for path in files.get(name, []):
                source = {'Path': str(path.resolve())}
                try:
                    source['Sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
                    metadata, stable = extract_text_metadata(str(path))
                    source.update(Stable=stable, Metadata=metadata)
                except Exception as error:
                    source.update(Stable=False, Metadata=[], Error=str(error))
                sources.append(source)
            packages[name] = sources
        return packages[name]

    records = []
    refs = references(tables)
    identities = Counter((r['Kind'], r['CampaignId'], r['Raw'].get('ShuffleTalkId'),
                          r['Raw'].get('ShuffleTalkSequenceNo'), r['Raw'].get('CharacterId')) for r in refs)
    for ref in refs:
        raw = ref['Raw']
        cid, cue = raw.get('CharacterId'), raw.get('VoiceCueName') or ''
        campaign = campaigns.get(ref['CampaignId'], {})
        candidates = package_names(cid, cue)
        sources = [source for name in candidates for source in load(name)]
        matches = [dict(item, Path=source['Path'], Sha256=source['Sha256'])
                   for source in sources if source['Stable'] for item in source['Metadata']
                   if item.get('CueName') == cue and item.get('MatchStatus') == 'matched_by_acb_utf']
        texts = {readable(m.get('Text')) for m in matches if readable(m.get('Text'))}
        inline = readable(raw.get('Text'))
        if inline.casefold() == 'test':
            inline = ''
        reasons = []
        if not campaign:
            reasons.append('找不到所属活动')
        identity = (ref['Kind'], ref['CampaignId'], raw.get('ShuffleTalkId'),
                    raw.get('ShuffleTalkSequenceNo'), cid)
        if identities[identity] > 1:
            reasons.append('同一入口或对话序号有重复配置')
        text, source_kind = '', ''
        if len(texts) > 1 or (inline and texts and inline not in texts):
            status = '待核对'
            reasons.append('同一角色与语音标识存在不同文本')
        elif inline or texts:
            text = inline or next(iter(texts))
            source_kind = '游戏表文本' if inline else 'ACB 文本'
            status = '正常'
        elif not cue:
            status = '待核对'
            reasons.append('无语音标识且没有有效文本；占位配置不计作已确认漏文')
        elif not candidates:
            status = '待核对'
            reasons.append('尚未适配的角色或语音包类型')
        else:
            status = '缺失'
            reasons.append('缺少语音包' if not sources else '语音包中没有可用的对应台词')
        if any(not s['Stable'] for s in sources):
            reasons.append('部分语音包读取失败或不稳定')
        if reasons and status == '正常':
            status = '待核对'
        records.append({**ref, 'CampaignTitle': campaign.get('CampaignTitle') or f"活动({ref['CampaignId']})",
                        'Character': names.character(cid), 'CueName': cue, 'Text': text,
                        'TextSource': source_kind, 'Status': status, 'Note': '；'.join(reasons),
                        'Title': matches[0].get('Title', '') if matches else '',
                        'StartTime': campaign.get('StartTime'), 'EndTime': campaign.get('EndTime'),
                        'Availability': date_window(campaign.get('StartTime'), campaign.get('EndTime'),
                                                    as_of=now, active=campaign.get('IsActive', True)),
                        'Matches': matches, 'Placeholder': not cue and not inline})
    records.sort(key=lambda r: (r['CampaignId'] or 0, r['Kind'], r['Raw'].get('ShuffleTalkId', 0),
                               r['Raw'].get('ShuffleTalkSequenceNo', 0), r['Raw'].get('CharacterId', 0)))
    return {'AsOf': now.isoformat(), 'Records': records, 'Packages': packages}


def export(data):
    pages, talks, review = [], [], []
    groups = defaultdict(list)
    for r in data['Records']:
        raw = r['Raw']
        groups[r['CampaignId']].append(r)
        prefix = [r['CampaignId'], r['CampaignTitle']]
        condition = [r['StartTime'], r['EndTime'], STATUS_LABELS[r['Availability']['Status']]]
        if r['Kind'] == 'page' and not r['Placeholder']:
            pages.append(prefix + [r['Character'], r['Title'], r['Text'], '', *condition,
                                   r['CueName'], r['TextSource'], r['Status'], r['Note']])
        elif r['Kind'] == 'talk':
            talk = r['Talk']
            talks.append(prefix + [raw.get('ShuffleTalkId'), talk.get('TitleName'),
                                   raw.get('ShuffleTalkSequenceNo'), r['Character'], r['Text'], '',
                                   *condition, '是' if talk.get('IsInitialUnlocked') else '否',
                                   r['CueName'], r['Status'], r['Note']])
        if r['Status'] != '正常':
            review.append(prefix + ['活动页' if r['Kind'] == 'page' else 'Shuffle Talk',
                                    raw.get('ShuffleTalkId'), raw.get('ShuffleTalkSequenceNo'),
                                    r['Character'], r['CueName'], r['Status'], r['Note']])
    overview = []
    for eid, rows in groups.items():
        r = rows[0]
        overview.append([eid, r['CampaignTitle'], r['StartTime'], r['EndTime'],
                         STATUS_LABELS[r['Availability']['Status']],
                         sum(x['Kind'] == 'page' for x in rows), sum(x['Kind'] == 'talk' for x in rows),
                         sum(bool(x['Text']) for x in rows), sum(x['Placeholder'] for x in rows)])
    return write_workbook(xlsx_path('活动语音与对话.xlsx'), [
        {'title': '活动一览', 'headers': ['活动ID', '活动名', '开始（原值）', '结束（原值）', '日期状态',
                                       '活动页配置数', '对话台词数', '取得文本数', '占位配置数'], 'rows': overview,
         'col_widths': {'B': 40, 'C': 22, 'D': 22}},
        {'title': '活动页台词', 'headers': ['活动ID', '活动名', '角色', '语音标题', '日文台词', '中文翻译',
                                         '开始（原值）', '结束（原值）', '日期状态', '语音标识', '文本来源',
                                         '核对状态', '说明'], 'rows': pages,
         'col_widths': {'B': 35, 'C': 16, 'D': 24, 'E': 65, 'F': 50, 'J': 32, 'M': 45}, 'wrap_cols': [5, 13]},
        {'title': 'Shuffle Talk', 'headers': ['活动ID', '活动名', '对话ID', '对话标题', '顺序', '角色',
                                           '日文台词', '中文翻译', '开始（原值）', '结束（原值）', '日期状态',
                                           '初始解锁', '语音标识', '核对状态', '说明'], 'rows': talks,
         'col_widths': {'B': 35, 'D': 25, 'F': 16, 'G': 65, 'H': 50, 'M': 36, 'O': 45}, 'wrap_cols': [7, 15]},
        {'title': '待核对', 'headers': ['活动ID', '活动名', '入口', '对话ID', '顺序', '角色', '语音标识',
                                     '核对状态', '说明'], 'rows': review,
         'col_widths': {'B': 35, 'F': 16, 'G': 32, 'I': 65}, 'wrap_cols': [9]},
        {'title': '说明', 'headers': ['项目', '说明'], 'col_widths': {'A': 18, 'B': 95}, 'wrap_cols': [2], 'rows': [
            ['用途', '活动页台词与 Shuffle Talk。主页中复用的周年语音也会出现在本表；按活动入口检索，不要求每组21人。'],
            ['关联', '按角色与完整语音标识匹配 ACB；对话按 ShuffleTalkId、ShuffleTalkSequenceNo 排序。'],
            ['日期', f"核对时刻 {jst(data['AsOf'])} JST。起止列保留数据原值及偏移；日期状态按这些偏移计算，不代表已确认的游戏时区或账号解锁。"],
            ['时间口径待核对', '截图的2.5周年截止为11月17日17:59，数据EndTime为同日18:00且带+00:00。两者语义尚未统一，不直接加9小时标作JST；原始偏移不能据此当作已确认的实际开放时刻。'],
            ['初始解锁', '来自 IsInitialUnlocked；否不等于永远不可读，具体解锁任务另行判断。'],
            ['占位配置', '没有语音标识且文本为空或 test 的配置单列待核对，不猜测 Cue，也不计作已经证实丢失的台词。'],
            ['来源与冲突', '游戏表的有效文本与 ACB 原文均保留在审计 JSON；存在不同文本时留空并标待核对。'],
        ]},
    ])


def run(root, *, session, as_of=None):
    data = extract(session.tables, root, as_of=as_of)
    save_json(data, audit_path('campaign_voices.json'))
    flagged = [r for r in data['Records'] if r['Status'] != '正常']
    if flagged:
        placeholder = sum(r['Placeholder'] for r in flagged)
        record_warning(f'活动语音有 {placeholder} 条占位配置、{len(flagged) - placeholder} 条其他待核对或缺项，详见 campaign_voices.json')
    return export(data)
