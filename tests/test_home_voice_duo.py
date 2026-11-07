import unittest

from toolkit.core.tables import TableCatalog
from toolkit.domains.home_voice_duo import build


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


if __name__ == '__main__':
    unittest.main()
