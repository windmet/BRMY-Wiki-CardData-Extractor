import unittest
from toolkit.core.acquisition import acquisition_index
from toolkit.core.tables import TableCatalog


class AcquisitionTests(unittest.TestCase):
    def test_ojt_boxes_follow_shift_owner_and_keep_pool_namespaces(self):
        data = {'mst_event': [{'EventId': 50, 'EventFormat': 5}],
                'mst_event_ojt_shift': [{'OjtShiftId': 7, 'EventId': 50}],
                'mst_event_ojt_prize_box': [{'OjtShiftId': 7, 'PrizeBoxRewardId': 9, 'PrizeBoxRewardRandomId': 9},
                                          {'OjtShiftId': 50, 'PrizeBoxRewardId': 9}],
                'mst_event_ojt_training_reward': [{'OjtShiftId': 7, 'DirectRewardGroupId': 9}]}
        refs, issues = acquisition_index(TableCatalog([dict.fromkeys(data, []), *data.values()]))
        for table, kind in [('mst_direct_reward', 'ojt_training'), ('mst_event_ojt_prize_box_reward', 'ojt_fixed_box'),
                            ('mst_event_ojt_prize_box_reward_random', 'ojt_random_box')]:
            self.assertEqual(kind, refs[(table, 9)][0]['Kind'])
            self.assertEqual(50, refs[(table, 9)][0]['OwnerId'])
            self.assertEqual(1, len(refs[(table, 9)]))
        self.assertEqual('missing_or_ambiguous_ojt_owner', issues[0]['Status'])

    def test_mission_owner_types_and_present_namespaces_stay_separate(self):
        data = {'mst_event': [{'EventId': 7}], 'mst_campaign': [{'CampaignId': 7}],
                'mst_mission': [{'MissionId': i, 'SpecialTabTypeCode': code, 'SpecialTabTargetId': 7} for i, code in [(1, 1), (2, 2)]],
                'mst_mission_sequence': [{'MissionId': i, 'DirectRewardGroupId': 9} for i in [1, 2]],
                'mst_present_serial_code': [{'PresentId': 9}]}
        refs, issues = acquisition_index(TableCatalog([dict.fromkeys(data, []), *data.values()]))
        self.assertEqual(['event_mission', 'campaign_mission'], [r['Kind'] for r in refs[('mst_direct_reward', 9)]])
        self.assertEqual(['serial_code'], [r['Kind'] for r in refs[('mst_present', 9)]])
        self.assertEqual([], issues)
