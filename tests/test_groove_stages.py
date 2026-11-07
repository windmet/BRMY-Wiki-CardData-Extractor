import unittest
from toolkit.core.tables import TableCatalog
from toolkit.domains.groove_stages import StageChallenges


class StageTests(unittest.TestCase):
    def source(self):
        return TableCatalog([{'mst_groove_extra_achievement': [], 'mst_groove_achievement_reward': [], 'mst_direct_reward': [], 'mst_item': []},
            [{'GrooveExtraAchievementId': 1, 'Description': 'clear', 'IsActive': True}],
            [{'GrooveAchievementRewardId': 1, 'RewardGrooveExtra1': 100}],
            [{'DirectRewardGroupId': 100, 'RewardTypeCode': 2, 'RewardTargetId': 566, 'RewardCount': 5}],
            [{'ItemId': 566, 'ItemName': 'Polish', 'IsActive': True}]])

    def test_exact_links_and_missing_condition(self):
        source = self.source()
        issues = []
        row = {'MusicId': 1, 'GrooveMusicStageType': 1, 'GrooveAchievementRewardId': 1, 'GrooveExtraAchievementId1': 1}
        result = StageChallenges(source).project(row, issues)
        self.assertEqual(result[0]['Rewards'][0]['RewardName'], 'Polish')
        self.assertEqual(result[0]['Rewards'][0]['RewardCount'], 5)
        self.assertEqual(issues, [])
        row['GrooveExtraAchievementId1'] = 999
        self.assertEqual(StageChallenges(source).project(row, issues)[0]['Resolution'], 'unresolved')
        self.assertEqual(len(issues), 1)

    def test_does_not_join_unknown_reward_type_to_item(self):
        source = self.source()
        source.rows('mst_direct_reward')[0]['RewardTypeCode'] = 999
        issues = []
        result = StageChallenges(source).project({'GrooveAchievementRewardId': 1, 'GrooveExtraAchievementId1': 1}, issues)
        self.assertEqual(result[0]['Resolution'], 'unresolved')
        self.assertNotEqual(result[0]['Rewards'][0]['RewardName'], 'Polish')
