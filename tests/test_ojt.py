import unittest
from types import SimpleNamespace

from toolkit.core.tables import TableCatalog
from toolkit.domains.ojt import extract


class OjtTests(unittest.TestCase):
    def test_shift_owner_and_reward_namespaces(self):
        tables = {
            'mst_event': [{'EventId': 50, 'EventFormat': 5}],
            'mst_event_c': [{'EventId': 50}],
            'mst_event_ojt_chart': [{'EventId': 50, 'LeftString': 'Left'}],
            'mst_event_ojt_shift': [{'EventId': 50, 'OjtShiftId': 7}],
            'mst_event_ojt_prize_box': [{'OjtShiftId': 7, 'PrizeBoxNo': 1, 'PrizeBoxRewardId': 9, 'PrizeBoxRewardRandomId': 9}],
            'mst_event_ojt_prize_box_reward': [{'PrizeBoxRewardId': 9, 'RewardTypeCode': 2, 'RewardTargetId': 1, 'RewardCount': 4, 'PrizeStock': 3}],
            'mst_event_ojt_prize_box_reward_random': [{'PrizeBoxRewardRandomId': 9, 'RewardTypeCode': 2, 'RewardTargetId': 2, 'RewardCount': 5, 'LotteryRate': 7}],
            'mst_item': [{'ItemId': 1, 'ItemName': 'Fixed'}, {'ItemId': 2, 'ItemName': 'Random'}],
            'mst_event_ojt_terminal_character_text': [{'OjtShiftId': 50, 'Text': 'Orphan'}],
        }
        session = SimpleNamespace(tables=TableCatalog([dict.fromkeys(tables, []), *tables.values()]))
        data = extract(session, as_of='2026-09-09T00:00:00Z')
        shift = data['Events'][0]['Shifts'][0]
        self.assertEqual([], shift['TerminalTexts'])
        self.assertEqual('unlinked_shift', data['Issues'][0]['Status'])
        box = shift['PrizeBoxes'][0]
        self.assertEqual('Fixed', box['FixedRewards'][0]['RewardName'])
        self.assertEqual('Random', box['RandomRewards'][0]['RewardName'])
        self.assertEqual(3, box['FixedRewards'][0]['RawReward']['PrizeStock'])
        self.assertEqual('not_loaded', data['ChartCoordinates'])

    def test_wrong_event_format_is_not_silently_accepted(self):
        session = SimpleNamespace(tables=TableCatalog([
            {'mst_event': [], 'mst_event_c': []},
            [{'EventId': 1, 'EventFormat': 1}], [{'EventId': 1}],
        ]))
        data = extract(session, as_of='2026-09-09T00:00:00Z')
        self.assertEqual([], data['Events'])
        self.assertEqual('invalid_event_owner', data['Issues'][0]['Status'])


if __name__ == '__main__':
    unittest.main()
