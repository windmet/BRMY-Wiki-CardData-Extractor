"""Exception table for card voice cues that play more than one spoken clip.

The card workbook keeps one text per voice column. Some cards break that
model: third-round birthday cards chain one combi clip per department member
inside ``card_vo_skill_combi``, and a few cues layer several clips. Those
cards are listed here, one row per clip, instead of widening the card table.

ACB metadata stores at most one ``title:{}text:{}`` per cue, so it cannot
name the speaker or text of each clip. Candidates come from
``CharacterGroupCode`` membership; clip text stays a manual column.
"""
import os
import re
import shutil
import subprocess
from collections import defaultdict

from ..core.cri_utf import CriUtfError, extract_acb_cue_clips, read_memory_awb
from ..core.exporter import audit_path, xlsx_path, write_xlsx
from ..core.output import record_output, record_warning
from ..core.scanner import save_json
from .audio import CARD_FILE_RE, _read_stable_bytes, _walk_source_files

COMBI_CUE = 'card_vo_skill_combi'
NON_STAFF_GROUP = 99
TEXT_RE = re.compile(r'title:\{(.*?)\}text:\{(.*)\}', re.DOTALL)

HEADERS = [
    '卡牌ID', '卡牌名', '卡牌角色', '部门编号', 'Cue', '例外类型', '段序', '段数',
    '开始秒', '时长秒', '候选说话角色', 'masterdata协作对象', 'Cue元数据文本（整条Cue共用）',
    '音频文件', '台词J（人工听写）', '台词C（人工）', '说明',
]

KIND_LABELS = {
    'department_combi': '部门协作语音',
    'department_combi_count_mismatch': '协作语音段数与部门人数不符',
    'multi_clip_other': '其他多段语音',
}

NOTES = {
    'department_combi': '例外：一条协作Cue依次播放部门内其他成员各一段；卡牌全表只保留Cue元数据文本，逐段内容在此表人工听写。',
    'department_combi_count_mismatch': '例外：协作Cue含多段，但段数不等于部门人数减一，需人工核对说话角色。',
    'multi_clip_other': '例外：一条Cue含多段音频（可能叠放播放），卡牌全表只保留Cue元数据文本。',
}


def scan_card_clips(input_path):
    """Return ``{card_id: record}`` for card ACBs with a multi-clip cue."""
    input_path = os.path.abspath(input_path)
    found, warnings, scanned = {}, [], 0
    for base, filename in _walk_source_files(input_path):
        match = CARD_FILE_RE.match(filename)
        if not match:
            continue
        path = os.path.join(base, filename)
        relative = os.path.relpath(path, input_path)
        try:
            data, stable = _read_stable_bytes(path)
            cues = extract_acb_cue_clips(data)
        except (OSError, CriUtfError) as error:
            warnings.append(f'无法解析 {relative}: {error}')
            continue
        scanned += 1
        multi = [cue for cue in cues if len(cue['Clips']) > 1]
        if not multi:
            continue
        card_id = int(match.group(1))
        if card_id in found:
            warnings.append(f'卡牌 {card_id} 存在重复 ACB: {found[card_id]["AcbFile"]} / {relative}')
            continue
        found[card_id] = {'CharacterCardId': card_id, 'AcbFile': relative, 'AbsolutePath': path,
                          'StableRead': stable, 'Cues': multi}
    return found, warnings, scanned


def _cue_text(user_data):
    match = TEXT_RE.fullmatch(user_data or '')
    return match.group(2).replace('\\n', '').replace('\n', '') if match else ''


def build(tables, scanned):
    cards = tables.by_id('mst_character_card', 'CharacterCardId')
    characters = tables.by_id('mst_character', 'CharacterId', required=False)
    groups = defaultdict(list)
    for row in characters.values():
        groups[row.get('CharacterGroupCode')].append(row.get('CharacterId'))

    entries, issues = [], []
    for card_id in sorted(scanned):
        record = scanned[card_id]
        card = cards.get(card_id)
        if card is None:
            issues.append({'CharacterCardId': card_id, 'Status': 'missing_card_master'})
            continue
        owner = card.get('CharacterId')
        group = characters.get(owner, {}).get('CharacterGroupCode')
        mates = sorted(cid for cid in groups.get(group, []) if cid != owner) if group != NON_STAFF_GROUP else []
        combi_partner = card.get('CombiCharacterId') or None
        for cue in record['Cues']:
            clips = cue['Clips']
            if cue['CueName'] == COMBI_CUE:
                kind = 'department_combi' if mates and len(clips) == len(mates) else 'department_combi_count_mismatch'
                candidates = mates
            else:
                kind, candidates = 'multi_clip_other', []
            if kind != 'department_combi':
                issues.append({'CharacterCardId': card_id, 'CueName': cue['CueName'], 'Status': kind,
                               'ClipCount': len(clips), 'DepartmentMates': mates})
            entries.append({
                'CharacterCardId': card_id,
                'CharacterCardName': card.get('CharacterCardName', ''),
                'CharacterId': owner,
                'CharacterGroupCode': group,
                'CombiCharacterId': combi_partner,
                'CueName': cue['CueName'],
                'Kind': kind,
                'CandidateSpeakerIds': candidates,
                'CueText': _cue_text(cue['UserData']),
                'Clips': clips,
                'UnknownCommands': cue['UnknownCommands'],
                'AcbFile': record['AcbFile'],
            })
    return {'Entries': entries, 'Issues': issues,
            'SpeakerPolicy': 'candidates_from_CharacterGroupCode_clip_speaker_unconfirmed',
            'TextPolicy': 'acb_metadata_is_one_text_per_cue_not_per_clip'}


def _export_clips(record, entry, directory, ffmpeg):
    """Write each clip as HCA (and WAV when ffmpeg exists); return file names."""
    try:
        data, _ = _read_stable_bytes(record['AbsolutePath'])
        awb = read_memory_awb(data)
    except (OSError, CriUtfError) as error:
        record_warning(f"卡牌 {entry['CharacterCardId']} 音频读取失败: {error}")
        return [''] * len(entry['Clips'])
    names = []
    for order, clip in enumerate(entry['Clips'], start=1):
        blob = awb.get(clip['MemoryAwbId']) if not clip.get('Streaming') else None
        if not blob or blob[:3] != b'HCA':
            names.append('')
            continue
        stem = f"voice_{entry['CharacterCardId']}_{entry['CueName']}_{order}"
        hca = os.path.join(directory, stem + '.hca')
        with open(hca, 'wb') as stream:
            stream.write(blob)
        record_output(hca)
        name = stem + '.hca'
        if ffmpeg:
            wav = os.path.join(directory, stem + '.wav')
            done = subprocess.run([ffmpeg, '-v', 'error', '-y', '-i', hca, wav],
                                  capture_output=True, check=False)
            if done.returncode == 0:
                record_output(wav)
                name = stem + '.wav'
        names.append(name)
    return names


def run(acb_root, session=None):
    scanned, warnings, count = scan_card_clips(acb_root)
    data = build(session.tables, scanned)
    data.update(ScanWarnings=warnings, ScannedAcbCount=count)
    characters = session.tables.by_id('mst_character', 'CharacterId', required=False)

    def name(cid):
        return characters.get(cid, {}).get('CharacterNameJpn', f'Character({cid})') if cid else '/'

    directory = audit_path('card_combi_voices_audio')
    os.makedirs(directory, exist_ok=True)
    ffmpeg = shutil.which('ffmpeg')
    rows = []
    for entry in data['Entries']:
        files = _export_clips(scanned[entry['CharacterCardId']], entry, directory, ffmpeg)
        candidates = ' / '.join(name(cid) for cid in entry['CandidateSpeakerIds']) or '待人工确认'
        for order, (clip, audio_file) in enumerate(zip(entry['Clips'], files), start=1):
            clip['AudioFile'] = audio_file
            rows.append([
                entry['CharacterCardId'], entry['CharacterCardName'], name(entry['CharacterId']),
                entry['CharacterGroupCode'], entry['CueName'], KIND_LABELS[entry['Kind']],
                order, len(entry['Clips']), clip['StartSeconds'], clip['DurationSeconds'],
                candidates, name(entry['CombiCharacterId']), entry['CueText'],
                audio_file, '', '', NOTES[entry['Kind']],
            ])
    save_json(data, audit_path('card_combi_voices.json'))
    write_xlsx(rows, xlsx_path('card_combi_voices.xlsx'), HEADERS, sheet_title='多段协作语音（例外）')
    if data['Issues'] or warnings:
        record_warning(f"多段协作语音有 {len(data['Issues'])} 条需人工核对、{len(warnings)} 条扫描告警，详见 card_combi_voices.json")
    if not ffmpeg:
        record_warning('未找到 ffmpeg，多段协作语音只导出 HCA 原始音频')
    return data
