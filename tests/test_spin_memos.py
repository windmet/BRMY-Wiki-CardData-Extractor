import unittest
from types import SimpleNamespace

from toolkit.core.tables import TableCatalog
from toolkit.domains.spin_memos import extract


def catalog(**tables):
    return TableCatalog([dict.fromkeys(tables, []), *tables.values()])


def snapshot(snapshot_id, set_id, rarity, comment, *notes, cast=(1,)):
    row = {'SnapshotId': snapshot_id, 'SpinSetId': set_id, 'SnapshotRarityCode': rarity,
           'SnapshotCharacterIds': list(cast), 'Comment': comment}
    row.update({f'StickyNoteId{i}': 0 for i in range(1, 5)})
    for slot, note in notes:
        row[f'StickyNoteId{slot}'] = note
    return row


class SpinMemoTests(unittest.TestCase):
    def test_trios_merge_across_sets_corners_and_limited_costumes(self):
        tables = catalog(
            mst_spin_snapshot=[
                snapshot(1, 100001, 1, '〜朝型？夜型？〜\n夜型'), snapshot(2, 100001, 2, 'SR memo', (1, 11)),
                snapshot(3, 100001, 3, 'SSR memo', (1, 12), (2, 13)),
                # Same content: the SR note sits in another corner with its own id, and the
                # trio straddles two sets.
                snapshot(4, 400001, 1, '〜朝型？夜型？〜\n夜型'), snapshot(5, 400002, 2, 'SR memo', (2, 21)),
                snapshot(6, 400002, 3, 'SSR memo', (1, 12), (2, 13)),
                snapshot(7, 500021, 1, '2026 BirthDay'), snapshot(8, 500021, 2, '2026 BirthDay'),
                snapshot(9, 500021, 3, '2026 BirthDay', (1, 14)),
                snapshot(10, 200001, 1, 'duo', cast=(1, 16)), snapshot(11, 200001, 3, 'broken', cast=(1, 16)),
            ],
            mst_spin_set=[{'SpinSetId': 100001, 'SpinBaseCode': 1, 'SpinMotionIds': [1]},
                          {'SpinSetId': 400001, 'SpinBaseCode': 4, 'SpinMotionIds': []},
                          {'SpinSetId': 400002, 'SpinBaseCode': 4, 'SpinMotionIds': []},
                          {'SpinSetId': 500021, 'SpinBaseCode': 1, 'SpinMotionIds': []},
                          {'SpinSetId': 200001, 'SpinBaseCode': 2, 'SpinMotionIds': []}],
            mst_spin_motion=[{'SpinMotionId': 1, 'SpinCharacterMotionIds': [10]}],
            mst_spin_character_motion=[{'SpinCharacterMotionId': 10, 'SpinCharacterMotionFileName': 'Bg001/Bg001_Slot01_01'}],
            mst_spin_sticky_note=[{'StickyNoteId': 11, 'CharacterId': 21, 'Comment': 'SR note'},
                                  {'StickyNoteId': 21, 'CharacterId': 21, 'Comment': 'SR note'},
                                  {'StickyNoteId': 12, 'CharacterId': 13, 'Comment': 'a'},
                                  {'StickyNoteId': 13, 'CharacterId': 10, 'Comment': 'b'},
                                  {'StickyNoteId': 14, 'CharacterId': 2, 'Comment': 'happy birthday'}],
            mst_spin_film=[{'FilmId': 1, 'FilmRarityCode': 1, 'CharacterIds': [1], 'SpinSetIds': [100001, 400001, 400002]}],
            mst_spin_film_limited_costume_mini=[{'FilmId': 1, 'SpinCostumeMiniRegulationId': 21,
                                                 'SpinSetIds': [100001, 400001, 400002, 500021]}],
            mst_spin_costume_mini_regulation=[{'SpinCostumeMiniRegulationId': 21, 'CostumeMiniIds': [305]}],
            mst_costume_mini=[{'CostumeMiniId': 305, 'CostumeMiniName': "Ai's special day",
                               'ReleaseDateTime': '2026-05-24T15:00:00+00:00'}],
        )
        data = extract(SimpleNamespace(tables=tables))
        regular, limited = data['Cards']
        self.assertEqual([100001, 400001, 400002], regular['SpinSetIds'])
        self.assertEqual(['太空赌场', '美式餐厅'], regular['Scenes'])
        self.assertEqual(['老虎机'], regular['Positions'])
        self.assertEqual(('朝型？夜型？', '夜型', '通常·单人'), (regular['Topic'], regular['TopicAnswer'], regular['Category']))
        self.assertEqual(['麻波麗'], [c['Character'] for c in regular['Memos'][1]['Comments']])
        self.assertEqual(('限定·单人', '2026-05-25'), (limited['Category'], limited['Date']))
        self.assertEqual(["Ai's special day"], limited['LimitedCostumes'])
        self.assertEqual(['皇坂逢(N)'], limited['Films'])
        self.assertEqual('irregular_snapshot_group', data['Issues'][0]['Status'])
        self.assertEqual(9, data['SnapshotCount'])


if __name__ == '__main__':
    unittest.main()
