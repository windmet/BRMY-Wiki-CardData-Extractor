import unittest

from toolkit.core.tables import TableCatalog
from toolkit.domains.home_voices import build_home_voice_catalog


def catalog_with(tables):
    names = list(tables)
    return TableCatalog([{name: index for index, name in enumerate(names)}] + [tables[name] for name in names])


class HomeVoiceCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tables = catalog_with({
            "mst_character": [
                {"CharacterId": 1, "CharacterNameJpn": "角色一", "IsActive": True},
                {"CharacterId": 2, "CharacterNameJpn": "角色二", "IsActive": True},
            ],
            "mst_home_voice": [
                {
                    "HomeVoiceTypeCode": 1, "HomeVoiceTargetId": speaker,
                    "HomeVoiceNo": 83, "HomeVoiceCategory": 4,
                    "KeyTargetValue": 2, "MotionCharacterId": speaker,
                    "VoiceCueName": "vo_home_2_83", "IsActive": True,
                }
                for speaker in (1, 2)
            ],
            "mst_season": [],
            "mst_character_home_voice_season": [],
            "mst_character_home_voice_limited": [],
        })

    def test_birthday_subject_uses_cue_target_and_masterdata_year(self):
        scanned = [
            {
                "SpeakerCharacterId": speaker, "AcbFile": f"voice_{speaker}_2.acb",
                "AcbBucket": 2, "CueName": "vo_home_2_83", "CueIndex": 4,
                "CueId": 10, "TitleRaw": title, "TextRaw": f"台词{speaker}",
                "TextWiki": f"台词{speaker}", "MetadataMatchStatus": "matched_by_acb_utf",
                "StableRead": True,
            }
            for speaker, title in ((1, "错误标题"), (2, "角色二の誕生日 [2年目]"))
        ]

        result = build_home_voice_catalog(self.tables, scanned, expected_character_ids=(1, 2))

        self.assertEqual(1, len(result["Subjects"]))
        subject = result["Subjects"][0]
        self.assertEqual("birthday:character=2:year=2", subject["SubjectKey"])
        self.assertEqual("角色二的生日全员祝福 [2年目]", subject["SubjectDisplayName"])
        self.assertTrue(subject["Complete"])
        self.assertEqual("matched", subject["MasterdataStatus"])
        self.assertIn("title_outlier", result["Records"][0]["AuditFlags"])

    def test_acb_only_subject_is_retained_and_missing_speaker_is_reported(self):
        scanned = [{
            "SpeakerCharacterId": 1, "AcbFile": "voice_one_general.acb",
            "AcbBucket": 0, "CueName": "vo_home_legacy", "CueIndex": 1,
            "CueId": 1, "TitleRaw": "旧语音", "TextRaw": "文本",
            "TextWiki": "文本", "MetadataMatchStatus": "matched_by_acb_utf",
            "StableRead": True,
        }]

        result = build_home_voice_catalog(self.tables, scanned, expected_character_ids=(1, 2))

        subject = result["Subjects"][0]
        self.assertEqual("acb_only:cue=vo_home_legacy", subject["SubjectKey"])
        self.assertEqual([2], subject["MissingCharacterIds"])
        self.assertFalse(subject["Complete"])
        self.assertEqual("acb_only", result["Records"][0]["MasterdataMatchStatus"])
        self.assertIn("masterdata_missing", result["Records"][0]["AuditFlags"])

    def test_non_birthday_key_target_does_not_trigger_package_year_warning(self):
        tables = catalog_with({
            "mst_character": [{"CharacterId": 1, "CharacterNameJpn": "角色一"}],
            "mst_home_voice": [{
                "HomeVoiceTypeCode": 1, "HomeVoiceTargetId": 1, "HomeVoiceNo": 1,
                "HomeVoiceCategory": 9, "KeyTargetValue": 10, "MotionCharacterId": 1,
                "VoiceCueName": "vo_home_1",
            }],
            "mst_season": [],
            "mst_character_home_voice_season": [],
            "mst_character_home_voice_limited": [],
        })
        scanned = [{
            "SpeakerCharacterId": 1, "AcbFile": "voice_one_general.acb",
            "AcbBucket": 0, "CueName": "vo_home_1", "CueIndex": 1, "CueId": 1,
            "TitleRaw": "朝", "TextRaw": "文本", "TextWiki": "文本",
            "MetadataMatchStatus": "matched_by_acb_utf", "StableRead": True,
            "AlternateAcbFiles": [],
        }]

        result = build_home_voice_catalog(tables, scanned, expected_character_ids=(1,))

        self.assertNotIn("package_year_mismatch", result["Records"][0]["AuditFlags"])


if __name__ == "__main__":
    unittest.main()
