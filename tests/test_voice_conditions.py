import unittest

from toolkit.domains.home_voices import _conditions_sheet, build_home_voice_catalog, _purpose_sheets, _campaign_reference_sheet
from toolkit.core.tables import TableCatalog


class VoiceConditionsTests(unittest.TestCase):
    def test_global_and_character_windows_stay_separate_and_midnight_is_preserved(self):
        record = {'SubjectDisplayName': 'Subject', 'SpeakerCharacterName': 'Character',
                  'GlobalLimitedName': 'Name', 'StartTime': 'character-start', 'EndTime': 'character-end',
                  'GlobalLimitedRecords': [{'StartTime': 'global-start', 'EndTime': 'global-end'}],
                  'TimeDivisionRecords': [{'TimeDivisionName': 'night', 'StartHour': 0, 'StartMinutes': 0,
                                           'EndHour': 5, 'EndMinutes': 59}]}
        row = _conditions_sheet([record])['rows'][0]
        self.assertEqual(['character-start', 'character-end', 'global-start', 'global-end'], row[3:7])
        self.assertEqual(['night', '00:00', '05:59'], row[7:])


    def test_campaign_join_requires_speaker_and_cue_and_keeps_home_status(self):
        raw_tables = {'mst_campaign': [{'CampaignId': 185, 'CampaignTitle': '2.5th Anniversary',
                                  'StartTime': '2026-11-06T13:00:00+00:00', 'EndTime': '2026-11-17T08:59:00+00:00'}],
                               'mst_campaign_character_voice': [
                                   {'CampaignId': 185, 'CharacterId': 15, 'VoiceCueName': 'vo_home_138'},
                                   {'CampaignId': 185, 'CharacterId': 1, 'VoiceCueName': ''}]}
        tables = TableCatalog([dict.fromkeys(raw_tables, [])] + list(raw_tables.values()))
        scanned = [{'SpeakerCharacterId': cid, 'CueName': 'vo_home_138', 'AcbBucket': 3,
                    'TitleRaw': '2.5th Anniv.', 'TextRaw': '台词', 'TextWiki': '台词',
                    'AcbFile': 'source.acb', 'MetadataMatchStatus': 'matched_by_acb_utf', 'StableRead': True}
                   for cid in (15, 1)]
        records = build_home_voice_catalog(tables, scanned)['Records']
        matched = next(r for r in records if r['SpeakerCharacterId'] == 15)
        other = next(r for r in records if r['SpeakerCharacterId'] == 1)
        self.assertEqual('acb_only', matched['MasterdataMatchStatus'])
        self.assertEqual(185, matched['CampaignReferences'][0]['CampaignId'])
        self.assertEqual([], other['CampaignReferences'])
        rows = _purpose_sheets(records)[0]['rows']
        self.assertTrue(any('活动页引用：2.5th Anniversary' in row[-1] for row in rows))
        self.assertFalse(any('可能尚未开放' in row[-1] for row in rows))
        self.assertEqual(1, len(_campaign_reference_sheet(records)['rows']))


if __name__ == '__main__':
    unittest.main()
