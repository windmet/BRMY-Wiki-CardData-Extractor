import unittest

from toolkit.core.tables import TableCatalog
from toolkit.domains.event_missions import extract_event_missions


def catalog(**tables):
    return TableCatalog([dict.fromkeys(tables, []), *tables.values()])


class EventMissionTests(unittest.TestCase):
    def test_owner_type_prevents_campaign_collision_and_keeps_reward_sequences(self):
        tables = catalog(
            mst_event=[{'EventId': 7}],
            mst_mission=[
                {'MissionId': 1, 'SpecialTabTypeCode': 1, 'SpecialTabTargetId': 7, 'Description': 'Do # times'},
                {'MissionId': 2, 'SpecialTabTypeCode': 2, 'SpecialTabTargetId': 7},
                {'MissionId': 3, 'SpecialTabTypeCode': 1, 'SpecialTabTargetId': 7, 'IsActive': False},
            ],
            mst_mission_sequence=[
                {'MissionId': 1, 'MissionSequenceNo': 2, 'Border': 20, 'DirectRewardGroupId': 9},
                {'MissionId': 1, 'MissionSequenceNo': 1, 'Border': 0, 'DirectRewardGroupId': 9},
                {'MissionId': 1, 'MissionSequenceNo': 3, 'IsActive': False},
                {'MissionId': 2, 'MissionSequenceNo': 1, 'DirectRewardGroupId': 99},
            ],
            mst_direct_reward=[
                {'DirectRewardGroupId': 9, 'DirectRewardSequenceNo': 1, 'RewardTypeCode': 2, 'RewardTargetId': 5, 'RewardCount': 3},
                {'DirectRewardGroupId': 9, 'DirectRewardSequenceNo': 2, 'RewardTypeCode': 2, 'RewardTargetId': 5, 'RewardCount': 4},
            ],
            mst_item=[{'ItemId': 5, 'ItemName': 'Item'}],
        )
        result, audit = extract_event_missions(tables)
        self.assertEqual([1], [m['MissionId'] for m in result[7]])
        seq = result[7][0]['Sequences']
        self.assertEqual([1, 2], [s['SequenceNo'] for s in seq])
        self.assertEqual('Do 0 times', seq[0]['Description'])
        self.assertEqual([3, 4], [r['RewardCount'] for r in seq[0]['Rewards']])
        self.assertEqual(2, audit['ExcludedOwners'][0]['SpecialTabTypeCode'])
        self.assertEqual([], audit['Issues'])

    def test_missing_and_ambiguous_relations_are_explicit(self):
        tables = catalog(
            mst_event=[{'EventId': 7}],
            mst_mission=[dict(MissionId=i, SpecialTabTypeCode=1, SpecialTabTargetId=owner)
                         for i, owner in [(1, 99), (2, 7), (3, 7), (4, 7), (5, 7), (5, 7)]],
            mst_mission_sequence=[
                {'MissionId': 3, 'MissionSequenceNo': 1, 'DirectRewardGroupId': 99},
                {'MissionId': 4, 'MissionSequenceNo': 1},
                {'MissionId': 4, 'MissionSequenceNo': 1},
            ],
        )
        result, audit = extract_event_missions(tables)
        self.assertNotIn(99, result)
        self.assertEqual({2, 3, 4}, {m['MissionId'] for m in result[7]})
        statuses = {i.get('Status', i.get('Resolution')) for i in audit['Issues']}
        self.assertEqual({'missing_event', 'missing_sequence', 'missing_reward_group',
                          'ambiguous_sequence', 'ambiguous_mission'}, statuses)
        reward_issue = next(i for i in audit['Issues'] if i.get('Resolution') == 'missing_reward_group')
        self.assertEqual((3, 1), (reward_issue['MissionId'], reward_issue['SequenceNo']))


if __name__ == '__main__':
    unittest.main()
