"""Review list for card voice texts that the ACB metadata likely got wrong.

ACB ``title:{}text:{}`` metadata is authored by hand and has been copied
between cards (for example the same skill line on several unrelated cards).
The card workbook keeps whatever the ACB says; this module only lists
suspicious entries for editors and never rewrites a text. Gacha cues are
skipped because the card workbook does not export them and most recent
cards leave their text empty.
"""
import os
import re
from collections import defaultdict

from ..core.cri_utf import CriUtfError, extract_acb_cue_rows
from ..core.exporter import audit_path, xlsx_path, write_xlsx
from ..core.output import record_warning
from ..core.scanner import save_json
from .audio import CARD_FILE_RE, _read_stable_bytes, _walk_source_files

TEXT_RE = re.compile(r'title:\{(.*?)\}text:\{(.*)\}', re.DOTALL)
GACHA_CUE = 'card_vo_gacha'

HEADERS = ['卡牌ID', '卡牌名', '卡牌角色', '发布时间', '语音条目', '问题类型', 'ACB文本',
           '同文本卡牌', 'ACB原始信息', '核对后台词J（人工）', '说明']

KIND_LABELS = {
    'reused_copy': '跨卡重复（较晚出现）',
    'reused_first': '跨卡重复（最早出现）',
    'same_card_duplicate': '同卡两条语音重复',
    'empty_text': '文本为空',
    'malformed_metadata': 'ACB信息格式损坏',
}

NOTES = {
    'reused_copy': '同一句话出现在更早的卡上，较可能是 ACB 里复制粘贴的文本，请优先试听核对。',
    'reused_first': '这一句也出现在其他卡上；按发布时间推测此处较可能是原句，仍需核对。',
    'same_card_duplicate': '同一张卡的两条语音文本相同，可能有一条写错。',
    'empty_text': 'ACB 有这条语音，但文本为空。',
    'malformed_metadata': 'ACB 里这条语音的信息不符合 title:{}text:{} 格式，卡牌表中此条为空；原始内容见“ACB原始信息”。',
}


def _normalize(text):
    return re.sub(r'\s+', '', text.replace('\\n', ''))


def scan_card_metadata(input_path):
    """Return raw cue metadata per card ACB, including entries the card parser drops."""
    input_path = os.path.abspath(input_path)
    found, warnings = {}, []
    for base, filename in _walk_source_files(input_path):
        match = CARD_FILE_RE.match(filename)
        if not match:
            continue
        path = os.path.join(base, filename)
        try:
            data, _ = _read_stable_bytes(path)
            rows = extract_acb_cue_rows(data)
        except (OSError, CriUtfError) as error:
            warnings.append(f'无法解析 {os.path.relpath(path, input_path)}: {error}')
            continue
        found.setdefault(int(match.group(1)), rows)
    return found, warnings


def build(scanned, cards):
    """``cards`` maps card id to its masterdata row; returns review entries."""
    entries, occurrences, skipped = [], defaultdict(list), 0

    def add(card_id, cue, kind, text='', raw='', related=()):
        card = cards.get(card_id, {})
        entries.append({'CharacterCardId': card_id, 'CharacterCardName': card.get('CharacterCardName', ''),
                        'CharacterId': card.get('CharacterId'), 'ReleaseDateTime': card.get('ReleaseDateTime', ''),
                        'CueName': cue, 'Kind': kind, 'Text': text, 'RawUserData': raw,
                        'RelatedCardIds': sorted(set(related) - {card_id})})

    for card_id in sorted(scanned):
        texts = {}
        for row in scanned[card_id]:
            user_data = row.get('UserData') or ''
            cue = row.get('CueName', '')
            if cue == GACHA_CUE:
                skipped += 1
                continue
            if not isinstance(user_data, str) or not user_data:
                continue
            match = TEXT_RE.fullmatch(user_data)
            if not match:
                if 'title:{' in user_data:
                    add(card_id, cue, 'malformed_metadata', raw=user_data)
                continue
            text = match.group(2)
            if not _normalize(text):
                add(card_id, cue, 'empty_text')
                continue
            texts[cue] = text
            occurrences[_normalize(text)].append((card_id, cue, text))
        by_text = defaultdict(list)
        for cue, text in texts.items():
            by_text[_normalize(text)].append(cue)
        for cues in by_text.values():
            for cue in cues if len(cues) > 1 else ():
                add(card_id, cue, 'same_card_duplicate', texts[cue])

    for items in occurrences.values():
        card_ids = {card_id for card_id, _, _ in items}
        if len(card_ids) < 2:
            continue
        first = min(card_ids, key=lambda cid: (cards.get(cid, {}).get('ReleaseDateTime') or '9999', cid))
        for card_id, cue, text in items:
            add(card_id, cue, 'reused_first' if card_id == first else 'reused_copy', text, related=card_ids)

    order = list(KIND_LABELS)
    entries.sort(key=lambda e: (order.index(e['Kind']) if e['Kind'].startswith('reused') else len(order),
                                e['RelatedCardIds'], e['CharacterCardId'], e['CueName']))
    return entries, skipped


def run(audio_dir, tables, character_name):
    scanned, warnings = scan_card_metadata(audio_dir)
    cards = tables.by_id('mst_character_card', 'CharacterCardId')
    entries, skipped = build(scanned, cards)
    save_json({'Entries': entries, 'ScanWarnings': warnings, 'SkippedGachaCues': skipped,
               'Policy': 'review_only_card_workbook_keeps_acb_text'}, audit_path('card_voice_review.json'))
    rows = [[e['CharacterCardId'], e['CharacterCardName'], character_name(e['CharacterId']),
             e['ReleaseDateTime'][:10], e['CueName'], KIND_LABELS[e['Kind']],
             e['Text'].replace('\\n', '').replace('\n', ''),
             ', '.join(str(cid) for cid in e['RelatedCardIds']), e['RawUserData'], '', NOTES[e['Kind']]]
            for e in entries]
    write_xlsx(rows, xlsx_path('card_voice_review.xlsx'), HEADERS, sheet_title='卡牌语音待核对')
    if entries:
        record_warning(f'卡牌语音有 {len(entries)} 条待核对（重复、空文本或格式损坏），详见 card_voice_review.xlsx')
    return entries
