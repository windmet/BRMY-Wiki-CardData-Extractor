import unittest
from toolkit.core.tables import TableCatalog
from toolkit.core.character_metadata import character_metadata


class CharacterMetadataTests(unittest.TestCase):
    def test_target_namespaces_and_location_records_are_preserved(self):
        chars = [{'CharacterId': 1, 'CharacterGroupCode': 2}, {'CharacterId': 2, 'CharacterGroupCode': 1}]
        colors = [{'ColorTargetType': code, 'ColorTargetId': 1, 'ColorLocationType': location, 'ColorCode': '#Aa0000'}
                  for code, location in [(1, 1), (1, 2), (2, 1), (99, 1)]]
        data = character_metadata(TableCatalog([{'mst_character': [], 'mst_color_code': []}, chars, colors]))
        self.assertEqual(colors, [c['Raw'] for c in data['Colors']])
        self.assertEqual([chars[0]], data['Colors'][0]['CharacterRecords'])
        self.assertEqual([chars[1]], data['Colors'][2]['CharacterRecords'])
        self.assertEqual('unsupported_target_type', data['Colors'][3]['TargetStatus'])
        self.assertEqual([], data['Colors'][3]['CharacterRecords'])
