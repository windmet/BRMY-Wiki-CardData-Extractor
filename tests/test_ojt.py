import os
import tempfile
import unittest
from types import SimpleNamespace

from openpyxl import load_workbook

from toolkit.core.tables import TableCatalog
from toolkit.domains.ojt import export, extract


class OjtTests(unittest.TestCase):
    def test_training_phase_uses_shift_and_global_conversion_uses_reward_group(self):
        tables = {
            'mst_event': [{'EventId': 50, 'EventFormat': 5}], 'mst_event_c': [{'EventId': 50}],
            'mst_event_ojt_chart': [{'EventId': 50}],
            'mst_event_ojt_shift': [{'EventId': 50, 'OjtShiftId': 7}, {'EventId': 50, 'OjtShiftId': 8}],
            'mst_event_ojt_puzzle_stage': [{'OjtShiftId': 8, 'OjtPhase': 1, 'PuzzleMapId': 9}],
            'mst_puzzle_map': [{'PuzzleMapId': 9}],
            'mst_event_ojt_training_reward': [{'OjtShiftId': 7, 'OjtPhase': 1}],
            'mst_event_ojt_constant': [{'ConstantKey': 1, 'ChartStampConvertedDirectRewardGroupId': 20}],
            'mst_direct_reward': [{'DirectRewardGroupId': 20, 'RewardTypeCode': 2, 'RewardTargetId': 1, 'RewardCount': 5}],
            'mst_item': [{'ItemId': 1, 'ItemName': 'Conversion'}],
        }
        session = SimpleNamespace(tables=TableCatalog([dict.fromkeys(tables, []), *tables.values()]))
        data = extract(session, as_of='2026-09-09T00:00:00Z')
        self.assertEqual('missing_training_phase', data['Issues'][0]['Status'])
        self.assertEqual([], data['Events'][0]['Shifts'][0]['TrainingRewards'][0]['Stages'])
        self.assertEqual(9, data['Events'][0]['Shifts'][1]['StageMaps'][0]['Maps'][0]['PuzzleMapId'])
        self.assertEqual('Conversion', data['Constants'][0]['ChartStampConversionRewards'][0]['RewardName'])

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

    def test_workbook_uses_readable_sheets_phases_and_one_shared_random_pool(self):
        tables = {
            'mst_event': [{'EventId': 50, 'EventFormat': 5, 'EventTitle': 'Ev', 'OpenStartTime': '2026-01-01T16:00:00+00:00'}],
            'mst_event_c': [{'EventId': 50, 'PickUpCharacterCardId': 3, 'CharacterCardIds': [3]}],
            'mst_event_ojt_chart': [{'EventId': 50, 'ChartTitle': 'Q', 'ChartFileName': 'c'}],
            'mst_event_ojt_shift': [{'EventId': 50, 'OjtShiftId': 7, 'CharacterId': 1, 'StartTime': '2026-01-01T16:00:00+00:00'},
                                    {'EventId': 50, 'OjtShiftId': 8, 'CharacterId': 1}],
            'mst_event_ojt_puzzle_stage': [
                {'OjtShiftId': 7, 'OjtPhase': 1, 'PuzzleStageNo': 1, 'BreakScoreMin': 900000, 'BreakScoreMax': 900000, 'RentalCharacterCardIds': [3]},
                {'OjtShiftId': 7, 'OjtPhase': 0, 'PuzzleStageNo': 2, 'BreakScoreMin': 250000, 'BreakScoreMax': 920000}],
            'mst_event_ojt_training_reward': [{'OjtShiftId': 7, 'OjtPhase': 1, 'DirectRewardGroupId': 20}],
            'mst_direct_reward': [{'DirectRewardGroupId': 20, 'RewardTypeCode': 2, 'RewardTargetId': 1, 'RewardCount': 5}],
            'mst_event_ojt_terminal_character_text': [{'OjtShiftId': 7, 'OjtTerminalCharacterTextType': 3, 'Text': 'A\\nB'}],
            'mst_event_ojt_prize_box': [{'OjtShiftId': s, 'PrizeBoxNo': 1, 'PrizeBoxRewardId': 9, 'PrizeBoxRewardRandomId': 4,
                                         'RewardLotteryRate': 90, 'RewardRandomLotteryRate': 10} for s in (7, 8)],
            'mst_event_ojt_prize_box_reward': [{'PrizeBoxRewardId': 9, 'RewardTypeCode': 2, 'RewardTargetId': 1, 'RewardCount': 1,
                                                'PrizeStock': 3, 'IsPickUp': True}],
            'mst_event_ojt_prize_box_reward_random': [
                {'PrizeBoxRewardRandomId': 4, 'RewardTypeCode': 2, 'RewardTargetId': 1, 'RewardCount': 1, 'LotteryRate': 1},
                {'PrizeBoxRewardRandomId': 4, 'RewardTypeCode': 2, 'RewardTargetId': 1, 'RewardCount': 2, 'LotteryRate': 3}],
            'mst_item': [{'ItemId': 1, 'ItemName': 'Medal'}],
            'mst_character': [{'CharacterId': 1, 'CharacterNameJpn': 'Chara'}],
            'mst_character_card': [{'CharacterCardId': 3, 'CharacterId': 1, 'CharacterCardName': 'Card', 'CardRarityCode': 2}],
        }
        session = SimpleNamespace(tables=TableCatalog([dict.fromkeys(tables, []), *tables.values()]))
        data = extract(session, as_of='2026-01-02T00:00:00Z')
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            os.chdir(directory)
            try:
                book = load_workbook(export(data))
            finally:
                os.chdir(previous)
        self.assertEqual(['活动总览', '轮次', '关卡', '奖箱', '奖箱内容', '随机奖励', '站位坐标', '规则', '说明'], book.sheetnames)
        self.assertEqual('Card（Chara SR）', book['活动总览']['F2'].value)
        self.assertEqual(('Chara', '2026-01-02 01:00', 'A\nB'), (book['轮次']['D2'].value, book['轮次']['E2'].value, book['轮次']['J2'].value))
        stages = [[c.value for c in row] for row in book['关卡'].iter_rows(min_row=2)]
        self.assertEqual(['训练 Lv1', '900,000', 'Medal x5', 'Card（Chara SR）'], [stages[0][i] for i in (4, 6, 7, 8)])
        self.assertEqual(['进阶', '250,000～920,000', None], [stages[1][i] for i in (4, 6, 7)])
        self.assertEqual(['90%', '10%', 3, 'Medal'], [book['奖箱'].cell(2, c).value for c in (7, 8, 9, 10)])
        pool = [[c.value for c in row] for row in book['随机奖励'].iter_rows(min_row=2)]
        self.assertEqual([[4, '全部轮次', 'Medal', 1, 1, '25.000%'], [4, '全部轮次', 'Medal', 2, 3, '75.000%']], pool)

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
