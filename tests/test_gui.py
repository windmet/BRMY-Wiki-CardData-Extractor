import tempfile
import time
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

import tkinter as tk

from toolkit.gui import JobRequest, ToolkitApp, execute_job, self_test


class GuiRequestTests(unittest.TestCase):
    def test_hidden_tk_construction_probe_reports_its_limited_scope(self):
        result = self_test()
        self.assertEqual('PASS', result['status'])
        self.assertEqual('hidden-widget-construction', result['scope'])
    def test_online_chart_and_missing_update_workbook_are_rejected_before_download(self):
        with self.assertRaisesRegex(ValueError, '谱面'):
            JobRequest('online', ['charts'], 'output', 'cache').validate()
        with self.assertRaisesRegex(ValueError, '旧 Excel'):
            JobRequest('online', ['card_update'], 'output', 'cache').validate()

    def test_local_mode_does_not_call_remote_service(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'song.s2blyrics'
            source.write_bytes(b'input')
            request = JobRequest('local', ['lyrics'], directory, '', source=str(source))
            with patch('toolkit.generate.generate', return_value={'status': 'PASS'}) as generate:
                with patch('toolkit.resolve.synchronize') as remote:
                    execute_job(request, False, lambda: False, lambda event: None)
                    remote.assert_not_called()
                    self.assertEqual(str(source), generate.call_args.kwargs['source'])


class GuiWidgetTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = ToolkitApp(self.root, settings_path=Path(self.directory.name) / 'settings.json')

    def tearDown(self):
        self.app.cancel_event.set()
        if self.app.worker:
            self.app.worker.join(timeout=3)
        self.root.destroy()
        self.directory.cleanup()

    def pump(self, condition):
        deadline = time.monotonic() + 4
        while not condition() and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.02)
        self.assertTrue(condition())

    def test_failed_new_job_clears_old_results_and_restores_controls(self):
        self.app.artifacts['old'] = {'path': 'old.xlsx'}
        self.app.results.insert('', 'end', iid='old', values=('old.xlsx', 'cards', '已生成'))
        self.app.backend = lambda *args: {'status': 'FAIL', 'artifacts': [], 'errors': ['download failed']}
        self.app.start()
        self.assertEqual([], list(self.app.results.get_children()))
        self.pump(lambda: self.app.last_result is not None)
        self.assertIn('未完整完成', self.app.status.get())
        self.assertEqual('normal', str(self.app.start_button['state']))
        self.assertIn('download failed', self.app.details.get('1.0', 'end'))

    def test_cancel_keeps_ui_responsive_and_prevents_a_second_worker(self):
        started = Event()
        def backend(request, plan, cancelled, progress):
            started.set()
            while not cancelled():
                time.sleep(0.01)
            return {'status': 'FAIL', 'artifacts': [], 'errors': ['任务已取消']}
        self.app.backend = backend
        self.app.start()
        first = self.app.worker
        self.assertTrue(started.wait(1))
        self.app.start()
        self.assertIs(first, self.app.worker)
        self.app.cancel_button.invoke()
        self.pump(lambda: self.app.last_result is not None)
        self.assertIn('已取消', self.app.status.get())

    def test_only_current_wiki_artifacts_are_listed_and_partial_is_visible(self):
        self.app.active_request = self.app.request()
        self.app._complete({'status': 'FAIL', 'artifacts': [
            {'path': 'partial.xlsx', 'kind': 'wiki', 'domain': 'cards', 'domain_status': 'FAIL'},
            {'path': 'raw.json', 'kind': 'audit', 'domain': 'cards', 'domain_status': 'FAIL'},
        ], 'errors': ['partial']})
        self.assertEqual(1, len(self.app.results.get_children()))
        self.assertEqual('不完整', self.app.results.item('0', 'values')[2])

    def test_requested_script_json_is_visible_even_though_it_is_a_technical_output(self):
        self.app.active_request = self.app.request()
        self.app._complete({'status': 'PASS', 'artifacts': [
            {'path': 'story.s2bscript.json', 'kind': 'audit', 'domain': 'scripts', 'domain_status': 'PASS'},
        ]})
        self.assertEqual('story.s2bscript.json', self.app.results.item('0', 'values')[0])


if __name__ == '__main__':
    unittest.main()
