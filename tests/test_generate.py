import hashlib
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from threading import Event

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
                    self.assertTrue(Path(artifact['path']).resolve().is_relative_to(
                        (root / f'out{index}').resolve()))
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

    def test_cancellation_during_last_domain_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'story.s2bscript'
            source.write_bytes(msgpack.packb([]))
            cancelled = Event()
            with patch('toolkit.domains.scripts.run', side_effect=lambda path: cancelled.set()):
                report = generate(['scripts'], Path(directory) / 'out', source=source,
                                  cancelled=cancelled.is_set)
            self.assertEqual('FAIL', report['status'])
            self.assertIn('取消', report['errors'][0]['error'])

    def test_task_options_reach_their_domains(self):
        """Covers what the retired `cli run birthday/home_voices` and `cli update cards` passed."""
        from unittest.mock import MagicMock
        from toolkit.domains import DOMAINS
        session = MagicMock()
        session.assessment.changes, session.assessment.errors = [], []
        modules = {name: MagicMock() for name in ('birthday', 'home_voices', 'card_update')}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'Musics').mkdir()
            with patch('toolkit.generate.MasterDataSession.open', return_value=session), \
                    patch('toolkit.generate.validate_domain_input'), patch.dict(DOMAINS, modules):
                report = generate(['birthday', 'home_voices', 'card_update'], root / 'out',
                                  masterdata=root / 'master_data.json', audio=str(root / 'Musics'),
                                  old_workbook='old.xlsx', cycle=3, year=2026,
                                  subject='vo_home_13_126', recent_year='2026-08-15')
        self.assertEqual('PASS', report['status'])
        modules['birthday'].run.assert_called_once_with(session=session, target_cycle=3, target_year=2026)
        modules['card_update'].run.assert_called_once_with('old.xlsx', audio_dir=str(root / 'Musics'), session=session)
        kwargs = modules['home_voices'].run.call_args.kwargs
        self.assertEqual(('vo_home_13_126', '2026-08-15'), (kwargs['selected_subject'], kwargs['recent_year_end']))


if __name__ == '__main__':
    unittest.main()
