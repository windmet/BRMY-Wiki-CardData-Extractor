import unittest
from types import SimpleNamespace

from toolkit.core.tables import TableCatalog
from toolkit.domains.story_catalog import extract


class StoryCatalogTests(unittest.TestCase):
    def test_unknown_story_type_does_not_link_matching_numbers(self):
        tables = {
            'mst_main_story_chapter': [{'MainStoryThreadNo': 1, 'MainStoryChapterNo': 1}],
            'mst_main_story_section': [{'MainStoryThreadNo': 1, 'MainStoryChapterNo': 1, 'MainStorySectionNo': 1}],
            'mst_puzzle_story': [{'StoryTypeCode': 99, 'StoryTargetBaseId': 1, 'StoryTargetChapterId': 1, 'StoryTargetSectionNo': 1, 'PuzzleStoryNo': 1}],
            'mst_puzzle_story_stage': [{'StoryTypeCode': 99, 'StoryTargetBaseId': 1, 'StoryTargetChapterId': 1, 'StoryTargetSectionNo': 1}],
        }
        data = extract(SimpleNamespace(tables=TableCatalog([dict.fromkeys(tables, []), *tables.values()])), as_of='2026-09-09T00:00:00Z')
        self.assertEqual('unsupported_story_type', data['CrossStoryLinks'][0]['Status'])
        self.assertIsNone(data['CrossStoryLinks'][0]['TargetTable'])

    def test_chapter_keys_do_not_collide_and_missing_scripts_are_not_invented(self):
        tables = {
            'mst_main_story_chapter': [{'MainStoryThreadNo': 1, 'MainStoryChapterNo': n} for n in (1, 2)],
            'mst_main_story_section': [{'MainStoryThreadNo': 1, 'MainStoryChapterNo': n, 'MainStorySectionNo': 1} for n in (1, 2)],
            'mst_character_story': [{'CharacterId': 1, 'CharacterStoryChapterNo': 1}],
            'mst_character_story_section': [{'CharacterId': 1, 'CharacterStoryChapterNo': 1, 'CharacterStorySectionNo': 1, 'ReleaseDateTime': '3001-01-01T00:00:00Z'}],
        }
        data = extract(SimpleNamespace(tables=TableCatalog([dict.fromkeys(tables, []), *tables.values()])), as_of='2026-09-09T00:00:00Z')
        self.assertEqual(3, len(data['Sections']))
        self.assertNotEqual(data['Sections'][0]['Key'], data['Sections'][1]['Key'])
        self.assertTrue(all(x['ScriptResolution'] == 'not_declared' for x in data['Sections']))
        self.assertEqual('unreleased_placeholder', data['Sections'][2]['Availability']['Status'])
        self.assertEqual([], data['Issues'])


if __name__ == '__main__':
    unittest.main()
