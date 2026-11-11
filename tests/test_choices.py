import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from toolkit.choices import latest_masterdata, load_choices, save_subjects
from toolkit.domains.birthday import cycle_options
from toolkit.domains.home_voices import subject_options
from tests.test_home_voices import catalog_with


def voice(speaker, number, category, cue, key=None):
    return {"HomeVoiceTypeCode": 1, "HomeVoiceTargetId": speaker, "HomeVoiceNo": number,
            "HomeVoiceCategory": category, "KeyTargetValue": key, "VoiceCueName": cue, "IsActive": True}


TABLES = {
    "mst_character": [
        {"CharacterId": 1, "CharacterNameJpn": "角色一", "BirthMonth": 5, "BirthDay": 14, "IsActive": True},
        {"CharacterId": 2, "CharacterNameJpn": "角色二", "BirthMonth": 1, "BirthDay": 6, "IsActive": True},
    ],
    "mst_character_birthday_mini_game_text": [
        {"CharacterId": 1, "Year": 2024}, {"CharacterId": 2, "Year": 2025}, {"CharacterId": 1, "Year": 2025},
    ],
    "mst_home_voice": [
        voice(1, 83, 4, "vo_home_2_83", key=2), voice(2, 83, 4, "vo_home_2_83", key=2),
        voice(1, 69, 7, "vo_home_69"), voice(1, 109, 7, "vo_home_109"),
        voice(1, 58, 6, "vo_home_58"),
        voice(1, 10, 11, "vo_home_duo_10"),
    ],
    "mst_season": [{"SeasonId": 3, "SeasonName": "5~6月", "IsActive": True}],
    "mst_character_home_voice_season": [
        {"CharacterId": 1, "HomeVoiceNo": 69, "SeasonId": 3, "IsActive": True},
        {"CharacterId": 1, "HomeVoiceNo": 109, "SeasonId": 3, "IsActive": True},
    ],
    "mst_character_home_voice_limited": [],
    "mst_home_voice_limited": [{"HomeVoiceNo": 58, "HomeVoiceNoName": "クリスマス", "IsActive": True}],
}


class ChoiceTests(unittest.TestCase):
    def test_cycles_come_from_birthday_text_years(self):
        self.assertEqual([(1, 2024), (2, 2025)], cycle_options(catalog_with(TABLES)))

    def test_subjects_are_grouped_named_and_unique_without_duo_lines(self):
        options = dict(subject_options(catalog_with(TABLES)))
        self.assertEqual('角色生日祝福｜角色二的生日全员祝福 [2年目]', options['birthday:character=2:year=2'])
        self.assertEqual('节日与话题｜クリスマス', options['limited:home_voice_no=58'])
        # Two years of the same season share a name, so the voice number tells them apart.
        self.assertEqual('季节｜5~6月（69号）', options['season:3:home_voice_no=69'])
        self.assertEqual('季节｜5~6月（109号）', options['season:3:home_voice_no=109'])
        self.assertFalse(any('duo' in key or 'category=11' in key for key in options))
        ordered = [label.split('｜')[0] for _, label in subject_options(catalog_with(TABLES))]
        self.assertEqual(['节日与话题', '季节', '季节', '角色生日祝福'], ordered)

    def test_subjects_saved_by_a_full_run_add_acb_only_ones_and_win_on_names(self):
        saved = [{"SubjectKey": "acb_only:cue=vo_home_146", "SubjectType": "acb_only",
                  "SubjectDisplayName": "3rd Anniv.", "CueName": "vo_home_146"},
                 {"SubjectKey": "limited:home_voice_no=58", "SubjectType": "limited",
                  "SubjectDisplayName": "クリスマス [1年目]", "HomeVoiceNo": 58, "CueName": "vo_home_58"}]
        options = dict(subject_options(catalog_with(TABLES), saved))
        self.assertEqual('周年纪念｜3rd Anniv.', options['acb_only:cue=vo_home_146'])
        self.assertEqual('节日与话题｜クリスマス [1年目]', options['limited:home_voice_no=58'])

    def test_latest_masterdata_needs_a_finished_preparation(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(latest_masterdata(directory))
            self.assertIsNone(load_choices(directory))
            jobs = Path(directory) / 'production-abc' / 'jobs'
            for index, name in enumerate(['old', 'new', 'unfinished']):
                path = jobs / name / 'master_data.s2b'
                path.parent.mkdir(parents=True)
                path.write_bytes(b'x')
                os.utime(path, (1000 + index, 1000 + index))
                if name != 'unfinished':
                    path.with_suffix('.provenance.json').write_text('{}')
            self.assertEqual(jobs / 'new' / 'master_data.s2b', latest_masterdata(directory))

    def test_load_choices_reads_saved_subjects_next_to_the_jobs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'production-abc'
            masterdata = root / 'jobs' / 'one' / 'master_data.s2b'
            masterdata.parent.mkdir(parents=True)
            masterdata.write_bytes(b'x')
            masterdata.with_suffix('.provenance.json').write_text('{}')
            catalog = Path(directory) / 'Home_Voice_Catalog.json'
            catalog.write_text(json.dumps({'Subjects': [{
                'SubjectKey': 'acb_only:cue=vo_home_146', 'SubjectType': 'acb_only',
                'SubjectDisplayName': '3rd Anniv.', 'CueName': 'vo_home_146', 'RowCount': 21}]}), encoding='utf-8')
            save_subjects(root, catalog)
            names = list(TABLES)
            raw = [{name: index for index, name in enumerate(names)}] + [TABLES[name] for name in names]
            with patch('toolkit.core.masterdata.decode_masterdata', return_value=raw):
                choices = load_choices(directory)
            self.assertEqual([('1', '第1轮（2024–25）'), ('2', '第2轮（2025–26）')], choices['cycles'])
            self.assertIn(('acb_only:cue=vo_home_146', '周年纪念｜3rd Anniv.'), choices['subjects'])
            self.assertNotIn('RowCount', json.loads((root / 'home_voice_subjects.json').read_text(encoding='utf-8'))[0])


if __name__ == '__main__':
    unittest.main()
