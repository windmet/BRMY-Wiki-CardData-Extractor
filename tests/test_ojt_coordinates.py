import tempfile
import unittest
from pathlib import Path

import msgpack

from toolkit.core.tables import TableCatalog
from toolkit.domains.ojt_coordinates import load_coordinates


class CoordinateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tables = TableCatalog([{'mst_character': []}, [{'CharacterId': 1, 'CharacterNameJpn': 'Name'}]])
        self.events = [{'EventId': 43, 'Charts': [{'ChartFileName': 'event43_chart_layout'}]}]

    def write(self, name='event43_chart_layout.s2bchart', position=None):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(msgpack.packb({'IconLayouts': {'1': {
            'IconPosition': position if position is not None else [1.5, -2], 'SiblingIndex': 0}}}, use_bin_type=True))
        return path

    def test_exact_filename_and_raw_coordinates(self):
        path = self.write()
        data = load_coordinates(self.events, self.tables, path)
        self.assertEqual('loaded', data['Status'])
        self.assertEqual(-2, data['Charts'][0]['Coordinates'][0]['Y'])
        self.assertEqual(64, len(data['Charts'][0]['Sha256']))
        self.assertEqual('unconfirmed', data['Charts'][0]['Units'])

    def test_no_guessed_alias_and_no_duplicate_selection(self):
        self.write('event43_chart.s2bchart')
        data = load_coordinates(self.events, self.tables, self.root)
        self.assertEqual(['missing_file', 'unmatched_file'], [i['Status'] for i in data['Issues']])
        self.write()
        self.write('duplicate/event43_chart_layout.s2bchart')
        data = load_coordinates(self.events, self.tables, self.root)
        self.assertEqual('ambiguous_file', data['Charts'][0]['Status'])
        self.assertEqual([], data['Charts'][0]['Coordinates'])

    def test_invalid_coordinates_never_leak_partial_rows(self):
        for position in ([True, 1], [float('nan'), 2], [1], ['1', 2]):
            with self.subTest(position=position):
                data = load_coordinates(self.events, self.tables, self.write(position=position))
                self.assertEqual('invalid_file', data['Charts'][0]['Status'])
                self.assertEqual([], data['Charts'][0]['Coordinates'])

    def test_unknown_character_and_corrupt_file(self):
        empty = TableCatalog([{'mst_character': []}, []])
        path = self.write()
        self.assertEqual('invalid_file', load_coordinates(self.events, empty, path)['Charts'][0]['Status'])
        path.write_bytes(b'\xc1')
        self.assertEqual('invalid_file', load_coordinates(self.events, self.tables, path)['Charts'][0]['Status'])

    def test_optional_and_explicit_missing_input(self):
        self.assertEqual('not_loaded', load_coordinates(self.events, self.tables)['Status'])
        with self.assertRaises(ValueError):
            load_coordinates(self.events, self.tables, self.root / 'missing.s2bchart')


if __name__ == '__main__':
    unittest.main()
