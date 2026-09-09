import unittest
from types import SimpleNamespace

from toolkit.core.tables import TableCatalog
from toolkit.domains.collections import extract


class CollectionTests(unittest.TestCase):
    def test_typed_reverse_references_preserve_multiple_groups_without_icon_names(self):
        tables = {
            'mst_costume_model': [{'CostumeModelId': 1, 'CostumeModelName': 'Style'}],
            'mst_honor': [{'HonorId': 1, 'HonorName': '', 'HonorFileName': 'not-a-name'}],
            'mst_direct_reward': [{'DirectRewardGroupId': 10, 'RewardTypeCode': 4, 'RewardTargetId': 1},
                                  {'DirectRewardGroupId': 11, 'RewardTypeCode': 6, 'RewardTargetId': 1}],
            'mst_present': [{'PresentId': 10, 'RewardTypeCode': 4, 'RewardTargetId': 1}],
        }
        data = extract(SimpleNamespace(tables=TableCatalog([dict.fromkeys(tables, []), *tables.values()])), as_of='2026-09-09T00:00:00Z')
        style, honor = data['Collections']
        self.assertEqual(['mst_direct_reward', 'mst_present'], [r['SourceTable'] for r in style['RewardReferences']])
        self.assertEqual([11], [r['GroupId'] for r in honor['RewardReferences']])
        self.assertNotIn('not-a-name', honor['Name'])
        self.assertEqual('no_known_entries', style['AcquisitionEntryStatus'])
        self.assertEqual(style['RewardReferences'], style['UnresolvedRewardReferences'])


if __name__ == '__main__':
    unittest.main()
