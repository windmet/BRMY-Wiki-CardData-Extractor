import json
import tempfile
import time
import unittest
from datetime import date
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
    def test_online_chart_is_allowed_and_missing_update_workbook_is_rejected_before_download(self):
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
        self.app = ToolkitApp(self.root, settings_path=Path(self.directory.name) / 'settings.json',
                              choice_loader=lambda cache: None)

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

    def test_preview_uses_explicit_assessment_and_does_not_guess_absent_counts(self):
        self.app.active_request = self.app.request()
        report = {'status': 'PLANNED', 'plan': {'resources': [1, 2]},
                  'cache_assessment': {'verified': 1, 'not_verified': 1}}
        self.app._complete(report)
        self.assertIn('已校验可用 1 项', self.app.status.get())
        del report['cache_assessment']
        self.app._complete(report)
        self.assertNotIn('已校验可用', self.app.status.get())

    def test_task_help_covers_every_task_and_has_keyboard_close_binding(self):
        from toolkit.gui import TASK_HELP, TASKS
        self.assertEqual(set(TASKS), set(TASK_HELP))
        self.app.help_button.invoke()
        dialog = next(child for child in self.root.winfo_children() if isinstance(child, tk.Toplevel))
        self.assertTrue(dialog.bind('<Escape>'))
        content = next(child for child in dialog.winfo_children() if isinstance(child, tk.Text)).get('1.0', 'end')
        self.assertIn('生日祝福在“主页 / 生日祝福”', content)
        dialog.destroy()

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

    def test_information_does_not_mark_every_artifact_as_missing_content(self):
        self.app.active_request = self.app.request()
        report = {'status': 'PASS_WITH_WARNINGS', 'artifacts': [
            {'path': 'ojt.xlsx', 'kind': 'wiki', 'domain': 'ojt', 'domain_status': 'PASS'},
            {'path': 'birthday.xlsx', 'kind': 'wiki', 'domain': 'birthday_archive', 'domain_status': 'PASS'}],
            'warnings': [{'domain': 'resources', 'kind': 'offline_snapshot', 'warning': 'offline'},
                         {'domain': 'ojt', 'warning': 'missing coordinates'}]}
        self.app._complete(report)
        self.assertEqual('已生成，请核对', self.app.results.item('0', 'values')[2])
        self.assertEqual('已生成', self.app.results.item('1', 'values')[2])
        content = self.app.details.get('1.0', 'end')
        self.assertIn('内容与数据需要核对（1 项）', content)
        self.assertIn('资源与运行提示（1 项）', content)
        self.assertEqual(report, self.app.last_result)

    def test_every_task_is_in_exactly_one_group_and_presets_select_known_tasks(self):
        from toolkit.gui import PRESETS, TASK_GROUPS, TASKS
        grouped = [name for _, names, _ in TASK_GROUPS for name in names]
        self.assertEqual(sorted(TASKS), sorted(grouped))
        self.app.apply_preset(PRESETS['只更新语音'])
        self.assertEqual(set(PRESETS['只更新语音']),
                         {name for name, value in self.app.selected.items() if value.get()})
        self.app.apply_preset(())
        self.assertFalse(any(value.get() for value in self.app.selected.values()))

    def test_local_files_switch_overrides_mode_and_disables_mode_box(self):
        self.app.use_local.set(True)
        self.app._mode_changed()
        self.assertEqual('local', self.app.mode_code())
        self.assertEqual('disabled', str(self.app.mode_box['state']))
        self.app.use_local.set(False)
        self.app.mode.set('只用已下载缓存')
        self.app._mode_changed()
        self.assertEqual('offline', self.app.mode_code())
        self.assertEqual('readonly', str(self.app.mode_box['state']))

    def test_settings_saved_by_earlier_versions_map_to_new_modes(self):
        settings = Path(self.directory.name) / 'old.json'
        for saved, mode, local in [('正式服离线缓存', '只用已下载缓存', False), ('用本地缓存', '只用已下载缓存', False),
                                   ('使用本地资源', '联网更新', True)]:
            settings.write_text(json.dumps({'mode': saved}, ensure_ascii=False), encoding='utf-8')
            app = ToolkitApp(tk.Toplevel(self.root), settings_path=settings, choice_loader=lambda cache: None)
            self.assertEqual(mode, app.mode.get())
            self.assertEqual(local, app.use_local.get())

    def test_failed_run_opens_details_tab(self):
        self.app.active_request = self.app.request()
        self.app._complete({'status': 'PASS', 'artifacts': []})
        self.assertEqual(0, self.app.tabs.index('current'))
        self.app._complete({'status': 'FAIL', 'artifacts': [], 'errors': ['boom']})
        self.assertEqual(2, self.app.tabs.index('current'))

    def test_without_cached_masterdata_cycle_and_subject_stay_free_text(self):
        self.pump(lambda: '先联网更新一次' in self.app.choice_hint.get())
        box = self.app.choice_boxes['subject']
        self.assertEqual('normal', str(box.cget('state')))
        self.app.choice_text['subject'].set('vo_home_58')
        self.assertEqual('vo_home_58', self.app.request().subject)

    def test_cached_masterdata_turns_cycle_and_subject_into_dropdowns(self):
        settings = Path(self.directory.name) / 'saved.json'
        settings.write_text(json.dumps({'paths': {'cycle': '2', 'subject': 'gone:subject'}}), encoding='utf-8')
        choices = {'cycles': [('1', '第1轮（2024–25）'), ('2', '第2轮（2025–26）')],
                   'subjects': [('limited:home_voice_no=58', '节日与话题｜クリスマス [1年目]')]}
        app = ToolkitApp(tk.Toplevel(self.root), settings_path=settings, choice_loader=lambda cache: choices)
        self.pump(lambda: '2 轮' in app.choice_hint.get())
        self.assertEqual('readonly', str(app.choice_boxes['cycle'].cget('state')))
        self.assertEqual('第2轮（2025–26）', app.choice_text['cycle'].get())
        # A saved subject that no longer exists falls back to the default and says so.
        self.assertEqual('不另出表', app.choice_text['subject'].get())
        self.assertIn('gone:subject', app.choice_hint.get())
        app.choice_text['subject'].set('节日与话题｜クリスマス [1年目]')
        app.choice_text['cycle'].set('全部轮次')
        request = app.request()
        self.assertEqual(('', 'limited:home_voice_no=58'), (request.cycle, request.subject))

    def test_recent_year_is_a_date_that_is_off_until_ticked(self):
        self.assertEqual('', self.app.request().recent_year)
        self.assertEqual('disabled', str(self.app.recent_boxes[0].cget('state')))
        self.app.recent_enabled.set(True)
        self.app._sync_recent()
        self.assertEqual(date.today().isoformat(), self.app.request().recent_year)
        self.app.recent_parts['month'].set('2')
        self.app.recent_parts['day'].set('30')
        self.app._sync_recent()
        with self.assertRaises(ValueError):
            self.app.request()


if __name__ == '__main__':
    unittest.main()
