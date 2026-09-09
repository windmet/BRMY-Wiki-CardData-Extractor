import unittest
from toolkit.core.acquisition import acquisition_index
from toolkit.core.tables import TableCatalog


class AcquisitionTests(unittest.TestCase):
    def test_mission_owner_types_and_present_namespaces_stay_separate(self):
        data = {'mst_event': [{'EventId': 7}], 'mst_campaign': [{'CampaignId': 7}],
                'mst_mission': [{'MissionId': i, 'SpecialTabTypeCode': code, 'SpecialTabTargetId': 7} for i, code in [(1, 1), (2, 2)]],
                'mst_mission_sequence': [{'MissionId': i, 'DirectRewardGroupId': 9} for i in [1, 2]],
                'mst_present_serial_code': [{'PresentId': 9}]}
        refs, issues = acquisition_index(TableCatalog([dict.fromkeys(data, []), *data.values()]))
        self.assertEqual(['event_mission', 'campaign_mission'], [r['Kind'] for r in refs[('mst_direct_reward', 9)]])
        self.assertEqual(['serial_code'], [r['Kind'] for r in refs[('mst_present', 9)]])
        self.assertEqual([], issues)
