import struct
import unittest

from toolkit.core.cri_utf import CriUtfError, extract_acb_cue_clips, read_memory_awb
from toolkit.core.tables import TableCatalog
from toolkit.domains.card_combi_voices import build

_FORMATS = {2: '>H', 4: '>I'}


def utf_table(name, rows):
    """Write a minimal @UTF table; ints are u16 unless named in ``U32``, bytes/str by type."""
    columns = list(rows[0]) if rows else []
    strings, data = bytearray(b'<NULL>\x00'), bytearray()

    def string(value):
        offset = len(strings)
        strings.extend(value.encode() + b'\x00')
        return offset

    def kind(value, column):
        if isinstance(value, bytes):
            return 11
        if isinstance(value, str):
            return 10
        return 4 if column in U32 else 2

    table_name = string(name)
    schema = bytearray()
    kinds = [kind(rows[0][c], c) for c in columns]
    for column, value_type in zip(columns, kinds):
        schema += bytes([0x50 | value_type]) + struct.pack('>I', string(column))
    body = bytearray()
    for row in rows:
        for column, value_type in zip(columns, kinds):
            value = row[column]
            if value_type == 10:
                body += struct.pack('>I', string(value))
            elif value_type == 11:
                body += struct.pack('>II', len(data), len(value))
                data.extend(value)
            else:
                body += struct.pack(_FORMATS[value_type], value)
    width = sum({2: 2, 4: 4, 10: 4, 11: 8}[k] for k in kinds)
    rows_offset = 24 + len(schema)
    strings_offset = rows_offset + len(body)
    data_offset = strings_offset + len(strings)
    header = struct.pack('>HHIIIHHI', 1, rows_offset, strings_offset, data_offset,
                         table_name, len(columns), width, len(rows))
    payload = header + schema + body + strings + data
    return b'@UTF' + struct.pack('>I', len(payload)) + payload


U32 = {'NumSamples', 'SamplingRate'}


def afs2(entries):
    ids = sorted(entries)
    alignment = 32
    offsets, blob = [], bytearray()
    head = 16 + 4 * len(ids) + 4 * (len(ids) + 1)
    cursor = head
    for awb_id in ids:
        offsets.append(cursor)
        start = -(-cursor // alignment) * alignment
        blob += b'\x00' * (start - cursor) + entries[awb_id]
        cursor = start + len(entries[awb_id])
    offsets.append(cursor)
    out = b'AFS2' + bytes([2, 4]) + struct.pack('<H', 4) + struct.pack('<II', len(ids), alignment)
    out += b''.join(struct.pack('<I', i) for i in ids) + b''.join(struct.pack('<I', o) for o in offsets)
    return out + bytes(blob)


def note_on(synth):
    return struct.pack('>HB', 0x07D0, 4) + struct.pack('>HH', 2, synth)


def delay(ms):
    return struct.pack('>HB', 0x07D1, 4) + struct.pack('>I', ms)


def card_acb():
    """skill plays synth 0; combi plays synths 1, 2, 3 back to back."""
    combi = note_on(2) + delay(1000) + struct.pack('>HB', 0x07D5, 2) + b'\x01\x8b' + note_on(1) + delay(500) + note_on(3)
    events = [note_on(0) + b'\x00\x00\x00', combi + b'\x00\x00\x00']
    header = utf_table('Header', [{
        'CueTable': utf_table('Cue', [
            {'CueId': 0, 'ReferenceType': 3, 'ReferenceIndex': 0, 'UserData': 'title:{スキルボイス}text:{一}'},
            {'CueId': 1, 'ReferenceType': 3, 'ReferenceIndex': 1, 'UserData': 'title:{コンビボイス}text:{共用}'},
        ]),
        'CueNameTable': utf_table('CueName', [
            {'CueName': 'card_vo_skill', 'CueIndex': 0},
            {'CueName': 'card_vo_skill_combi', 'CueIndex': 1},
        ]),
        'SequenceTable': utf_table('Sequence', [
            {'NumTracks': 1, 'TrackIndex': struct.pack('>H', 0)},
            {'NumTracks': 1, 'TrackIndex': struct.pack('>H', 1)},
        ]),
        'TrackTable': utf_table('Track', [{'EventIndex': 0}, {'EventIndex': 1}]),
        'TrackEventTable': utf_table('TrackEvent', [{'Command': e} for e in events]),
        'SynthTable': utf_table('Synth', [{'ReferenceItems': struct.pack('>HH', 1, i)} for i in range(4)]),
        'WaveformTable': utf_table('Waveform', [
            {'MemoryAwbId': i, 'StreamAwbId': 65535, 'Streaming': 0, 'SamplingRate': 48000, 'NumSamples': 48000 * (i + 1)}
            for i in range(4)
        ]),
        'AwbFile': afs2({i: b'HCA\x00' + bytes([i]) * 8 for i in range(4)}),
    }])
    return header


class ClipParserTests(unittest.TestCase):
    def test_combi_cue_chains_clips_with_delays(self):
        cues = {cue['CueName']: cue for cue in extract_acb_cue_clips(card_acb())}
        self.assertEqual([0], [clip['SynthIndex'] for clip in cues['card_vo_skill']['Clips']])
        combi = cues['card_vo_skill_combi']
        self.assertEqual([2, 1, 3], [clip['SynthIndex'] for clip in combi['Clips']])
        self.assertEqual([0.0, 1.0, 1.5], [clip['StartSeconds'] for clip in combi['Clips']])
        self.assertEqual(3.0, combi['Clips'][0]['DurationSeconds'])
        self.assertEqual([{'Code': 0x07D5, 'Payload': '018b'}], combi['UnknownCommands'])

    def test_memory_awb_entries_are_addressed_by_id(self):
        awb = read_memory_awb(card_acb())
        self.assertEqual([0, 1, 2, 3], sorted(awb))
        self.assertEqual(b'HCA\x00' + b'\x02' * 8, awb[2])

    def test_unsupported_synth_reference_is_rejected(self):
        data = card_acb().replace(struct.pack('>HH', 1, 3), struct.pack('>HH', 3, 3))
        with self.assertRaises(CriUtfError):
            extract_acb_cue_clips(data)


def tables(card_owner=13, combi=14):
    group = {11: 4, 12: 4, 13: 4, 14: 4, 1: 1, 22: 99}
    return TableCatalog([
        {'mst_character_card': [], 'mst_character': []},
        [{'CharacterCardId': 421, 'CharacterId': card_owner, 'CombiCharacterId': combi,
          'CharacterCardName': 'Present for Soyogu', 'IsActive': True}],
        [{'CharacterId': cid, 'CharacterGroupCode': code, 'IsActive': True} for cid, code in group.items()],
    ])


def scanned(cue='card_vo_skill_combi', clips=3):
    return {421: {'AcbFile': 'voice_421.acb', 'Cues': [{
        'CueName': cue, 'UserData': 'title:{コンビボイス}text:{いろんな\\nこと}',
        'Clips': [{'StartSeconds': i, 'DurationSeconds': 1} for i in range(clips)], 'UnknownCommands': []}]}}


class BuildTests(unittest.TestCase):
    def test_department_combi_lists_other_members_as_candidates(self):
        result = build(tables(), scanned())
        entry = result['Entries'][0]
        self.assertEqual('department_combi', entry['Kind'])
        self.assertEqual([11, 12, 14], entry['CandidateSpeakerIds'])
        self.assertEqual('いろんなこと', entry['CueText'])
        self.assertEqual([], result['Issues'])

    def test_clip_count_mismatch_is_reported_not_guessed(self):
        result = build(tables(), scanned(clips=2))
        self.assertEqual('department_combi_count_mismatch', result['Entries'][0]['Kind'])
        self.assertEqual(1, len(result['Issues']))

    def test_other_multi_clip_cue_has_no_candidates(self):
        result = build(tables(), scanned(cue='card_vo_skill', clips=2))
        entry = result['Entries'][0]
        self.assertEqual(('multi_clip_other', []), (entry['Kind'], entry['CandidateSpeakerIds']))

    def test_unknown_card_is_an_issue(self):
        result = build(tables(), {999: scanned()[421]})
        self.assertEqual([], result['Entries'])
        self.assertEqual('missing_card_master', result['Issues'][0]['Status'])


if __name__ == '__main__':
    unittest.main()
