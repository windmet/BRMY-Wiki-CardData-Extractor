import unittest

from toolkit.core.tables import TableCatalog
from toolkit.domains.home_voice_duo import build, build_sheets


class DuoTests(unittest.TestCase):
    def test_pair_sides_use_character_and_number_not_number_alone(self):
        tables = TableCatalog([
            {'mst_home_voice': [], 'mst_character_home_voice_duo': []},
            [{'HomeVoiceTypeCode': 1, 'HomeVoiceCategory': 11, 'HomeVoiceTargetId': cid, 'HomeVoiceNo': 9, 'VoiceCueName': 'cue'} for cid in (1, 2)],
            [{'CharacterId': 1, 'HomeVoiceNo': 9, 'PartnerCharacterId': 2, 'PartnerHomeVoiceNo': 9}],
        ])
        source = {'CueName': 'cue', 'StableRead': True, 'MetadataMatchStatus': 'matched_by_acb_utf'}
        scanned = [dict(source, SpeakerCharacterId=1, TextWiki='First'), dict(source, SpeakerCharacterId=2, TextWiki='Second')]
        result = build(tables, scanned)
        self.assertEqual('First', result['Pairs'][0]['First']['Text'])
        self.assertEqual('Second', result['Pairs'][0]['Partner']['Text'])
        self.assertEqual([], result['Issues'])
        missing = build(tables, scanned[:1])
        self.assertEqual('missing_acb_cue', missing['Pairs'][0]['Partner']['Status'])
        conflict = build(tables, scanned + [dict(source, SpeakerCharacterId=1, TextWiki='Different')])
        self.assertEqual('conflicting_text', conflict['Pairs'][0]['First']['Status'])
        self.assertEqual('', conflict['Pairs'][0]['First']['Text'])


def side(cid, number, key, text='t'):
    return {'CharacterId': cid, 'HomeVoiceNo': number, 'Masters': [{'KeyTargetValue': key}],
            'Text': text, 'Status': 'resolved'}


def pair(first, second, number, key):
    return {'PairKey': sorted([first, second]), 'Raw': {'PartnerVoiceStart': 0.2},
            'First': side(first, number, key), 'Partner': side(second, number, key)}


class SheetTests(unittest.TestCase):
    def test_pairs_are_grouped_triangularly_with_batches(self):
        pairs = [pair(3, 1, 157, 2), pair(1, 2, 9, 0), pair(2, 1, 154, 2), pair(1, 3, 12, 0)]
        sheets = {s['title']: s for s in build_sheets(pairs, lambda cid: f'C{cid}')}
        rows = sheets['按组合登记']['rows']
        self.assertEqual([(1, 'C1', 'C2', '第1批'), (1, 'C1', 'C2', '第2批'), (2, 'C1', 'C3', '第1批'),
                          (2, 'C1', 'C3', '第2批')], [tuple(r[:4]) for r in rows])
        self.assertEqual('C3', rows[3][5])  # the later C1-C3 conversation is opened by C3
        by_character = sheets['按角色查看']['rows']
        self.assertEqual(8, len(by_character))
        self.assertEqual(['C1', 'C1', 'C1', 'C1'], [r[0] for r in by_character[:4]])
        self.assertEqual(['C1', 2, 4, 2, 2, 2], sheets['统计']['rows'][0])


if __name__ == '__main__':
    unittest.main()
