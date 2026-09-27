import unittest

from toolkit.domains.jukebox import REQUIRED, build_source
from toolkit.resolve import build_plan, MASTER_KEY


class JukeboxSourceTests(unittest.TestCase):
    def test_sync_plan_requires_only_masterdata(self):
        plan = build_plan(['jukebox'], {MASTER_KEY: {}, 'Musics/preview.acb': {}})
        self.assertEqual([], plan['errors'])
        self.assertEqual([MASTER_KEY], [row['key'] for row in plan['resources']])

    def test_typed_reward_identity_and_revision_consumer(self):
        tables = {name: [] for name in REQUIRED}
        tables.update({
            'mst_music': [
                {'MusicId': 1, 'DisplayName': 'Welcome'},
                {'MusicId': 900011, 'DisplayName': 'BREAK MY PHASE'},
                {'MusicId': 900012, 'DisplayName': 'Revision Song'},
            ],
            'mst_music_out_game': [
                {'MusicId': mid, 'ProfileMusicCueId': mid} for mid in (1, 900011, 900012)
            ],
            'mst_music_position_jukebox': [{'MusicId': mid} for mid in (1, 900011, 900012)],
            'mst_music_cue': [{'MusicCueId': mid, 'MusicCueSheetId': mid} for mid in (1, 900011, 900012)],
            'mst_music_cue_sheet': [{'MusicCueSheetId': mid} for mid in (1, 900011, 900012)],
            'mst_direct_reward': [
                {'DirectRewardGroupId': 10173, 'DirectRewardSequenceNo': 1, 'RewardTypeCode': 8, 'RewardTargetId': 900011},
                {'DirectRewardGroupId': 200, 'DirectRewardSequenceNo': 1, 'RewardTypeCode': 8, 'RewardTargetId': 900012},
            ],
            'mst_mission_sequence': [{'MissionId': 100498, 'MissionSequenceNo': 1, 'DirectRewardGroupId': 10173}],
            'mst_mission': [{'MissionId': 100498, 'Description': 'Clear SIDE A', 'SpecialTabTypeCode': 0,
                             'MissionType': 1008, 'Value1': 20001, 'Value2': 1}],
            'mst_character_card_revision': [{'CharacterCardId': 143, 'RevisionRank': 1, 'DirectRewardGroupId': 200}],
            'mst_character_card': [{'CharacterCardId': 143, 'CharacterCardName': 'Card'}],
        })
        source = build_source(tables, 'a' * 64)
        by_id = {entry['id']: entry for entry in source['Entries']}
        self.assertEqual([], source['Audit']['issues'])
        self.assertEqual([], by_id[1]['acquisitionRoutes'])
        mission_route = by_id[900011]['acquisitionRoutes'][0]
        self.assertEqual(900011, mission_route['rewardTargetMusicId'])
        self.assertEqual(20001, mission_route['conditionTarget']['value1'])
        self.assertEqual('mission:100498:1', mission_route['key'])
        self.assertEqual('card_revision:143:1', by_id[900012]['acquisitionRoutes'][0]['key'])


if __name__ == '__main__':
    unittest.main()
