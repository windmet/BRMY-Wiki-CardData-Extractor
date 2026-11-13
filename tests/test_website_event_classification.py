import unittest
from types import SimpleNamespace
from toolkit.core.tables import TableCatalog
from toolkit.website.puzzle import extract

class WebsiteEventClassificationTests(unittest.TestCase):
    def test_map_owner_joins_event_a_and_keeps_unknown_codes(self):
        tables = {
            'mst_puzzle_map': [{'PuzzleMapId': 1, 'EventId': 10}, {'PuzzleMapId': 2, 'EventId': 11}],
            'mst_event': [{'EventId': 10, 'EventFormat': 2, 'EventTitle': 'Anniversary'}, {'EventId': 11, 'EventFormat': 999}],
            'mst_event_a': [{'EventId': 10, 'EventAType': 4}],
        }
        source = extract(SimpleNamespace(tables=TableCatalog([dict.fromkeys(tables), *tables.values()])))
        known, unknown = [row['Owner']['Classification'] for row in source['Maps']]
        self.assertEqual('no_ranking', known['Subtype'])
        self.assertEqual(4, known['EventAType'])
        self.assertEqual('unknown', unknown['Status'])
        self.assertEqual(999, unknown['EventFormat'])
