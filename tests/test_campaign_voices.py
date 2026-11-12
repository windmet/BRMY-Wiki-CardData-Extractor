import json
import io
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from openpyxl import load_workbook

from toolkit.core.tables import TableCatalog
from toolkit.domains import campaign_voices
from toolkit.resolve import build_plan, MASTER_KEY
from toolkit.generate import generate
from toolkit.core.session import REQUIRED_SCHEMA


def masterdata(**overrides):
    tables = {
        'mst_character': [{'CharacterId': 6, 'CharacterNameJpn': '樋宮明星'},
                          {'CharacterId': 15, 'CharacterNameJpn': '在間樹帆'}],
        'mst_campaign': [{'CampaignId': 185, 'CampaignTitle': '2.5th Anniversary',
                          'StartTime': '2026-11-06T13:00:00+00:00', 'EndTime': '2026-11-17T18:00:00+00:00'},
                         {'CampaignId': 188, 'CampaignTitle': 'Shuffle Song',
                          'StartTime': '2026-11-13T18:00:00+00:00', 'EndTime': '2026-11-21T04:00:00+00:00'}],
        'mst_campaign_character_voice': [
            {'CampaignId': 185, 'CharacterId': 15, 'VoiceCueName': 'vo_home_138', 'Text': ''},
            {'CampaignId': 188, 'CharacterId': 6, 'VoiceCueName': 'vo_campaign_unit_14_20_4', 'Text': ''},
            {'CampaignId': 185, 'CharacterId': 6, 'VoiceCueName': '', 'Text': 'test'}],
        'mst_shuffle_talk': [{'ShuffleTalkId': 1, 'CampaignId': 188, 'TitleName': '対話①',
                              'IsInitialUnlocked': False}],
        'mst_shuffle_talk_sequence': [
            {'ShuffleTalkId': 1, 'ShuffleTalkSequenceNo': seq, 'CharacterId': 6,
             'VoiceCueName': f'vo_campaign_unit_14_20_{seq}', 'Text': ''} for seq in (2, 1)],
    }
    tables.update(overrides)
    for name, fields in REQUIRED_SCHEMA.items():
        # The shared session validates the global schema even for unrelated tables.
        tables.setdefault(name, [{**dict.fromkeys(fields, 0), 'IsActive': False}])
    for row in tables['mst_character']:
        row.update(CharacterNameEng='fixture', IsActive=True)
    return [dict.fromkeys(tables, [])] + list(tables.values())


def metadata(path):
    filename = Path(path).name
    cues = {'voice_arima_3.acb': ['vo_home_138'],
            'voice_hinomiya_campaign.acb': [f'vo_campaign_unit_14_20_{i}' for i in (1, 2, 4)]}
    return [{'CueName': cue, 'Text': f'{cue}\\n台词', 'Title': '原始标题',
             'MatchStatus': 'matched_by_acb_utf'} for cue in cues.get(filename, [])], True


class CampaignVoiceTests(unittest.TestCase):
    def test_resource_plan_is_driven_by_speaker_and_cue_family(self):
        tables = TableCatalog(masterdata())
        keys = campaign_voices.resource_keys(tables)
        self.assertEqual(5, len(keys))
        self.assertIn('Musics/voice_hinomiya_campaign.acb', keys)
        self.assertIn('Musics/voice_arima_3.acb', keys)
        self.assertNotIn('Musics/voice_hinomiya_general.acb', keys)
        plan = build_plan(['campaign_voices'], {MASTER_KEY: None, **dict.fromkeys(keys)}, tables)
        self.assertFalse(plan['errors'])
        self.assertEqual(6, len(plan['resources']))
        missing = build_plan(['campaign_voices'], {MASTER_KEY: None}, tables)
        self.assertFalse(missing['errors'])
        self.assertEqual(5, len(missing['warnings']))

    @patch('toolkit.domains.campaign_voices.extract_text_metadata', side_effect=metadata)
    def test_generate_preserves_order_future_state_and_placeholder_evidence(self, _):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            md = root / 'input.json'
            md.write_text(json.dumps(masterdata()), encoding='utf-8')
            for name in ('voice_arima_3.acb', 'voice_hinomiya_campaign.acb'):
                (root / name).write_bytes(b'fixture')
            with io.TextIOWrapper(io.BytesIO(), encoding='cp1252') as legacy, redirect_stdout(legacy):
                report = generate(['campaign_voices'], root / 'out', masterdata=md, audio=root,
                                  as_of='2026-11-12T00:00:00+00:00')
            self.assertEqual('PASS_WITH_WARNINGS', report['status'], report['errors'])
            data = json.loads((root / 'out/audit_output/campaign_voices.json').read_text(encoding='utf-8'))
            self.assertEqual(1, sum(r['Placeholder'] for r in data['Records']))
            self.assertEqual(4, sum(r['Status'] == '正常' for r in data['Records']))
            talk = [r for r in data['Records'] if r['Kind'] == 'talk']
            self.assertEqual([1, 2], [r['Raw']['ShuffleTalkSequenceNo'] for r in talk])
            self.assertEqual({'scheduled'}, {r['Availability']['Status'] for r in talk})
            self.assertIn('Sha256', talk[0]['Matches'][0])
            book = load_workbook(root / 'out/wiki_output/活动语音与对话.xlsx')
            try:
                self.assertEqual(['活动一览', '活动页台词', 'Shuffle Talk', '待核对', '说明'], book.sheetnames)
                self.assertEqual('未开始', book['Shuffle Talk']['K2'].value)
                self.assertEqual('否', book['Shuffle Talk']['L2'].value)
                self.assertEqual(2, book['待核对'].max_row)
                self.assertIn('\n', book['Shuffle Talk']['G2'].value)
            finally:
                book.close()

    def test_missing_packages_and_placeholders_are_distinct(self):
        with tempfile.TemporaryDirectory() as root:
            data = campaign_voices.extract(TableCatalog(masterdata()), root)
        self.assertEqual(4, sum(r['Status'] == '缺失' for r in data['Records']))
        self.assertEqual(1, sum(r['Placeholder'] and r['Status'] == '待核对' for r in data['Records']))

    def test_conflicting_packages_are_not_arbitrarily_selected(self):
        def conflicting(path):
            return [{'CueName': 'vo_home_138', 'Text': Path(path).parent.name,
                     'MatchStatus': 'matched_by_acb_utf'}], True
        with tempfile.TemporaryDirectory() as root:
            for folder in ('a', 'b'):
                p = Path(root) / folder / 'voice_arima_3.acb'
                p.parent.mkdir()
                p.write_bytes(b'fixture')
            with patch('toolkit.domains.campaign_voices.extract_text_metadata', side_effect=conflicting):
                data = campaign_voices.extract(TableCatalog(masterdata()), root)
        r = next(r for r in data['Records'] if r['Raw']['CharacterId'] == 15)
        self.assertEqual('待核对', r['Status'])
        self.assertEqual('', r['Text'])
        self.assertEqual(2, len(r['Matches']))

    def test_inline_text_works_without_acb_and_unknown_parent_is_flagged(self):
        raw = {'CampaignId': 999, 'CharacterId': 6, 'VoiceCueName': '', 'Text': '有效文本'}
        tables = TableCatalog(masterdata(mst_campaign_character_voice=[raw], mst_shuffle_talk_sequence=[]))
        with tempfile.TemporaryDirectory() as root:
            r = campaign_voices.extract(tables, root)['Records'][0]
        self.assertEqual('有效文本', r['Text'])
        self.assertFalse(r['Placeholder'])
        self.assertEqual('待核对', r['Status'])
        self.assertEqual('unknown', r['Availability']['Status'])


if __name__ == '__main__':
    unittest.main()
