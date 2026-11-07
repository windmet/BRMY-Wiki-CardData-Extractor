import unittest
from toolkit.core.tables import TableCatalog
from toolkit.domains.music_source import build_source
from toolkit.resolve import build_plan, MASTER_KEY

class MusicSourceTests(unittest.TestCase):
    def test_same_title_keeps_distinct_identities_and_evidence(self):
        rows={'mst_music':[{'MusicId':n,'DisplayName':'same'} for n in (20001,21001,900011)],
              'mst_music_out_game':[{'MusicId':900011}],
              'mst_music_puzzle_stage':[{'MusicId':20001,'MusicPuzzleStageId':3}]}
        source=build_source(TableCatalog([dict.fromkeys(rows),*rows.values()]),'a'*64)
        entries={e['id']:e for e in source['Entries']}
        self.assertEqual(3,len(entries));self.assertFalse(entries[20001]['jukebox'])
        self.assertEqual(['PUZZLE'],entries[20001]['usages'])
        self.assertEqual(['Jukebox'],entries[900011]['usages'])
        self.assertEqual([],entries[21001]['usages'])

    def test_sync_does_not_depend_on_media(self):
        plan=build_plan(['music','jukebox'],{MASTER_KEY:{}})
        self.assertEqual([],plan['errors']);self.assertEqual([MASTER_KEY],[r['key'] for r in plan['resources']])
