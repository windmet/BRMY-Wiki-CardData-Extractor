import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from openpyxl import load_workbook

from toolkit.core.output import OutputContext
from toolkit.core.tables import TableCatalog
from toolkit.domains import bar_events, exchange_events, vignette_events
from toolkit.domains.event_common import plain_text, tier_label, tier_ranges


def session(**tables):
    return SimpleNamespace(tables=TableCatalog([dict.fromkeys(tables, [])] + list(tables.values())))


def run(module, tables):
    with tempfile.TemporaryDirectory() as directory:
        context = OutputContext(Path(directory), domain=module.__name__.rsplit('.', 1)[-1])
        with context.activate():
            path = module.run(session=tables, as_of='2026-11-12T00:00:00Z')
        book = load_workbook(path)
        try:
            return {sheet.title: [list(row) for row in sheet.iter_rows(values_only=True)] for sheet in book}
        finally:
            book.close()


SHIFT_A = ('2026-01-01T16:00:00+00:00', '2026-01-05T16:00:00+00:00')
SHIFT_B = ('2026-01-05T16:00:00+00:00', '2026-01-09T16:00:00+00:00')


class EventCommonTests(unittest.TestCase):
    def test_plain_text_keeps_line_breaks_and_drops_style_tags(self):
        self.assertEqual('a\nb 重点', plain_text('a<br><color=#33FFCC>b</color> <size=22>重点</size>'))

    def test_equal_neighbouring_tiers_merge_but_pickups_split(self):
        rows = [{'K': 1, 'R': 'x'}, {'K': 2, 'R': 'x'}, {'K': 3, 'R': 'y'}, {'K': 4, 'R': 'x'}]
        merged = tier_ranges(rows, 'K', lambda r: r['R'])
        self.assertEqual([(1, 2, 2, 'x'), (3, 3, 1, 'y'), (4, 4, 1, 'x')], merged)
        self.assertEqual('1,000～2,000 EN（2 档，每档各得一次）', tier_label(1000, 2000, 2, ' EN'))


class BarEventTests(unittest.TestCase):
    def tables(self):
        return session(
            mst_event=[{'EventId': 10, 'EventFormat': 3, 'EventTitle': 'Bar', 'OpenStartTime': SHIFT_A[0],
                        'EndTime': SHIFT_B[1]},
                       {'EventId': 11, 'EventFormat': 1, 'EventTitle': 'Other'}],
            mst_event_b=[{'EventId': 10, 'PickUpCharacterCardId': 5, 'CharacterCardIds': [5],
                          'DropEventBonusId': 1, 'SalesEventBonusId': 1}],
            mst_event_bonus=[{'EventBonusId': 1, 'BonusIncreaseRateByCharacterCard': 20,
                              'BonusIncreaseRatesByLimitBreakSSR': [5, 5]}],
            mst_character=[{'CharacterId': 1, 'CharacterNameJpn': 'Alpha'}, {'CharacterId': 2, 'CharacterNameJpn': 'Beta'}],
            mst_character_collaboration=[{'CharacterId': 10001, 'CharacterNameJpn': 'Guest'}],
            mst_character_card=[{'CharacterCardId': 5, 'CharacterCardName': 'Card', 'CharacterId': 1,
                                 'CardRarityCode': 3, 'CardAttributeCode': 1}],
            # Listed out of order: shifts are numbered by start time, not by id.
            mst_event_shift=[{'ShiftId': 8, 'EventId': 10, 'CharacterId': 2, 'StartTime': SHIFT_B[0], 'EndTime': SHIFT_B[1]},
                             {'ShiftId': 7, 'EventId': 10, 'CharacterId': 1, 'StartTime': SHIFT_A[0], 'EndTime': SHIFT_A[1]}],
            mst_event_special_time=[{'ShiftId': 7, 'SpecialTimeSequenceNo': 1, 'CharacterId': 10001,
                                     'StartTime': SHIFT_A[0], 'EndTime': SHIFT_A[1]}],
            mst_event_menu=[{'ShiftId': 7, 'MenuSequenceNo': 2, 'RecipeId': 2, 'MenuUnlockConditionIdA': 1},
                            {'ShiftId': 7, 'MenuSequenceNo': 1, 'RecipeId': 1}],
            mst_event_menu_unlock_condition=[{'MenuUnlockConditionId': 1, 'MenuUnlockConditionCode': 1,
                                              'Value1': 1, 'Value2': 100}],
            mst_event_recipe=[{'RecipeId': 1, 'RecipeName': 'Gin Tonic', 'EventId': 10, 'IngredientIds': [1, 101],
                               'RecipeMemo': 'line1\\nline2', 'DirectRewardGroupId': 3},
                              {'RecipeId': 2, 'RecipeName': 'Special', 'EventId': 10, 'RecommendCharacterId': 1,
                               'IngredientIds': [10001]}],
            mst_event_ingredient=[{'IngredientId': 1, 'IngredientName': 'Gin'},
                                  {'IngredientId': 101, 'IngredientName': 'Soda'},
                                  {'IngredientId': 10001, 'IngredientName': 'Candy'}],
            mst_puzzle_map=[{'PuzzleMapId': 50, 'EventId': 10}, {'PuzzleMapId': 1, 'CharacterId': 1}],
            mst_puzzle_stage=[
                {'PuzzleMapId': 50, 'PuzzleStageNo': 1, 'PuzzleType': 1, 'MusicPuzzleStageId': 9,
                 'ReleaseDateTime': SHIFT_A[0], 'EndTime': SHIFT_A[1]},
                {'PuzzleMapId': 50, 'PuzzleStageNo': 1, 'PuzzleType': 2, 'MusicPuzzleStageId': 9,
                 'ReleaseDateTime': SHIFT_B[0], 'EndTime': SHIFT_B[1]},
                {'PuzzleMapId': 50, 'PuzzleStageNo': 2, 'PuzzleType': 1, 'MusicPuzzleStageId': 4,
                 'ReleaseDateTime': SHIFT_A[0], 'EndTime': SHIFT_A[1]},
                {'PuzzleMapId': 50, 'PuzzleStageNo': 3, 'PuzzleType': 1, 'MusicPuzzleStageId': 4,
                 'ReleaseDateTime': SHIFT_A[0], 'EndTime': '2026-02-01T00:00:00+00:00'},
            ],
            mst_music_puzzle_stage=[{'MusicPuzzleStageId': 9, 'MusicId': 9}, {'MusicPuzzleStageId': 4, 'MusicId': 4}],
            mst_music=[{'MusicId': 9, 'DisplayName': 'Shared Song'}, {'MusicId': 4, 'DisplayName': 'Shift Song'}],
            mst_event_puzzle_stage_ingredient=[
                {'EventId': 10, 'PuzzleMapId': 50, 'PuzzleStageNo': 1, 'PuzzleType': 1, 'PickUpIngredientIds': [1],
                 **{f'PuzzleDropRewardIngredientGroupId{r}': 20 for r in ('SS', 'S', 'A', 'B', 'C', 'D', 'E')}},
                {'EventId': 10, 'PuzzleMapId': 1, 'PuzzleStageNo': 1, 'PuzzleType': 1, 'PickUpIngredientIds': [101]},
            ],
            mst_event_puzzle_drop_reward_ingredient=[
                {'PuzzleDropRewardIngredientGroupId': 20, 'PuzzleDropRewardIngredientSequenceNo': 1,
                 'RewardTargetId': 1, 'RewardCount': 1, 'LotteryRate': 3},
                {'PuzzleDropRewardIngredientGroupId': 20, 'PuzzleDropRewardIngredientSequenceNo': 2,
                 'RewardTargetId': 101, 'RewardCount': 2, 'LotteryRate': 1},
            ],
            mst_event_sales_reward=[
                {'EventId': 10, 'ShiftId': 7, 'KeySales': 500, 'DirectRewardGroupId': 3},
                {'EventId': 10, 'ShiftId': 0, 'KeySales': 1000, 'DirectRewardGroupId': 3},
                {'EventId': 10, 'ShiftId': 0, 'KeySales': 2000, 'DirectRewardGroupId': 3},
                {'EventId': 10, 'ShiftId': 0, 'KeySales': 3000, 'DirectRewardGroupId': 3, 'IsPickUp': True},
            ],
            mst_direct_reward=[{'DirectRewardGroupId': 3, 'RewardTypeCode': 2, 'RewardTargetId': 1, 'RewardCount': 5}],
            mst_item=[{'ItemId': 1, 'ItemName': 'Crystal'}],
        )

    def test_extract_joins_stages_to_shifts_by_exact_window(self):
        data = bar_events.extract(self.tables(), as_of='2026-11-12T00:00:00Z')
        self.assertEqual([10], [e['EventId'] for e in data['Events']])
        event = data['Events'][0]
        first, second = event['Shifts']
        self.assertEqual(('Alpha', 1), (first['Character'], first['Number']))
        self.assertEqual([(1, 'A', True), (2, 'A', False)],
                         [(s['StageNo'], s['Face'], s['Shared']) for s in first['Stages']])
        self.assertEqual([(1, 'B')], [(s['StageNo'], s['Face']) for s in second['Stages']])
        self.assertEqual(['unmatched_stage'], [i['Status'] for i in data['Issues']])
        self.assertEqual('Gin x1（75%） / Soda x2（25%）', first['Stages'][0]['Drops'])
        self.assertEqual(['一开始即可制作', '上一道配方制作 100 次'], [m['Unlock'] for m in first['Menu']])
        self.assertEqual({'StageCount': 1, 'PickUp': ['Soda']}, event['OtherStageDrops'])

    def test_workbook_sheets_and_merged_sales_tiers(self):
        book = run(bar_events, self.tables())
        self.assertEqual(['活动总览', '轮班', '菜单与配方', '材料', '关卡掉落', '特别营业', '营业额奖励', '说明'], list(book))
        overview = book['活动总览'][1]
        self.assertEqual('Card（Alpha SSR日）', overview[8])
        self.assertEqual('活动卡牌 +20%；SSR突破每阶 +5/5%', overview[10])
        self.assertEqual('line1\nline2', book['菜单与配方'][1][13])
        self.assertEqual('Guest', book['特别营业'][1][5])
        self.assertEqual(['基酒', '软饮', '联动限定'], [row[1] for row in book['材料'][1:]])
        sales = [row[2:6] for row in book['营业额奖励'][1:]]
        self.assertEqual([
            ['全期累计', '1,000～2,000 EN（2 档，每档各得一次）', 'Crystal x5', None],
            ['全期累计', '3,000 EN', 'Crystal x5', '是'],
            ['第1轮 Alpha', '500 EN', 'Crystal x5', None],
        ], sales)


class ExchangeEventTests(unittest.TestCase):
    def tables(self):
        return session(
            mst_event=[{'EventId': 3, 'EventFormat': 2, 'EventTitle': 'Prequel Story', 'OpenStartTime': '2026-01-01T00:00:00+00:00',
                        'EndTime': '2026-01-10T00:00:00+00:00'},
                       {'EventId': 11, 'EventFormat': 2, 'EventTitle': '0.5th Anniversary'}],
            mst_event_a=[{'EventId': 3, 'EventAType': 2, 'ExchangeId': 1003, 'EventItemId': 1},
                         {'EventId': 11, 'EventAType': 4}],
            mst_event_ranking_reward=[
                {'EventId': 3, 'RankingType': 2, 'StartRank': 1, 'PresentId': 8},
                {'EventId': 3, 'RankingType': 2, 'StartRank': 11, 'PresentId': 8},
                {'EventId': 3, 'RankingType': 2, 'StartRank': 101, 'PresentId': 0},
                {'EventId': 3, 'RankingType': 1, 'StartRank': 1, 'PresentId': 8, 'RewardWappenCount': 3},
            ],
            mst_present=[{'PresentId': 8, 'RewardTypeCode': 2, 'RewardTargetId': 1, 'RewardCount': 1}],
            mst_exchange=[{'ExchangeId': 1003, 'ExchangeName': 'Shop', 'CostItemId1': 1}],
            mst_exchange_product=[
                {'ExchangeId': 1003, 'ExchangeProductNo': 1, 'DirectRewardGroupId': 3, 'CostItemIdNumber': 1,
                 'CostItemCount': 100, 'ProductAllStock': 0, 'StartTime': '2026-01-01T00:00:00+00:00',
                 'EndTime': '9999-01-01T00:00:00+00:00'},
                {'ExchangeId': 1003, 'ExchangeProductNo': 2, 'DirectRewardGroupId': 3, 'CostItemIdNumber': 1,
                 'CostItemCount': 200, 'ProductAllStock': 5, 'StartTime': '2026-01-05T00:00:00+00:00',
                 'EndTime': '2026-01-10T00:00:00+00:00'},
            ],
            mst_direct_reward=[{'DirectRewardGroupId': 3, 'RewardTypeCode': 2, 'RewardTargetId': 1, 'RewardCount': 5}],
            mst_item=[{'ItemId': 1, 'ItemName': 'Medal'}],
        )

    def test_workbook_ranks_shop_and_subtypes(self):
        book = run(exchange_events, self.tables())
        self.assertEqual(['活动总览', '排名奖励', '兑换所', '说明'], list(book))
        self.assertEqual([('Prequel', 'Medal'), ('无排名特别活动', None)],
                         [(row[3], row[11]) for row in book['活动总览'][1:]])
        self.assertEqual([['高分排名', '1 名以后', 'Medal x1', 3],
                          ['活动 pt 排名', '1～10 名', 'Medal x1', None],
                          ['活动 pt 排名', '11～100 名', 'Medal x1', None]],
                         [row[3:7] for row in book['排名奖励'][1:]])
        self.assertEqual([['Medal x5', 'Medal x100', '不限', None, None],
                          ['Medal x5', 'Medal x200', 5, '2026-01-05 09:00', None]],
                         [row[3:8] for row in book['兑换所'][1:]])


class VignetteEventTests(unittest.TestCase):
    def test_accumulate_tiers_merge(self):
        tables = session(
            mst_event=[{'EventId': 49, 'EventFormat': 6, 'EventTitle': 'Vignette -A/B-'}],
            mst_event_accumulate_item=[{'EventId': 49, 'EventItemId': 1, 'CharacterIds': [1], 'PickUpCharacterCardIds': []}],
            mst_event_accumulate_item_reward=[
                {'EventId': 49, 'KeyCount': 100, 'DirectRewardGroupId': 3},
                {'EventId': 49, 'KeyCount': 200, 'DirectRewardGroupId': 3},
                {'EventId': 49, 'KeyCount': 300, 'DirectRewardGroupId': 3, 'IsPickUp': True},
            ],
            mst_direct_reward=[{'DirectRewardGroupId': 3, 'RewardTypeCode': 2, 'RewardTargetId': 1, 'RewardCount': 5}],
            mst_item=[{'ItemId': 1, 'ItemName': 'Bookmark'}],
            mst_character=[{'CharacterId': 1, 'CharacterNameJpn': 'Alpha'}],
        )
        book = run(vignette_events, tables)
        self.assertEqual(['活动总览', '累积奖励', '说明'], list(book))
        self.assertEqual(['Alpha', 'Bookmark', 3], [book['活动总览'][1][i] for i in (5, 8, 10)])
        self.assertEqual([['100～200（2 档，每档各得一次）', 'Bookmark x5', None], ['300', 'Bookmark x5', '是']],
                         [row[2:5] for row in book['累积奖励'][1:]])


if __name__ == '__main__':
    unittest.main()
