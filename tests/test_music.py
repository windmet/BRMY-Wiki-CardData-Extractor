import json
import tempfile
import unittest
from pathlib import Path

from types import SimpleNamespace
from toolkit.core.output import OutputContext
from toolkit.core.tables import TableCatalog
from toolkit.domains import music as music_domain


def run_music(output, *, masterdata):
    tables = TableCatalog(json.loads(masterdata.read_text(encoding="utf-8")))
    with OutputContext(output, domain="music").activate():
        music_domain.run(session=SimpleNamespace(tables=tables))


class MusicRelationsTests(unittest.TestCase):
    def test_left_join_preserves_catalog_and_resource_suffixes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = {
                'mst_music': [
                    {'MusicId': 1, 'DisplayName': 'One'},
                    {'MusicId': 2, 'DisplayName': 'Two'},
                    {'MusicId': 3, 'DisplayName': 'Legacy', 'AudioFileName': 'old'},
                ],
                'mst_music_out_game': [
                    {'MusicId': 1, 'AudioFileName': 'one.mp3', 'JacketFileName': 'cover'},
                    {'MusicId': 2, 'AudioFileName': 'inactive', 'IsActive': False},
                ],
                'mst_music_info': [{'MusicId': 1, 'PuzzlePlaySeconds': 99}],
            }
            path = root / 'master.json'
            path.write_text(json.dumps([dict.fromkeys(data, []), *data.values()]), encoding='utf-8')
            run_music(root / 'output', masterdata=path)
            audit_dir = root / 'output' / 'audit_output'
            music = json.loads((audit_dir / 'Music_Database.json').read_text(encoding='utf-8'))
            self.assertEqual(['1', '2', '3'], list(music))
            self.assertEqual('one.mp3', music['1']['AudioFileName'])
            self.assertEqual('cover.png', music['1']['JacketFileName'])
            self.assertEqual('', music['2']['AudioFileName'])
            self.assertEqual('old.mp3', music['3']['AudioFileName'])
            self.assertNotEqual('01:39', music['1']['DurationStr'])
            audit = json.loads((audit_dir / 'music_relations.json').read_text(encoding='utf-8'))
            self.assertEqual(['matched', 'unmatched', 'unmatched'], [r['Status'] for r in audit['Music']])

    def test_duplicate_and_orphan_resources_are_auditable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = [{'mst_music': [], 'mst_music_out_game': []},
                    [{'MusicId': 1}],
                    [{'MusicId': 1, 'AudioFileName': 'a'},
                     {'MusicId': 1, 'AudioFileName': 'b'},
                     {'MusicId': 99, 'AudioFileName': 'orphan'}]]
            path = root / 'master.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            run_music(root / 'output', masterdata=path)
            audit_dir = root / 'output' / 'audit_output'
            audit = json.loads((audit_dir / 'music_relations.json').read_text(encoding='utf-8'))
            music = json.loads((audit_dir / 'Music_Database.json').read_text(encoding='utf-8'))
            self.assertEqual('', music['1']['AudioFileName'])
            self.assertEqual(['ambiguous', 'missing_music'], [r['Status'] for r in audit['Issues']])


if __name__ == '__main__':
    unittest.main()
