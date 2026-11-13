import unittest
from toolkit.core.tables import TableCatalog
from toolkit.domains.audio_labels import AudioLabels
from toolkit.resolve import build_plan, MASTER_KEY


def labels():
    raw = {'mst_character': [{'CharacterId': i, 'CharacterNameJpn': n}
                            for i, n in [(11, '節見静'), (14, '相沢篠信'), (15, '在間樹帆')]]}
    return AudioLabels(TableCatalog([dict.fromkeys(raw, [])] + list(raw.values())))


class AudioLabelTests(unittest.TestCase):
    def test_audio_resource_plan_requires_masterdata_for_names(self):
        plan = build_plan(['audio'], {MASTER_KEY: None, 'Musics/voice_403.acb': None})
        self.assertFalse(plan['errors'])
        self.assertTrue(next(r for r in plan['resources'] if r['key'] == MASTER_KEY)['required'])
        self.assertTrue(build_plan(['audio'], {'Musics/voice_403.acb': None})['errors'])

    def test_package_speaker_is_not_the_home_voice_target(self):
        r = labels().label('hash/voice_arima_3.acb', 'vo_home_2_83')
        self.assertEqual('在間樹帆', r['Speaker'])
        r = labels().label('voice_aizawa_campaign.acb', 'vo_campaign_unit_6_20_4')
        self.assertEqual('相沢篠信', r['Speaker'])
        r = labels().label('local_voice.acb', 'vo_profile_2_15')
        self.assertEqual('在間樹帆', r['Speaker'])
        r = labels().label('local_voice.acb', 'vo_coly_999')
        self.assertEqual([], r['SpeakerCharacterIds'])

    def test_multispeaker_story_is_retained_as_unknown(self):
        r = labels().label('voice_story_2_1_1.acb', 'vo_1')
        self.assertEqual([], r['SpeakerCharacterIds'])
        self.assertEqual('待核对', r['Status'])

    def test_fallback_or_unstable_read_does_not_claim_confirmed_identity(self):
        r = labels().label('voice_arima_3.acb', 'vo_home_138', stable=False,
                           match_status='matched_by_title_fallback')
        self.assertEqual('在間樹帆', r['Speaker'])
        self.assertEqual('待核对', r['Status'])


if __name__ == '__main__':
    unittest.main()
