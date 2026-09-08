import hashlib
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import msgpack
from openpyxl import Workbook

from toolkit.generate import generate
from toolkit.core.output import OutputContext, current_output
from toolkit.core.exporter import xlsx_path, write_xlsx


class GenerateTests(unittest.TestCase):
    def test_concurrent_jobs_route_outputs_without_changing_cwd_or_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = []
            for index in range(2):
                source = root / f'input{index}' / 'song.s2blyrics'
                source.parent.mkdir()
                source.write_bytes(msgpack.packb([[[0, 1.25, f'Line {index}']]]))
                sources.append(source)
            cwd = os.getcwd()
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(generate, ['lyrics'], root / f'out{i}', source=str(source))
                           for i, source in enumerate(sources)]
                reports = [future.result() for future in futures]
            self.assertEqual(cwd, os.getcwd())
            self.assertIsNone(current_output())
            for index, report in enumerate(reports):
                self.assertEqual('PASS', report['status'])
                self.assertEqual(2, len(report['artifacts']))
                self.assertEqual([sources[index]], list(sources[index].parent.iterdir()))
                self.assertIn(f'Line {index}', (root / f'out{index}/wiki_output/song.lrc').read_text(encoding='utf-8-sig'))
                for artifact in report['artifacts']:
                    self.assertTrue(Path(artifact['path']).is_relative_to(root / f'out{index}'))
                    self.assertEqual(artifact['sha256'], hashlib.sha256(Path(artifact['path']).read_bytes()).hexdigest())

    def test_failed_retry_receipt_excludes_old_files_and_marks_partial_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'valid.s2bscript'
            source.write_bytes(msgpack.packb({'text': 'valid'}))
            output = root / 'out'
            good = generate(['scripts'], output, source=source)
            self.assertEqual('PASS', good['status'])
            source.write_bytes(b'\xc1')
            failed = generate(['scripts'], output, source=source)
            self.assertEqual('FAIL', failed['status'])
            self.assertEqual([], failed['artifacts'])
            self.assertEqual('FAIL', failed['domains'][0]['status'])
            self.assertTrue(Path(good['artifacts'][0]['path']).exists())
            self.assertEqual(failed, json.loads((output / 'audit_output/output_receipt.json').read_text(encoding='utf-8')))
            self.assertEqual(2, len(list((output / 'audit_output').glob('output_receipt_*.json'))))

    def test_locked_workbook_receipt_tracks_alternative_path_only(self):
        with tempfile.TemporaryDirectory() as directory:
            context = OutputContext(Path(directory))
            original_save = Workbook.save
            def save(book, path):
                if Path(path).name == 'cards.xlsx':
                    raise PermissionError('Excel lock')
                return original_save(book, path)
            with context.activate(), patch.object(Workbook, 'save', save):
                context.domain = 'cards'
                actual = write_xlsx([['text']], xlsx_path('cards.xlsx'))
            report = context.finish()
            self.assertEqual('cards_new.xlsx', Path(actual).name)
            self.assertEqual([str(Path(actual).resolve())], [a['path'] for a in report['artifacts']])

    def test_missing_masterdata_and_wrong_source_type_are_explicit_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual('FAIL', generate(['cards'], directory)['status'])
            source = Path(directory) / 'wrong.txt'
            source.write_text('input', encoding='utf-8')
            self.assertEqual('FAIL', generate(['scripts'], directory, source=source)['status'])

    def test_schema_failure_does_not_write_to_source_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'input/master_data.json'
            source.parent.mkdir()
            source.write_text('[{}, []]', encoding='utf-8')
            report = generate(['cards'], root / 'output', masterdata=source)
            self.assertEqual('FAIL', report['status'])
            self.assertEqual([source], list(source.parent.iterdir()))
            self.assertTrue((root / 'output/audit_output/run_manifest.json').exists())
            self.assertFalse((root / 'output/wiki_output/cards_data.xlsx').exists())

    def test_audio_warnings_are_exposed_to_application(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'input'
            source.mkdir()
            (source / 'voice_1.acb').write_bytes(b'')
            report = generate(['audio'], root / 'output', audio=source)
            self.assertEqual('PASS_WITH_WARNINGS', report['status'])
            self.assertTrue(report['warnings'])


if __name__ == '__main__':
    unittest.main()
